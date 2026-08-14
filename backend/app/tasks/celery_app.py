from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "binom_ai_tasks",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.tasks.document_tasks",
        "app.tasks.analysis_tasks",
        "app.tasks.product_search_tasks",
        "app.tasks.tender_tasks"
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Almaty",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600, # 1 hour max
    worker_prefetch_multiplier=1, # Fair dispatching
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "refresh-tender-lots": {
            "task": "app.tasks.tender_tasks.refresh_all_tenders",
            "schedule": crontab(minute="*/15"),
        },
    },
)
