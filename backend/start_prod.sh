#!/bin/sh
set -e

# Redis runs inside the same container (free plan has no managed Redis).
if ! redis-cli -p 6379 ping >/dev/null 2>&1; then
  redis-server --daemonize yes --save "" --appendonly no
  sleep 1
fi

# Single-process worker with embedded beat: keeps total RSS under the 512MB
# container limit (separate worker+beat+2 children exceeded it and got OOM-killed).
celery -A app.tasks.celery_app worker \
  --beat \
  --schedule /tmp/celerybeat-schedule \
  --loglevel=info \
  --concurrency=1 \
  --max-tasks-per-child=50 &

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --timeout-keep-alive 5 \
  --no-server-header
