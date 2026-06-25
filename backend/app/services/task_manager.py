# -*- coding: utf-8 -*-
"""评测任务管理器(SQLite 持久化版)。

负责:接收上传文件 → 后台异步跑评测 → 逐条落盘 + 上报进度 → 结果持久化 →
导出不一致 case。任务跑一半中断可断点续跑(resume)。

为什么持久化:每天 3万行量级,跑一半服务重启/崩溃,内存版会全部丢失重来;
落盘后只补未完成的行。
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from app.config import settings
from app.core.bu.registry import get_bu
from app.services import store
from app.services.evaluator import run_evaluation

logger = logging.getLogger(__name__)


def _public(t: dict) -> dict:
    """把 store 的任务行转成对外状态(含进度百分比)。"""
    total = t.get("progress_total") or 0
    done = t.get("progress_done") or 0
    pct = round(done / total * 100, 1) if total else 0.0
    bu_code = t.get("bu") or get_bu(None).code
    return {
        "task_id": t["task_id"],
        "filename": t["filename"],
        "bu": bu_code,
        "bu_name": get_bu(bu_code).name,
        "status": t["status"],
        "stage": t.get("stage") or "",
        "mode": t.get("mode") or "",
        "progress_done": done,
        "progress_total": total,
        "progress_pct": pct,
        "created_at": t.get("created_at"),
        "finished_at": t.get("finished_at"),
        "error": t.get("error"),
        "backend": settings.judge_backend,
    }


class TaskManager:
    def __init__(self) -> None:
        store.init_db()

    def create(self, filename: str, file_path: str, bu: str) -> dict:
        task_id = uuid.uuid4().hex[:12]
        store.create_task(task_id, filename, file_path, bu)
        return self.get(task_id)

    def get(self, task_id: str) -> Optional[dict]:
        t = store.get_task(task_id)
        return _public(t) if t else None

    def list(self) -> list[dict]:
        return [_public(t) for t in store.list_tasks()]

    async def run(self, task_id: str, resume: bool = False) -> None:
        """后台跑评测。resume=True 时断点续跑(跳过已落盘行)。"""
        t = store.get_task(task_id)
        if not t:
            return
        bu = get_bu(t.get("bu"))
        store.update_task(task_id, status="running", error=None)

        def on_progress(stage: str, done: int, total: int):
            store.update_task(task_id, stage=stage, progress_done=done, progress_total=total)

        try:
            result = await run_evaluation(
                t["file_path"], bu, on_progress=on_progress, task_id=task_id, persist=True,
            )
            store.save_result(task_id, result)
            store.update_task(
                task_id, status="done", stage="done", mode=result["mode"],
                finished_at=time.time(),
            )
            logger.info("评测完成 task=%s 样本=%s", task_id, result["summary"]["total_samples"])
        except Exception as e:
            logger.exception("评测失败 task=%s", task_id)
            store.update_task(task_id, status="failed", error=str(e), finished_at=time.time())

    def get_result(self, task_id: str) -> Optional[dict]:
        return store.load_result(task_id)

    def can_resume(self, task_id: str) -> bool:
        """failed 且已有部分落盘 → 可续跑。"""
        t = store.get_task(task_id)
        return bool(t and t["status"] == "failed" and store.done_row_indices(task_id))

    def export_disagreements(self, task_id: str) -> Optional[Path]:
        """把不一致 case 导出成 Excel,返回文件路径。"""
        result = store.load_result(task_id)
        if not result:
            return None
        records: list[dict[str, Any]] = []
        for r in result.get("disagreements", []):
            j = r["judge"] if isinstance(r["judge"], dict) else {}
            records.append({
                "会话ID": r["session"],
                "轮次": r["turn"],
                "客户问题": r["question"],
                "Judge意图": r["j_intent"],
                "Judge分发判定": r["j_dispatch"],
                "金标-分发是否正确": r["gold"].get("dispatch", ""),
                "Judge解决度": r["j_resolved"],
                "金标-答案是否解决": r["gold"].get("resolved", ""),
                "Judge理由": j.get("dispatch_reason", ""),
                "答案文本": r["answer_text"],
                "需人工复核": j.get("needs_human_review", ""),
            })
        columns = [
            "会话ID", "轮次", "客户问题", "Judge意图", "Judge分发判定",
            "金标-分发是否正确", "Judge解决度", "金标-答案是否解决", "Judge理由",
            "答案文本", "需人工复核",
        ]
        df = pd.DataFrame(records, columns=columns)
        out = settings.outputs_dir / f"不一致case_{task_id}.xlsx"
        df.to_excel(out, index=False)
        return out

    def export_rows(self, task_id: str) -> Optional[Path]:
        """逐条评测明细全量导出 Excel:每条一行,含模型完整判断 + 答案原文。"""
        result = store.load_result(task_id)
        if not result:
            return None
        records: list[dict[str, Any]] = []
        for r in result.get("rows", []):
            j = r["judge"] if isinstance(r["judge"], dict) else {}
            records.append({
                "会话ID": r["session"],
                "轮次": r["turn"],
                "客户问题": r["question"],
                "业务分类": r["j_intent"],
                "分发场景": r.get("dispatch_scene", ""),       # 正常/该拒未拒/该分未分
                "AI判该本BU接": j.get("should_dispatch_to_bu", ""),
                "实际分给本BU": r.get("dispatched_to_bu", ""),
                "分发判定理由": j.get("dispatch_reason", ""),
                "是否解决": r["j_resolved"],
                "解决度原值": r.get("j_resolved_raw", ""),
                "解决度理由": j.get("resolved_reason", ""),
                "未解决原因": j.get("unresolved_cause", ""),
                "需人工复核": j.get("needs_human_review", ""),
                "复核原因": j.get("review_reason", ""),
                "金标-分发是否正确": r["gold"].get("dispatch", ""),
                "金标-答案是否解决": r["gold"].get("resolved", ""),
                "答案原文": r["answer_text"],
            })
        columns = [
            "会话ID", "轮次", "客户问题", "业务分类", "分发场景",
            "AI判该本BU接", "实际分给本BU", "分发判定理由",
            "是否解决", "解决度原值", "解决度理由", "未解决原因",
            "需人工复核", "复核原因",
            "金标-分发是否正确", "金标-答案是否解决", "答案原文",
        ]
        df = pd.DataFrame(records, columns=columns)
        out = settings.outputs_dir / f"评测明细_{task_id}.xlsx"
        df.to_excel(out, index=False)
        return out

    def export_report(self, task_id: str) -> Optional[Path]:
        """完整评估报告导出 Excel:概览 / BU分发漏斗 / 业务洞察切片 / 优化建议 多 sheet。"""
        result = store.load_result(task_id)
        if not result:
            return None
        s = result["summary"]
        disp = s.get("bu_dispatch") or {}
        overall = result["insights"]["overall"]

        def pct(v):  # 比例转百分比字符串
            return f"{round((v or 0) * 100, 1)}%"

        overview = [
            ("业务单元(BU)", s.get("bu_name", "")),
            ("评测模式", "校准(有人工金标)" if result["mode"] == "calibration" else "生产(无标注)"),
            ("评测样本数", s.get("total_samples", 0)),
            ("会话数", s.get("sessions", 0)),
            ("多轮会话数", s.get("multi_turn_sessions", 0)),
            ("BU分发准确率", pct(s.get("dispatch_accuracy"))),
            ("端到端解决率(仅分发到本BU)", pct(s.get("end_to_end_resolved_rate"))),
            ("需人工复核数", s.get("needs_review", 0)),
            ("评测出错数", s.get("errors", 0)),
        ]
        dispatch = [
            ("参与评分条数", disp.get("scored", 0)),
            ("分发判对", disp.get("correct", 0)),
            ("分发判错", disp.get("wrong", 0)),
            ("准确率", pct(disp.get("accuracy"))),
            ("该拒未拒(误收)", disp.get("over_should_reject_but_accepted", 0)),
            ("该分未分(漏收)", disp.get("miss_should_accept_but_rejected", 0)),
        ]
        slices = [
            {
                "业务分类": x["name"],
                "样本量": x["count"],
                "进漏斗(分发到本BU)": x.get("in_bu_count", 0),
                "端到端解决率": pct(x.get("resolved_rate")),
                "需复核率": pct(x.get("needs_review_rate")),
                "典型未解决问题": "；".join(x.get("unresolved_examples", [])[:3]),
            }
            for x in result["insights"]["by_intent"]
        ]
        advice = [
            {
                "作用域": a.get("scope", ""),
                "严重度": a.get("severity", ""),
                "问题": a.get("problem", ""),
                "根因": a.get("root_cause", ""),
                "建议动作": a.get("suggestion", ""),
                "依据": a.get("evidence", ""),
            }
            for a in result.get("advice", {}).get("items", [])
        ]

        out = settings.outputs_dir / f"评估报告_{task_id}.xlsx"
        with pd.ExcelWriter(out) as writer:
            pd.DataFrame(overview, columns=["指标", "数值"]).to_excel(writer, sheet_name="概览", index=False)
            pd.DataFrame(dispatch, columns=["指标", "数值"]).to_excel(writer, sheet_name="BU分发漏斗", index=False)
            pd.DataFrame(slices).to_excel(writer, sheet_name="业务洞察", index=False)
            adv_df = pd.DataFrame(advice) if advice else pd.DataFrame([{"说明": "本次无优化建议(指标良好或样本不足)"}])
            adv_df.to_excel(writer, sheet_name="优化建议", index=False)
        return out


task_manager = TaskManager()
