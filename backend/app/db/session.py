from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
import itertools
from app.core.config import settings

# PgBouncer (Supabase pooler) reuses server connections across clients and
# keeps prepared statements alive, so asyncpg's auto-generated statement
# names ("__asyncpg_stmt_N__") collide with leftovers. Generating a unique
# name per statement makes collisions impossible; the dialect statement
# cache is disabled accordingly.
_statement_names = itertools.count()

def _unique_statement_name() -> str:
    return f"_binom_{next(_statement_names)}"

# Supabase pooler requires TLS.
_db_connect_args = (
    {
        "ssl": "require",
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": _unique_statement_name,
    }
    if settings.DATABASE_SSL
    else {}
)

# Session pooler caps at 10 client connections on the free plan. Leave headroom:
# Celery tasks use NullPool connections that can add up to `concurrency` more.
_db_pool_kwargs = (
    {"pool_size": 5, "max_overflow": 2}
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
