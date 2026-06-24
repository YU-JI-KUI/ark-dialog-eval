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
                "系统分发": r["dispatched_intent"],
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
            "会话ID", "轮次", "客户问题", "系统分发", "Judge意图", "Judge分发判定",
            "金标-分发是否正确", "Judge解决度", "金标-答案是否解决", "Judge理由",
            "答案文本", "需人工复核",
        ]
        df = pd.DataFrame(records, columns=columns)
        out = settings.outputs_dir / f"不一致case_{task_id}.xlsx"
        df.to_excel(out, index=False)
        return out


task_manager = TaskManager()
