from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.product_search import ProductSearchItem
from app.schemas.product_search import ProductSearchItemResponse
from app.tasks.product_search_tasks import search_products_task

router = APIRouter()


async def _get_project_or_404(db: AsyncSession, project_id: uuid.UUID, user: User) -> Project:
    stmt = select(Project).where(Project.id == project_id, Project.company_id == user.company_id)
    proj = (await db.execute(stmt)).scalars().first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@router.post("/{project_id}/products/search", status_code=202)
async def start_product_search(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger background market search for products extracted from the tender spec."""
    await _get_project_or_404(db, project_id, current_user)
    search_products_task.delay(str(project_id))
    return {"status": "started", "message": "Поиск товаров запущен в фоне"}


@router.get("/{project_id}/products", response_model=List[ProductSearchItemResponse])
async def list_product_search_items(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List extracted products with their market search results."""
    await _get_project_or_404(db, project_id, current_user)
    stmt = (
        select(ProductSearchItem)
        .where(ProductSearchItem.project_id == project_id)
        .order_by(ProductSearchItem.created_at.desc())
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())
