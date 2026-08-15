#!/bin/sh
set -e

# Redis runs inside the same container (free plan has no managed Redis).
if ! redis-cli -p 6379 ping >/dev/null 2>&1; then
  redis-server --daemonize yes --save "" --appendonly no
  sleep 1
fi

# Recycle child processes after 50 tasks to bound memory growth; the SDKs are
# imported lazily (llm_client) so workers stay well under the 512MB container limit.
celery -A app.tasks.celery_app worker \
  --loglevel=info \
  --concurrency=2 \
  --max-tasks-per-child=50 &

celery -A app.tasks.celery_app beat \
  --loglevel=info \
  --schedule /tmp/celerybeat-schedule &

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --timeout-keep-alive 5 \
  --no-server-header
