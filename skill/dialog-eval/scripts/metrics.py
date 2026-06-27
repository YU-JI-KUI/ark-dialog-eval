# -*- coding: utf-8 -*-
"""校准指标:对二值人工金标算 准/召/F1 + 混淆矩阵 + Cohen's κ。

用于校准模式:把 AI 判断与人工金标对齐,产出可信度数字(给团队认可的证据)。

用法(读 prepare.py 的样本 + AI 判断结果):
    python metrics.py judged.json > report.json

judged.json 结构:[{"gold":{"dispatch":"是","resolved":"否"},
                    "j_dispatch":"是","j_resolved":"否"}, ...]
其中 j_dispatch / j_resolved 是把 AI 输出归一成「是/否」后的值:
  - dispatch_correct=true → "是",否则 "否"
  - answer_resolved=="yes" → "是",其余 → "否"

依赖:scikit-learn。
"""
from __future__ import annotations

import json
import sys

from sklearn.metrics import (
    accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

_LABELS = ["是", "否"]


def binary_report(name: str, y_true: list, y_pred: list) -> dict:
    p, r, f, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=_LABELS, zero_division=0
    )
    kappa = float(cohen_kappa_score(y_true, y_pred)) if len(set(y_true)) > 1 else 0.0
    return {
        "name": name,
        "n": len(y_true),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "kappa": round(kappa, 4),
        "kappa_verdict": _verdict(kappa),
        "per_label": {
            lab: {"precision": round(float(pp), 4), "recall": round(float(rr), 4), "f1": round(float(ff), 4)}
            for lab, pp, rr, ff in zip(_LABELS, p, r, f)
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=_LABELS).tolist(),
    }


def _verdict(kappa: float) -> str:
    if kappa >= 0.8:
        return "高度一致(可信)"
    if kappa >= 0.6:
        return "可信"
    if kappa >= 0.4:
        return "中等,需改进评判规则"
    return "偏低,评判标准或人工标注需对齐"


def evaluate(judged: list) -> dict:
    """对三个二值金标维度分别算指标。"""
    specs = [
        ("分发是否正确", "dispatch", "j_dispatch"),
        ("一键场景分发是否正确", "oneclick", "j_dispatch"),
        ("答案是否解决客户问题", "resolved", "j_resolved"),
    ]
    out = []
    for name, gold_key, j_key in specs:
        y_true, y_pred = [], []
        for r in judged:
            gv = r.get("gold", {}).get(gold_key, "")
            jv = r.get(j_key, "")
            if gv in ("是", "否") and jv in ("是", "否"):
                y_true.append(gv)
                y_pred.append(jv)
        if y_true:
            out.append(binary_report(name, y_true, y_pred))
    # 不一致 case
    disagreements = [
        r for r in judged
        if (r.get("gold", {}).get("dispatch") in ("是", "否") and r["gold"]["dispatch"] != r.get("j_dispatch"))
        or (r.get("gold", {}).get("resolved") in ("是", "否") and r["gold"]["resolved"] != r.get("j_resolved"))
    ]
    return {"metrics": out, "disagreement_count": len(disagreements), "disagreements": disagreements}


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def aggregate(records: list) -> dict:
    """新口径报告聚合(生产模式核心)。

    输入:每条 = prepare 的样本字段 + LLM 判断字段合并,需含:
      dispatched_to_bu(bool,日志是否分给本BU)、should_dispatch_to_bu(bool,LLM判该不该)、
      business_type(业务类型标签)、answer_resolved(yes/partial/no/unknown)、unresolved_cause。

    产出:
      ① BU 分发准确率 + 两类错误(漏:该承接却拒识 / 误收:该拒识却承接)
      ② 端到端解决率(分母=分发到本BU的子集)+ 按业务类型切片的解决率
      ③ 未解决原因聚类
    """
    from collections import Counter, defaultdict

    n = len(records)
    # —— 维度①:BU 分发 ——
    dispatch_correct = 0
    miss = 0   # 该承接(LLM true)却被日志拒识(dispatched_to_bu false)
    over = 0   # 该拒识(LLM false)却被日志承接(dispatched_to_bu true)
    for r in records:
        should = bool(r.get("should_dispatch_to_bu"))
        actual = bool(r.get("dispatched_to_bu"))
        if should == actual:
            dispatch_correct += 1
        elif should and not actual:
            miss += 1
        elif not should and actual:
            over += 1

    # —— 维度②:解决度漏斗(只看日志分发到本BU的子集)——
    in_bu = [r for r in records if r.get("dispatched_to_bu")]
    resolved_yes = sum(1 for r in in_bu if r.get("answer_resolved") == "yes")
    end2end_rate = _rate(resolved_yes, len(in_bu))

    by_type = defaultdict(list)
    for r in in_bu:
        by_type[r.get("business_type") or "(未标注)"].append(r)
    type_slices = []
    for t, rows in by_type.items():
        ry = sum(1 for r in rows if r.get("answer_resolved") == "yes")
        type_slices.append({
            "business_type": t,
            "count": len(rows),
            "resolved_rate": _rate(ry, len(rows)),
            "unresolved_examples": [r.get("question", "") for r in rows
                                    if r.get("answer_resolved") in ("no", "partial")][:3],
        })
    type_slices.sort(key=lambda x: x["resolved_rate"])  # 差的在前

    # —— 未解决原因聚类 ——
    causes = Counter(
        r.get("unresolved_cause") for r in in_bu
        if r.get("answer_resolved") in ("no", "partial") and r.get("unresolved_cause")
    )

    return {
        "total": n,
        "bu_dispatch": {
            "accuracy": _rate(dispatch_correct, n),
            "correct": dispatch_correct,
            "wrong": n - dispatch_correct,
            # 四象限场景(与 FastAPI 报告口径一致):
            #   正常=should==actual / 该分未分(漏)=should且未分给本BU / 该拒未拒(误收)=不该却分了
            "scene_normal": dispatch_correct,
            "scene_miss_should_accept_but_rejected": miss,      # 该分未分(漏)
            "scene_over_should_reject_but_accepted": over,      # 该拒未拒(误收)
        },
        "resolution_funnel": {
            "dispatched_to_bu": len(in_bu),
            "end_to_end_resolved_rate": end2end_rate,
            "resolved_yes": resolved_yes,
            "by_business_type": type_slices,
        },
        "unresolved_causes": [{"cause": c, "count": n_} for c, n_ in causes.most_common()],
    }


if __name__ == "__main__":
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    # 自动判断:含 dispatched_to_bu → 走新口径 aggregate;否则走旧校准 evaluate
    fn = aggregate if (data and isinstance(data, list) and "dispatched_to_bu" in data[0]) else evaluate
    json.dump(fn(data), sys.stdout, ensure_ascii=False, indent=2)
