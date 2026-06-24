# -*- coding: utf-8 -*-
"""REST API 路由。

  POST /api/eval/upload        上传 Excel,创建并启动评测任务
  GET  /api/eval/sample        用内置合成样例数据创建并启动评测任务
  GET  /api/eval/tasks         任务列表
  GET  /api/eval/tasks/{id}    任务状态(轮询进度)
  GET  /api/eval/tasks/{id}/result        完整评测结果
  GET  /api/eval/tasks/{id}/export        导出不一致 case Excel
  GET  /api/meta/intents       意图体系标签全集
  GET  /api/meta/config        当前后端配置(mock/pingan)
"""
from __future__ import annotations

import asyncio
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.core.bu.registry import get_bu, list_bus
from app.core.llm.judge_runner import active_backend
from app.services.task_manager import task_manager

router = APIRouter(prefix="/api")

_ALLOWED = (".xlsx", ".xls")

# 保留后台任务的强引用,否则 asyncio 可能在任务跑完前把 Task 回收掉
_background_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    """后台跑协程并保留强引用,防止被 GC。"""
    handle = asyncio.create_task(coro)
    _background_tasks.add(handle)
    handle.add_done_callback(_background_tasks.discard)


def _start_task(filename: str, file_path: str, bu: str) -> dict:
    task = task_manager.create(filename, file_path, bu)
    # 后台异步跑,立刻返回 task_id 供前端轮询
    _spawn(task_manager.run(task["task_id"]))
    return task


@router.post("/eval/upload")
async def upload(file: UploadFile = File(...), bu: str = "securities"):
    """上传日志 Excel 起评测。bu 指定业务单元(securities/life),决定意图体系。"""
    if not file.filename or not file.filename.lower().endswith(_ALLOWED):
        raise HTTPException(400, "只接受 .xlsx / .xls 文件")
    dest = settings.uploads_dir / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return _start_task(file.filename, str(dest), get_bu(bu).code)


@router.get("/eval/sample")
async def run_sample(bu: str = "securities", kind: str = "calib"):
    """用内置合成样例数据起一个评测任务,零配置体验全流程。

    bu:   securities(证券) / life(寿险)
    kind: calib(校准集,有金标) / prod(生产集,无金标)
    各 BU 的样例文件名由 BUConfig 提供。
    """
    bu_cfg = get_bu(bu)
    fname = bu_cfg.sample_prod if kind == "prod" else bu_cfg.sample_calib
    sample = settings.sample_dir / fname
    if not sample.exists():
        raise HTTPException(
            404, f"{bu_cfg.name} 的样例 {fname} 不存在,请先运行 scripts 生成样例数据"
        )
    return _start_task(sample.name, str(sample), bu_cfg.code)


@router.get("/eval/tasks")
async def list_tasks():
    return {"tasks": task_manager.list()}


@router.get("/eval/tasks/{task_id}")
async def task_status(task_id: str):
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    task["can_resume"] = task_manager.can_resume(task_id)
    return task


@router.get("/eval/tasks/{task_id}/result")
async def task_result(task_id: str):
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if task["status"] != "done":
        raise HTTPException(409, f"任务尚未完成(当前状态: {task['status']})")
    result = task_manager.get_result(task_id)
    if not result:
        raise HTTPException(409, "结果尚未就绪")
    return result


@router.post("/eval/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """断点续跑:对中断的任务,跳过已完成行继续。"""
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if not task_manager.can_resume(task_id):
        raise HTTPException(409, "该任务无需或无法续跑")
    _spawn(task_manager.run(task_id, resume=True))
    return task_manager.get(task_id)


@router.get("/eval/tasks/{task_id}/export")
async def export_disagreements(task_id: str):
    path = task_manager.export_disagreements(task_id)
    if not path:
        raise HTTPException(404, "无可导出结果")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )


@router.get("/meta/bus")
async def get_bus():
    """列出可选业务单元(BU),供前端上传时选择。"""
    return {"bus": list_bus()}


@router.get("/meta/intents")
async def get_intents(bu: str = "securities"):
    """返回指定 BU 的意图体系全集。"""
    return {"bu": get_bu(bu).code, "intents": get_bu(bu).intent_list()}


@router.get("/meta/config")
async def get_config():
    return {
        "app_name": settings.app_name,
        "configured_backend": settings.judge_backend,
        "active_backend": active_backend(),
        "pingan_ready": settings.pingan_ready(),
        "concurrency": settings.judge_concurrency,
    }
