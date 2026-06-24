# -*- coding: utf-8 -*-
"""答案解析器回归测试:覆盖两种已见 schema + 容错兜底。"""
import json

from app.core.eval.answer_parser import extract_answer, extract_intent_signals


def test_activity_card():
    """活动权益卡:抽出 mainTitle/subTitle/benefitName/buttonName。"""
    raw = json.dumps([{
        "catalogId": "mx-activity-result-multiple",
        "data": {
            "cardHead": {"mainTitle": "恭喜领取以下权益", "subTitle": "数量有限尽快领取"},
            "benefits": [{"benefitName": "超级Level-2", "buttonName": "去使用"}],
        },
    }], ensure_ascii=False)
    r = extract_answer(raw)
    assert r["answer_type"] == "mx-activity-result-multiple"
    assert "超级Level-2" in r["text"]
    assert "恭喜领取以下权益" in r["text"]
    assert "去使用" in r["text"]


def test_faq_text_double_nested_and_html():
    """文本/FAQ:解双层嵌套 msgContext + 清 HTML + 丢假链接。"""
    inner = {"msgInfo": {"data": {"content":
        '<p>条件:20个交易日日均≥10万</p>'
        '<p><a href="javascript:void(0)" onclick="sign()">点击签署</a></p>'}}}
    raw = json.dumps([{
        "roomMark": "person", "msgType": "aat_text",
        "msgContext": json.dumps(inner, ensure_ascii=False),
    }], ensure_ascii=False)
    r = extract_answer(raw)
    assert r["answer_type"] == "faq_text"
    assert "20个交易日日均≥10万" in r["text"]
    # 假链接 href 被丢,只留文字
    assert "点击签署" in r["text"]
    assert "javascript" not in r["text"]
    assert "<p>" not in r["text"]  # HTML 标签已清


def test_intent_signals_from_blob():
    """从答案 blob 挖埋藏的意图元数据。"""
    inner = {
        "msgInfo": {"data": {"content": "<p>点击转人工</p>"}},
        "ths_intent_info": {"intent_name": "转人工服务"},
        "stQuestion": "平安证券客服电话和服务时间",
        "bot_name": "自研指令",
        "source": "zongkong",
    }
    raw = json.dumps([{
        "msgType": "aat_text", "msgContext": json.dumps(inner, ensure_ascii=False),
    }], ensure_ascii=False)
    sig = extract_intent_signals(raw)
    assert sig["intent_name"] == "转人工服务"
    assert sig["matched_std_q"] == "平安证券客服电话和服务时间"
    assert sig["bot"] == "自研指令"
    assert sig["source"] == "zongkong"


def test_plain_text_fallback():
    """非 JSON 内容降级为纯文本兜底,不报错。"""
    r = extract_answer("这是一段纯文本回答")
    assert r["answer_type"] == "plain_text"
    assert r["text"] == "这是一段纯文本回答"


def test_malformed_json_does_not_crash():
    """内部混入非法片段(Java toString)时仍能抠出 content,不整体崩。"""
    raw = ('[{"msgType":"aat_text","msgContext":"{\\"msgInfo\\":{\\"data\\":'
           '{\\"content\\":\\"<p>正常内容</p>\\"}},\\"rule\\":{type=0, match=1}}"}]')
    r = extract_answer(raw)
    assert "正常内容" in r["text"]
