#!/usr/bin/env bash
# 构建前端产物 → 之后后端单进程即可托管整个应用(内网部署无需常驻 node)。
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "▶ 安装前端依赖并构建产物 ..."
cd "$ROOT/frontend"
npm ci 2>/dev/null || npm install
npm run build

echo ""
echo "✓ 前端已构建到 frontend/dist"
echo ""
echo "启动(单进程,后端直接托管前端):"
echo "  cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8848"
echo "  打开 http://<本机IP>:8848"
