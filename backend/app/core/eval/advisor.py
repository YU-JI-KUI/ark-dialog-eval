# -*- coding: utf-8 -*-
"""优化建议生成器。

读「业务洞察聚合指标 + 典型失败样例」→ 让大模型给出针对性的优化建议。
无模型时退化为规则版建议(基于阈值),保证任何环境都有可用输出。

建议结构(每条):
  scope        : 作用域(业务分类 / 全局)
  severity     : high / medium / low
  problem      : 一句话问题描述
  root_cause   : 根因判断(分发问题 / 答案问题 / 数据问题 / 需人工)
  suggestion   : 具体优化动作
  evidence     : 支撑数字
"""
from __future__ import annotations

import json

from app.core.bu.base import BUConfig

# 规则版阈值:解决率低于此判为需优化
_LOW_RESOLVED = 0.6
_LOW_DISPATCH = 0.7
_HIGH_REVIEW = 0.4
_MIN_SAMPLES = 3  # 样本太少不下结论


def build_advice_prompt(insights: dict, bu: BUConfig, bu_dispatch: dict | None = None) -> list[dict]:
    """构造给大模型的消息:把聚合指标 + 失败样例喂进去。"""
    system = (
        f"你是平安{bu.name}智能问答系统的优化顾问。基于给定的评测聚合指标和失败样例,"
        "给出有针对性、可落地的优化建议,只依据数据,不臆测。"
    )
    overall = insights["overall"]
    # 只把信息量大的切片喂给模型(进漏斗样本量足够的),控制 token
    slices = [s for s in insights["by_intent"] if s.get("in_bu_count", 0) >= _MIN_SAMPLES]
    payload = {
        "BU分发": bu_dispatch or {},   # 准确率 + 两类错误(漏收/误收)
        "整体端到端解决率": overall["resolved_rate"],
        "各业务类型切片(端到端解决率,分母=分发到本BU的子集)": [
            {
                "业务类型": s["name"],
                "进漏斗样本量": s.get("in_bu_count", 0),
                "端到端解决率": s["resolved_rate"],
                "需复核率": s["needs_review_rate"],
                "未解决典型问题": s["unresolved_examples"],
            }
            for s in slices
        ],
    }
    user = f"""下面是一批对话评测的聚合指标(按意图切片):

{json.dumps(payload, ensure_ascii=False, indent=2)}

请找出最需要优化的 3-5 个点,每个点给出:
- scope: 作用域(具体业务分类 / 全局)
- severity: high/medium/low
- problem: 一句话问题
- root_cause: 根因(分发问题/答案问题/数据问题/需人工 之一)
- suggestion: 具体可落地的优化动作(如:补该意图标问、调分发阈值、补知识库、转人工兜底)
- evidence: 支撑数字

只输出 JSON 数组,形如:
[{{"scope":"...","severity":"high","problem":"...","root_cause":"...","suggestion":"...","evidence":"..."}}]"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_advice(text: str) -> list[dict]:
    """解析模型返回的建议数组。容错 Markdown 围栏。"""
    fence = chr(96) * 3
    t = text.strip().replace(fence + "json", "").replace(fence, "").strip()
    data = json.loads(t)
    return data if isinstance(data, list) else []


def rule_based_advice(insights: dict, bu_dispatch: dict | None = None) -> list[dict]:
    """规则版兜底建议:无模型时基于阈值生成,保证总有可用输出。

    bu_dispatch:BU 分发漏斗统计(两类错误),用于给"如何提升 BU 分发准确率"建议。
    """
    advice: list[dict] = []

    # —— BU 分发层建议(全局,基于两类错误)——
    if bu_dispatch and bu_dispatch.get("scored"):
        acc = bu_dispatch["accuracy"]
        miss = bu_dispatch.get("miss_should_accept_but_rejected", 0)
        over = bu_dispatch.get("over_should_reject_but_accepted", 0)
        if acc < _LOW_DISPATCH:
            cause = "误收(他业务问题被本BU收下)" if over >= miss else "漏收(本应承接却被拒识)"
            fix = ("补拒识规则,把无关问题挡在外面" if over >= miss
                   else "放宽分发/补本BU意图覆盖,别把该接的拒了")
            advice.append({
                "scope": "BU 分发(全局)",
                "severity": "high",
                "problem": f"BU 分发准确率仅 {acc:.0%},主要错误是{cause}",
                "root_cause": "分发问题",
                "suggestion": fix,
                "evidence": f"漏收 {miss} 条 / 误收 {over} 条",
            })

    # —— 解决度层建议(按业务类型切片)——
    for s in insights["by_intent"]:
        if s.get("in_bu_count", 0) < _MIN_SAMPLES or s["name"] == "(未分类)":
            continue
        if s["resolved_rate"] < _LOW_RESOLVED:
            advice.append({
                "scope": s["name"],
                "severity": "medium",
                "problem": f"『{s['name']}』端到端解决率仅 {s['resolved_rate']:.0%}",
                "root_cause": "答案问题",
                "suggestion": f"分发到本BU但没解决,排查答案质量:补该业务类型的知识库/标问答案,"
                              f"或检查答案卡渲染是否完整。",
                "evidence": f"漏斗内 {s['in_bu_count']} 条,解决率 {s['resolved_rate']:.0%},"
                            f"典型未解决:{'、'.join(s['unresolved_examples'][:2]) or '—'}",
            })
        if s["needs_review_rate"] >= _HIGH_REVIEW:
            advice.append({
                "scope": s["name"],
                "severity": "low",
                "problem": f"『{s['name']}』需人工复核率高达 {s['needs_review_rate']:.0%}",
                "root_cause": "需人工",
                "suggestion": "该意图 Judge 置信普遍偏低,建议补充意图定义/示例,或纳入人工复核队列。",
                "evidence": f"需复核率 {s['needs_review_rate']:.0%}",
            })
    # 按严重度排序
    order = {"high": 0, "medium": 1, "low": 2}
    advice.sort(key=lambda a: order.get(a["severity"], 9))
    return advice[:6]
