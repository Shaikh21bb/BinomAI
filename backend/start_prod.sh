#!/bin/sh
if ! redis-cli -p 6379 ping >/dev/null 2>&1; then
  redis-server --daemonize yes --save "" --appendonly no
  sleep 1
fi
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2 &
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"