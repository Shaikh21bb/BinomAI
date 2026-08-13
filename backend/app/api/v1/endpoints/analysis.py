import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.document import Document
from app.tasks.analysis_tasks import run_analysis_task

router = APIRouter()

@router.get("/{project_id}")
async def get_analysis_results(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the current active analysis results for a project.
    """
    # Verify access
    stmt_proj = select(Project).where(Project.id == project_id, Project.company_id == current_user.company_id)
    res_proj = await db.execute(stmt_proj)
    if not res_proj.scalars().first():
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch current analysis
    stmt = text("""
        SELECT * FROM analysis_results 
        WHERE project_id = :project_id AND is_current = true
    """)
    res = await db.execute(stmt, {"project_id": project_id})
    analysis = res.mappings().first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="No active analysis found for this project")
        
    return dict(analysis)

@router.post("/{project_id}/retry")
async def retry_analysis(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger a re-analysis. Uses the latest active document.
    """
    # Verify access
    stmt_proj = select(Project).where(Project.id == project_id, Project.company_id == current_user.company_id)
    res_proj = await db.execute(stmt_proj)
    if not res_proj.scalars().first():
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Get the latest processed document
    stmt_doc = (
        select(Document)
        .where(
            Document.project_id == project_id,
            Document.processing_status == "ready",
        )
        .order_by(Document.created_at.desc())
        .limit(1)
    )
    res_doc = await db.execute(stmt_doc)
    doc = res_doc.scalars().first()
    
    if not doc:
        raise HTTPException(status_code=400, detail="No ready document found to analyze")
        
    if doc.processing_status != "ready":
        raise HTTPException(status_code=400, detail="Document processing is not yet ready")

    # Trigger Celery task
    run_analysis_task.delay(str(project_id), str(doc.id), str(current_user.company_id))
    
    return {"status": "success", "message": "Analysis retry initiated"}
