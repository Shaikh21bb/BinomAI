import uuid
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime

from app.db.repositories.base import BaseRepository
from app.db.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate

class ProjectRepository(BaseRepository[Project, ProjectCreate, ProjectUpdate]):
    async def get_by_company(
        self, 
        db: AsyncSession, 
        *, 
        company_id: uuid.UUID, 
        page_size: int = 20, 
        cursor_created_at: Optional[datetime] = None,
        cursor_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Project]:
        """
        Cursor-based pagination (keyset pagination) implementation.
        Sorts by created_at DESC, id DESC. Supports optional text search and status filter.
        """
        stmt = select(Project).where(Project.company_id == company_id)

        if status:
            stmt = stmt.where(Project.status == status)

        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                (Project.name.ilike(pattern))
                | (Project.customer_name.ilike(pattern))
                | (Project.tender_number.ilike(pattern))
            )

        if cursor_created_at and cursor_id:
            # (created_at, id) < (cursor_created_at, cursor_id)
            stmt = stmt.where(
                (Project.created_at < cursor_created_at) |
                ((Project.created_at == cursor_created_at) & (Project.id < cursor_id))
            )
            
        stmt = stmt.order_by(desc(Project.created_at), desc(Project.id)).limit(page_size)
        result = await db.execute(stmt)
        return list(result.scalars().all())

project_repo = ProjectRepository(Project)
