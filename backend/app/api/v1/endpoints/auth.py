from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, get_redis, security
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit, rate_limit_subject
from app.db.models.user import User
from app.core.supabase import supabase_admin, create_supabase_http_client, supabase_auth_errors
from app.schemas.auth import (
    UserLogin, UserRegister, TokenRefresh,
    LoginResponse, RegisterResponse, RefreshResponse,
    ForgotPasswordRequest, ResetPasswordRequest
)
from app.services.auth_service import AuthService
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _limit_auth(
    cache: redis.Redis,
    request: Request,
    scope: str,
    identifier: str,
) -> None:
    client_host = request.client.host if request.client else "unknown"
    await enforce_rate_limit(
        cache,
        scope=f"auth-{scope}",
        subject=rate_limit_subject(client_host, identifier),
        rate=settings.RATE_LIMIT_AUTH,
    )

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
    cache: redis.Redis = Depends(get_redis),
):
    """
    Register a new company and user.
    Uses Supabase GoTrue API underneath.
    """
    await _limit_auth(cache, request, "register", str(data.email))
    logger.info("auth_register_attempt", email=data.email)
    return await AuthService.register(db, data)

@router.post("/login", response_model=LoginResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
    cache: redis.Redis = Depends(get_redis),
):
    """
    Login using email and password.
    Returns access token, refresh token, and user metadata.
    """
    await _limit_auth(cache, request, "login", str(credentials.email))
    logger.info("auth_login_attempt", email=credentials.email)
    return await AuthService.login(db, credentials)

@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    token_data: TokenRefresh,
    request: Request,
    cache: redis.Redis = Depends(get_redis),
):
    """
    Refresh an expired access token using a valid refresh token.
    """
    await _limit_auth(cache, request, "refresh", token_data.refresh_token)
    return await AuthService.refresh_token(token_data)

@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    cache: redis.Redis = Depends(get_redis),
):
    """
    Request a password recovery email via Supabase GoTrue.
    Always returns 200 so the endpoint never leaks whether an email exists.
    """
    await _limit_auth(cache, request, "forgot-password", str(data.email))
    url = f"{settings.SUPABASE_URL}/auth/v1/recover"
    async with supabase_auth_errors(), create_supabase_http_client() as client:
        await client.post(
            url,
            json={"email": data.email},
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
        )
    return {"success": True, "message": "Если аккаунт с таким email существует, мы отправили инструкции"}

@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    request: Request,
    cache: redis.Redis = Depends(get_redis),
):
    """
    Set a new password using the access token from the recovery email.
    """
    await _limit_auth(cache, request, "reset-password", data.access_token)
    url = f"{settings.SUPABASE_URL}/auth/v1/user"
    async with supabase_auth_errors(), create_supabase_http_client() as client:
        response = await client.put(
            url,
            json={"password": data.new_password},
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {data.access_token}",
                "Content-Type": "application/json",
            },
        )
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Ссылка для сброса недействительна или истекла")
    return {"success": True, "message": "Пароль успешно изменён"}

@router.post("/logout")
async def logout(
    request: Request,
    token: HTTPAuthorizationCredentials = Depends(security),
    cache: redis.Redis = Depends(get_redis),
):
    """
    Invalidate the current session.
    """
    await _limit_auth(cache, request, "logout", token.credentials)
    await AuthService.logout(token.credentials)
    return {"success": True, "data": {"message": "Вы успешно вышли из системы"}}

@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Return the current authenticated user's profile.
    Used by frontend to verify session validity.
    """
    email = current_user.email or ""
    if not email:
        try:
            async with supabase_admin.get_client() as client:
                resp = await client.get(f"/auth/v1/admin/users/{current_user.id}")
                if resp.status_code == 200:
                    email = resp.json().get("email") or ""
        except Exception:
            pass
    return {
        "id": current_user.id,
        "email": email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "company_id": current_user.company_id
    }
