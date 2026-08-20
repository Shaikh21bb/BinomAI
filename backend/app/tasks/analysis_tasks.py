import asyncio
import uuid
import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import async_task_session_factory as async_session_factory
from app.db.models.document import Document
from app.db.models.company import Company
from app.db.models.project import Project
from app.ai.llm_client import AIQuotaExhaustedError
from app.ai.analysis_agent import AnalysisAgent
from app.core.supabase import supabase_admin
from app.services.analysis_service import AnalysisService
from app.services.notifications import notify_company

logger = structlog.get_logger(__name__)

async def run_analysis_async(task, project_id_str: str, document_id_str: str, company_id_str: str) -> dict:
    project_id = uuid.UUID(project_id_str)
    document_id = uuid.UUID(document_id_str)
    company_id = uuid.UUID(company_id_str)
    
    async with async_session_factory() as db:
        # 1. Create Pending Analysis Record
        analysis_id = await AnalysisService.create_pending_analysis(db, project_id, document_id, company_id)
        
        try:
            await AnalysisService.update_analysis_status(db, analysis_id, "processing")
            task.update_state(state="PROGRESS", meta={"step": "AI Analysis started", "analysis_id": str(analysis_id)})
            
            # Fetch company context (optional, but helpful for AI)
            stmt = select(Company).where(Company.id == company_id)
            res = await db.execute(stmt)
            company = res.scalars().first()
            company_context = f"{company.name}. {company.description or ''} {company.specialization or ''}" if company else ""
            
            # 2. Run the AI Orchestrator
            task.update_state(state="PROGRESS", meta={"step": "Waiting for LLM response", "analysis_id": str(analysis_id)})

            try:
                output, metadata = await AnalysisAgent.run_analysis(
                    document_id=str(document_id),
                    project_id=str(project_id),
                    company_id=str(company_id),
                    company_context=company_context
                )
            except Exception as ai_e:
                # Fallback: deterministic heuristic analysis so the pipeline doesn't stall
                # when the LLM is unavailable (daily quota, network issues).
                logger.warning("analysis_llm_failed_falling_back_to_heuristic",
                               analysis_id=str(analysis_id), error=str(ai_e))
                text_path = f"{company_id}/{project_id}/{document_id}.txt"
                async with supabase_admin.get_client() as client:
                    resp = await client.get(f"/storage/v1/object/extracted-texts/{text_path}")
                    if resp.status_code != 200:
                        raise ai_e
                    text_content = resp.text
                output, metadata = AnalysisAgent.heuristic_analysis(text_content)

            # 3. Save Results
            task.update_state(state="PROGRESS", meta={"step": "Saving results", "analysis_id": str(analysis_id)})
            await AnalysisService.save_analysis_results(db, analysis_id, project_id, output, metadata)

            # 4. Move project forward: analysis done -> clarification dialogue stage
            proj_stmt = select(Project).where(Project.id == project_id)
            proj_res = await db.execute(proj_stmt)
            proj = proj_res.scalars().first()
            if proj and proj.status in ("draft", "analyzing"):
                proj.status = "clarifying"
                await db.commit()

            # 5. Notify the company that the analysis is ready
            await notify_company(
                db,
                company_id,
                "analysis_ready",
                f"AI-анализ ТЗ завершён",
                f"Анализ документа «{getattr(proj, 'name', '') or 'без названия'}» готов — можно переходить к уточнениям и генерации.",
                f"/projects/{project_id}/analysis",
            )
            await db.commit()

            return {"status": "success", "analysis_id": str(analysis_id)}
            
        except Exception as e:
            logger.error("analysis_failed", analysis_id=str(analysis_id), error=str(e))
            await AnalysisService.update_analysis_status(db, analysis_id, "failed", str(e))
            raise e # Let celery handle retries

@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def run_analysis_task(self, project_id_str: str, document_id_str: str, company_id_str: str):
    """
    Celery task wrapper for AI Analysis.
    """
    logger.info("ai_analysis_task_started", task_id=self.request.id, project_id=project_id_str)
    try:
        # Validate arguments early: malformed payloads (e.g. leftover test mocks) must
        # NOT be retried forever — fail fast instead of poisoning the queue.
        uuid.UUID(project_id_str)
        uuid.UUID(document_id_str)
        uuid.UUID(company_id_str)
    except (ValueError, TypeError, AttributeError) as exc:
        logger.error("ai_analysis_invalid_args", task_id=self.request.id, error=str(exc))
        raise exc
    try:
        result = asyncio.run(run_analysis_async(self, project_id_str, document_id_str, company_id_str))
        return result
    except AIQuotaExhaustedError as exc:
        # Daily quota exhaustion won't recover in seconds — do not waste retries
        logger.error("ai_analysis_quota_exhausted", error=str(exc))
        raise exc
    except Exception as exc:
        logger.warning("ai_analysis_retrying", exc=str(exc))
        raise self.retry(exc=exc)
