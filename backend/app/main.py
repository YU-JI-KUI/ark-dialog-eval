# -*- coding: utf-8 -*-
"""FastAPI 应用入口。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import settings
from app.core.llm.pingan_client import close_client

# 前端构建产物目录(npm run build 后生成);存在则由后端直接托管,
# 内网部署只需一个 Python 进程,无需 node。
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_client()  # 关闭 httpx 连接池


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# 开发期允许前端跨域(Vite 默认 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "backend": settings.judge_backend}


# ---- 托管前端构建产物(若存在)----
# 放在所有 /api 路由之后注册,确保不抢占 API。SPA 路由全部回 index.html。
if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    async def _index():
        return FileResponse(_FRONTEND_DIST / "index.html")

    _DIST_ROOT = _FRONTEND_DIST.resolve()

    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        # 非 API、非静态资源的路径一律回前端入口,交给前端路由。
        # 正规化路径并校验仍在 dist 内,防止 ../ 路径遍历。
        candidate = (_FRONTEND_DIST / full_path).resolve()
        if str(candidate).startswith(str(_DIST_ROOT)) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
