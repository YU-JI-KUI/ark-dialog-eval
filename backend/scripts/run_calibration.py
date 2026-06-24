# -*- coding: utf-8 -*-
"""命令行校准入口 —— 不开 Web,直接对一份标注 Excel 跑评测并打印指标。

适合内网定时任务 / 无 GUI 场景。Web 和 CLI 共用同一套评测引擎,结果一致。

用法:
    uv run python -m scripts.run_calibration 你的标注.xlsx
    uv run python -m scripts.run_calibration 你的标注.xlsx --export 不一致.xlsx
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import pandas as pd

from app.core.bu.registry import get_bu
from app.core.llm.judge_runner import active_backend
from app.services.evaluator import run_evaluation


def _print_metrics(result: dict) -> None:
    s = result["summary"]
    f = result["filter_stats"]
    print(f"\n后端: {s['backend']}  |  原始 {f['total']} 条 → 有效 {s['total_samples']} 条"
          f"(过滤 {f['dropped']} 条)  |  会话 {s['sessions']} 个")
    print("=" * 60)
    if not result["metrics"]:
        print("⚠️  无可用二值人工金标,无法计算校准指标。")
        return
    for m in result["metrics"]:
        print(f"\n【{m['name']}】 n={m['n']}")
        print(f"  准确率={m['accuracy']:.3f}  κ={m['kappa']:.3f}  宏F1={m['macro_f1']:.3f}")
        for lab, st in m["per_label"].items():
            print(f"    {lab}: P={st['precision']:.3f} R={st['recall']:.3f} F1={st['f1']:.3f}")
        cm = m["confusion_matrix"]
        print(f"  混淆矩阵[真是/否 × 预是/否]: {cm}")
    print(f"\n不一致 case: {s['disagreement_count']} 条  |  需人工复核: {s['needs_review']} 条")


def _export(result: dict, out_path: str) -> None:
    records = []
    for r in result["disagreements"]:
        j = r["judge"] if isinstance(r["judge"], dict) else {}
        records.append({
            "会话ID": r["session"], "轮次": r["turn"], "客户问题": r["question"],
            "系统分发": r["dispatched_intent"], "Judge意图": r["j_intent"],
            "Judge分发": r["j_dispatch"], "金标-分发": r["gold"].get("dispatch", ""),
            "Judge解决": r["j_resolved"], "金标-解决": r["gold"].get("resolved", ""),
            "Judge理由": j.get("dispatch_reason", ""), "答案文本": r["answer_text"],
        })
    pd.DataFrame(records).to_excel(out_path, index=False)
    print(f"\n已导出 {len(records)} 条不一致 case → {out_path}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="平安多 BU 对话评测 - 命令行校准")
    parser.add_argument("excel", help="标注 Excel 路径")
    parser.add_argument("--bu", help="业务单元 securities/life", default="securities")
    parser.add_argument("--export", help="把不一致 case 导出到此 Excel", default=None)
    args = parser.parse_args()

    if not Path(args.excel).exists():
        print(f"❌ 文件不存在: {args.excel}")
        return 1

    bu = get_bu(args.bu)
    print(f"评测后端: {active_backend()}  |  BU: {bu.name}  |  输入: {args.excel}")
    last = {"done": 0}

    def on_progress(stage, done, total):
        if stage == "judging" and done != last["done"]:
            last["done"] = done
            print(f"\r  Judge 进度 {done}/{total}", end="", flush=True)

    result = await run_evaluation(args.excel, bu, on_progress=on_progress)
    _print_metrics(result)
    if args.export:
        _export(result, args.export)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
