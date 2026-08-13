from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Create async engine for PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
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
)

async_task_session_factory = async_sessionmaker(
    task_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)
