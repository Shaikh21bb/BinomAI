import structlog
from celery import shared_task
from datetime import datetime, timedelta
from sqlalchemy import select

from app.db.session import async_task_session_factory as async_session_factory
from app.db.models.tender_lot import TenderLot

logger = structlog.get_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def refresh_all_tenders(self):
    """Refresh all watched lots whose check time is due. Runs on a schedule."""
    import asyncio

    async def _run():
        now = datetime.utcnow()
        async with async_session_factory() as db:
            stmt = (
                select(TenderLot)
                .where(
                    (TenderLot.next_check_at.is_(None)) | (TenderLot.next_check_at <= now)
                )
                .order_by(TenderLot.next_check_at.asc())
                .limit(50)
            )
            lots = (await db.execute(stmt)).scalars().all()
            if not lots:
                return 0

            from app.api.v1.endpoints.tender_monitor import _refresh_lot

            for lot in lots:
                try:
                    await _refresh_lot(db, lot, save=True)
                except Exception as e:  # noqa: BLE001
                    logger.error("tender_lot_task_failed", lot_id=str(lot.id), error=str(e))
            return len(lots)

    count = asyncio.run(_run())
    logger.info("tenders_refreshed", count=count)
    return count
