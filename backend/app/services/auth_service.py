import uuid
import httpx
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.core.config import settings
from app.core.supabase import supabase_admin
from app.schemas.auth import UserLogin, UserRegister, TokenRefresh
from app.db.models.user import User
from app.db.models.company import Company
from app.db.models.invite import Invite
from app.db.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)

# Reusing base repo for simple checks
user_repo = BaseRepository(User)
company_repo = BaseRepository(Company)

class AuthService:
    """
    Handles authentication via Supabase GoTrue API and syncs custom user/company metadata.
    """
    
    @staticmethod
    async def login(db: AsyncSession, credentials: UserLogin) -> dict:
        url = f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=password"
        
        async with httpx.AsyncClient() as client:
            headers = {
                "apikey": settings.SUPABASE_ANON_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "email": credentials.email,
                "password": credentials.password
            }
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                logger.warning("supabase_login_failed", email=credentials.email, status=response.status_code)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Неверный email или пароль"
                )
                
            data = response.json()
            
            # Fetch user from our database to return full profile
            user_id = uuid.UUID(data["user"]["id"])
            stmt = select(User).where(User.id == user_id)
            result = await db.execute(stmt)
            db_user = result.scalars().first()
            
            if not db_user or not db_user.is_active:
                raise HTTPException(status_code=403, detail="Пользователь заблокирован или не найден")

            # Persist email locally (Supabase auth is external)
            if not db_user.email:
                db_user.email = credentials.email.lower()
                await db.flush()
                
            # Fetch company name
            stmt_c = select(Company).where(Company.id == db_user.company_id)
            res_c = await db.execute(stmt_c)
            db_company = res_c.scalars().first()
            
            return {
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "expires_in": data["expires_in"],
                "user": {
                    "id": db_user.id,
                    "email": credentials.email,
                    "full_name": db_user.full_name,
                    "role": db_user.role,
                    "company_id": db_user.company_id,
                    "company_name": db_company.name if db_company else ""
                }
            }

    @staticmethod
    async def refresh_token(token_data: TokenRefresh) -> dict:
        url = f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=refresh_token"
        
        async with httpx.AsyncClient() as client:
            headers = {
                "apikey": settings.SUPABASE_ANON_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "refresh_token": token_data.refresh_token
            }
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительный refresh токен"
                )
                
            data = response.json()
            return {
                "access_token": data["access_token"],
                "expires_in": data["expires_in"]
            }

    @staticmethod
    async def logout(access_token: str) -> None:
        url = f"{settings.SUPABASE_URL}/auth/v1/logout"
        
        async with httpx.AsyncClient() as client:
            headers = {
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {access_token}"
            }
            await client.post(url, headers=headers)
            
    @staticmethod
    async def register(db: AsyncSession, data: UserRegister) -> dict:
        """
        Creates a new user via Supabase Admin API, then creates the Company and User in our DB.
        """
        # 1. Create User in Supabase Auth
        url = f"{settings.SUPABASE_URL}/auth/v1/admin/users"
        
        async with supabase_admin.get_client() as client:
            payload = {
                "email": data.email,
                "password": data.password,
                "email_confirm": True # Auto-confirm for this implementation
            }
            response = await client.post(url, json=payload)
            
            if response.status_code != 200:
                error_msg = response.json().get("msg", "Registration failed")
                if "already exists" in error_msg.lower() or response.status_code == 422:
                    raise HTTPException(status_code=409, detail="Email уже зарегистрирован")
                raise HTTPException(status_code=400, detail=error_msg)
                
            auth_data = response.json()
            user_id = uuid.UUID(auth_data["id"])
            
        try:
            # Resolve invite (if provided) -> join owner's company with full access,
            # otherwise create own company with limited role.
            role = "limited"
            company_id: uuid.UUID | None = None

            if data.invite_code:
                invite = await _consume_invite(db, data.invite_code)
                if not invite:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Недействительный или истёкший инвайт-код",
                    )
                role = "member"
                company_id = invite.company_id

            if company_id is None:
                company = Company(name=data.company_name, plan="trial")
                db.add(company)
                await db.flush()
                company_id = company.id

            user = User(
                id=user_id,
                company_id=company_id,
                full_name=data.full_name,
                email=data.email.lower(),
                role=role,
            )
            db.add(user)
            await db.flush()

        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error("db_registration_failed", error=str(e))
            raise HTTPException(status_code=500, detail="Failed to create company profile")

        # 4. Auto-login to get tokens
        tokens = await AuthService.login(db, UserLogin(email=data.email, password=data.password))
        db_company = await _get_company(db, company_id)
        tokens["company"] = {
            "id": str(company_id),
            "name": db_company.name if db_company else "",
            "plan": db_company.plan if db_company else "trial",
        }
        return tokens


async def _consume_invite(db: AsyncSession, code: str) -> Invite | None:
    """Validates the invite code and increments its usage counter."""
    code = code.strip().upper()
    if not code:
        return None
    stmt = select(Invite).where(Invite.code == code)
    result = await db.execute(stmt)
    invite = result.scalars().first()

    if not invite or not invite.active:
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires = invite.expires_at
    if expires is not None:
        if expires.tzinfo is not None:
            expires = expires.astimezone().replace(tzinfo=None)
        if expires < now:
            return None
    if invite.uses >= invite.max_uses:
        return None

    invite.uses += 1
    await db.flush()
    return invite


async def _get_company(db: AsyncSession, company_id: uuid.UUID) -> Company | None:
    stmt = select(Company).where(Company.id == company_id)
    result = await db.execute(stmt)
    return result.scalars().first()
