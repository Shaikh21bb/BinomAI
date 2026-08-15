import asyncio
import uuid
import structlog
from celery import shared_task

from app.db.session import async_task_session_factory as async_session_factory
from app.services.generation_service import GenerationService

logger = structlog.get_logger(__name__)


@shared_task(
    bind=True,
    acks_late=True,
    soft_time_limit=240,
    time_limit=300,
    max_retries=1,
    default_retry_delay=30,
)
def generate_document_task(self, doc_id_str: str):
    """Run LLM generation for a pending GeneratedDocument row in the background."""
    doc_id = uuid.UUID(doc_id_str)

    async def _run():
        async with async_session_factory() as db:
            doc = await GenerationService.run_generation(db, doc_id)
            return doc.generation_status if doc else None

    try:
        status = asyncio.run(_run())
        logger.info("document_generation_task_finished", doc_id=doc_id_str, status=status)
        return status
    except Exception as e:  # noqa: BLE001
        logger.error("document_generation_task_crashed", doc_id=doc_id_str, error=str(e))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        raise
