from fastapi import APIRouter, Response, status
import json
from sqlalchemy import text
import redis.asyncio as redis
import structlog
import httpx

from app.core.config import settings
from app.db.session import async_session_factory

router = APIRouter()
logger = structlog.get_logger(__name__)

@router.get("/health")
@router.get("/health/live")
async def health_live():
    """Liveness probe: the process is up and serving requests."""
    return {"status": "ok", "service": "binom-api"}

@router.get("/health/ready")
async def health_ready():
    """Readiness probe: checks DB, Redis and external integrations."""
    health_status = {
        "status": "ok",
        "database": "unknown",
        "redis": "unknown",
        "celery": "unknown",
        "supabase": "unknown",
        "ai_engine": "unknown"
    }

    # 1. Check DB
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        health_status["database"] = "ok"
    except Exception as e:
        logger.error("health_check_db_failed", error=str(e))
        health_status["database"] = "error"
        health_status["status"] = "error"

    # 2. Check Redis
    try:
        async with redis.from_url(settings.REDIS_URL) as redis_client:
            await redis_client.ping()
        health_status["redis"] = "ok"
    except Exception as e:
        logger.error("health_check_redis_failed", error=str(e))
        health_status["redis"] = "error"
        health_status["status"] = "error"

    # 3. Check Celery (workers answering ping)
    try:
        from app.tasks.celery_app import celery_app
        i = celery_app.control.inspect()
        active = i.active()
        if active is None or len(active) == 0:
            health_status["celery"] = "no workers"
        else:
            health_status["celery"] = "ok"
    except Exception as e:
        logger.error("health_check_celery_failed", error=str(e))
        health_status["celery"] = "error"

    # 4. Check Supabase (REST API ping)
    try:
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            health_status["supabase"] = "error (missing env)"
            health_status["status"] = "error"
        else:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(
                    f"{settings.SUPABASE_URL}/rest/v1/",
                    headers={"apikey": settings.SUPABASE_ANON_KEY},
                )
                if res.status_code in [200, 404, 401]:
                    health_status["supabase"] = "ok"
                else:
                    health_status["supabase"] = "error"
    except Exception as e:
        logger.error("health_check_supabase_failed", error=str(e))
        health_status["supabase"] = "error"

    # 5. Check AI Engine (keys presence)
    if settings.GOOGLE_AI_API_KEY and len(settings.GOOGLE_AI_API_KEY) > 5:
        health_status["ai_engine"] = "ok"
    else:
        health_status["ai_engine"] = "error (missing key)"
        health_status["status"] = "error"

    # 6. JWT configuration
    if not settings.SUPABASE_JWT_SECRET:
        health_status["status"] = "error"
        health_status["jwt"] = "error (missing secret)"

    return Response(
        content=json.dumps(health_status, ensure_ascii=False),
        media_type="application/json",
        status_code=status.HTTP_200_OK if health_status["status"] == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
