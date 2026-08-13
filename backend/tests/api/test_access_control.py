import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient
import uuid
from datetime import datetime, timedelta, timezone

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.invite import Invite
from app.db.models.company import Company

DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OWNER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
INVITE_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
PROJECT_LIMIT = 2


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


def make_limited_user():
    return User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="limited", full_name="Limited User")


def make_owner_user():
    return User(id=OWNER_USER_ID, company_id=DUMMY_COMPANY_ID, role="owner", full_name="Owner")


@pytest.mark.asyncio
async def test_create_project_limited_blocked(client):
    user = make_limited_user()
    app.dependency_overrides[get_current_user] = lambda: user

    result_proxy = MagicMock()
    result_proxy.scalar.return_value = PROJECT_LIMIT

    async def fake_execute(stmt, *a, **kw):
        return result_proxy

    async def override_db():
        session = AsyncMock()
        session.execute = fake_execute
        yield session
    app.dependency_overrides[get_db] = override_db

    with patch("app.api.v1.endpoints.projects.ProjectService.create_project", new_callable=AsyncMock) as mock_create:
        response = await client.post("/api/v1/projects/", json={"name": "P3"})
        mock_create.assert_not_awaited()

    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "PROJECT_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_create_project_limited_under_limit(client):
    user = make_limited_user()
    app.dependency_overrides[get_current_user] = lambda: user

    result_proxy = MagicMock()
    result_proxy.scalar.return_value = 1

    from app.api.v1.endpoints import projects as projects_module
    async def fake_execute(stmt, *a, **kw):
        return result_proxy

    async def override_db():
        session = AsyncMock()
        session.execute = fake_execute
        yield session
    app.dependency_overrides[get_db] = override_db

    with patch("app.api.v1.endpoints.projects.ProjectService.create_project", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = Project(
            id=uuid.uuid4(),
            name="P1",
            company_id=DUMMY_COMPANY_ID,
            created_by=DUMMY_USER_ID,
            status="draft",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        response = await client.post("/api/v1/projects/", json={"name": "P1"})

    assert response.status_code == 201

    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_invite_consume_increments_uses():
    from app.services.auth_service import _consume_invite

    invite = Invite(
        id=INVITE_ID,
        code="TESTCODE1",
        created_by=OWNER_USER_ID,
        company_id=DUMMY_COMPANY_ID,
        max_uses=3,
        uses=1,
        expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        active=True,
    )

    db = AsyncMock()
    result = MagicMock()
    result.scalars().first.return_value = invite
    db.execute.return_value = result

    consumed = await _consume_invite(db, "testcode1")
    assert consumed is invite
    assert invite.uses == 2


@pytest.mark.asyncio
async def test_invite_consume_expired_rejected():
    from app.services.auth_service import _consume_invite

    invite = Invite(
        id=INVITE_ID,
        code="EXPIRED01",
        created_by=OWNER_USER_ID,
        company_id=DUMMY_COMPANY_ID,
        max_uses=3,
        uses=0,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        active=True,
    )

    db = AsyncMock()
    result = MagicMock()
    result.scalars().first.return_value = invite
    db.execute.return_value = result

    assert await _consume_invite(db, "EXPIRED01") is None
    assert invite.uses == 0


@pytest.mark.asyncio
async def test_invite_consume_maxed_rejected():
    from app.services.auth_service import _consume_invite

    invite = Invite(
        id=INVITE_ID,
        code="MAXED001",
        created_by=OWNER_USER_ID,
        company_id=DUMMY_COMPANY_ID,
        max_uses=1,
        uses=1,
        active=True,
    )

    db = AsyncMock()
    result = MagicMock()
    result.scalars().first.return_value = invite
    db.execute.return_value = result

    assert await _consume_invite(db, "MAXED001") is None


@pytest.mark.asyncio
async def test_register_assigns_limited_without_invite(client):
    from app.services import auth_service

    class FakeSession(AsyncMock):
        def __init__(self):
            super().__init__()
            company = Company(id=DUMMY_COMPANY_ID, name="New Co", plan="trial")
            result = MagicMock()
            result.scalars.return_value.first.return_value = None
            self.execute.return_value = result
            self._added = []
            self.company = company

        def add(self, obj):
            self._added.append(obj)

        async def flush(self):
            pass

    mock_supabase_response = MagicMock()
    mock_supabase_response.status_code = 200
    mock_supabase_response.json.return_value = {"id": str(uuid.uuid4())}

    with patch("app.services.auth_service.supabase_admin.get_client") as mock_admin, \
         patch("app.services.auth_service.AuthService.login", new_callable=AsyncMock) as mock_login:

        mock_client_instance = mock_admin.return_value.__aenter__.return_value
        mock_client_instance.post.return_value = mock_supabase_response
        mock_login.return_value = {"access_token": "x", "refresh_token": "y", "expires_in": 3600, "user": {}}

        session = FakeSession()
        result = await auth_service.AuthService.register(session, MagicMock(
            email="new@test.kz", password="Password123!", full_name="New",
            company_name="New Co", invite_code=None,
        ))

    added_users = [o for o in session._added if isinstance(o, User)]
    assert len(added_users) == 1
    assert added_users[0].role == "limited"
    assert result is not None


@pytest.mark.asyncio
async def test_admin_invites_requires_owner(client):
    user = make_limited_user()
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.get("/api/v1/admin/invites")
    assert response.status_code == 403

    response = await client.post("/api/v1/admin/invites", json={"max_uses": 1, "expires_in_days": 30})
    assert response.status_code == 403

    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 403

    app.dependency_overrides.pop(get_current_user, None)
