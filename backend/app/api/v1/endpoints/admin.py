import uuid
import secrets
import string
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, RoleChecker
from app.core.config import settings
from app.core.plans import get_plan, PLANS
from app.db.models.user import User
from app.db.models.invite import Invite
from app.db.models.company import Company
from app.db.models.project import Project
from app.core.supabase import supabase_admin
from app.schemas.admin import (
    InviteCreate, InviteResponse, UserAdminResponse, RoleUpdate, AdminAccountCreate,
    CompanyAdminResponse, PlanUpdate,
)
from app.schemas.plan import PlanRequestResponse, PlanRequestStatusUpdate
from app.db.models.plan_request import PlanRequest
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

OWNER_ONLY = RoleChecker(["owner"])

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_code(length: int = 8) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


@router.post("/invites", response_model=InviteResponse, status_code=201)
async def create_invite(
    payload: InviteCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(OWNER_ONLY),
):
    """Create a new invite code bound to the owner's company."""
    code = _generate_code()
    while (await db.execute(select(Invite).where(Invite.code == code))).scalars().first():
        code = _generate_code()

    expires_at = None
    if payload.expires_in_days > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)

    invite = Invite(
        code=code,
        created_by=admin.id,
        company_id=admin.company_id,
        max_uses=max(1, payload.max_uses),
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    logger.info("invite_created", invite_id=str(invite.id), code=code)
    return invite


@router.post("/accounts", response_model=UserAdminResponse, status_code=201)
async def create_account(
    payload: AdminAccountCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(OWNER_ONLY),
):
    """Create a user account directly by email and password. The user can log in immediately."""
    email = payload.email.lower()

    existing = (await db.execute(select(User).where(User.email == email))).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="Email уже зарегистрирован")

    company = await db.get(Company, admin.company_id)
    plan = get_plan(company.plan if company else None)
    if plan.max_users is not None:
        user_count = (
            await db.execute(
                select(func.count()).select_from(User).where(
                    User.company_id == admin.company_id,
                    User.is_active.is_(True),
                )
            )
        ).scalar() or 0
        if user_count >= plan.max_users:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "USER_LIMIT_REACHED",
                    "message": f"Лимит пользователей для тарифа «{plan.name}»: {user_count} из {plan.max_users}. Обновите тариф.",
                    "usage": {"current": user_count, "limit": plan.max_users},
                },
            )

    url = f"{settings.SUPABASE_URL}/auth/v1/admin/users"
    async with supabase_admin.get_client() as client:
        response = await client.post(
            url,
            json={"email": email, "password": payload.password, "email_confirm": True},
        )
    if response.status_code != 200:
        error_msg = response.json().get("msg", "Ошибка создания аккаунта")
        if "already exists" in error_msg.lower() or response.status_code == 422:
            raise HTTPException(status_code=409, detail="Email уже зарегистрирован")
        raise HTTPException(status_code=400, detail=error_msg)

    user_id = uuid.UUID(response.json()["id"])

    company_id = admin.company_id
    if payload.company_name:
        company = Company(name=payload.company_name, plan="trial")
        db.add(company)
        await db.flush()
        company_id = company.id

    user = User(
        id=user_id,
        company_id=company_id,
        full_name=payload.full_name,
        email=email,
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)

    company = (await db.execute(select(Company).where(Company.id == user.company_id))).scalars().first()
    pcount = (await db.execute(select(func.count()).select_from(Project).where(Project.created_by == user.id))).scalar() or 0
    logger.info("admin_account_created", user_id=str(user.id), email=email, role=payload.role)
    return UserAdminResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        company_id=user.company_id,
        company_name=company.name if company else None,
        project_count=pcount,
        created_at=user.created_at,
    )


@router.get("/invites", response_model=list[InviteResponse])
async def list_invites(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(OWNER_ONLY),
):
    stmt = select(Invite).where(Invite.created_by == admin.id).order_by(Invite.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.delete("/invites/{invite_id}", status_code=204)
async def disable_invite(
    invite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(OWNER_ONLY),
):
    stmt = select(Invite).where(Invite.id == invite_id, Invite.created_by == admin.id)
    result = await db.execute(stmt)
    invite = result.scalars().first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite.active = False
    await db.commit()
    logger.info("invite_disabled", invite_id=str(invite_id))


@router.get("/users", response_model=list[UserAdminResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(OWNER_ONLY),
):
    stmt = (
        select(User, Company.name, func.count(Project.id))
        .outerjoin(Company, Company.id == User.company_id)
        .outerjoin(Project, Project.created_by == User.id)
        .group_by(User.id, Company.name)
        .order_by(User.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        UserAdminResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            company_id=u.company_id,
            company_name=cname,
            project_count=pcount,
            created_at=u.created_at,
        )
        for u, cname, pcount in rows
    ]


@router.patch("/users/{user_id}/role", response_model=UserAdminResponse)
async def update_user_role(
    user_id: uuid.UUID,
    payload: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(OWNER_ONLY),
):
    """Change a user's role between 'member' and 'limited'. Owner role is protected."""
    if payload.role not in ("member", "limited"):
        raise HTTPException(status_code=400, detail="Допустимые роли: member, limited")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя изменить роль владельца")

    user.role = payload.role
    await db.commit()
    await db.refresh(user)

    company = (await db.execute(select(Company).where(Company.id == user.company_id))).scalars().first()
    pcount = (await db.execute(select(func.count()).select_from(Project).where(Project.created_by == user.id))).scalar() or 0
    return UserAdminResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        company_id=user.company_id,
        company_name=company.name if company else None,
        project_count=pcount,
        created_at=user.created_at,
    )


@router.get("/companies", response_model=list[CompanyAdminResponse])
async def list_companies(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(OWNER_ONLY),
):
    """List all companies with plan info and usage counts for the admin panel."""
    stmt = (
        select(
            Company.id, Company.name, Company.plan, Company.plan_expires_at, Company.created_at,
            func.count(func.distinct(User.id)).label("user_count"),
            func.count(func.distinct(Project.id)).label("project_count"),
        )
        .outerjoin(User, User.company_id == Company.id)
        .outerjoin(Project, Project.company_id == Company.id)
        .group_by(Company.id)
        .order_by(Company.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        CompanyAdminResponse(
            id=row.id,
            name=row.name,
            plan=row.plan,
            plan_expires_at=row.plan_expires_at,
            user_count=row.user_count,
            project_count=row.project_count,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.patch("/companies/{company_id}/plan", response_model=CompanyAdminResponse)
async def update_company_plan(
    company_id: uuid.UUID,
    payload: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(OWNER_ONLY),
):
    """Change a company's subscription plan."""
    if payload.plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Неизвестный тариф: {payload.plan}")

    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")

    company.plan = payload.plan
    company.plan_expires_at = payload.plan_expires_at
    await db.commit()
    await db.refresh(company)

    user_count = (
        await db.execute(select(func.count()).select_from(User).where(User.company_id == company.id))
    ).scalar() or 0
    project_count = (
        await db.execute(select(func.count()).select_from(Project).where(Project.company_id == company.id))
    ).scalar() or 0
    logger.info("company_plan_updated", company_id=str(company.id), plan=payload.plan)
    return CompanyAdminResponse(
        id=company.id,
        name=company.name,
        plan=company.plan,
        plan_expires_at=company.plan_expires_at,
        user_count=user_count,
        project_count=project_count,
        created_at=company.created_at,
    )


@router.get("/plan-requests", response_model=list[PlanRequestResponse])
async def list_plan_requests(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(OWNER_ONLY),
):
    """List all plan upgrade requests, pending first."""
    stmt = (
        select(PlanRequest, Company.name, User.full_name, User.email)
        .join(Company, Company.id == PlanRequest.company_id)
        .join(User, User.id == PlanRequest.user_id)
        .order_by(
            (PlanRequest.status != "pending").asc(),
            PlanRequest.created_at.desc(),
        )
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        PlanRequestResponse(
            id=r.id,
            company_id=r.company_id,
            company_name=cname,
            user_name=uname,
            user_email=uemail,
            current_plan=r.current_plan,
            requested_plan=r.requested_plan,
            message=r.message,
            status=r.status,
            created_at=r.created_at,
        )
        for r, cname, uname, uemail in rows
    ]


@router.patch("/plan-requests/{request_id}/status", response_model=PlanRequestResponse)
async def update_plan_request_status(
    request_id: uuid.UUID,
    payload: PlanRequestStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(OWNER_ONLY),
):
    """Mark a plan request as done/declined. A 'done' request also upgrades the company plan."""
    stmt = select(PlanRequest).where(PlanRequest.id == request_id)
    result = await db.execute(stmt)
    req = result.scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    req.status = payload.status
    if payload.status == "done":
        company = await db.get(Company, req.company_id)
        if company:
            company.plan = req.requested_plan
    await db.commit()
    await db.refresh(req)

    company = await db.get(Company, req.company_id)
    user = await db.get(User, req.user_id)
    return PlanRequestResponse(
        id=req.id,
        company_id=req.company_id,
        company_name=company.name if company else None,
        user_name=user.full_name if user else None,
        user_email=user.email if user else None,
        current_plan=req.current_plan,
        requested_plan=req.requested_plan,
        message=req.message,
        status=req.status,
        created_at=req.created_at,
    )