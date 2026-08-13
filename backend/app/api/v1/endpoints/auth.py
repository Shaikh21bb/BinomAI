from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.api.deps import get_db, get_current_user, security
from app.core.config import settings
from app.db.models.user import User
from app.core.supabase import supabase_admin
from app.schemas.auth import (
    UserLogin, UserRegister, TokenRefresh,
    LoginResponse, RegisterResponse, RefreshResponse,
    ForgotPasswordRequest, ResetPasswordRequest
)
from app.services.auth_service import AuthService
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Register a new company and user.
    Uses Supabase GoTrue API underneath.
    """
    logger.info("auth_register_attempt", email=data.email)
    return await AuthService.register(db, data)

@router.post("/login", response_model=LoginResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Login using email and password.
    Returns access token, refresh token, and user metadata.
    """
    logger.info("auth_login_attempt", email=credentials.email)
    return await AuthService.login(db, credentials)

@router.post("/refresh", response_model=RefreshResponse)
async def refresh(token_data: TokenRefresh):
    """
    Refresh an expired access token using a valid refresh token.
    """
    return await AuthService.refresh_token(token_data)

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    """
    Request a password recovery email via Supabase GoTrue.
    Always returns 200 so the endpoint never leaks whether an email exists.
    """
    url = f"{settings.SUPABASE_URL}/auth/v1/recover"
    async with httpx.AsyncClient() as client:
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
async def reset_password(data: ResetPasswordRequest):
    """
    Set a new password using the access token from the recovery email.
    """
    url = f"{settings.SUPABASE_URL}/auth/v1/user"
    async with httpx.AsyncClient() as client:
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
async def logout(token: HTTPAuthorizationCredentials = Depends(security)):
    """
    Invalidate the current session.
    """
    await AuthService.logout(token.credentials)
    return {"success": True, "data": {"message": "Вы успешно вышли из системы"}}

@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the current authenticated user's profile.
    Used by frontend to verify session validity.
    """
    email = ""
    try:
        from sqlalchemy import select
        from app.db.models.company import Company
        res = await db.execute(select(Company.email).where(Company.id == current_user.company_id))
        email = res.scalar_one_or_none() or ""
    except Exception:
        email = ""
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
