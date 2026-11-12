#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ "${1:-}" = "--reset" ]; then
  echo "› 重置演示数据库…"
  rm -f server/data/ecoa.db     
fi

if [ ! -d server/.venv ]; then
  echo "› 创建 Python 虚拟环境…"
  python3 -m venv server/.venv
fi

echo "› 安装后端依赖…"
server/.venv/bin/pip install -q -r server/requirements.txt

if [ ! -d web/node_modules ]; then
  echo "› 安装前端依赖…"
  (cd web && npm install --no-audit --no-fund)
fi

cleanup() {
  if [ -n "${BACK_PID:-}" ]; then kill "$BACK_PID" 2>/dev/null || true; fi
  if [ -n "${FRONT_PID:-}" ]; then kill "$FRONT_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

echo "› 启动后端 http://localhost:8000"
(cd server && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000) &
BACK_PID=$!

echo "› 启动前端 http://localhost:5173"
(cd web && npm run dev) &
FRONT_PID=$!

echo ""
echo "=============================================="
echo "  智营 · 电商运营助手 已启动"
echo "  前端：http://localhost:5173"
echo "  接口：http://localhost:8000/docs"
echo "  账号：operator / 123456（运营人员）"
echo "        manager  / 123456（运营主管）"
echo "  重置演示数据：./start.sh --reset"
echo "=============================================="
echo ""

wait
