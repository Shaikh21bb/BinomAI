import json

import pytest
from starlette.requests import Request

from app.core.exceptions import custom_http_exception_handler


@pytest.mark.asyncio
async def test_internal_error_does_not_expose_exception_details():
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/boom",
        "headers": [],
        "state": {"request_id": "req_support123"},
    })
    response = await custom_http_exception_handler(
        request,
        RuntimeError("postgresql://user:secret@private-host/database"),
    )

    payload = json.loads(response.body)
    assert response.status_code == 500
    assert payload["error"]["message"] == "Внутренняя ошибка сервера."
    assert "secret" not in response.body.decode()
    assert payload["meta"]["request_id"] == "req_support123"
    assert payload["meta"]["timestamp"]
    assert response.headers["X-Request-ID"] == "req_support123"
