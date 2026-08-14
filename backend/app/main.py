from contextlib import asynccontextmanager
import asyncio
from sqlalchemy import text
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import custom_http_exception_handler, validation_exception_handler, http_exception_handler
from app.core.redis import init_redis, close_redis
from app.core.supabase import supabase_admin
from app.api.v1.api import api_router

logger = structlog.get_logger(__name__)

# During deploys Supabase's pooler can briefly be unreachable; retry instead
# of shipping an instance with no schema. Fail hard when the DB never comes
# up so Render marks the deploy as failed instead of serving a broken app.
DB_SCHEMA_RETRIES = 5
DB_SCHEMA_RETRY_DELAY = 10

# create_all adds new tables but never alters existing ones; run additive
# column migrations here (idempotent).
ADDITIVE_MIGRATIONS = [
    "ALTER TABLE tender_lots ADD COLUMN IF NOT EXISTS deadline_warn_level INTEGER NOT NULL DEFAULT 0",
]

async def _run_light_migrations() -> None:
    from app.db.session import engine

    try:
        async with engine.begin() as conn:
            for sql in ADDITIVE_MIGRATIONS:
                await conn.execute(text(sql))
        logger.info("light_migrations_ok", count=len(ADDITIVE_MIGRATIONS))
    except Exception as e:  # noqa: BLE001
        logger.warning("light_migrations_skipped", error=str(e))


async def _ensure_db_schema() -> None:
    from app.db.base import Base
    from app.db.session import engine
    import app.db.models  # ensure all models are registered

    last_error: Exception | None = None
    for attempt in range(1, DB_SCHEMA_RETRIES + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("db_schema_ready", attempt=attempt)
            return
        except Exception as e:  # noqa: BLE001
            last_error = e
            logger.warning("db_create_all_retry", attempt=attempt, error=str(e))
            if attempt < DB_SCHEMA_RETRIES:
                await asyncio.sleep(DB_SCHEMA_RETRY_DELAY)
    raise RuntimeError(f"db_schema_not_ready: {last_error}")

REQUIRED_STORAGE_BUCKETS = [
    settings.STORAGE_BUCKET_TENDER_DOCS,
    settings.STORAGE_BUCKET_COMPANY_ASSETS,
    settings.STORAGE_BUCKET_EXPORTS,
    "extracted-texts",
]

async def ensure_storage_buckets() -> None:
    """Create required Supabase Storage buckets if they don't exist yet."""
    try:
        async with supabase_admin.get_client() as client:
            resp = await client.get("/storage/v1/bucket")
            existing = {b.get("name") for b in resp.json()} if resp.status_code == 200 else set()
            for bucket in REQUIRED_STORAGE_BUCKETS:
                if bucket in existing:
                    continue
                created = await client.post("/storage/v1/bucket", json={"name": bucket, "public": False})
                if created.status_code in (200, 201):
                    logger.info("storage_bucket_created", bucket=bucket)
                else:
                    logger.warning("storage_bucket_creation_failed", bucket=bucket, status=created.status_code)
    except Exception as e:
        logger.error("storage_buckets_check_failed", error=str(e))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events for infrastructure connections.
    """
    # Startup
    logger.info("app_starting", version=settings.APP_VERSION, env=settings.APP_ENV)
    await init_redis()
    await ensure_storage_buckets()
    await _run_light_migrations()
    await _ensure_db_schema()
    
    yield
    
    # Shutdown
    logger.info("app_shutting_down")
    await close_redis()

def create_app() -> FastAPI:
    """
    FastAPI application factory.
    """
    # Initialize structured logging
    setup_logging(is_production=(settings.APP_ENV == "production"))
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # Set all CORS enabled origins
    if settings.parsed_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.parsed_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Exception handlers
    app.add_exception_handler(Exception, custom_http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Routers
    app.include_router(api_router, prefix="/api/v1")

    return app

app = create_app()
