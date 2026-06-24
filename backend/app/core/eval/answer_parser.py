# -*- coding: utf-8 -*-
"""答案(AE 列)解析器 + 意图信号挖取。

AE 列不是纯文本,而是结构化 JSON 渲染卡,评测前必须先解析成语义文本。
已覆盖两种 schema:
  - 活动权益卡(catalogId=mx-activity-result-multiple):走 benefits/cardHead 字段。
  - 文本/FAQ/转人工(msgType=aat_text):真正回答埋在 msgContext(JSON-in-JSON)
    → msgInfo.data.content,content 是 HTML 富文本,要解两层 + 清标签。
未知类型降级为纯文本兜底(够用;判不准再补专门分支)。

另提供 extract_intent_signals:从答案 blob 挖系统埋的意图元数据,可作 Judge
上下文,也可批量挖来攒意图标签全集。

Java 类比:answer_parser 相当于一个把多种「响应 DTO」反序列化成统一
「语义文本」的适配器层(Adapter Pattern),每种 schema 一个分支。
"""
from __future__ import annotations

import json
import re
from html import unescape


def _link(m: re.Match) -> str:
    """<a href> 处理:javascript/空锚点是噪声只留文字,真实链接拼成 文字(url)。"""
    href, text = m.group(1), m.group(2)
    return text if (href.startswith("javascript") or href in ("#", "")) else f"{text}({href})"


def _strip_html(s: str) -> str:
    """清 HTML 标签、还原换行与转义实体、压多余空白,得到可读纯文本。"""
    s = re.sub(r'<a\s[^>]*?href="([^"]*)"[^>]*>(.*?)</a>', _link, s, flags=re.S)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</p>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _try_json(v):
    """字符串看起来像 JSON([ 或 { 开头)就尝试解析,失败原样返回(容错)。"""
    if isinstance(v, str) and v.strip()[:1] in "[{":
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def _grab_content(inner: str) -> str:
    """正则只抠出 content/text 字段,不硬解整段(整段常混入 Java toString 非法片段)。"""
    m = (
        re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', inner)
        or re.search(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', inner)
    )
    if not m:
        return ""
    g = m.group(1)
    try:
        # 借 json.loads 还原 \n \" \/ 等转义;失败则手工 replace 兜底
        g = json.loads('"' + g + '"')
    except Exception:
        g = g.replace("\\n", "\n").replace('\\"', '"').replace("\\/", "/").replace("\\\\", "\\")
    return _strip_html(g)


# 活动权益卡里承载语义的字段白名单
_BENEFIT_KEYS = {
    "mainTitle", "subTitle", "title",
    "benefitName", "benefitSubTitle", "buttonName",
}


def extract_answer(raw) -> dict:
    """把 AE 列原始值解析成 {answer_type, text}。

    返回:
        answer_type: 答案类型标识(catalogId / faq_text / plain_text / unknown)
        text: 抽出的语义文本
    """
    obj = _try_json(raw)
    if not isinstance(obj, (list, dict)):
        return {"answer_type": "plain_text", "text": str(raw).strip()}

    nodes = obj if isinstance(obj, list) else [obj]

    # —— 分支 1:文本类(FAQ / 转人工),靠 msgType 识别 ——
    if any(isinstance(n, dict) and "msgType" in n for n in nodes):
        texts = []
        for n in nodes:
            mc = n.get("msgContext", "")
            inner = mc if isinstance(mc, str) else json.dumps(mc, ensure_ascii=False)
            c = _grab_content(inner)
            if c:
                texts.append(c)
        return {"answer_type": "faq_text", "text": "\n\n".join(texts)}

    # —— 分支 2:活动权益卡 / 其他卡片,递归收集白名单字段 ——
    head = nodes[0] if nodes else {}
    atype = head.get("catalogId") or head.get("cardType") or "unknown"
    texts: list[str] = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in _BENEFIT_KEYS and isinstance(v, str) and v.strip():
                    texts.append(v.strip())
                else:
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)

    walk(obj)

    # 去重保序(dict.fromkeys 也行,这里显式写更直观)
    seen, uniq = set(), []
    for t in texts:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return {"answer_type": atype, "text": " | ".join(uniq)}


def _flatten(s: str) -> str:
    """反复去转义(最多 4 层),把 JSON-in-JSON 摊平好让正则抓字段。"""
    if not isinstance(s, str):
        s = str(s)
    for _ in range(4):
        n = s.replace('\\"', '"').replace("\\\\", "\\")
        if n == s:
            break
        s = n
    return s


def extract_intent_signals(raw) -> dict:
    """从答案 blob 挖系统埋的意图/匹配信号。

    可作 Judge 上下文(系统识别到的意图、命中的标准问、承接模块),
    也可批量挖来攒意图标签全集。
    """
    f = _flatten(raw)

    def g(k: str):
        m = re.search(r'"%s"\s*:\s*"([^"]+)"' % k, f)
        return m.group(1) if m else None

    return {
        "intent_name": g("intent_name"),
        "matched_std_q": g("stQuestion") or g("siQuestion"),
        "user_input": g("userInput"),
        "bot": g("bot_name") or g("sema_bot"),
        "source": g("source"),
    }
