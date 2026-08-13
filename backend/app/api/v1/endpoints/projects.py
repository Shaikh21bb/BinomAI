from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import uuid

from app.api.deps import get_db, get_current_user
from app.core.config import settings
from app.core.plans import get_plan
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.company import Company
from app.schemas.project import ProjectResponse, ProjectCreate, ProjectUpdate
from app.schemas.pagination import CursorPaginatedResponse
from app.services.project_service import ProjectService
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()

@router.get("/", response_model=CursorPaginatedResponse[ProjectResponse])
async def list_projects(
    page_size: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = None,
    search: Optional[str] = Query(None, description="Поиск по названию, заказчику или номеру"),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List projects for the user's company using cursor-based pagination.
    Supports text search and status filter.
    """
    return await ProjectService.get_projects_by_company(
        db, company_id=current_user.company_id, page_size=page_size, cursor=cursor,
        search=search, status=status,
    )

@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new project.
    """
    company = await db.get(Company, current_user.company_id)
    plan = get_plan(company.plan if company else None)

    if plan.max_projects is not None:
        stmt = select(func.count()).select_from(Project).where(Project.company_id == current_user.company_id)
        result = await db.execute(stmt)
        project_count = result.scalar() or 0
        if project_count >= plan.max_projects:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PROJECT_LIMIT_REACHED",
                    "message": f"Лимит проектов для тарифа «{plan.name}»: {project_count} из {plan.max_projects}. Обновите тариф.",
                    "usage": {"current": project_count, "limit": plan.max_projects},
                },
            )

    return await ProjectService.create_project(
        db, company_id=current_user.company_id, user_id=current_user.id, obj_in=project_in
    )

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get project details.
    """
    project = await ProjectService.get_project(db, project_id)
    if not project or project.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update project fields (name, status, deadline, notes, etc.).
    """
    project = await ProjectService.get_project(db, project_id)
    if not project or project.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Project not found")

    return await ProjectService.update_project(db, project=project, obj_in=project_in)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a project.
    """
    project = await ProjectService.get_project(db, project_id)
    if not project or project.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Project not found")
        
    await ProjectService.delete_project(db, project_id)
