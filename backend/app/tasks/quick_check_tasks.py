"""Durable, item-by-item product discovery for saved quick PDF checks."""

import asyncio
from datetime import datetime, timedelta, timezone
import uuid

from celery import shared_task
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
import structlog

from app.db.models.quick_check_report import QuickCheckReport
from app.db.session import async_task_session_factory
from app.services.market_search import search_products
from app.services.product_matching import evaluate_product_leads
from app.tasks.product_search_tasks import _build_search_query

logger = structlog.get_logger(__name__)
_STALE_ITEM_AFTER = timedelta(minutes=5)


async def _claim_item(report_id: uuid.UUID, run_id: uuid.UUID, index: int) -> tuple[str, str | None] | None:
    """Reserve one item, committing before any network request starts."""
    async with async_task_session_factory() as db:
        report = (await db.execute(
            select(QuickCheckReport).where(QuickCheckReport.id == report_id).with_for_update()
        )).scalars().first()
        if report is None or report.run_id != run_id or index >= len(report.items):
            return None
        item = report.items[index]
        if item.get("state") == "ready":
            return None
        if item.get("state") == "searching" and item.get("run_id") == str(run_id):
            try:
                started = datetime.fromisoformat(item.get("search_started_at", ""))
                if started.tzinfo and datetime.now(timezone.utc) - started < _STALE_ITEM_AFTER:
                    return None
            except (TypeError, ValueError):
                pass
        updated = list(report.items)
        updated[index] = {
            **item,
            "state": "searching",
            "run_id": str(run_id),
            "search_started_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
        }
        report.items = updated
        report.processing_state = "running"
        await db.commit()
        return item["product_name"], item.get("specs")


async def _finish_item(
    report_id: uuid.UUID, run_id: uuid.UUID, index: int, *,
    results: list[dict] | None = None, error: bool = False,
) -> None:
    async with async_task_session_factory() as db:
        report = (await db.execute(
            select(QuickCheckReport).where(QuickCheckReport.id == report_id).with_for_update()
        )).scalars().first()
        if report is None or report.run_id != run_id or index >= len(report.items):
            return
        item = report.items[index]
        if item.get("run_id") != str(run_id) or item.get("state") != "searching":
            return
        updated_item = {key: value for key, value in item.items() if key not in {"run_id", "search_started_at"}}
        updated_item.update({
            "state": "error" if error else "ready",
            "results": [] if error else (results or []),
            "error": "Не удалось проверить товар. Повторите поиск позже." if error else None,
            "checked_at": None if error else datetime.now(timezone.utc).isoformat(),
        })
        updated = list(report.items)
        updated[index] = updated_item
        report.items = updated
        await db.commit()


async def _finish_report(report_id: uuid.UUID, run_id: uuid.UUID) -> dict:
    async with async_task_session_factory() as db:
        report = (await db.execute(
            select(QuickCheckReport).where(QuickCheckReport.id == report_id).with_for_update()
        )).scalars().first()
        if report is None or report.run_id != run_id:
            return {"status": "stale"}
        unfinished = any(item.get("state") not in {"ready", "error"} for item in report.items)
        report.processing_state = "running" if unfinished else "completed"
        await db.commit()
        return {"status": report.processing_state, "checked_items": sum(item.get("state") == "ready" for item in report.items)}


async def _fail_report(report_id: uuid.UUID, run_id: uuid.UUID) -> None:
    async with async_task_session_factory() as db:
        report = (await db.execute(
            select(QuickCheckReport).where(QuickCheckReport.id == report_id).with_for_update()
        )).scalars().first()
        if report is None or report.run_id != run_id:
            return
        report.processing_state = "error"
        await db.commit()


async def run_quick_check_async(report_id_str: str, run_id_str: str) -> dict:
    report_id, run_id = uuid.UUID(report_id_str), uuid.UUID(run_id_str)
    async with async_task_session_factory() as db:
        report = (await db.execute(select(QuickCheckReport).where(QuickCheckReport.id == report_id))).scalars().first()
        if report is None or report.run_id != run_id:
            return {"status": "stale"}
        count = len(report.items)

    for index in range(count):
        claim = await _claim_item(report_id, run_id, index)
        if claim is None:
            continue
        name, specs = claim
        try:
            results = await search_products(_build_search_query(name, specs))
            checked = jsonable_encoder((await evaluate_product_leads(name, specs, results))[:16])
        except Exception as exc:
            logger.warning("quick_check_item_failed", report_id=str(report_id), index=index, error_type=type(exc).__name__)
            await _finish_item(report_id, run_id, index, error=True)
        else:
            await _finish_item(report_id, run_id, index, results=checked)

    return await _finish_report(report_id, run_id)


@shared_task(bind=True, max_retries=2, default_retry_delay=360, acks_late=True, reject_on_worker_lost=True)
def search_quick_report_task(self, report_id_str: str, run_id_str: str) -> dict:
    """Search sequentially so one PDF does not flood public product sites."""
    try:
        result = asyncio.run(run_quick_check_async(report_id_str, run_id_str))
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=360)
        logger.error("quick_check_task_failed", report_id=report_id_str, error_type=type(exc).__name__)
        asyncio.run(_fail_report(uuid.UUID(report_id_str), uuid.UUID(run_id_str)))
        raise
    if result.get("status") == "running" and self.request.retries < self.max_retries:
        raise self.retry(countdown=360)
    if result.get("status") == "running":
        asyncio.run(_fail_report(uuid.UUID(report_id_str), uuid.UUID(run_id_str)))
        return {"status": "error", "checked_items": result.get("checked_items", 0)}
    return result
