from contextlib import asynccontextmanager
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
    try:
        from app.db.base import Base
        from app.db.session import engine
        import app.db.models  # ensure all models are registered
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        logger.error("db_create_all_failed", error=str(e))
    
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
