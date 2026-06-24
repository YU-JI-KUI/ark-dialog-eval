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
        ("自选", ["我的自选股今天表现如何", "帮我看下现在自选股的涨跌情况", "添加贵州茅台到自选"], "自选智能体", 0.10, 0.18),
        ("资产查询", ["我的总资产多少", "账户余额", "可用资金还有多少"], "资产查询智能体", 0.05, 0.10),
        ("交易", ["买入贵州茅台", "帮我卖出1000股宁德时代", "撤销指定委托"], "交易智能体", 0.10, 0.20),
        ("查持仓", ["我的持仓有哪些", "我持有股票的总市值是多少", "查一下今天的委托"], "查持仓智能体", 0.08, 0.15),
        ("到价提醒", ["比亚迪跌到200时提醒我", "涨到50提醒我", "设置到价提醒"], "到价提醒智能体", 0.12, 0.18),
        ("股票主力资金流向分析", ["五粮液近5日主力资金流向", "贵州茅台主力资金流入流出", "这只股主力资金怎么样"], "股票主力资金流向分析智能体", 0.18, 0.32),
        ("主力资金流向选股", ["连续3天主力净流入的股票", "帮我选主力资金流入的股", "主力净流入选股"], "主力资金流向选股智能体", 0.22, 0.40),
        ("查开户营业部", ["我在哪个营业部开户的", "查询开户营业部信息", "营业部电话"], "查开户营业部智能体", 0.05, 0.10),
        ("问诊股", ["3月9日涨停的股票", "天齐锂业最新半年报公告", "请评估国泰君安和海通证券合并的影响", "有关浦发银行的最新研报"], "问诊股智能体", 0.15, 0.30),
        ("咨询客服", ["身份证如何更新", "当天买入的股票不产生收益吗", "邓君老师最新市场观点"], "咨询客服智能体", 0.06, 0.12),
        ("拒识", ["手机充值", "银行卡变更", "春节红包活动规则", "世界杯竞猜"], "", 0.55, 0.70),
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
            is_reject = intent == "拒识"
            # 确定性注入:用全局序号判断这条是否「分发错」
            is_dispatch_err = (i % 100) < int(err_rate * 100)
            is_unresolved = (i % 100) < int(unresolved_rate * 100)

            # 真实体现 BU 分发漏斗(分发BU = 证券 表示被本BU承接,留空表示拒识):
            #  - 非拒识类:正常应被本BU承接(分发BU=证券);分发错=被错误拒识(留空)→ 漏收
            #  - 拒识类:正常应被拒识(分发BU留空);分发错=被本BU误收(分发BU=证券)→ 误收
            if is_reject:
                dispatched_bu = bu_name if is_dispatch_err else ""   # 误收时才落到证券
                answer = _faq("抱歉,我暂时无法处理该业务。") if not is_dispatch_err else _faq("已为您处理该问题。")
            else:
                dispatched_bu = "" if is_dispatch_err else bu_name   # 漏收时留空
                # 未解决:答案含糊简短(mock 据完整性判 no/partial);否则给完整答案
                answer = _faq("建议您查看页面。") if (is_unresolved and not is_dispatch_err) \
                    else _faq(f"针对『{q}』,已为您查询并处理完成,结果如上。")

            rec = {c: "" for c in ALL_COLUMNS}
            rec.update({
                "日期": "2026-06-16", "时间": "2026-06-16 18:41:26",
                "日志环境": "正式", "是否测试账号": "否", "BU": bu_name, "渠道": bu_name,
                "入口": "原生", "分发BU": dispatched_bu, "实际应分BU": bu_name, "咨询产生方式": "键盘",
                "入口BU是否具备该业务": "是", "当前问问是否有效": "是",
                "客户问题": q,
                "客户咨询轮次": "1",
                "应用会话ID": f"S{i:06d}",
                "答案": answer,
                "模型意图": "" if is_reject else intent,
                "智能体分类": module,
                "常规意图识别模块": module,
                "问题识别类型": "常规",
                "分发BU理由": "LLMIntent",
            })
            if with_gold:
                # 金标:分发是否正确 = 系统分发结果是否符合应然(非拒识应承接、拒识应留空)
                dispatch_ok = (dispatched_bu == bu_name) if not is_reject else (dispatched_bu == "")
                # 解决度只对「被本BU承接」的样本有意义
                resolved = "" if dispatched_bu != bu_name else ("否" if is_unresolved else "是")
                rec.update({
                    "分发是否正确": "是" if dispatch_ok else "否",
                    "答案是否解决客户问题": resolved,
                    "未解决原因": ("分发错误" if not dispatch_ok else
                                   ("答案不够具体" if resolved == "否" else "")),
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
