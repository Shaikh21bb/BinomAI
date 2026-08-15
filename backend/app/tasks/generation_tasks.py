import asyncio
import uuid
import structlog
from datetime import datetime, timedelta, timezone
from celery import shared_task
from sqlalchemy import select

from app.db.session import async_task_session_factory as async_session_factory
from app.db.models.generated_document import GeneratedDocument
from app.services.generation_service import GenerationService

logger = structlog.get_logger(__name__)


@shared_task(bind=True)
def sweep_stale_generations(self):
    """Mark docs stuck in 'generating' for >10 min as failed (worker death, OOM, etc.)."""

    async def _run():
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        async with async_session_factory() as db:
            stmt = (
                select(GeneratedDocument)
                .where(
                    GeneratedDocument.generation_status == "generating",
                    GeneratedDocument.updated_at < cutoff,
                )
                .limit(50)
            )
            docs = (await db.execute(stmt)).scalars().all()
            for doc in docs:
                doc.generation_status = "failed"
                doc.error_message = "Генерация прервана по таймауту — запустите повторно"
            await db.commit()
            return len(docs)

    try:
        count = asyncio.run(_run())
        logger.info("stale_generations_swept", count=count)
        return count
    except Exception as e:  # noqa: BLE001
        logger.error("stale_generations_sweep_failed", error=str(e))
        return 0


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
