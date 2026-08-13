from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
import uuid

from app.api.deps import get_db, get_current_user
from app.core.plans import get_plan
from app.db.models.user import User
from app.db.models.company import Company
from app.db.models.document import Document
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService
from app.services.project_service import ProjectService
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()

@router.post("/{project_id}/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a document (e.g. Technical Specification) to a project.
    """
    # Verify project exists and belongs to company
    project = await ProjectService.get_project(db, project_id)
    if not project or project.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Project not found")

    company = await db.get(Company, current_user.company_id)
    plan = get_plan(company.plan if company else None)
    if plan.max_documents is not None:
        count = (
            await db.execute(
                select(func.count()).select_from(Document).where(Document.company_id == current_user.company_id)
            )
        ).scalar() or 0
        if count >= plan.max_documents:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "DOCUMENT_LIMIT_REACHED",
                    "message": f"Лимит документов для тарифа «{plan.name}»: {count} из {plan.max_documents}. Обновите тариф.",
                    "usage": {"current": count, "limit": plan.max_documents},
                },
            )
        
    return await DocumentService.create_document(
        db=db,
        project_id=project_id,
        company_id=current_user.company_id,
        user_id=current_user.id,
        file=file
    )

@router.get("/{project_id}/documents/current", response_model=List[DocumentResponse])
async def get_current_documents(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all active documents for a project.
    """
    project = await ProjectService.get_project(db, project_id)
    if not project or project.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return await DocumentService.get_current_documents(db, project_id)

@router.get("/{project_id}/documents/history", response_model=List[DocumentResponse])
async def get_document_history(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all document versions (history) for a project, newest first.
    """
    project = await ProjectService.get_project(db, project_id)
    if not project or project.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Project not found")

    return await DocumentService.get_document_history(db, project_id)

@router.get("/{project_id}/documents/{document_id}/status")
async def get_document_status(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the processing status of a specific document.
    """
    project = await ProjectService.get_project(db, project_id)
    if not project or project.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Project not found")
        
    from sqlalchemy import select
    from app.db.models.document import Document
    
    stmt = select(Document).where(Document.id == document_id, Document.project_id == project_id)
    result = await db.execute(stmt)
    doc = result.scalars().first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return {
        "id": doc.id,
        "filename": doc.filename,
        "processing_status": doc.processing_status,
        "error_message": doc.error_message
    }

@router.get("/{project_id}/documents/{document_id}/download")
async def download_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a short-lived signed download URL for an uploaded document.
    """
    project = await ProjectService.get_project(db, project_id)
    if not project or project.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Project not found")

    stmt = select(Document).where(Document.id == document_id, Document.project_id == project_id)
    result = await db.execute(stmt)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    url = await DocumentService.get_signed_download_url(doc.storage_path)
    return {"url": url, "filename": doc.filename}


@router.delete("/{project_id}/documents/{document_id}", status_code=204)
async def delete_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a document: removes the raw file + extracted text from storage
    and deletes the DB record.
    """
    project = await ProjectService.get_project(db, project_id)
    if not project or project.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Project not found")

    from sqlalchemy import select, delete
    from app.db.models.document import Document

    stmt = select(Document).where(Document.id == document_id, Document.project_id == project_id)
    result = await db.execute(stmt)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.processing_status == "processing":
        raise HTTPException(status_code=409, detail="Document is being processed, cannot delete right now")

    await DocumentService.delete_from_storage(doc.storage_path)
    if doc.extracted_text_path:
        await DocumentService.delete_from_storage(doc.extracted_text_path, bucket="extracted-texts")

    await db.execute(delete(Document).where(Document.id == document_id))
    await db.commit()

    # If we removed the current document, promote the latest ready version back
    if doc.is_current:
        from app.db.models.document import Document as DocModel
        promote_stmt = (
            select(DocModel)
            .where(
                DocModel.project_id == project_id,
                DocModel.is_current == False,
                DocModel.processing_status == "ready",
            )
            .order_by(DocModel.version.desc())
            .limit(1)
        )
        promote = (await db.execute(promote_stmt)).scalars().first()
        if promote:
            promote.is_current = True
            await db.commit()

    return None
