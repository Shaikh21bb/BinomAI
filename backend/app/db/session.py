from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Supabase pooler (PgBouncer) disallows prepared statements and requires TLS;
# disable statement caching on both asyncpg and the SQLAlchemy asyncpg dialect.
_db_connect_args = (
    {
        "ssl": "require",
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
    if settings.DATABASE_SSL
    else {}
)

# Create async engine for PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=_db_connect_args,
)

# Create session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Celery workers run each task in its own event loop via asyncio.run().
# A shared pool would bind connections to a loop that may already be closed,
# raising "attached to a different loop". NullPool keeps background tasks safe.
task_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    connect_args=_db_connect_args,
)

async_task_session_factory = async_sessionmaker(
    task_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)
