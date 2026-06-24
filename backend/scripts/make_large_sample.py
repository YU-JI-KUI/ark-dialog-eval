# -*- coding: utf-8 -*-
"""生成大数据量合成样例(模拟生产:无人工标注 / 或部分标注)。

按真实意图分布放大,并为不同意图注入可控的「分发失败率 / 未解决率」,
让业务洞察与优化建议有真实可分析的差异。

用法:
    uv run python scripts/make_large_sample.py            # 默认 3000 行,无金标(生产)
    uv run python scripts/make_large_sample.py 30000      # 3万行
    uv run python scripts/make_large_sample.py 2000 gold  # 2000 行带金标(校准集)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"

# 每个 BU 一套:意图 -> (问题模板, 系统分发模块, 注入的分发错误率, 注入的未解决率)
# 用确定性方式注入,使指标可复现、洞察有差异。
SPECS_BY_BU = {
    "securities": [
        ("资产查询", ["我的融资利率年化是多少", "账户总资产怎么查", "融资成本高吗"], "自研指令", 0.05, 0.10),
        ("查持仓", ["当日盈亏怎么看不到", "我的持仓在哪里", "持仓收益怎么算"], "自研指令", 0.08, 0.15),
        ("交易", ["怎么买入股票", "如何撤单", "委托怎么下"], "自研指令", 0.10, 0.20),
        ("查开户营业部", ["变更开户营业部", "我的营业部是哪个"], "自研指令", 0.05, 0.10),
        ("到价提醒", ["设置股价提醒", "到价提醒在哪"], "自研指令", 0.12, 0.18),
        ("问诊股", ["涨停板封成比换手怎么算", "帮我诊断这只股", "技术面分析"], "同花顺", 0.15, 0.40),
        ("股票资金流向分析", ["这只股资金流向", "板块资金流向分析"], "同花顺", 0.20, 0.35),
        ("资金流向选股", ["按资金流向选股", "筛选主力流入的股"], "同花顺", 0.25, 0.45),
        ("自选", ["添加自选股", "我的自选在哪"], "同花顺", 0.10, 0.20),
        ("咨询客服", ["人工服务", "客服电话多少", "转人工"], "自研指令", 0.05, 0.08),
        ("活动", ["帮我解锁消费权益", "怎么领取权益", "活动在哪参加"], "小安", 0.08, 0.12),
        ("拒识", ["手机充值", "银行卡变更", "话费充值"], "小安", 0.60, 0.70),
    ],
    "life": [
        ("保单查询", ["我的保单还有效吗", "保单受益人是谁", "保额是多少"], "保单助手", 0.05, 0.10),
        ("理赔咨询", ["住院了怎么理赔", "理赔需要什么材料", "理赔进度查询"], "理赔助手", 0.10, 0.30),
        ("缴费续期", ["下次缴费是什么时候", "怎么交保费", "自动扣款怎么开"], "保单助手", 0.08, 0.15),
        ("保全变更", ["怎么改受益人", "保单地址变更", "犹豫期退保"], "保单助手", 0.12, 0.25),
        ("投保咨询", ["高血压能买吗", "投保要体检吗", "健康告知怎么填"], "智能顾问", 0.15, 0.35),
        ("产品咨询", ["这款保险保什么", "和重疾险有啥区别", "条款解释"], "智能顾问", 0.18, 0.30),
        ("万能账户", ["万能账户价值多少", "结算利率是多少", "怎么追加"], "智能顾问", 0.20, 0.30),
        ("贷款咨询", ["保单能贷多少钱", "保单贷款利率", "怎么还款"], "智能顾问", 0.15, 0.25),
        ("咨询客服", ["人工服务", "客服电话多少", "转人工"], "客服", 0.05, 0.08),
        ("活动", ["怎么领取权益", "积分怎么用", "会员活动"], "客服", 0.08, 0.12),
        ("拒识", ["手机充值", "查股票", "买基金"], "客服", 0.55, 0.70),
    ],
}

ALL_COLUMNS = [
    "日期", "时间", "一账通ID", "追踪ID", "日志环境", "是否测试账号", "产险内测白名单",
    "常规专项白名单", "客户问题", "Python解析", "AI解析", "赞踩结果", "赞踩原因", "安全围栏",
    "围栏审核结果", "问题一级围栏标签", "问题二级围栏标签", "答案一级围栏标签", "答案二级围栏标签",
    "小导航拒识", "BU", "渠道", "入口", "细分入口", "客户咨询轮次", "分发BU", "标问", "标准问答案",
    "命中卡片", "一键问答", "答案", "模型意图", "调用答案类型", "相似问", "智能体名称", "智能体分类",
    "机器人", "咨询产生方式", "问题识别类型", "分发BU理由", "应用会话ID", "当前问问是否有效",
    "无效意图联系上下文后是否有效", "联系上下文后意图变化情况", "问题类型", "常规意图识别模块",
    "入口BU是否具备该业务", "分发是否正确", "一键场景分发是否正确", "实际应分BU", "答案是否解决客户问题",
    "未解决原因", "可解决的标问", "优化方向", "备注", "120一键场景/其他", "场景名称", "本BU误拦/大导航分发错识",
]


def _faq(content: str) -> str:
    inner = {"msgInfo": {"data": {"content": f"<p>{content}</p>"}}}
    return json.dumps([{
        "roomMark": "person", "msgType": "aat_text",
        "msgContext": json.dumps(inner, ensure_ascii=False),
    }], ensure_ascii=False)


def build(bu_code: str, out_name: str, n_rows: int, with_gold: bool) -> None:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.core.bu.registry import get_bu
    specs = SPECS_BY_BU[bu_code]
    bu_name = get_bu(bu_code).name  # BU 名取自 registry,不再三元写死
    # 用确定性轮转分配,避免依赖随机数(也便于复现)
    records = []
    i = 0
    while len(records) < n_rows:
        for intent, questions, module, err_rate, unresolved_rate in specs:
            if len(records) >= n_rows:
                break
            q = questions[i % len(questions)]
            # 确定性注入:用全局序号判断这条是否「分发错/未解决」
            is_dispatch_err = (i % 100) < int(err_rate * 100)
            is_unresolved = (i % 100) < int(unresolved_rate * 100)

            rec = {c: "" for c in ALL_COLUMNS}
            rec.update({
                "日期": "2026-06-16", "时间": "2026-06-16 18:41:26",
                "日志环境": "正式", "是否测试账号": "否", "BU": bu_name, "渠道": bu_name,
                "入口": "原生", "分发BU": bu_name, "实际应分BU": bu_name, "咨询产生方式": "键盘",
                "入口BU是否具备该业务": "是", "当前问问是否有效": "是",
                "客户问题": q,
                "客户咨询轮次": "1",
                "应用会话ID": f"S{i:06d}",
                "答案": _faq(f"针对『{q}』的回答内容。"),
                # 分发错时,系统分发到一个「错的」模块
                "模型意图": "其他" if is_dispatch_err else intent,
                "智能体分类": module,
                "常规意图识别模块": module,
                "问题识别类型": "活动" if intent == "活动" else "常规",
                "分发BU理由": "LLMIntent",
            })
            if with_gold:
                rec.update({
                    "分发是否正确": "否" if is_dispatch_err else "是",
                    "答案是否解决客户问题": "否" if is_unresolved else "是",
                    "未解决原因": "分发错误—BU多分" if is_dispatch_err else (
                        "答案不够具体" if is_unresolved else ""),
                    "一键场景分发是否正确": ("否" if is_dispatch_err else "是") if intent == "活动" else "",
                })
            records.append(rec)
            i += 1

    df = pd.DataFrame(records, columns=ALL_COLUMNS)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    out = SAMPLE_DIR / out_name
    df.to_excel(out, index=False)
    print(f"已生成: {out}  ({len(df)} 行, BU={bu_name}, {'带金标/校准集' if with_gold else '无金标/生产'})")


def _gen_all() -> None:
    """生成两个 BU 各自的生产+校准样例,文件名取自 BUConfig,与后端 /eval/sample 对齐。"""
    # 延迟 import,避免脚本作为纯数据工具时强依赖 app
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.core.bu.registry import get_bu

    for code in ("securities", "life"):
        bu = get_bu(code)
        build(code, bu.sample_prod, 3000, with_gold=False)
        build(code, bu.sample_calib, 2000, with_gold=True)


if __name__ == "__main__":
    # 无参 = 生成全部 BU 的样例;否则 make_large_sample.py <bu> <n> [gold]
    if len(sys.argv) == 1:
        _gen_all()
    else:
        bu_code = sys.argv[1] if sys.argv[1] in SPECS_BY_BU else "securities"
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
        gold = len(sys.argv) > 3 and sys.argv[3] == "gold"
        name = f"{bu_code}_dialog_{'calib' if gold else 'prod'}_{n}.xlsx"
        build(bu_code, name, n, gold)
