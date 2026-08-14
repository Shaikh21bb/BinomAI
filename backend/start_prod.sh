#!/bin/sh
set -e

# Redis runs inside the same container (free plan has no managed Redis).
if ! redis-cli -p 6379 ping >/dev/null 2>&1; then
  redis-server --daemonize yes --save "" --appendonly no
  sleep 1
fi

# Leak protection for long-running workers on a 512MB free instance:
# recycle child processes after 50 tasks or 200MB RSS.
celery -A app.tasks.celery_app worker \
  --loglevel=info \
  --concurrency=2 \
  --max-tasks-per-child=50 \
  --max-memory-per-child=200000 &

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --timeout-keep-alive 5 \
  --no-server-header
