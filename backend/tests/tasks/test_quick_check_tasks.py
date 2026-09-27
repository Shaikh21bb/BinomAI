"""Background quick checks persist progress one item at a time."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
import uuid

import pytest

from app.db.models.quick_check_report import QuickCheckReport
from app.tasks import quick_check_tasks
from app.tasks.celery_app import celery_app
from tests.conftest import scalar_first


@pytest.mark.asyncio
async def test_item_progress_is_saved_and_repeated_claim_is_ignored(monkeypatch):
    run_id = uuid.uuid4()
    report = QuickCheckReport(
        id=uuid.uuid4(), company_id=uuid.uuid4(), created_by=uuid.uuid4(),
        filename="spec.pdf", page_count=1, ocr_pages=0, total_items=1,
        truncated=False, processing_state="queued", run_id=run_id,
        items=[{"product_name": "Средство для посуды", "specs": "500 мл", "state": "pending", "results": []}],
    )
    db = AsyncMock()
    db.execute.return_value = scalar_first(report)

    @asynccontextmanager
    async def session():
        yield db

    monkeypatch.setattr(quick_check_tasks, "async_task_session_factory", session)

    assert await quick_check_tasks._claim_item(report.id, run_id, 0) == ("Средство для посуды", "500 мл")
    assert report.processing_state == "running"
    assert report.items[0]["state"] == "searching"
    assert await quick_check_tasks._claim_item(report.id, run_id, 0) is None
    await quick_check_tasks._finish_item(report.id, run_id, 0, results=[{"title": "Товар"}])
    assert report.items[0]["state"] == "ready"
    assert report.items[0]["results"] == [{"title": "Товар"}]
    assert report.items[0]["checked_at"]
    assert await quick_check_tasks._finish_report(report.id, run_id) == {"status": "completed", "checked_items": 1}
    assert db.commit.await_count == 3


def test_quick_check_task_is_registered_with_worker():
    assert "app.tasks.quick_check_tasks.search_quick_report_task" in celery_app.tasks
