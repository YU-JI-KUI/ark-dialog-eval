# -*- coding: utf-8 -*-
"""对话日志预处理:列解析 → 会话重组 → 输出样本 JSON(不做样本过滤,上传什么评什么)。

平安 One 调本脚本拿到「干净的可评测样本」,无需自己逐条读原始 Excel。
注意:答案**不做代码解析**(格式无法穷举,硬解会崩),答案原文(JSON+标签)
原样放进样本,由 LLM 在评测时自行读懂。

用法:
    python prepare.py 日志.xlsx > samples.json
    python prepare.py 日志.xlsx --limit 50           # 只取前 50 条(试水)

输出:JSON,含 mode(校准/生产)、filter_stats、samples[]。
每个 sample 带:row_index/session/turn/question/context/next_user_turn/
dispatched_bu/dispatched_to_bu/answer_text(原文)/gold。
依赖:pandas, openpyxl。
"""
from __future__ import annotations

import argparse
import json
import sys

import pandas as pd


# 逻辑键 -> 候选列名(精确优先,再包含匹配)
COLS = {
    "question": ["客户问题"],
    "turn": ["客户咨询轮次"],
    "session": ["应用会话ID"],
    "answer": ["答案"],
    "dispatch_bu": ["分发BU"],
    "gold_dispatch": ["分发是否正确"],
    "gold_oneclick": ["一键场景分发是否正确"],
    "gold_resolved": ["答案是否解决客户问题"],
    "gold_qtype": ["问题类型"],
    "unresolved_reason": ["未解决原因"],
}
_GOLD_KEYS = ("gold_dispatch", "gold_oneclick", "gold_resolved")


def resolve_columns(df: pd.DataFrame) -> dict:
    """精确匹配优先,避免「答案」误命中「答案一级围栏标签」「标准问答案」。"""
    cols = [str(c) for c in df.columns]
    m: dict = {}
    for key, cands in COLS.items():
        hit = next((c for c in cands if c in cols), None)
        if hit is None:
            hit = next((c for c in cols if any(cand in c for cand in cands)), None)
        if hit is not None:
            m[key] = hit
    miss = [k for k in ("question", "session", "turn", "answer") if k not in m]
    if miss:
        raise KeyError(f"缺少关键列: {miss}")
    return m


def prepare(path: str, limit: int | None = None, bu_name: str = "证券",
            dispatch_aliases: list | None = None) -> dict:
    """bu_name:本次评测的目标 BU 名(证券/寿险),用于展示与报告。

    dispatch_aliases:日志「分发BU」列里代表本 BU 的取值列表(可多个,如
    ["证券","证券业务","PA_SEC"])。真实日志列值若不是中文展示名,在这里补。
    不传时回退到「bu_name 子串匹配」(兼容,但真实环境建议显式给别名)。
    """
    aliases = dispatch_aliases or []
    df = pd.read_excel(path, dtype=str).fillna("")
    m = resolve_columns(df)
    total = len(df)

    # 不做样本过滤:上传什么评什么。按行删测试环境/账号/无效问题会破坏多轮上下文。
    df = df.copy()
    df["_turn_n"] = pd.to_numeric(df[m["turn"]], errors="coerce").fillna(0).astype(int)
    df = df.sort_values([m["session"], "_turn_n"]).reset_index(drop=True)

    # 模式判定:有二值金标 → 校准;否则 → 生产
    has_gold = any(
        k in m and df[m[k]].isin(["是", "否"]).any() for k in _GOLD_KEYS
    )
    mode = "calibration" if has_gold else "production"

    rows = df if limit is None else df.head(limit)
    samples = []
    for i in range(len(rows)):
        row = df.iloc[i]
        sess = row[m["session"]]
        prior = df[(df[m["session"]] == sess) & (df["_turn_n"] < row["_turn_n"])]
        nxt = df[(df[m["session"]] == sess) & (df["_turn_n"] > row["_turn_n"])]
        # 上下文 = 前文每一轮的「用户问 + AI 答原文」(不解析)。
        context = [
            {
                "turn": int(r["_turn_n"]),
                "user": r[m["question"]],
                "ai": r[m["answer"]],
            }
            for _, r in prior.iterrows()
        ]
        # 日志事实:分发BU 是否代表本次评测的目标 BU。
        # 有 aliases→精确相等(最安全);无→回退 bu_name 子串匹配。
        dbu = (row.get(m["dispatch_bu"], "") if "dispatch_bu" in m else "").strip()
        if not dbu:
            dispatched_to_bu = False
        elif aliases:
            dispatched_to_bu = dbu in aliases
        else:
            dispatched_to_bu = bu_name in dbu
        samples.append({
            "row_index": int(i),
            "session": sess,
            "turn": int(row["_turn_n"]),
            "question": row[m["question"]],
            "context": context,
            "next_user_turn": (nxt.iloc[0][m["question"]] if len(nxt) else None),
            "dispatched_bu": dbu,                      # 日志原始「分发BU」值
            "dispatched_to_bu": dispatched_to_bu,      # 日志是否把这条分给了本 BU
            "target_bu": bu_name,
            "answer_text": row[m["answer"]],   # 答案原文,交给 LLM 读
            "gold": {
                "dispatch": row.get(m.get("gold_dispatch", ""), "") if "gold_dispatch" in m else "",
                "oneclick": row.get(m.get("gold_oneclick", ""), "") if "gold_oneclick" in m else "",
                "resolved": row.get(m.get("gold_resolved", ""), "") if "gold_resolved" in m else "",
                "qtype": row.get(m.get("gold_qtype", ""), "") if "gold_qtype" in m else "",
            },
        })

    return {
        "mode": mode,
        "target_bu": bu_name,
        "filter_stats": {"total": total},
        "sample_count": len(samples),
        "samples": samples,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="对话日志预处理 → 可评测样本 JSON")
    p.add_argument("excel", help="日志 Excel 路径")
    p.add_argument("--limit", type=int, default=None, help="只取前 N 条")
    p.add_argument("--bu", default="证券", help="本次评测的目标 BU 名(证券/寿险)")
    p.add_argument("--dispatch-alias", action="append", default=None,
                   help="日志「分发BU」列里代表本BU的值,可多次传(如 --dispatch-alias 证券 --dispatch-alias PA_SEC)")
    args = p.parse_args()
    result = prepare(args.excel, args.limit, args.bu, args.dispatch_alias)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
