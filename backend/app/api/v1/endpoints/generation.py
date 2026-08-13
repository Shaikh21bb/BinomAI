import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.company import Company
from app.schemas.generated_document import (
    GenerateRequest,
    GenerateResponse,
    GeneratedDocumentResponse,
    ExportRequest,
)
from app.services.generation_service import GenerationService
from app.services.project_service import ProjectService
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _get_project_or_404(db: AsyncSession, project_id: uuid.UUID, current_user: User) -> Project:
    project = await ProjectService.get_project(db, project_id)
    if not project or project.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/generate", response_model=GenerateResponse)
async def generate_document(
    project_id: uuid.UUID,
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a tender document using AI (analysis + chat context + company profile)."""
    project = await _get_project_or_404(db, project_id, current_user)

    stmt = select(Company).where(Company.id == current_user.company_id)
    res = await db.execute(stmt)
    company = res.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company profile not found")

    doc = await GenerationService.generate(db, project, company, body)
    return doc


@router.get("/{project_id}/documents/generated", response_model=list[GeneratedDocumentResponse])
async def list_generated_documents(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List generated documents for a project."""
    await _get_project_or_404(db, project_id, current_user)
    return await GenerationService.list_generated(db, project_id)


@router.get("/{project_id}/documents/generated/{doc_type}/content", response_model=GenerateResponse)
async def get_generated_content(
    project_id: uuid.UUID,
    doc_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the latest generated document content (markdown + html) for preview."""
    await _get_project_or_404(db, project_id, current_user)
    doc = await GenerationService.get_latest(db, project_id, doc_type)
    if not doc or doc.generation_status != "ready" or not doc.content_md:
        raise HTTPException(status_code=404, detail="Generated document not found or not ready")
    return doc


@router.post("/{project_id}/documents/generated/{doc_type}/export")
async def export_document(
    project_id: uuid.UUID,
    doc_type: str,
    body: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export the latest generated document as DOCX or PDF via Gotenberg."""
    await _get_project_or_404(db, project_id, current_user)
    content, filename, mime = await GenerationService.export(db, project_id, doc_type, body.format)
    from urllib.parse import quote
    return Response(
        content=content,
        media_type=mime,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )