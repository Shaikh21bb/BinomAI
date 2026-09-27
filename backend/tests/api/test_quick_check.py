"""The quick PDF flow must work without creating a project or tender."""

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_redis
from app.api.v1.endpoints import quick_check
from app.db.models.user import User
from app.main import app


@pytest.fixture
def authenticated_user():
    cache = AsyncMock()
    cache.eval.return_value = [1, 60]

    async def current_user():
        return User(id=uuid.uuid4(), company_id=uuid.uuid4(), role="limited")

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_redis] = lambda: cache
    yield
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
