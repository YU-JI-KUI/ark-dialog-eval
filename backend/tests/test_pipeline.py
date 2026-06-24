# -*- coding: utf-8 -*-
"""流水线测试:列解析(精确优先)、过滤、会话重组。"""
import pandas as pd

from app.core.bu.securities import SECURITIES as SEC
from app.core.eval.pipeline import (
    build_all_samples,
    filter_samples,
    resolve_columns,
)


def _df():
    return pd.DataFrame([
        {
            "客户问题": "手机充值", "客户咨询轮次": "1", "应用会话ID": "A1",
            "答案一级围栏标签": "x", "标准问答案": "y", "答案": "真答案",
            "日志环境": "正式", "是否测试账号": "否", "当前问问是否有效": "是",
            "分发是否正确": "否", "答案是否解决客户问题": "否",
        },
    ])


def test_exact_match_beats_substring():
    """关键回归:『答案』必须精确命中『答案』列,而非『答案一级围栏标签』。"""
    m = resolve_columns(_df())
    assert m["answer"] == "答案"  # 不能是『答案一级围栏标签』或『标准问答案』
    assert m["gold_resolved"] == "答案是否解决客户问题"


def test_filter_drops_invalid():
    """无效问题被过滤。"""
    df = pd.DataFrame([
        {"客户问题": "a", "客户咨询轮次": "1", "应用会话ID": "S1", "答案": "",
         "日志环境": "正式", "是否测试账号": "否", "当前问问是否有效": "是"},
        {"客户问题": "b", "客户咨询轮次": "1", "应用会话ID": "S2", "答案": "",
         "日志环境": "正式", "是否测试账号": "否", "当前问问是否有效": "否"},
    ])
    m = resolve_columns(df)
    kept, stats = filter_samples(df, m)
    assert stats["total"] == 2
    assert stats["kept"] == 1


def test_session_context_reconstruction():
    """同会话多轮:第2轮应能拿到第1轮作为上下文,第1轮记录下一轮。"""
    df = pd.DataFrame([
        {"客户问题": "融资利率", "客户咨询轮次": "1", "应用会话ID": "S", "答案": "6.5%",
         "日志环境": "正式", "是否测试账号": "否", "当前问问是否有效": "是"},
        {"客户问题": "融资成本", "客户咨询轮次": "2", "应用会话ID": "S", "答案": "中等",
         "日志环境": "正式", "是否测试账号": "否", "当前问问是否有效": "是"},
    ])
    m = resolve_columns(df)
    df["_turn_n"] = pd.to_numeric(df[m["turn"]]).astype(int)
    df = df.sort_values(["应用会话ID", "_turn_n"]).reset_index(drop=True)
    samples = build_all_samples(df, m, SEC)
    assert samples[0]["next_user_turn"] == "融资成本"
    # 第2轮的上下文应含第1轮的「用户问 + AI 答」(AI 答用于解析指代)
    ctx = samples[1]["context"]
    assert len(ctx) == 1
    assert ctx[0]["user"] == "融资利率"
    assert ctx[0]["ai"] == "6.5%"  # 上一轮 AI 答也带上了
