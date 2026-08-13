from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Supabase session pooler (port 5432) pins each client connection to a server
# connection, so asyncpg prepared statements are safe there (unlike the
# transaction pooler). It only requires TLS.
_db_connect_args = (
    {"ssl": "require"}
    if settings.DATABASE_SSL
    else {}
)

# Session pooler caps at 10 client connections on the free plan.
_db_pool_kwargs = (
    {"pool_size": 5, "max_overflow": 5}
    if settings.DATABASE_SSL
    else {}
)

# Create async engine for PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    connect_args=_db_connect_args,
    **_db_pool_kwargs,
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
