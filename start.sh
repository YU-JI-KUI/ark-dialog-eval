#!/usr/bin/env bash
# 内网一键启动:编译前端 → 后端单进程托管 dist + API。
# 只需跑这一个脚本,不用单独开前端。前端产物由 FastAPI 直接 serve(见 backend/app/main.py)。
#
# 用法:
#   ./start.sh                 # 默认 0.0.0.0:8848
#   ./start.sh 9000            # 指定端口
#   PINGAN_ENV=1 ./start.sh    # (可选)提示已配好 .env 用平安大模型
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-8848}"

echo "▶ [1/3] 编译前端 ..."
cd "$ROOT/frontend"
# npm ci 严格按 lock 安装(内网无平台噪音);无 lock 时回退 npm install
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
npm run build
echo "  ✓ 前端已编译到 frontend/dist"

echo "▶ [2/3] 安装后端依赖 ..."
cd "$ROOT/backend"
uv sync
echo "  ✓ 后端依赖就绪"

echo "▶ [3/3] 启动服务(单进程,已挂载前端 dist)..."
echo "  打开 http://<本机IP>:$PORT   (API 文档 http://<本机IP>:$PORT/docs)"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
