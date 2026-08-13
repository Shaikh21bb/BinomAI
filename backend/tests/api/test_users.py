import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.company import Company

DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def make_user():
    return User(
        id=DUMMY_USER_ID,
        company_id=DUMMY_COMPANY_ID,
        full_name="Иван",
        email="ivan@test.kz",
        role="member",
        language="ru",
        timezone="Asia/Almaty",
        email_notifications=True,
        onboarding_completed=True,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def make_company():
    return Company(
        id=DUMMY_COMPANY_ID,
        name="ТОО Тест",
        plan="trial",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_client(db, user):
    async def override_get_db():
        yield db

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _patch_email(token_value="ivan@test.kz"):
    return patch("app.api.v1.endpoints.users.verify_jwt_token",
                 return_value={"email": token_value})


async def _run(client, coro):
    try:
        return await coro
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_me_200():
    db = AsyncMock()
    db.get = AsyncMock(return_value=make_company())
    user = make_user()
    client = _make_client(db, user)

    with _patch_email():
        resp = await _run(client, client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer tok"}
        ))

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "ivan@test.kz"
    assert body["company_name"] == "ТОО Тест"
    assert body["role"] == "member"


@pytest.mark.asyncio
async def test_patch_me_200():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=make_company())
    user = make_user()
    client = _make_client(db, user)

    with _patch_email():
        resp = await _run(client, client.patch(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer tok"},
            json={"full_name": "Пётр", "language": "en"},
        ))

    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "Пётр"
    assert body["language"] == "en"
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_my_company_200():
    db = AsyncMock()
    db.get = AsyncMock(return_value=make_company())
    user = make_user()
    client = _make_client(db, user)

    resp = await _run(client, client.get(
        "/api/v1/users/me/company", headers={"Authorization": "Bearer tok"}
    ))

    assert resp.status_code == 200
    assert resp.json()["name"] == "ТОО Тест"
    assert resp.json()["plan"] == "trial"


@pytest.mark.asyncio
async def test_get_my_company_404():
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    user = make_user()
    client = _make_client(db, user)

    resp = await _run(client, client.get(
        "/api/v1/users/me/company", headers={"Authorization": "Bearer tok"}
    ))

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_my_company_200():
    company = make_company()
    db = AsyncMock()
    db.get = AsyncMock(return_value=company)
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    user = make_user()
    client = _make_client(db, user)

    resp = await _run(client, client.patch(
        "/api/v1/users/me/company",
        headers={"Authorization": "Bearer tok"},
        json={"name": "ТОО Новое", "website": "https://example.kz"},
    ))

    assert resp.status_code == 200
    assert company.name == "ТОО Новое"
    assert company.website == "https://example.kz"
    assert resp.json()["name"] == "ТОО Новое"
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_patch_my_company_not_found_404():
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    user = make_user()
    client = _make_client(db, user)

    resp = await _run(client, client.patch(
        "/api/v1/users/me/company",
        headers={"Authorization": "Bearer tok"},
        json={"name": "ТОО Новое"},
    ))

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_change_password_success():
    client = _make_client(AsyncMock(), make_user())

    with _patch_email("ivan@test.kz"):
        with patch("httpx.AsyncClient") as mock_http:
            instance = mock_http.return_value.__aenter__.return_value
            ok = MagicMock(status_code=200)
            instance.post.return_value = ok
            instance.put.return_value = ok
            resp = await _run(client, client.put(
                "/api/v1/users/me/password",
                headers={"Authorization": "Bearer tok"},
                json={"current_password": "old", "new_password": "new"},
            ))

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    instance.put.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_password_wrong_current_400():
    client = _make_client(AsyncMock(), make_user())

    with _patch_email("ivan@test.kz"):
        with patch("httpx.AsyncClient") as mock_http:
            instance = mock_http.return_value.__aenter__.return_value
            instance.post.return_value = MagicMock(status_code=400)
            resp = await _run(client, client.put(
                "/api/v1/users/me/password",
                headers={"Authorization": "Bearer tok"},
                json={"current_password": "wrong", "new_password": "new"},
            ))

    assert resp.status_code == 400
    assert "Текущий пароль" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_change_password_update_failed_400():
    client = _make_client(AsyncMock(), make_user())

    with _patch_email("ivan@test.kz"):
        with patch("httpx.AsyncClient") as mock_http:
            instance = mock_http.return_value.__aenter__.return_value
            instance.post.return_value = MagicMock(status_code=200)
            instance.put.return_value = MagicMock(status_code=500)
            resp = await _run(client, client.put(
                "/api/v1/users/me/password",
                headers={"Authorization": "Bearer tok"},
                json={"current_password": "old", "new_password": "new"},
            ))

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_patch_notifications_200():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=make_company())
    user = make_user()
    client = _make_client(db, user)

    with _patch_email():
        resp = await _run(client, client.patch(
            "/api/v1/users/me/notifications",
            headers={"Authorization": "Bearer tok"},
            json={"email_notifications": False},
        ))

    assert resp.status_code == 200
    assert resp.json()["email_notifications"] is False
    assert user.email_notifications is False
    db.flush.assert_awaited_once()
