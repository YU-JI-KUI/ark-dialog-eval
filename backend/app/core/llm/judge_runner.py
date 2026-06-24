# -*- coding: utf-8 -*-
"""Judge 调度入口:按配置选 mock / pingan,对外暴露统一的 async 接口。

service 层只认 judge_one(sample) -> dict,不关心底层用谁。
"""
from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.core.bu.base import BUConfig
from app.core.eval.advisor import (
    build_advice_prompt,
    parse_advice,
    rule_based_advice,
)
from app.core.eval.judge import build_messages, parse_judge_output
from app.core.llm.mock_judge import mock_judge
from app.core.llm.pingan_client import call_bigmodel_api, extract_content

logger = logging.getLogger(__name__)


def active_backend() -> str:
    """返回当前实际生效的后端。配置 pingan 但变量不全时降级到 mock。"""
    if settings.judge_backend == "pingan" and settings.pingan_ready():
        return "pingan"
    return "mock"


async def _judge_strong(sample: dict, bu: BUConfig) -> dict:
    """调强模型(平安大模型)做精判。"""
    messages = build_messages(sample, bu)
    resp = await call_bigmodel_api(
        query=messages,
        scene_id=settings.llm_scene_id,
        app_key=settings.llm_app_key,
        app_secret=settings.llm_app_secret,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        response_format={"type": "json_object"},
    )
    content = extract_content(resp)
    return parse_judge_output(content)


def _should_escalate(fast: dict) -> bool:
    """判断快层结果是否需要升级到强模型精判。

    难例 = 置信低 / 快层要求复核 / 判到边界兜底意图(其他/拒识)。
    这些正是「容易判错、值得花强模型」的样本。
    """
    if not isinstance(fast, dict):
        return True
    if fast.get("intent_confidence", 0) < settings.escalate_confidence:
        return True
    if fast.get("needs_human_review"):
        return True
    if fast.get("intent_pred") in ("其他", "拒识"):
        return True
    if fast.get("answer_resolved") in ("no", "partial"):
        return True
    return False


async def judge_one(sample: dict, bu: BUConfig) -> dict:
    """对单条样本跑 Judge,返回结构化结果。失败时返回带 _error 的结果。

    分层策略(仅 pingan 后端 + tiered_judge 开启时):
      快层 mock 初判 → 仅难例升级强模型;否则直接用快层结果(省成本)。
    结果带 _tier 字段(fast/strong)用于统计节省量。
    """
    backend = active_backend()
    try:
        if backend == "pingan":
            if settings.tiered_judge:
                fast = mock_judge(sample, bu)
                if not _should_escalate(fast):
                    fast["_tier"] = "fast"
                    return fast
                strong = await _judge_strong(sample, bu)
                strong["_tier"] = "strong"
                return strong
            strong = await _judge_strong(sample, bu)
            strong["_tier"] = "strong"
            return strong
        # mock 后端:全部走规则桩
        result = mock_judge(sample, bu)
        result["_tier"] = "fast"
        return result
    except Exception as e:  # 单条失败不应中断整批
        logger.error("judge 单条失败 row=%s: %s", sample.get("row_index"), e)
        return {"_error": str(e), "needs_human_review": True, "_tier": "error"}


async def judge_batch(samples: list[dict], bu: BUConfig, on_progress=None) -> list[dict]:
    """并发跑一批样本。on_progress(done, total) 回调用于上报进度。"""
    total = len(samples)
    results: list[dict | None] = [None] * total
    sem = asyncio.Semaphore(max(1, settings.judge_concurrency))
    done = 0
    lock = asyncio.Lock()

    async def worker(idx: int, s: dict):
        nonlocal done
        async with sem:
            results[idx] = await judge_one(s, bu)
        async with lock:
            done += 1
            if on_progress:
                on_progress(done, total)

    # return_exceptions=True:即便某 worker 抛出非预期异常,也不中断整批;
    # 该位置的结果回填为带 _error 的占位,保证 results 与 samples 一一对应。
    outcomes = await asyncio.gather(
        *(worker(i, s) for i, s in enumerate(samples)),
        return_exceptions=True,
    )
    for idx, o in enumerate(outcomes):
        if isinstance(o, Exception) and results[idx] is None:
            results[idx] = {"_error": str(o), "needs_human_review": True}
    return results  # type: ignore[return-value]


async def generate_advice(insights: dict, bu: BUConfig, bu_dispatch: dict | None = None) -> dict:
    """生成优化建议。走真实模型则让模型读聚合指标给建议,否则用规则兜底。

    返回 {"source": "model"|"rule", "items": [...]}。模型失败自动降级到规则。
    """
    if active_backend() == "pingan":
        try:
            messages = build_advice_prompt(insights, bu)
            resp = await call_bigmodel_api(
                query=messages,
                scene_id=settings.llm_scene_id,
                app_key=settings.llm_app_key,
                app_secret=settings.llm_app_secret,
                timeout=settings.llm_timeout,
                max_retries=settings.llm_max_retries,
            )
            items = parse_advice(extract_content(resp))
            if items:
                return {"source": "model", "items": items}
        except Exception as e:
            logger.error("模型生成建议失败,降级到规则: %s", e)
    return {"source": "rule", "items": rule_based_advice(insights, bu_dispatch)}
