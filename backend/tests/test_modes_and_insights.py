# -*- coding: utf-8 -*-
"""双模式判定 + 业务洞察 + 优化建议测试。"""
import pandas as pd

from app.core.bu.securities import SECURITIES as SEC
from app.core.eval.advisor import rule_based_advice
from app.core.eval.pipeline import detect_gold, resolve_columns
from app.services.evaluator import _bu_dispatch_stats, compute_insights


def _df(with_gold: bool):
    rows = []
    for i in range(6):
        r = {
            "客户问题": f"问题{i}", "客户咨询轮次": "1", "应用会话ID": f"S{i}", "答案": "答",
            "日志环境": "正式", "是否测试账号": "否", "当前问问是否有效": "是",
        }
        if with_gold:
            r["分发是否正确"] = "是" if i % 2 else "否"
            r["答案是否解决客户问题"] = "是"
        else:
            r["分发是否正确"] = ""
            r["答案是否解决客户问题"] = ""
        rows.append(r)
    return pd.DataFrame(rows)


def test_detect_gold_calibration():
    """有金标 → calibration 模式。"""
    df = _df(with_gold=True)
    info = detect_gold(df, resolve_columns(df))
    assert info["mode"] == "calibration"
    assert info["gold_coverage"]["gold_dispatch"] == 6


def test_detect_gold_production():
    """无金标(空标注列)→ production 模式。"""
    df = _df(with_gold=False)
    info = detect_gold(df, resolve_columns(df))
    assert info["mode"] == "production"
    assert info["gold_coverage"]["gold_dispatch"] == 0


def _rows(intent, n, resolved="yes", to_bu=True, review=False):
    """to_bu=分发到本BU(进解决度漏斗);resolved=漏斗内的解决度。"""
    return [{
        "j_intent": intent, "j_resolved_raw": resolved, "answer_type": "faq_text",
        "question": f"{intent}问题{i}", "dispatched_to_bu": to_bu,
        "judge": {"business_group": None, "needs_human_review": review},
    } for i in range(n)]


def test_compute_insights_funnel_resolved_rate():
    """解决率漏斗口径:分母只算分发到本BU的样本。"""
    rows = _rows("资产查询", 4, resolved="yes", to_bu=True)
    rows += _rows("问诊股", 4, resolved="no", to_bu=True, review=True)
    rows += _rows("拒识", 2, resolved="unknown", to_bu=False)  # 漏斗外
    ins = compute_insights(rows, SEC)
    by = {s["name"]: s for s in ins["by_intent"]}
    assert by["资产查询"]["resolved_rate"] == 1.0
    assert by["问诊股"]["resolved_rate"] == 0.0
    assert by["拒识"]["in_bu_count"] == 0          # 拒识没进漏斗
    assert ins["overall"]["in_bu_count"] == 8      # 只有 8 条进漏斗(2条拒识不算)


def test_bu_dispatch_stats_two_error_types():
    """BU 分发统计:两类错误(漏/误收)正确区分。"""
    rows = [
        {"dispatch_correct": True, "dispatched_to_bu": True,
         "judge": {"should_dispatch_to_bu": True}},   # 对
        {"dispatch_correct": False, "dispatched_to_bu": True,
         "judge": {"should_dispatch_to_bu": False}},  # 误收:该拒却承接
        {"dispatch_correct": False, "dispatched_to_bu": False,
         "judge": {"should_dispatch_to_bu": True}},   # 漏:该承接却拒识
    ]
    st = _bu_dispatch_stats(rows)
    assert st["accuracy"] == round(1 / 3, 4)
    assert st["over_should_reject_but_accepted"] == 1
    assert st["miss_should_accept_but_rejected"] == 1


def test_rule_advice_flags_low_bu_dispatch():
    """BU 分发准确率低 → 规则建议给出 high 优先级『分发问题』。"""
    ins = compute_insights(_rows("资产查询", 5, resolved="yes"), SEC)
    bu_dispatch = {"scored": 10, "accuracy": 0.4,
                   "miss_should_accept_but_rejected": 1,
                   "over_should_reject_but_accepted": 5}
    advice = rule_based_advice(ins, bu_dispatch)
    assert advice, "应产出建议"
    top = advice[0]
    assert top["severity"] == "high"
    assert top["root_cause"] == "分发问题"
