#!/bin/sh
set -e

# Redis runs inside the same container (free plan has no managed Redis).
if ! redis-cli -p 6379 ping >/dev/null 2>&1; then
  redis-server --daemonize yes --save "" --appendonly no
  sleep 1
fi

# Single-process worker (solo pool) with embedded beat: no forked children,
# keeps total container RSS ~330MB, far under the 512MB free-tier limit.
celery -A app.tasks.celery_app worker \
  --pool=solo \
  --beat \
  --schedule /tmp/celerybeat-schedule \
  --loglevel=info &

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --timeout-keep-alive 5 \
  --no-server-header
