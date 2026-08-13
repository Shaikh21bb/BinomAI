import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient
import uuid

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User

DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")

@pytest.fixture
async def client():
    mock_session = AsyncMock()
    async def override_get_db():
        yield mock_session
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def mock_supabase_admin():
    with patch("app.services.auth_service.supabase_admin.get_client") as mock:
        yield mock

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient") as mock:
        yield mock

@pytest.fixture
def mock_verify_jwt():
    with patch("app.api.deps.verify_jwt_token") as mock:
        yield mock

@pytest.mark.asyncio
async def test_register_duplicate_email(client, mock_supabase_admin):
    # Setup mock response for duplicate email
    mock_response = MagicMock()
    mock_response.status_code = 422
    mock_response.json.return_value = {"msg": "Email already exists"}

    mock_client_instance = mock_supabase_admin.return_value.__aenter__.return_value
    mock_client_instance.post.return_value = mock_response

    response = await client.post("/api/v1/auth/register", json={
        "email": "test@test.com",
        "password": "password",
        "full_name": "Test User",
        "company_name": "Test Co"
    })

    assert response.status_code == 409
    assert "уже зарегистрирован" in response.json()["error"]["message"]

@pytest.mark.asyncio
async def test_login_invalid_credentials(client, mock_httpx_client):
    # Setup mock response for invalid login
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": "invalid_grant"}

    mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
    mock_client_instance.post.return_value = mock_response

    response = await client.post("/api/v1/auth/login", json={
        "email": "test@test.com",
        "password": "wrong"
    })

    assert response.status_code == 401
    assert "Неверный" in response.json()["error"]["message"]

@pytest.mark.asyncio
async def test_protected_route_without_token(client):
    # Attempt to hit /projects without a token
    response = await client.get("/api/v1/projects/")

    # Should be 403 Forbidden because FastAPI HTTPBearer returns 403 when Not authenticated
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_forgot_password_always_200(client, mock_httpx_client):
    mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
    mock_client_instance.post.return_value = MagicMock(status_code=500)

    response = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@test.kz"}
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    mock_client_instance.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_password_success(client, mock_httpx_client):
    mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
    mock_client_instance.put.return_value = MagicMock(status_code=200)

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"access_token": "recovery_token", "new_password": "new-pass-123"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    mock_client_instance.put.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_password_invalid_token_400(client, mock_httpx_client):
    mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
    mock_client_instance.put.return_value = MagicMock(status_code=400)

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"access_token": "bad_token", "new_password": "new-pass-123"},
    )

    assert response.status_code == 400
    assert "недействительна" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_protected_route_with_invalid_token(client, mock_verify_jwt):
    from fastapi import HTTPException
    # Mock verify_jwt to raise exception
    mock_verify_jwt.side_effect = HTTPException(status_code=401, detail="Token has expired")

    response = await client.get("/api/v1/projects/", headers={"Authorization": "Bearer invalid_token"})

    assert response.status_code == 401
    assert "expired" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_refresh_token_success(client, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "new_access", "expires_in": 3600}

    mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
    mock_client_instance.post.return_value = mock_response

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "rt"})

    assert response.status_code == 200
    assert response.json()["access_token"] == "new_access"


@pytest.mark.asyncio
async def test_refresh_token_invalid_401(client, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.status_code = 400

    mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
    mock_client_instance.post.return_value = mock_response

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "bad"})

    assert response.status_code == 401
    assert "refresh" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_logout_success(client, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
    mock_client_instance.post.return_value = mock_response

    response = await client.post(
        "/api/v1/auth/logout", headers={"Authorization": "Bearer some_token"}
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    mock_client_instance.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout_requires_bearer(client):
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_me_with_company_email(client):
    from app.db.models.company import Company
    from app.db.models.user import User
    from tests.conftest import scalar_first

    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    db = AsyncMock()

    def companies_entry(stmt):
        return scalar_first("company@test.kz")

    async def execute(stmt, *a, **kw):
        try:
            table = stmt.get_final_froms()[0].name
        except Exception:
            table = "default"
        if table == "companies":
            return companies_entry(stmt)
        return scalar_first(None)

    db.execute = execute

    async def override_get_db():
        yield db

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.get("/api/v1/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(DUMMY_USER_ID)
    assert body["email"] == "company@test.kz"
    assert body["role"] == "admin"


@pytest.mark.asyncio
async def test_get_me_falls_back_to_supabase_admin(client, mock_verify_jwt):
    from app.db.models.user import User
    from tests.conftest import scalar_first

    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="limited")
    db = AsyncMock()

    async def execute(stmt, *a, **kw):
        try:
            table = stmt.get_final_froms()[0].name
        except Exception:
            table = "default"
        return scalar_first(None) if table == "companies" else scalar_first(None)

    db.execute = execute

    async def override_get_db():
        yield db

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    from unittest.mock import MagicMock
    admin_response = MagicMock()
    admin_response.status_code = 200
    admin_response.json.return_value = {"email": "fallback@test.kz"}

    with patch("app.api.v1.endpoints.auth.supabase_admin.get_client") as mock_admin:
        mock_client = mock_admin.return_value.__aenter__.return_value
        mock_client.get.return_value = admin_response
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                response = await c.get("/api/v1/auth/me")
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["email"] == "fallback@test.kz"
    mock_client.get.assert_awaited_once()
