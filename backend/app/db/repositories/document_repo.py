import uuid
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.db.repositories.base import BaseRepository
from app.db.models.document import Document
from pydantic import BaseModel

class DocumentCreate(BaseModel):
    # This is a specialized creation schema used internally by the service
    filename: str
    file_size_bytes: int
    mime_type: str
    storage_path: str
    project_id: uuid.UUID
    company_id: uuid.UUID
    uploaded_by: uuid.UUID
    processing_status: str = "uploading"
    version: int = 1
    is_current: bool = True

class DocumentUpdate(BaseModel):
    processing_status: str

class DocumentRepository(BaseRepository[Document, DocumentCreate, DocumentUpdate]):
    async def get_current_documents_for_project(
        self, db: AsyncSession, *, project_id: uuid.UUID
    ) -> List[Document]:
        stmt = select(Document).where(
            and_(
                Document.project_id == project_id,
                Document.is_current == True
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_for_project(
        self, db: AsyncSession, *, project_id: uuid.UUID
    ) -> List[Document]:
        stmt = (
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.version.desc(), Document.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def supersede_previous(
        self, db: AsyncSession, *, project_id: uuid.UUID
    ) -> int:
        """Mark all current documents of a project as superseded (is_current=False)."""
        stmt = select(Document).where(
            and_(
                Document.project_id == project_id,
                Document.is_current == True,
            )
        )
        result = await db.execute(stmt)
        previous = list(result.scalars().all())
        for doc in previous:
            doc.is_current = False
        if previous:
            await db.commit()
        return len(previous)

    async def get_max_version(
        self, db: AsyncSession, *, project_id: uuid.UUID
    ) -> int:
        stmt = (
            select(Document.version)
            .where(Document.project_id == project_id)
            .order_by(Document.version.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first() or 0

document_repo = DocumentRepository(Document)
