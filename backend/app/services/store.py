# -*- coding: utf-8 -*-
"""SQLite 持久化层:任务元数据 + 逐条评测结果。

为什么用 SQLite:单文件、内网零依赖、3万行量级可靠。逐条结果落盘后,
任务跑一半中断可断点续跑(只补未完成的行)。

表结构:
  tasks      : 任务元数据与进度(每个评测任务一行)
  task_rows  : 逐条评测结果(task_id + row_index 唯一)

注:对单机演示与内网单副本足够。多副本需换成共享 DB,接口不变。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from app.config import settings

_DB_PATH = settings.outputs_dir / "eval.db"
_lock = threading.Lock()  # SQLite 写串行化,避免并发写锁冲突


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")  # 并发读友好
    return c


def init_db() -> None:
    with _lock, _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id     TEXT PRIMARY KEY,
                filename    TEXT,
                file_path   TEXT,
                bu          TEXT,
                status      TEXT,
                stage       TEXT,
                mode        TEXT,
                progress_done  INTEGER DEFAULT 0,
                progress_total INTEGER DEFAULT 0,
                created_at  REAL,
                finished_at REAL,
                error       TEXT,
                result_json TEXT
            );
            CREATE TABLE IF NOT EXISTS task_rows (
                task_id   TEXT,
                row_index INTEGER,
                row_json  TEXT,
                PRIMARY KEY (task_id, row_index)
            );
            """
        )


def create_task(task_id: str, filename: str, file_path: str, bu: str) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO tasks(task_id,filename,file_path,bu,status,stage,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (task_id, filename, file_path, bu, "pending", "", time.time()),
        )


def update_task(task_id: str, **fields: Any) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with _lock, _conn() as c:
        c.execute(f"UPDATE tasks SET {cols} WHERE task_id=?", (*fields.values(), task_id))


def get_task(task_id: str) -> Optional[dict]:
    with _conn() as c:
        r = c.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    return dict(r) if r else None


def list_tasks() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT task_id,filename,bu,status,stage,mode,progress_done,progress_total,"
            "created_at,finished_at,error FROM tasks ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def save_rows(task_id: str, rows: list[dict]) -> None:
    """批量落盘逐条结果(断点续跑的依据)。"""
    with _lock, _conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO task_rows(task_id,row_index,row_json) VALUES(?,?,?)",
            [(task_id, r["row_index"], json.dumps(r, ensure_ascii=False)) for r in rows],
        )


def done_row_indices(task_id: str) -> set[int]:
    """已落盘的 row_index 集合,用于跳过、断点续跑。"""
    with _conn() as c:
        rows = c.execute("SELECT row_index FROM task_rows WHERE task_id=?", (task_id,)).fetchall()
    return {r["row_index"] for r in rows}


def load_rows(task_id: str) -> list[dict]:
    """读回所有逐条结果(按 row_index 排序)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT row_json FROM task_rows WHERE task_id=? ORDER BY row_index", (task_id,)
        ).fetchall()
    return [json.loads(r["row_json"]) for r in rows]


def save_result(task_id: str, result: dict) -> None:
    """落盘聚合结果(指标/洞察/建议等,不含逐条 rows——rows 在 task_rows)。"""
    slim = {k: v for k, v in result.items() if k not in ("rows", "disagreements")}
    update_task(task_id, result_json=json.dumps(slim, ensure_ascii=False))


def load_result(task_id: str) -> Optional[dict]:
    t = get_task(task_id)
    if not t or not t.get("result_json"):
        return None
    result = json.loads(t["result_json"])
    # rows / disagreements 从 task_rows 读回拼上
    rows = load_rows(task_id)
    result["rows"] = rows
    result["disagreements"] = [r for r in rows if r.get("is_disagreement")]
    return result
