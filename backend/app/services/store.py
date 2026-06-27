# -*- coding: utf-8 -*-
"""PostgreSQL 持久化层:任务元数据 + 逐条评测结果。

用 SQLAlchemy 2.0 + psycopg2(与 datapulse 同栈,便于将来合并)。逐条结果落盘后,
任务跑一半中断可断点续跑(只补未完成的行)。JSON 列用 JSONB(可查询/索引)。

表(t_ 前缀 + eval_ 命名空间,避免与 datapulse 撞名):
  t_eval_task      : 任务元数据与进度(每个评测任务一行)
  t_eval_task_row  : 逐条评测结果(task_id + row_index 唯一)

对外暴露的函数签名与原 SQLite 版完全一致,上层(evaluator/task_manager)零改动。
"""
from __future__ import annotations

import time
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Column,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()


class EvalTask(Base):
    """t_eval_task — 评测任务元数据与进度。"""

    __tablename__ = "t_eval_task"

    task_id        = Column(String(64), primary_key=True)
    filename       = Column(Text)
    file_path      = Column(Text)
    bu             = Column(String(64))
    status         = Column(String(32))
    stage          = Column(String(64))
    mode           = Column(String(32))
    progress_done  = Column(Integer, default=0)
    progress_total = Column(Integer, default=0)
    created_at     = Column(Float)
    finished_at    = Column(Float)
    error          = Column(Text)
    result_json    = Column(JSONB)


class EvalTaskRow(Base):
    """t_eval_task_row — 逐条评测结果(断点续跑的依据)。"""

    __tablename__ = "t_eval_task_row"

    task_id   = Column(String(64), primary_key=True)
    row_index = Column(BigInteger, primary_key=True)
    row_json  = Column(JSONB)


_engine = create_engine(settings.db_url, pool_pre_ping=True, pool_size=5, future=True)
_Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)

# 任务元数据对外暴露的列(list_tasks 用,不含大字段 result_json)
_TASK_PUBLIC_COLS = (
    "task_id", "filename", "bu", "status", "stage", "mode",
    "progress_done", "progress_total", "created_at", "finished_at", "error",
)
# 单任务完整列(get_task 用)
_TASK_ALL_COLS = _TASK_PUBLIC_COLS + ("file_path", "result_json")


def init_db() -> None:
    Base.metadata.create_all(_engine)


def _task_dict(t: EvalTask, cols: tuple) -> dict:
    return {c: getattr(t, c) for c in cols}


def create_task(task_id: str, filename: str, file_path: str, bu: str) -> None:
    with _Session() as s, s.begin():
        # INSERT ... ON CONFLICT DO UPDATE = 原 SQLite 的 INSERT OR REPLACE
        stmt = pg_insert(EvalTask).values(
            task_id=task_id, filename=filename, file_path=file_path, bu=bu,
            status="pending", stage="", created_at=time.time(),
        ).on_conflict_do_update(
            index_elements=["task_id"],
            set_={"filename": filename, "file_path": file_path, "bu": bu,
                  "status": "pending", "stage": ""},
        )
        s.execute(stmt)


def update_task(task_id: str, **fields: Any) -> None:
    if not fields:
        return
    with _Session() as s, s.begin():
        s.query(EvalTask).filter(EvalTask.task_id == task_id).update(fields)


def get_task(task_id: str) -> Optional[dict]:
    with _Session() as s:
        t = s.get(EvalTask, task_id)
        return _task_dict(t, _TASK_ALL_COLS) if t else None


def list_tasks() -> list[dict]:
    with _Session() as s:
        rows = s.execute(
            select(EvalTask).order_by(EvalTask.created_at.desc())
        ).scalars().all()
    return [_task_dict(t, _TASK_PUBLIC_COLS) for t in rows]


def save_rows(task_id: str, rows: list[dict]) -> None:
    """批量 upsert 逐条结果(断点续跑的依据)。"""
    if not rows:
        return
    payload = [
        {"task_id": task_id, "row_index": r["row_index"], "row_json": r}
        for r in rows
    ]
    with _Session() as s, s.begin():
        stmt = pg_insert(EvalTaskRow).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["task_id", "row_index"],
            set_={"row_json": stmt.excluded.row_json},
        )
        s.execute(stmt)


def done_row_indices(task_id: str) -> set[int]:
    """已落盘的 row_index 集合,用于跳过、断点续跑。"""
    with _Session() as s:
        rows = s.execute(
            select(EvalTaskRow.row_index).where(EvalTaskRow.task_id == task_id)
        ).scalars().all()
    return set(rows)


def load_rows(task_id: str) -> list[dict]:
    """读回所有逐条结果(按 row_index 排序)。"""
    with _Session() as s:
        rows = s.execute(
            select(EvalTaskRow.row_json)
            .where(EvalTaskRow.task_id == task_id)
            .order_by(EvalTaskRow.row_index)
        ).scalars().all()
    return list(rows)


def save_result(task_id: str, result: dict) -> None:
    """落盘聚合结果(指标/洞察/建议等,不含逐条 rows——rows 在 t_eval_task_row)。"""
    slim = {k: v for k, v in result.items() if k not in ("rows", "disagreements")}
    update_task(task_id, result_json=slim)


def load_result(task_id: str) -> Optional[dict]:
    t = get_task(task_id)
    if not t or not t.get("result_json"):
        return None
    result = dict(t["result_json"])
    # rows / disagreements 从 t_eval_task_row 读回拼上
    rows = load_rows(task_id)
    result["rows"] = rows
    result["disagreements"] = [r for r in rows if r.get("is_disagreement")]
    return result
