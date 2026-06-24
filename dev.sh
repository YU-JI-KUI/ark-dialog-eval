#!/usr/bin/env bash
# 本地开发一键启动:同时起后端(8848)+ 前端 dev(5234,带热更新)。
# Ctrl-C 一并退出。内网部署见 README「内网部署」一节,不用这个脚本。
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() { echo "\n停止服务..."; kill 0; }
trap cleanup EXIT INT TERM

echo "▶ 启动后端 FastAPI (http://127.0.0.1:8848) ..."
( cd "$ROOT/backend" && uv run uvicorn app.main:app --reload --port 8848 ) &

echo "▶ 启动前端 Vite  (http://127.0.0.1:5234) ..."
( cd "$ROOT/frontend" && npm run dev ) &

echo ""
echo "  前端开发地址: http://127.0.0.1:5234"
echo "  后端 API 文档: http://127.0.0.1:8848/docs"
echo "  Ctrl-C 退出"
wait
