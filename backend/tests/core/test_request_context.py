import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app, create_app


@pytest.mark.asyncio
async def test_request_id_is_returned_in_headers_and_error_metadata():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/does-not-exist",
            headers={"X-Request-ID": "support-case_123"},
        )

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "support-case_123"
    assert response.headers["X-App-Version"] == settings.APP_VERSION
    assert response.json()["meta"]["request_id"] == "support-case_123"
    assert response.json()["meta"]["timestamp"]


@pytest.mark.asyncio
async def test_unsafe_request_id_is_replaced():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/health/live",
            headers={"X-Request-ID": "not safe for logs"},
        )

    request_id = response.headers["X-Request-ID"]
    assert request_id.startswith("req_")
    assert request_id != "not safe for logs"
    assert len(request_id) == 36


@pytest.mark.asyncio
async def test_unhandled_error_keeps_support_code_without_leaking_details():
    test_app = create_app()

    @test_app.get("/boom")
    async def boom():
        raise RuntimeError("private database details")

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/boom",
            headers={"X-Request-ID": "support-case_500"},
        )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "support-case_500"
    assert response.json()["meta"]["request_id"] == "support-case_500"
    assert response.json()["error"]["message"] == "Внутренняя ошибка сервера."
    assert "private database details" not in response.text
