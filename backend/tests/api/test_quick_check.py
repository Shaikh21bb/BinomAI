"""The quick PDF flow must work without creating a project or tender."""

import hashlib
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db, get_redis
from app.api.v1.endpoints import quick_check
from app.db.models.quick_check_report import QuickCheckReport
from app.db.models.user import User
from app.main import app
from tests.conftest import scalar_first


@pytest.fixture
def authenticated_user():
    cache = AsyncMock()
    cache.eval.return_value = [1, 60]
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.return_value = scalar_first(None)
    user = User(id=uuid.uuid4(), company_id=uuid.uuid4(), role="limited")

    async def current_user():
        return user

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_redis] = lambda: cache
    app.dependency_overrides[get_db] = lambda: db
    yield user, db
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_quick_parse_extracts_items_without_tender(authenticated_user, monkeypatch):
    monkeypatch.setattr(quick_check.DocumentParser, "get_page_count", lambda *_: 2)
    monkeypatch.setattr(quick_check, "extract_pdf_text_with_ocr", lambda *_: ("Товар и количество", 1))
    monkeypatch.setattr(quick_check, "extract_products_from_text", lambda *_: [
        {"product_name": "Средство для посуды 500 мл", "specs": "Жидкое", "quantity": 12, "unit": "шт"}
    ])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/quick-check/parse",
            files={"file": ("techspec.pdf", b"%PDF-test", "application/pdf")},
        )
    assert response.status_code == 200
    assert response.json()["items"][0]["quantity"] == 12
    assert response.json()["total_items"] == 1
    assert response.json()["ocr_pages"] == 1
    assert response.json()["processing_state"] == "queued"
    saved = authenticated_user[1].add.call_args.args[0]
    assert saved.items[0]["state"] == "pending"
    assert saved.items[0]["results"] == []
    assert saved.pdf_sha256 == hashlib.sha256(b"%PDF-test").hexdigest()
    assert not hasattr(saved, "pdf_bytes")
    authenticated_user[1].commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reupload_same_pdf_opens_saved_report_without_ocr_or_search(authenticated_user, monkeypatch):
    user, db = authenticated_user
    contents = b"%PDF-same-document"
    existing = QuickCheckReport(
        id=uuid.uuid4(), company_id=user.company_id, created_by=user.id,
        filename="original.pdf", page_count=2, ocr_pages=0, total_items=1,
        truncated=False, processing_state="completed", pdf_sha256=hashlib.sha256(contents).hexdigest(),
        items=[{"product_name": "Средство для посуды", "state": "ready", "results": [{"title": "Найдено"}]}],
    )
    db.execute.return_value = scalar_first(existing)
    parser = MagicMock(side_effect=AssertionError("Duplicate PDF must not be parsed again"))
    published = MagicMock()
    monkeypatch.setattr(quick_check.DocumentParser, "get_page_count", parser)
    monkeypatch.setattr(quick_check.search_quick_report_task, "delay", published)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/quick-check/parse",
            files={"file": ("renamed.pdf", contents, "application/pdf")},
        )
    assert response.status_code == 200
    assert response.json()["id"] == str(existing.id)
    assert response.json()["reused"] is True
    assert response.json()["items"][0]["results"] == [{"title": "Найдено"}]
    parser.assert_not_called()
    published.assert_not_called()
    db.add.assert_not_called()
    params = db.execute.call_args.args[0].compile().params.values()
    assert user.company_id in params
    assert user.id in params
    assert existing.pdf_sha256 in params


@pytest.mark.asyncio
async def test_quick_parse_keeps_report_when_queue_is_unavailable(authenticated_user, monkeypatch):
    monkeypatch.setattr(quick_check.DocumentParser, "get_page_count", lambda *_: 1)
    monkeypatch.setattr(quick_check, "extract_pdf_text_with_ocr", lambda *_: ("Товар", 0))
    monkeypatch.setattr(quick_check, "extract_products_from_text", lambda *_: [
        {"product_name": "Товар 500 мл", "quantity": 2, "unit": "шт"}
    ])
    monkeypatch.setattr(quick_check.search_quick_report_task, "delay", lambda *_: (_ for _ in ()).throw(ConnectionError()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/quick-check/parse",
            files={"file": ("spec.pdf", b"%PDF-test", "application/pdf")},
        )
    assert response.status_code == 200
    assert response.json()["processing_state"] == "error"
    assert response.json()["items"][0]["state"] == "pending"
    assert authenticated_user[1].commit.await_count == 2


@pytest.mark.asyncio
async def test_quick_parse_reports_ocr_limit(authenticated_user, monkeypatch):
    monkeypatch.setattr(quick_check.DocumentParser, "get_page_count", lambda *_: 13)

    def over_limit(_):
        raise quick_check.PdfOcrLimitError("too many scanned pages")

    monkeypatch.setattr(quick_check, "extract_pdf_text_with_ocr", over_limit)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/quick-check/parse",
            files={"file": ("scan.pdf", b"%PDF-test", "application/pdf")},
        )
    assert response.status_code == 413
    assert "12" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_quick_parse_rejects_non_pdf(authenticated_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/quick-check/parse",
            files={"file": ("fake.pdf", b"not a PDF", "application/pdf")},
        )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_quick_search_returns_checked_cards(authenticated_user, monkeypatch):
    seen = []

    async def search(query):
        seen.append(query)
        return [{"url": "https://shop.example.kz/p/gel-500", "is_product_page": True}]

    async def evaluate(name, specs, rows):
        seen.append((name, specs))
        return [{**rows[0], "match_status": "partial", "checks": []}]

    monkeypatch.setattr(quick_check, "search_products", search)
    monkeypatch.setattr(quick_check, "evaluate_product_leads", evaluate)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/quick-check/search",
            json={"product_name": "Средство для посуды 500 мл", "specs": "Жидкое"},
        )
    assert response.status_code == 200
    assert response.json()["results"][0]["match_status"] == "partial"
    assert seen[1] == ("Средство для посуды 500 мл", "Жидкое")


@pytest.mark.asyncio
async def test_saved_search_updates_only_owned_report(authenticated_user, monkeypatch):
    user, db = authenticated_user
    report = QuickCheckReport(
        id=uuid.uuid4(), company_id=user.company_id, created_by=user.id,
        filename="techspec.pdf", page_count=1, ocr_pages=0, total_items=1,
        truncated=False,
        items=[{"product_name": "Средство для посуды 500 мл", "specs": "Жидкое", "state": "pending", "results": []}],
    )
    db.execute.return_value = scalar_first(report)

    async def search(_):
        return [{"url": "https://shop.example.kz/p/gel-500"}]

    async def evaluate(*_):
        return [{"url": "https://shop.example.kz/p/gel-500", "match_status": "matched", "checks": []}]

    monkeypatch.setattr(quick_check, "search_products", search)
    monkeypatch.setattr(quick_check, "evaluate_product_leads", evaluate)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/quick-check/search",
            json={"product_name": "Средство для посуды 500 мл", "specs": "Жидкое",
                  "report_id": str(report.id), "item_index": 0},
        )
    assert response.status_code == 200
    assert report.items[0]["state"] == "ready"
    assert report.items[0]["checked_at"]
    assert report.items[0]["results"][0]["match_status"] == "matched"
    assert db.execute.await_count == 2
    for call in db.execute.call_args_list:
        params = call.args[0].compile().params.values()
        assert user.company_id in params
        assert user.id in params


@pytest.mark.asyncio
async def test_report_history_is_scoped_to_user_and_company(authenticated_user):
    user, db = authenticated_user
    timestamp = datetime.now(timezone.utc)
    rows = [{"id": uuid.uuid4(), "filename": f"techspec-{index}.pdf", "created_at": timestamp,
             "total_items": 1, "checked_items": 1, "processing_state": "completed"} for index in range(21)]
    totals_result = MagicMock()
    totals_result.one.return_value = (21, 21, 21)
    page_result = MagicMock()
    page_result.mappings.return_value.all.return_value = rows
    db.execute.side_effect = [totals_result, page_result]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/quick-check/reports")
    assert response.status_code == 200
    assert response.json()["reports"][0]["checked_items"] == 1
    assert response.json()["reports"][0]["processing_state"] == "completed"
    assert len(response.json()["reports"]) == 20
    assert response.json()["stats"] == {"total_reports": 21, "total_items": 21, "checked_items": 21}
    assert quick_check._decode_cursor(response.json()["next_cursor"]) == (timestamp, rows[19]["id"])
    for call in db.execute.call_args_list:
        params = call.args[0].compile().params.values()
        assert user.company_id in params
        assert user.id in params


@pytest.mark.asyncio
async def test_report_history_cursor_filters_older_checks(authenticated_user):
    user, db = authenticated_user
    timestamp = datetime.now(timezone.utc)
    last_id = uuid.uuid4()
    totals_result = MagicMock()
    totals_result.one.return_value = (1, 2, 0)
    page_result = MagicMock()
    page_result.mappings.return_value.all.return_value = []
    db.execute.side_effect = [totals_result, page_result]
    cursor = quick_check._encode_cursor(timestamp, last_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/quick-check/reports?cursor={cursor}")
    assert response.status_code == 200
    assert response.json()["reports"] == []
    assert response.json()["next_cursor"] is None
    params = db.execute.call_args_list[1].args[0].compile().params.values()
    assert user.company_id in params
    assert user.id in params
    assert last_id in params
    assert timestamp in params


@pytest.mark.asyncio
async def test_report_history_rejects_bad_cursor(authenticated_user):
    _, db = authenticated_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/quick-check/reports?cursor=not-a-valid-cursor")
    assert response.status_code == 422
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_report_not_found_does_not_leak_data(authenticated_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/quick-check/reports/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_saved_report_can_be_reopened(authenticated_user):
    user, db = authenticated_user
    report = QuickCheckReport(
        id=uuid.uuid4(), company_id=user.company_id, created_by=user.id,
        filename="techspec.pdf", page_count=1, ocr_pages=0, total_items=1,
        truncated=False, created_at=datetime.now(timezone.utc),
        items=[{"product_name": "Средство для посуды 500 мл", "state": "ready", "results": []}],
    )
    db.execute.return_value = scalar_first(report)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/quick-check/reports/{report.id}")
    assert response.status_code == 200
    assert response.json()["items"][0]["state"] == "ready"
    params = db.execute.call_args.args[0].compile().params.values()
    assert user.company_id in params
    assert user.id in params


@pytest.mark.asyncio
async def test_saved_report_can_resume_without_reupload(authenticated_user, monkeypatch):
    user, db = authenticated_user
    report = QuickCheckReport(
        id=uuid.uuid4(), company_id=user.company_id, created_by=user.id,
        filename="techspec.pdf", page_count=1, ocr_pages=0, total_items=1,
        truncated=False, processing_state="error",
        items=[{"product_name": "Средство для посуды", "state": "error", "results": []}],
    )
    db.execute.return_value = scalar_first(report)
    published = []
    monkeypatch.setattr(quick_check.search_quick_report_task, "delay", lambda *args: published.append(args))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/quick-check/reports/{report.id}/run")
    assert response.status_code == 200
    assert response.json()["processing_state"] == "queued"
    assert published == [(str(report.id), str(report.run_id))]
    db.commit.assert_awaited_once()
    params = db.execute.call_args.args[0].compile().params.values()
    assert user.company_id in params
    assert user.id in params


@pytest.mark.asyncio
async def test_rerun_creates_new_history_entry_without_reupload(authenticated_user, monkeypatch):
    user, db = authenticated_user
    original = QuickCheckReport(
        id=uuid.uuid4(), company_id=user.company_id, created_by=user.id,
        filename="techspec.pdf", page_count=2, ocr_pages=1, total_items=1,
        truncated=False, processing_state="completed", pdf_sha256="a" * 64,
        items=[{"product_name": "Средство для посуды", "specs": "500 мл", "quantity": 12,
                "unit": "шт", "state": "ready", "results": [{"title": "Старая цена"}],
                "checked_at": "2026-09-01T00:00:00Z"}],
    )
    db.execute.return_value = scalar_first(original)
    published = []
    monkeypatch.setattr(quick_check.search_quick_report_task, "delay", lambda *args: published.append(args))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/quick-check/reports/{original.id}/rerun")
    assert response.status_code == 200
    new_report = db.add.call_args.args[0]
    assert response.json()["id"] == str(new_report.id)
    assert new_report.id != original.id
    assert new_report.pdf_sha256 == original.pdf_sha256
    assert new_report.items == [{"product_name": "Средство для посуды", "specs": "500 мл",
                                 "quantity": 12, "unit": "шт", "state": "pending", "results": [],
                                 "checked_at": None}]
    assert original.items[0]["results"] == [{"title": "Старая цена"}]
    assert published == [(str(new_report.id), str(new_report.run_id))]
    params = db.execute.call_args.args[0].compile().params.values()
    assert user.company_id in params
    assert user.id in params


@pytest.mark.asyncio
async def test_rerun_rejects_active_report(authenticated_user, monkeypatch):
    user, db = authenticated_user
    report = QuickCheckReport(
        id=uuid.uuid4(), company_id=user.company_id, created_by=user.id,
        filename="techspec.pdf", page_count=1, ocr_pages=0, total_items=1,
        truncated=False, processing_state="running",
        items=[{"product_name": "Средство для посуды", "state": "searching", "results": []}],
    )
    db.execute.return_value = scalar_first(report)
    published = MagicMock()
    monkeypatch.setattr(quick_check.search_quick_report_task, "delay", published)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/quick-check/reports/{report.id}/rerun")
    assert response.status_code == 409
    db.add.assert_not_called()
    published.assert_not_called()


@pytest.mark.asyncio
async def test_resume_report_not_found_does_not_publish(authenticated_user, monkeypatch):
    published = []
    monkeypatch.setattr(quick_check.search_quick_report_task, "delay", lambda *args: published.append(args))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/quick-check/reports/{uuid.uuid4()}/run")
    assert response.status_code == 404
    assert not published


@pytest.mark.asyncio
async def test_saved_report_can_be_deleted_only_by_owner(authenticated_user):
    user, db = authenticated_user
    report = QuickCheckReport(
        id=uuid.uuid4(), company_id=user.company_id, created_by=user.id,
        filename="techspec.pdf", page_count=1, ocr_pages=0, total_items=1,
        truncated=False, items=[{"product_name": "Средство для посуды"}],
    )
    db.execute.return_value = scalar_first(report)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/api/v1/quick-check/reports/{report.id}")
    assert response.status_code == 204
    db.delete.assert_awaited_once_with(report)
    params = db.execute.call_args.args[0].compile().params.values()
    assert user.company_id in params
    assert user.id in params


@pytest.mark.asyncio
async def test_delete_report_not_found_does_not_leak_data(authenticated_user):
    _, db = authenticated_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/api/v1/quick-check/reports/{uuid.uuid4()}")
    assert response.status_code == 404
    db.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_saved_search_rejects_wrong_item_before_public_search(authenticated_user, monkeypatch):
    user, db = authenticated_user
    report = QuickCheckReport(
        id=uuid.uuid4(), company_id=user.company_id, created_by=user.id,
        filename="techspec.pdf", page_count=1, ocr_pages=0, total_items=1,
        truncated=False,
        items=[{"product_name": "Средство для посуды 500 мл", "state": "pending", "results": []}],
    )
    db.execute.return_value = scalar_first(report)
    search = AsyncMock()
    monkeypatch.setattr(quick_check, "search_products", search)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/quick-check/search", json={
            "product_name": "Другой товар", "report_id": str(report.id), "item_index": 0,
        })
    assert response.status_code == 409
    search.assert_not_awaited()


@pytest.mark.asyncio
async def test_quick_search_is_rate_limited(authenticated_user, monkeypatch):
    cache = AsyncMock()
    cache.eval.return_value = [11, 42]
    app.dependency_overrides[get_redis] = lambda: cache
    search = AsyncMock()
    monkeypatch.setattr(quick_check, "search_products", search)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/quick-check/search",
            json={"product_name": "Средство для посуды 500 мл"},
        )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "42"
    search.assert_not_awaited()
