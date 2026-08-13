import uuid
from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.db.repositories.project_repo import project_repo
from app.db.models.project import Project
from app.db.models.document import Document
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.schemas.pagination import CursorPaginationMeta, CursorPaginatedResponse
from app.services.document_service import DocumentService
import structlog

logger = structlog.get_logger(__name__)

class ProjectService:
    @staticmethod
    async def get_projects_by_company(
        db: AsyncSession, 
        company_id: uuid.UUID, 
        page_size: int = 20, 
        cursor: Optional[str] = None,
        search: Optional[str] = None,
        status: Optional[str] = None
    ) -> CursorPaginatedResponse[ProjectResponse]:
        """
        Retrieves projects for a company with cursor-based pagination.
        Cursor format: {created_at_iso}__{id_uuid}
        """
        cursor_created_at = None
        cursor_id = None
        
        if cursor:
            try:
                parts = cursor.split("__")
                if len(parts) == 2:
                    cursor_created_at = datetime.fromisoformat(parts[0])
                    cursor_id = uuid.UUID(parts[1])
            except Exception as e:
                logger.warning("invalid_cursor_format", cursor=cursor, error=str(e))
                # Fallback to no cursor if invalid

        # Fetch one extra to determine has_next
        fetch_limit = page_size + 1
        
        projects = await project_repo.get_by_company(
            db, 
            company_id=company_id, 
            page_size=fetch_limit, 
            cursor_created_at=cursor_created_at, 
            cursor_id=cursor_id,
            search=search,
            status=status,
        )

        has_next = len(projects) > page_size
        if has_next:
            projects = projects[:page_size]

        next_cursor = None
        if has_next and projects:
            last_item = projects[-1]
            next_cursor = f"{last_item.created_at.isoformat()}__{last_item.id}"

        pagination_meta = CursorPaginationMeta(
            page_size=page_size,
            has_next=has_next,
            next_cursor=next_cursor,
            total=None # Count is expensive, omit per specs unless explicitly needed
        )

        return CursorPaginatedResponse(data=projects, pagination=pagination_meta)

    @staticmethod
    async def create_project(db: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID, obj_in: ProjectCreate) -> Project:
        logger.info("creating_project", company_id=str(company_id), user_id=str(user_id))
        return await project_repo.create(db, obj_in=obj_in, company_id=company_id, created_by=user_id)
    
    @staticmethod
    async def get_project(db: AsyncSession, project_id: uuid.UUID) -> Optional[Project]:
        return await project_repo.get(db, id=project_id)

    @staticmethod
    async def update_project(db: AsyncSession, *, project: Project, obj_in: ProjectUpdate) -> Project:
        return await project_repo.update(db, db_obj=project, obj_in=obj_in)
        
    @staticmethod
    async def delete_project(db: AsyncSession, project_id: uuid.UUID) -> Optional[Project]:
        # Clean up files from Supabase storage before removing the row (DB cascades the rest).
        stmt = select(Document).where(Document.project_id == project_id)
        res = await db.execute(stmt)
        documents = res.scalars().all()
        for doc in documents:
            try:
                if doc.storage_path:
                    await DocumentService.delete_from_storage(doc.storage_path)
                if doc.extracted_text_path:
                    await DocumentService.delete_from_storage(
                        doc.extracted_text_path,
                        bucket=settings.STORAGE_BUCKET_EXTRACTED_TEXT,
                    )
            except Exception as e:
                logger.warning("project_storage_cleanup_failed", error=str(e), document_id=str(doc.id))
        return await project_repo.remove(db, id=project_id)
