from typing import AsyncGenerator, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import redis.asyncio as redis
import uuid
from sqlalchemy import select

from app.db.session import async_session_factory
from app.core.redis import get_redis_client
from app.db.models.user import User
from app.core.security import verify_jwt_token

security = HTTPBearer()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to provide an async SQLAlchemy session.
    Automatically commits on success, and rolls back on exception.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Alias for get_redis_client to match typical deps naming
async def get_redis(client: redis.Redis = Depends(get_redis_client)) -> redis.Redis:
    """
    Dependency to provide a Redis client.
    """
    return client

async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Validates JWT and returns the current active user.
    Enforces company isolation by returning the user model with their company_id.
    """
    payload = verify_jwt_token(token.credentials)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token payload")
        
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID in token")
        
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
        
    return user

class RoleChecker:
    """
    RBAC Dependency class. Usage: Depends(RoleChecker(["admin", "owner"]))
    """
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return user
