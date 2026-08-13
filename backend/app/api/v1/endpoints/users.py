import uuid
import secrets
from datetime import datetime, timedelta, timezone
import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, get_current_user, security
from app.core.config import settings
from app.core.plans import get_plan
from app.core.security import verify_jwt_token
from app.db.models.user import User
from app.db.models.company import Company
from app.db.models.project import Project
from app.db.models.document import Document
from app.db.models.plan_request import PlanRequest
from app.schemas.plan import PlanUsage, PlanRequestCreate, PlanRequestResponse
from app.schemas.user import (
    UserUpdate,
    UserProfileResponse,
    PasswordChange,
    NotificationsUpdate,
)
from app.schemas.company import CompanyUpdate, CompanyResponse
from app.schemas.team import MemberResponse, MemberRoleUpdate
from app.schemas.admin import InviteCreate, InviteResponse
from app.db.models.invite import Invite

logger = structlog.get_logger(__name__)
router = APIRouter()


def _email_from_token(token: str) -> str:
    payload = verify_jwt_token(token)
    return payload.get("email") or ""


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's profile, including email and company name."""
    company = await db.get(Company, current_user.company_id)
    profile = UserProfileResponse.model_validate(current_user)
    profile.email = _email_from_token(creds.credentials)
    profile.company_name = company.name if company else ""
    return profile


@router.patch("/me", response_model=UserProfileResponse)
async def update_my_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Update profile fields of the authenticated user."""
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    await db.flush()
    await db.refresh(current_user)

    company = await db.get(Company, current_user.company_id)
    profile = UserProfileResponse.model_validate(current_user)
    profile.email = _email_from_token(creds.credentials)
    profile.company_name = company.name if company else ""
    return profile


@router.get("/me/company", response_model=CompanyResponse)
async def get_my_company(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the company profile of the authenticated user."""
    company = await db.get(Company, current_user.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return company


@router.get("/me/company/plan-usage", response_model=PlanUsage)
async def get_company_plan_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the company's current plan, its limits, and actual usage."""
    company = await db.get(Company, current_user.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")

    plan = get_plan(company.plan)
    usage = {}

    if plan.max_projects is not None or plan.max_users is not None or plan.max_documents is not None:
        usage["projects"] = (
            await db.execute(
                select(func.count()).select_from(Project).where(Project.company_id == company.id)
            )
        ).scalar() or 0
        usage["users"] = (
            await db.execute(
                select(func.count()).select_from(User).where(User.company_id == company.id, User.is_active.is_(True))
            )
        ).scalar() or 0
        usage["documents"] = (
            await db.execute(
                select(func.count()).select_from(Document).where(Document.company_id == company.id)
            )
        ).scalar() or 0

    return PlanUsage(
        plan=company.plan,
        plan_name=plan.name,
        plan_price_monthly_kzt=plan.price_monthly_kzt,
        plan_expires_at=company.plan_expires_at,
        limits={
            "max_projects": plan.max_projects,
            "max_users": plan.max_users,
            "max_documents": plan.max_documents,
            "features": plan.features,
        },
        usage=usage,
    )


@router.patch("/me/company", response_model=CompanyResponse)
async def update_my_company(
    data: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the company profile of the authenticated user."""
    company = await db.get(Company, current_user.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    await db.flush()
    await db.refresh(company)
    return company


@router.put("/me/password", status_code=200)
async def change_my_password(
    data: PasswordChange,
    creds: HTTPAuthorizationCredentials = Depends(security),
):
    """Verify the current password and change it via Supabase GoTrue."""
    async with httpx.AsyncClient() as client:
        # 1. Verify current credentials via GoTrue token endpoint
        verify_response = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=password",
            json={"email": _email_from_token(creds.credentials), "password": data.current_password},
            headers={"apikey": settings.SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        )
        if verify_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Текущий пароль указан неверно")

        # 2. Update the password for the authenticated user
        update_response = await client.put(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            json={"password": data.new_password},
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {creds.credentials}",
                "Content-Type": "application/json",
            },
        )
        if update_response.status_code != 200:
            logger.warning("password_change_failed", status=update_response.status_code)
            raise HTTPException(status_code=400, detail="Не удалось сменить пароль")

    return {"success": True, "message": "Пароль успешно изменён"}


@router.patch("/me/notifications", response_model=UserProfileResponse)
async def update_my_notifications(
    data: NotificationsUpdate,
    current_user: User = Depends(get_current_user),
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Toggle email notifications for the authenticated user."""
    current_user.email_notifications = data.email_notifications
    await db.flush()
    await db.refresh(current_user)

    company = await db.get(Company, current_user.company_id)
    profile = UserProfileResponse.model_validate(current_user)
    profile.email = _email_from_token(creds.credentials)
    profile.company_name = company.name if company else ""
    return profile


@router.post("/me/plan-requests", response_model=PlanRequestResponse, status_code=201)
async def create_plan_request(
    data: PlanRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a request to upgrade the company's plan. Only one pending request per company."""
    company = await db.get(Company, current_user.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")

    pending = (
        await db.execute(
            select(PlanRequest).where(
                PlanRequest.company_id == company.id,
                PlanRequest.status == "pending",
            )
        )
    ).scalars().first()
    if pending:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "REQUEST_ALREADY_PENDING",
                "message": "Заявка на смену тарифа уже отправлена. Администратор рассмотрит её в ближайшее время.",
            },
        )

    request = PlanRequest(
        company_id=company.id,
        user_id=current_user.id,
        current_plan=company.plan,
        requested_plan=data.requested_plan,
        message=data.message,
    )
    db.add(request)
    await db.flush()
    await db.refresh(request)
    logger.info("plan_request_created", company_id=str(company.id), requested_plan=data.requested_plan)
    return PlanRequestResponse(
        id=request.id,
        company_id=request.company_id,
        company_name=company.name,
        user_name=current_user.full_name,
        user_email=current_user.email,
        current_plan=request.current_plan,
        requested_plan=request.requested_plan,
        message=request.message,
        status=request.status,
        created_at=request.created_at,
    )


@router.get("/me/plan-requests", response_model=list[PlanRequestResponse])
async def list_my_plan_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List plan requests of the current user's company, newest first."""
    stmt = (
        select(PlanRequest)
        .where(PlanRequest.company_id == current_user.company_id)
        .order_by(PlanRequest.created_at.desc())
    )
    result = await db.execute(stmt)
    requests = result.scalars().all()
    company = await db.get(Company, current_user.company_id)
    return [
        PlanRequestResponse(
            id=r.id,
            company_id=r.company_id,
            company_name=company.name if company else None,
            user_name=current_user.full_name,
            user_email=current_user.email,
            current_plan=r.current_plan,
            requested_plan=r.requested_plan,
            message=r.message,
            status=r.status,
            created_at=r.created_at,
        )
        for r in requests
    ]


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_code(length: int = 8) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


async def _require_owner(user: User) -> None:
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Только владелец компании может выполнять это действие")


@router.get("/me/company/members", response_model=list[MemberResponse])
async def list_company_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List members of the current user's company."""
    stmt = (
        select(User)
        .where(User.company_id == current_user.company_id)
        .order_by(User.created_at.asc())
    )
    result = await db.execute(stmt)
    members = result.scalars().all()
    return [
        MemberResponse(
            id=m.id,
            full_name=m.full_name,
            email=m.email,
            role=m.role,
            job_title=m.job_title,
            is_active=m.is_active,
            created_at=m.created_at,
            last_login_at=m.last_login_at,
        )
        for m in members
    ]


@router.patch("/me/company/members/{member_id}/role", response_model=MemberResponse)
async def update_member_role(
    member_id: uuid.UUID,
    data: MemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the role of a company member. Owner only. Roles: member / limited."""
    await _require_owner(current_user)

    member = await db.get(User, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if member.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="Нельзя изменить роль владельца")

    member.role = data.role
    await db.flush()
    await db.refresh(member)
    logger.info("member_role_updated", member_id=str(member.id), role=data.role, by=str(current_user.id))
    return MemberResponse(
        id=member.id,
        full_name=member.full_name,
        email=member.email,
        role=member.role,
        job_title=member.job_title,
        is_active=member.is_active,
        created_at=member.created_at,
        last_login_at=member.last_login_at,
    )


@router.delete("/me/company/members/{member_id}", status_code=204)
async def remove_company_member(
    member_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a company member. Owner only. Owner cannot be removed."""
    await _require_owner(current_user)

    if member_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")

    member = await db.get(User, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if member.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="Нельзя удалить владельца")

    member.is_active = False
    await db.commit()
    logger.info("company_member_removed", member_id=str(member.id), by=str(current_user.id))


@router.post("/me/company/invites", response_model=InviteResponse, status_code=201)
async def create_company_invite(
    payload: InviteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an invite code so employees can join the company. Owner only."""
    await _require_owner(current_user)

    code = _generate_code()
    while (await db.execute(select(Invite).where(Invite.code == code))).scalars().first():
        code = _generate_code()

    expires_at = None
    if payload.expires_in_days > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)

    invite = Invite(
        code=code,
        created_by=current_user.id,
        company_id=current_user.company_id,
        max_uses=max(1, payload.max_uses),
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    logger.info("company_invite_created", invite_id=str(invite.id), code=code, by=str(current_user.id))
    return invite


@router.get("/me/company/invites", response_model=list[InviteResponse])
async def list_company_invites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List active invite codes of the current user's company. Owner only."""
    await _require_owner(current_user)

    stmt = (
        select(Invite)
        .where(Invite.company_id == current_user.company_id)
        .order_by(Invite.created_at.desc())
    )
    result = await db.execute(stmt)
    invites = result.scalars().all()
    return [
        InviteResponse(
            id=i.id,
            code=i.code,
            max_uses=i.max_uses,
            uses=i.uses,
            expires_at=i.expires_at,
            active=i.active,
            created_at=i.created_at,
        )
        for i in invites
    ]


@router.delete("/me/company/invites/{invite_id}", status_code=204)
async def disable_company_invite(
    invite_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate an invite code. Owner only."""
    await _require_owner(current_user)

    stmt = select(Invite).where(Invite.id == invite_id, Invite.company_id == current_user.company_id)
    result = await db.execute(stmt)
    invite = result.scalars().first()
    if not invite:
        raise HTTPException(status_code=404, detail="Приглашение не найдено")
    invite.active = False
    await db.commit()
    logger.info("company_invite_disabled", invite_id=str(invite_id), by=str(current_user.id))