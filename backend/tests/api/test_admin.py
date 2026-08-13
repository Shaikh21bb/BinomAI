import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.invite import Invite
from app.db.models.company import Company
from tests.conftest import scalar_first, scalars_all, db_dispatch

DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OWNER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
MEMBER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
LIMITED_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
INVITE_ID = uuid.uuid4()


def make_user(role="owner", user_id=OWNER_USER_ID):
    return User(
        id=user_id,
        company_id=DUMMY_COMPANY_ID,
        role=role,
        full_name="Иван",
        email=f"user{user_id.int}@test.kz",
        created_at=datetime.now(timezone.utc),
    )


def make_invite():
    return Invite(
        id=INVITE_ID,
        code="ABCDEFGH",
        created_by=OWNER_USER_ID,
        company_id=DUMMY_COMPANY_ID,
        max_uses=5,
        uses=0,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        active=True,
        created_at=datetime.now(timezone.utc),
    )


def scalar_first(obj):
    r = MagicMock()
    r.scalars.return_value.first.return_value = obj
    return r


def scalars_all(objects):
    r = MagicMock()
    r.scalars.return_value.all.return_value = objects
    return r


async def _make_client(db, user):
    async def override_get_db():
        yield db

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_invite_owner_201():
    db = db_dispatch({"invites": None})  # code uniqueness check
    owner = make_user(role="owner")

    with patch("app.api.v1.endpoints.admin._generate_code", return_value="ABCDEFGH"):
        async def fake_commit():
            invite = db.add.call_args.args[0]
            for attr, value in (("id", INVITE_ID), ("uses", 0), ("active", True),
                                ("created_at", datetime.now(timezone.utc))):
                if getattr(invite, attr, None) is None:
                    setattr(invite, attr, value)
            return None

        db.commit = AsyncMock(side_effect=fake_commit)
        db.refresh = AsyncMock()
        async for client in _make_client(db, owner):
            resp = await client.post(
                "/api/v1/admin/invites",
                json={"max_uses": 5, "expires_in_days": 30},
            )

    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "ABCDEFGH"
    assert body["max_uses"] == 5


@pytest.mark.asyncio
async def test_create_invite_non_owner_forbidden_403():
    db = AsyncMock()
    member = make_user(role="member", user_id=MEMBER_USER_ID)

    async for client in _make_client(db, member):
        resp = await client.post(
            "/api/v1/admin/invites",
            json={"max_uses": 1, "expires_in_days": 30},
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_invites_owner_200():
    db = db_dispatch({"invites": [make_invite()]})
    owner = make_user(role="owner")

    async for client in _make_client(db, owner):
        resp = await client.get("/api/v1/admin/invites")

    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_disable_invite_204():
    invite = make_invite()
    db = db_dispatch({"invites": invite})
    owner = make_user(role="owner")

    async for client in _make_client(db, owner):
        resp = await client.delete(f"/api/v1/admin/invites/{INVITE_ID}")

    assert resp.status_code == 204
    assert invite.active is False


@pytest.mark.asyncio
async def test_disable_invite_not_found_404():
    db = db_dispatch({"invites": None})
    owner = make_user(role="owner")

    async for client in _make_client(db, owner):
        resp = await client.delete(f"/api/v1/admin/invites/{INVITE_ID}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_role_success():
    target = make_user(role="member", user_id=MEMBER_USER_ID)
    company = Company(id=DUMMY_COMPANY_ID, name="ТОО Тест")
    count_res = MagicMock()
    count_res.scalar.return_value = 3
    db = db_dispatch({
        "users": target,
        "companies": company,
        "projects": lambda stmt: count_res,
    })
    owner = make_user(role="owner")

    async for client in _make_client(db, owner):
        resp = await client.patch(
            f"/api/v1/admin/users/{MEMBER_USER_ID}/role",
            json={"role": "limited"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "limited"
    assert target.role == "limited"
    assert body["project_count"] == 3


@pytest.mark.asyncio
async def test_update_role_invalid_role_400():
    db = AsyncMock()
    owner = make_user(role="owner")

    async for client in _make_client(db, owner):
        resp = await client.patch(
            f"/api/v1/admin/users/{MEMBER_USER_ID}/role",
            json={"role": "superadmin"},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_own_role_forbidden_400():
    db = db_dispatch({"users": make_user(role="owner")})
    owner = make_user(role="owner")

    async for client in _make_client(db, owner):
        resp = await client.patch(
            f"/api/v1/admin/users/{OWNER_USER_ID}/role",
            json={"role": "member"},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_users_owner_200():
    u1 = make_user(role="member", user_id=MEMBER_USER_ID)
    u2 = make_user(role="limited", user_id=LIMITED_USER_ID)
    result = MagicMock()
    result.all.return_value = [(u1, "ТОО Тест", 3), (u2, "ТОО Тест", 0)]
    db = db_dispatch({"default": lambda stmt: result})
    owner = make_user(role="owner")

    async for client in _make_client(db, owner):
        resp = await client.get("/api/v1/admin/users")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["email"] == u1.email
    assert body[0]["company_name"] == "ТОО Тест"
    assert body[0]["project_count"] == 3
    assert body[1]["project_count"] == 0


@pytest.mark.asyncio
async def test_update_role_limited_forbidden_403():
    db = AsyncMock()
    limited = make_user(role="limited", user_id=LIMITED_USER_ID)

    async for client in _make_client(db, limited):
        resp = await client.patch(
            f"/api/v1/admin/users/{MEMBER_USER_ID}/role",
            json={"role": "member"},
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_account_owner_201():
    new_user_id = uuid.UUID("00000000-0000-0000-0000-000000000009")
    auth_response = MagicMock()
    auth_response.status_code = 200
    auth_response.json.return_value = {"id": str(new_user_id)}
    supabase_client = MagicMock()
    supabase_client.get_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=auth_response)

    company = Company(id=DUMMY_COMPANY_ID, name="ТОО Тест", plan="trial")
    count_res = MagicMock()
    count_res.scalar.return_value = 0

    def on_add(obj):
        if isinstance(obj, User):
            obj.id = new_user_id
            obj.created_at = datetime.now(timezone.utc)
        return None

    db = db_dispatch({
        "users": None,
        "companies": company,
        "projects": lambda stmt: count_res,
    })
    db.get = AsyncMock(return_value=Company(id=DUMMY_COMPANY_ID, name="ТОО Тест", plan="enterprise"))
    db.add = MagicMock(side_effect=on_add)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    owner = make_user(role="owner")

    with patch("app.api.v1.endpoints.admin.supabase_admin", supabase_client):
        async for client in _make_client(db, owner):
            resp = await client.post(
                "/api/v1/admin/accounts",
                json={
                    "email": "new.user@test.kz",
                    "password": "secret123",
                    "full_name": "Новый Пользователь",
                    "role": "member",
                },
            )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new.user@test.kz"
    assert body["role"] == "member"


@pytest.mark.asyncio
async def test_create_account_duplicate_email_409():
    db = db_dispatch({"users": make_user(role="member", user_id=MEMBER_USER_ID)})
    owner = make_user(role="owner")

    async for client in _make_client(db, owner):
        resp = await client.post(
            "/api/v1/admin/accounts",
            json={
                "email": "user0@test.kz",
                "password": "secret123",
                "role": "member",
            },
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_account_non_owner_forbidden_403():
    db = AsyncMock()
    member = make_user(role="member", user_id=MEMBER_USER_ID)

    async for client in _make_client(db, member):
        resp = await client.post(
            "/api/v1/admin/accounts",
            json={
                "email": "new.user@test.kz",
                "password": "secret123",
                "role": "member",
            },
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_account_invalid_role_422():
    db = AsyncMock()
    owner = make_user(role="owner")

    async for client in _make_client(db, owner):
        resp = await client.post(
            "/api/v1/admin/accounts",
            json={
                "email": "new.user@test.kz",
                "password": "secret123",
                "role": "superadmin",
            },
        )

    assert resp.status_code == 422