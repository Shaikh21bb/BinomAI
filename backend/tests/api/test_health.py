import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.config import settings
from app.tasks.celery_app import celery_app


@asynccontextmanager
async def _client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _patch_all_ok():
    db = AsyncMock()
    db.execute = AsyncMock()
    db_cm = MagicMock()
    db_cm.__aenter__ = AsyncMock(return_value=db)
    db_cm.__aexit__ = AsyncMock(return_value=False)
    patch_db = patch("app.api.v1.endpoints.health.async_session_factory",
                     MagicMock(return_value=db_cm))

    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_cm = MagicMock()
    redis_cm.__aenter__ = AsyncMock(return_value=redis_client)
    redis_cm.__aexit__ = AsyncMock(return_value=False)
    patch_redis = patch("app.api.v1.endpoints.health.redis.from_url",
                        MagicMock(return_value=redis_cm))

    fake_inspect = MagicMock()
    fake_inspect.active.return_value = {"celery@worker": []}
    fake_control = MagicMock()
    fake_control.inspect.return_value = fake_inspect
    patch_celery = patch.object(celery_app, "control", fake_control)

    http_client_class = MagicMock()
    http_client = MagicMock()
    http_client.get = AsyncMock(return_value=MagicMock(status_code=200))
    http_client_class.return_value.__aenter__ = AsyncMock(return_value=http_client)
    http_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
    patch_http = patch("app.api.v1.endpoints.health.httpx.AsyncClient", http_client_class)

    patch_url = patch.object(settings, "SUPABASE_URL", "https://example.supabase.co")
    patch_key = patch.object(settings, "SUPABASE_ANON_KEY", "test-key")
    patch_ai = patch.object(settings, "GOOGLE_AI_API_KEY", "sk-test-123456")
    patch_jwt = patch.object(settings, "SUPABASE_JWT_SECRET", "test-secret")
    return [patch_db, patch_redis, patch_celery, patch_http, patch_url, patch_key, patch_ai, patch_jwt]


@pytest.mark.asyncio
async def test_health_live_200():
    async with _client() as c:
        resp = await c.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "binom-api"


@pytest.mark.asyncio
async def test_health_live_alias_200():
    async with _client() as c:
        resp = await c.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_all_ok_200():
    patches = _patch_all_ok()
    for p in patches:
        p.start()
    try:
        async with _client() as c:
            resp = await c.get("/api/v1/health/ready")
    finally:
        for p in reversed(patches):
            p.stop()

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["redis"] == "ok"
    assert body["celery"] == "ok"
    assert body["supabase"] == "ok"
    assert body["ai_engine"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_db_and_redis_down_503():
    patch_db = patch("app.api.v1.endpoints.health.async_session_factory",
                     MagicMock(side_effect=Exception("db down")))
    patch_redis = patch("app.api.v1.endpoints.health.redis.from_url",
                        AsyncMock(side_effect=Exception("redis down")))
    fake_control = MagicMock()
    fake_control.inspect.side_effect = Exception("broker down")
    patch_celery = patch.object(celery_app, "control", fake_control)
    http_client_class = MagicMock()
    http_client = MagicMock()
    http_client.get = AsyncMock(return_value=MagicMock(status_code=200))
    http_client_class.return_value.__aenter__ = AsyncMock(return_value=http_client)
    http_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
    patch_http = patch("app.api.v1.endpoints.health.httpx.AsyncClient", http_client_class)
    patch_url = patch.object(settings, "SUPABASE_URL", "https://example.supabase.co")
    patch_key = patch.object(settings, "SUPABASE_ANON_KEY", "test-key")
    patch_ai = patch.object(settings, "GOOGLE_AI_API_KEY", "")
    patch_jwt = patch.object(settings, "SUPABASE_JWT_SECRET", "")

    patches = [patch_db, patch_redis, patch_celery, patch_http, patch_url, patch_key, patch_ai, patch_jwt]
    for p in patches:
        p.start()
    try:
        async with _client() as c:
            resp = await c.get("/api/v1/health/ready")
    finally:
        for p in reversed(patches):
            p.stop()

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["database"] == "error"
    assert body["redis"] == "error"
