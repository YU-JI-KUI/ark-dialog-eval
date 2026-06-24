# -*- coding: utf-8 -*-
"""内网单条试水脚本 —— 验收清单第 3/4 步。

到平安内网后,先跑这个脚本确认「签名能过网关 + 真实模型应答能被解析」,
再去跑整批校准。把「网络/凭据/签名」问题和「评测逻辑」问题彻底隔离。

用法(内网 CMD):
    set JUDGE_BACKEND=pingan
    uv run python scripts/check_pingan.py

或先 cp .env.sample .env 填好平安变量后直接:
    uv run python scripts/check_pingan.py
"""
from __future__ import annotations

import asyncio
import json
import sys

from app.config import settings
from app.core.bu.registry import get_bu
from app.core.eval.judge import OUTPUT_SCHEMA, build_messages, parse_judge_output
from app.core.llm.pingan_client import call_bigmodel_api, close_client, extract_content

# 一条最小评测样本(取自交接文档真实样例)
SAMPLE = {
    "question": "我的融资利率年化是百分之多少",
    "context": [],
    "dispatched_intent": "资产查询",
    "dispatch_reason": "命中标准问",
    "answer_text": "您当前融资利率年化为6.5%。",
    "answer_type": "faq_text",
    "next_user_turn": "我的融资成本高吗",
}


def _section(title: str) -> None:
    print("\n" + "=" * 56)
    print(f"  {title}")
    print("=" * 56)


async def main() -> int:
    _section("步骤 0:配置自检")
    print(f"JUDGE_BACKEND      = {settings.judge_backend}")
    print(f"OPEN_AI_URL        = {settings.open_ai_url or '(未配置)'}")
    print(f"平安变量是否齐全    = {settings.pingan_ready()}")
    if not settings.pingan_ready():
        print("\n❌ 平安大模型变量未配齐。请 cp .env.sample .env 并填入:")
        print("   OPEN_AI_URL / RSA_PK / CRE_ID / OPEN_API_CODE /")
        print("   LLM_APP_KEY / LLM_APP_SECRET / LLM_SCENE_ID")
        return 1

    _section("步骤 1:调用真实模型(验签名 + 网关连通)")
    messages = build_messages(SAMPLE, get_bu("securities"))
    print(f"发送 messages({len(messages)} 条),scene_id={settings.llm_scene_id}")
    resp = await call_bigmodel_api(
        query=messages,
        scene_id=settings.llm_scene_id,
        app_key=settings.llm_app_key,
        app_secret=settings.llm_app_secret,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        response_format={"type": "json_object"},
    )
    if not resp or "error" in (resp or {}):
        print(f"\n❌ 调用失败: {resp}")
        print("   排查方向:① 签名/凭据 ② 端点可达性 ③ scene_id 授权")
        return 1
    print("✓ 网关已返回响应")

    _section("步骤 2:解析模型输出(验输出格式契约)")
    try:
        content = extract_content(resp)
        print(f"模型原始内容(前 200 字):\n{content[:200]}")
        parsed = parse_judge_output(content)
    except Exception as e:
        print(f"\n❌ 解析失败: {e}")
        print("   模型输出未按 OUTPUT_SCHEMA 返回 → 需调 judge.py 的 prompt 收紧格式")
        return 1

    missing = [k for k in OUTPUT_SCHEMA if k not in parsed]
    if missing:
        print(f"\n⚠️  模型输出缺少约定字段: {missing}")
        print("   评测可降级运行,但建议在 prompt 里强调这些字段必填")
    else:
        print("✓ 输出包含全部约定字段")

    _section("结果:一条样本的完整 Judge 判断")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))

    _section("✅ 内网试水通过")
    print("签名、网关、模型应答、解析 全链路打通。")
    print("接下来可跑整批校准:uv run python -m scripts.run_calibration 你的标注.xlsx")
    return 0


if __name__ == "__main__":
    try:
        code = asyncio.run(main())
    finally:
        asyncio.run(close_client())
    sys.exit(code)
