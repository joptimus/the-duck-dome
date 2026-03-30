#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ── Setup (idempotent) ────────────────────────────────────────────────────────

echo "==> Checking backend..."
if [ ! -f "$REPO_ROOT/backend/.venv/bin/activate" ]; then
  echo "    Creating Python venv..."
  python3 -m venv "$REPO_ROOT/backend/.venv"
fi
source "$REPO_ROOT/backend/.venv/bin/activate"
pip install -e "$REPO_ROOT/backend[dev]" --quiet

echo "==> Checking web dependencies..."
if [ ! -d "$REPO_ROOT/apps/web/node_modules" ]; then
  echo "    Installing npm packages..."
  (cd "$REPO_ROOT/apps/web" && npm install --silent)
fi

echo "==> Checking desktop dependencies..."
if [ ! -d "$REPO_ROOT/apps/desktop/node_modules" ]; then
  echo "    Installing npm packages..."
  (cd "$REPO_ROOT/apps/desktop" && npm install --silent)
fi

# ── Run ───────────────────────────────────────────────────────────────────────

echo "==> Starting DuckDome..."

(cd "$REPO_ROOT/backend" && uvicorn duckdome.main:app --host 127.0.0.1 --port 8000 --reload) &
BACKEND_PID=$!

(cd "$REPO_ROOT/apps/web" && npm run dev) &
WEB_PID=$!

# Wait for Vite to be ready before launching Electron
echo "==> Waiting for Vite..."
until curl -s http://localhost:5173 > /dev/null 2>&1; do sleep 0.5; done

(cd "$REPO_ROOT/apps/desktop" && npm run dev) &
DESKTOP_PID=$!

cleanup() {
  echo ""
  echo "==> Shutting down..."
  kill "$BACKEND_PID" "$WEB_PID" "$DESKTOP_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$WEB_PID" "$DESKTOP_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo "    Backend → http://localhost:8000"
echo "    Web UI  → http://localhost:5173"
echo "    Electron → launching..."
echo ""
echo "    Ctrl+C to stop."
echo ""

wait
