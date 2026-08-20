import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text
from app.db.models.project import Project
from app.schemas.analysis import TenderAnalysisOutput
# Note: Assuming AnalysisResult model is created in app.db.models.analysis
# Wait, let's create the AnalysisResult model dynamically if not exists, 
# or execute raw SQL since we didn't explicitly create SQLAlchemy models for everything yet.
# To be safe and compliant, we will use raw SQL or SQLAlchemy core for analysis_results if the model is missing.
# Let's try importing it, if it's not there, we will just use SQL.

import structlog
logger = structlog.get_logger(__name__)

class AnalysisService:
    @staticmethod
    async def create_pending_analysis(
        db: AsyncSession, 
        project_id: uuid.UUID, 
        document_id: uuid.UUID, 
        company_id: uuid.UUID
    ) -> uuid.UUID:
        """
        Creates a new pending analysis record and deactivates previous ones (via trigger).
        """
        analysis_id = uuid.uuid4()
        
        # Using raw SQL to avoid needing the declarative model right now
        stmt = text("""
            INSERT INTO analysis_results (id, project_id, document_id, company_id, status, is_current, prompt_version)
            VALUES (:id, :project_id, :document_id, :company_id, 'pending', true, 'v1')
            RETURNING id
        """)
        
        await db.execute(stmt, {
            "id": analysis_id,
            "project_id": project_id,
            "document_id": document_id,
            "company_id": company_id
        })
        
        # Deactivate previous current analyses of the same project
        # (no DB trigger exists on this table)
        await db.execute(
            text("UPDATE analysis_results SET is_current = false WHERE project_id = :pid AND id != :id"),
            {"pid": project_id, "id": analysis_id}
        )
        
        await db.commit()
        return analysis_id

    @staticmethod
    async def update_analysis_status(
        db: AsyncSession, 
        analysis_id: uuid.UUID, 
        status: str, 
        error_message: Optional[str] = None
    ):
        stmt = text("""
            UPDATE analysis_results 
            SET status = :status, error_message = :error_message, updated_at = now()
            WHERE id = :id
        """)
        await db.execute(stmt, {"status": status, "error_message": error_message, "id": analysis_id})
        await db.commit()

    @staticmethod
    async def save_analysis_results(
        db: AsyncSession,
        analysis_id: uuid.UUID,
        project_id: uuid.UUID,
        output: TenderAnalysisOutput,
        metadata: dict
    ):
        """
        Saves the parsed AI results into the JSONB columns.
        """
        import json
        
        stmt = text("""
            UPDATE analysis_results
            SET status = 'completed',
                executive_summary = :executive_summary,
                tender_type = :tender_type,
                complexity_level = :complexity_level,
                estimated_duration_days = :estimated_duration_days,
                technical_requirements = :technical_requirements,
                commercial_requirements = :commercial_requirements,
                legal_requirements = :legal_requirements,
                required_documents = :required_documents,
                key_deadlines = :key_deadlines,
                risks = :risks,
                missing_info_from_tender = :missing_info,
                missing_company_data = :missing_company,
                llm_model = :llm_model,
                input_tokens = :input_tokens,
                output_tokens = :output_tokens,
                processing_time_ms = :processing_time_ms,
                updated_at = now()
            WHERE id = :id
        """)
        
        await db.execute(stmt, {
            "executive_summary": output.executive_summary,
            "tender_type": output.tender_type,
            "complexity_level": output.complexity_level,
            "estimated_duration_days": output.estimated_duration_days,
            
            "technical_requirements": json.dumps([r.model_dump() for r in output.technical_requirements]),
            "commercial_requirements": json.dumps([r.model_dump() for r in output.commercial_requirements]),
            "legal_requirements": json.dumps([r.model_dump() for r in output.legal_requirements]),
            
            "required_documents": json.dumps([d.model_dump() for d in output.required_documents]),
            "key_deadlines": json.dumps([d.model_dump() for d in output.key_deadlines]),
            "risks": json.dumps([r.model_dump() for r in output.risks]),
            
            "missing_info": json.dumps([m.model_dump() for m in output.missing_info_from_tender]),
            "missing_company": json.dumps(output.missing_company_data),
            
            "llm_model": metadata.get("llm_model"),
            "input_tokens": metadata.get("input_tokens"),
            "output_tokens": metadata.get("output_tokens"),
            "processing_time_ms": metadata.get("processing_time_ms"),
            
            "id": analysis_id
        })
        
        # Move project forward to the clarification stage (pipeline owner: analysis_tasks).
        # Only advance from in-progress states; never downgrade review/ready projects.
        await db.execute(
            text("UPDATE projects SET status = 'clarifying' WHERE id = :pid AND status IN ('draft', 'analyzing')"),
            {"pid": project_id}
        )
        
        await db.commit()
