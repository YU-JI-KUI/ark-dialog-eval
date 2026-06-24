# -*- coding: utf-8 -*-
"""分层 Judge 测试:验证快层粗筛 + 强模型只精判难例的路由逻辑。

不连真实端点,用 monkeypatch 把强模型/后端打桩,验证:
  - 快层高置信 → 不升级,直接用快层结果
  - 快层低置信/边界意图 → 升级到强模型
  - 升级与否都不影响结果结构
"""
import app.core.llm.judge_runner as jr
from app.core.bu.securities import SECURITIES as SEC
from app.core.llm.judge_runner import _should_escalate, judge_one


def test_escalate_rules():
    """难例判定:低置信/需复核/边界意图/未解决 → 升级。"""
    assert _should_escalate({"intent_confidence": 0.5}) is True          # 低置信
    assert _should_escalate({"intent_confidence": 0.9, "needs_human_review": True}) is True
    assert _should_escalate({"intent_confidence": 0.9, "intent_pred": "拒识"}) is True
    assert _should_escalate({"intent_confidence": 0.9, "answer_resolved": "no"}) is True
    # 高置信 + 明确意图 + 已解决 → 不升级
    assert _should_escalate({
        "intent_confidence": 0.9, "intent_pred": "资产查询",
        "needs_human_review": False, "answer_resolved": "yes",
    }) is False


async def test_high_confidence_stays_fast(monkeypatch):
    """高置信样本走快层,绝不调强模型。"""
    monkeypatch.setattr(jr, "active_backend", lambda: "pingan")
    monkeypatch.setattr(jr.settings, "tiered_judge", True)

    called = {"strong": 0}

    async def fake_strong(sample, bu):
        called["strong"] += 1
        return {"intent_pred": "X"}

    monkeypatch.setattr(jr, "_judge_strong", fake_strong)
    # 一个明确的资产查询问题,mock 会给高置信
    result = await judge_one({
        "question": "我的融资利率年化是多少", "dispatched_intent": "资产查询",
        "answer_text": "年化6.5%", "next_user_turn": None, "context": [],
    }, SEC)
    assert called["strong"] == 0          # 没调强模型
    assert result["_tier"] == "fast"


async def test_low_confidence_escalates(monkeypatch):
    """边界意图(拒识)升级到强模型。"""
    monkeypatch.setattr(jr, "active_backend", lambda: "pingan")
    monkeypatch.setattr(jr.settings, "tiered_judge", True)

    called = {"strong": 0}

    async def fake_strong(sample, bu):
        called["strong"] += 1
        return {"intent_pred": "拒识", "dispatch_correct": False}

    monkeypatch.setattr(jr, "_judge_strong", fake_strong)
    # 手机充值 → mock 判拒识 → 边界意图 → 升级
    result = await judge_one({
        "question": "手机充值", "dispatched_intent": "资产查询",
        "answer_text": "无法处理", "next_user_turn": None, "context": [],
    }, SEC)
    assert called["strong"] == 1          # 调了强模型
    assert result["_tier"] == "strong"
