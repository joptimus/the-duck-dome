#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting DuckDome dev environment..."

# Start backend
echo "Starting backend..."
(cd "$REPO_ROOT/backend" && uvicorn duckdome.main:app --host 127.0.0.1 --port 8000 --reload) &
BACKEND_PID=$!

# Start web dev server
echo "Starting web dev server..."
(cd "$REPO_ROOT/apps/web" && npm run dev) &
WEB_PID=$!

cleanup() {
  echo "Shutting down..."
  kill "$BACKEND_PID" "$WEB_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Backend: http://localhost:8000"
echo "Web:     http://localhost:5173"
echo "Press Ctrl+C to stop."

wait
