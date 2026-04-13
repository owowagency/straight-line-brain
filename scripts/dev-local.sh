#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

echo "Starting infra containers (db, redis, minio, chatbot-db)..."
docker compose stop api mcp chatbot >/dev/null 2>&1 || true
docker compose up -d db redis minio chatbot-db

for port in 8000 8001 3000; do
  PORT_PIDS="$(lsof -ti "tcp:${port}" 2>/dev/null || true)"
  if [ -n "$PORT_PIDS" ]; then
    echo "Freeing port ${port} (stopping existing process)..."
    kill $PORT_PIDS 2>/dev/null || true
    sleep 1
  fi
done

echo "Running chatbot DB migrations..."
(
  cd chatbot
  POSTGRES_URL="postgresql://chatbot:chatbot_dev@localhost:5433/chatbot" \
  pnpm db:migrate >/dev/null
)

echo
echo "Starting local processes with terminal logs:"
echo "  API      http://localhost:8000"
echo "  MCP      http://localhost:8001/mcp"
echo "  Chatbot  http://localhost:3000"
echo

if pgrep -f "/straight-line-brain/chatbot.*next dev" >/dev/null 2>&1; then
  echo "Stopping existing chatbot dev process..."
  pkill -f "/straight-line-brain/chatbot.*next dev" || true
  sleep 1
fi

IS_SHUTTING_DOWN=0

shutdown() {
  if [ "$IS_SHUTTING_DOWN" -eq 1 ]; then
    return
  fi
  IS_SHUTTING_DOWN=1
  echo
  echo "Stopping local processes..."
  kill "${API_PID:-}" "${MCP_PID:-}" "${CHATBOT_PID:-}" 2>/dev/null || true
  wait "${API_PID:-}" "${MCP_PID:-}" "${CHATBOT_PID:-}" 2>/dev/null || true
}

on_signal() {
  shutdown
  exit 0
}

trap on_signal INT TERM
trap shutdown EXIT

(
  DATABASE_URL="postgresql+asyncpg://brein:brein_dev@localhost:5432/digitaal_brein?ssl=disable" \
  REDIS_URL="redis://localhost:6379/0" \
  MINIO_ENDPOINT="localhost:9000" \
  API_HOST="0.0.0.0" \
  API_PORT="8000" \
  uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 2>&1
) | sed -u 's/^/[api] /' &
API_PID=$!

(
  BREIN_URL="http://localhost:8000" \
  MCP_HOST="0.0.0.0" \
  MCP_PORT="8001" \
  MCP_TRANSPORT="streamable-http" \
  uv run python mcp_server.py --remote 2>&1
) | sed -u 's/^/[mcp] /' &
MCP_PID=$!

(
  cd chatbot
  PORT="3000" \
  AUTH_SECRET="${AUTH_SECRET:-e3b0c44298fc1c149afbf4c8996fb924}" \
  POSTGRES_URL="postgresql://chatbot:chatbot_dev@localhost:5433/chatbot" \
  MCP_SERVER_URL="http://localhost:8001/mcp" \
  pnpm dev 2>&1
) | sed -u 's/^/[chatbot] /' &
CHATBOT_PID=$!

while true; do
  for pid in "$API_PID" "$MCP_PID" "$CHATBOT_PID"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      wait "$pid"
      exit $?
    fi
  done
  sleep 1
done
