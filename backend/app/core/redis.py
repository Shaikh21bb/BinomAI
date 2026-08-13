import redis.asyncio as redis
from typing import AsyncGenerator
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

# Global redis connection pool
redis_pool = None

async def init_redis():
    """Initialize Redis connection pool."""
    global redis_pool
    try:
        redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
        # Test connection
        client = redis.Redis(connection_pool=redis_pool)
        await client.ping()
        await client.aclose()
        logger.info("redis_connected", url=settings.REDIS_URL)
    except Exception as e:
        logger.error("redis_connection_failed", error=str(e))
        raise

async def close_redis():
    """Close Redis connection pool."""
    global redis_pool
    if redis_pool:
        await redis_pool.disconnect()
        logger.info("redis_disconnected")

async def get_redis_client() -> AsyncGenerator[redis.Redis, None]:
    """Dependency for getting a Redis client from the pool."""
    if not redis_pool:
        raise RuntimeError("Redis pool not initialized")
    
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.aclose()
