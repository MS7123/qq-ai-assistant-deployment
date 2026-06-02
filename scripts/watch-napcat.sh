#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/root/qq-ai-assistant-deployment}"
LOG_FILE="${LOG_FILE:-${PROJECT_DIR}/data/napcat-watchdog.log}"
CHECK_WINDOW="${CHECK_WINDOW:-15m}"

cd "$PROJECT_DIR"

mkdir -p "$(dirname "$LOG_FILE")"

if ! docker compose ps napcat --status running >/dev/null 2>&1; then
  echo "$(date '+%F %T') napcat container is not running, restarting..." >> "$LOG_FILE"
  docker compose up -d napcat >> "$LOG_FILE" 2>&1
  exit 0
fi

if docker compose logs --since "$CHECK_WINDOW" napcat \
  | grep -E "账号状态变更为离线|网络连接异常|1006514|No route to host|Network is unreachable" >/dev/null; then
  echo "$(date '+%F %T') napcat offline/network error detected, restarting..." >> "$LOG_FILE"
  docker compose restart napcat >> "$LOG_FILE" 2>&1
fi
