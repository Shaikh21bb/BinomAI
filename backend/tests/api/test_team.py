import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.invite import Invite
from tests.conftest import db_dispatch

DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OWNER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
MEMBER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
OTHER_COMPANY_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

NOW = datetime.now(timezone.utc)


def make_user(role="owner", user_id=OWNER_ID, company_id=DUMMY_COMPANY_ID):
    return User(id=user_id, company_id=company_id, role=role, email="u@test.kz")


def make_member(role="member", user_id=MEMBER_ID, is_active=True, company_id=DUMMY_COMPANY_ID):
    return User(
        id=user_id,
        company_id=company_id,
        role=role,
        email="member@test.kz",
        full_name="Сотрудник Тест",
        job_title="Менеджер",
        is_active=is_active,
        created_at=NOW,
        last_login_at=None,
    )


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
async def test_list_members_returns_company_members():
    member1 = make_member(role="owner", user_id=OWNER_ID)
    member2 = make_member(role="member", user_id=MEMBER_ID)
    db = db_dispatch({"users": [member1, member2]})
    user = make_user()

    async for client in _make_client(db, user):
        resp = await client.get("/api/v1/users/me/company/members")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert {m["role"] for m in body} == {"owner", "member"}


@pytest.mark.asyncio
async def test_update_role_by_owner():
    member = make_member(role="member")
    db = db_dispatch({})
    db.get = AsyncMock(return_value=member)
    user = make_user(role="owner")

    async for client in _make_client(db, user):
        resp = await client.patch(
            f"/api/v1/users/me/company/members/{MEMBER_ID}/role",
            json={"role": "limited"},
        )

    assert resp.status_code == 200
    assert resp.json()["role"] == "limited"


@pytest.mark.asyncio
async def test_update_role_requires_owner():
    db = db_dispatch({})
    user = make_user(role="member")

    async for client in _make_client(db, user):
        resp = await client.patch(
            f"/api/v1/users/me/company/members/{MEMBER_ID}/role",
            json={"role": "member"},
        )

    assert resp.status_code == 403
    assert db.get.await_count == 0


@pytest.mark.asyncio
async def test_update_role_rejects_owner_target():
    owner = make_member(role="owner", user_id=OWNER_ID)
    db = db_dispatch({})
    db.get = AsyncMock(return_value=owner)
    user = make_user(role="owner")

    async for client in _make_client(db, user):
        resp = await client.patch(
            f"/api/v1/users/me/company/members/{OWNER_ID}/role",
            json={"role": "member"},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_role_rejects_foreign_member():
    foreign = make_member(user_id=MEMBER_ID, company_id=OTHER_COMPANY_ID)
    db = db_dispatch({})
    db.get = AsyncMock(return_value=foreign)
    user = make_user(role="owner")

    async for client in _make_client(db, user):
        resp = await client.patch(
            f"/api/v1/users/me/company/members/{MEMBER_ID}/role",
            json={"role": "member"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_remove_member_deactivates():
    member = make_member(role="member")
    db = db_dispatch({})
    db.get = AsyncMock(return_value=member)
    user = make_user(role="owner")

    async for client in _make_client(db, user):
        resp = await client.delete(f"/api/v1/users/me/company/members/{MEMBER_ID}")

    assert resp.status_code == 204
    assert member.is_active is False


@pytest.mark.asyncio
async def test_remove_self_forbidden():
    db = db_dispatch({})
    user = make_user(role="owner")

    async for client in _make_client(db, user):
        resp = await client.delete(f"/api/v1/users/me/company/members/{OWNER_ID}")

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_invite_by_owner():
    def apply_defaults(obj):
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.uses is None:
            obj.uses = 0
        if obj.active is None:
            obj.active = True
        if obj.created_at is None:
            obj.created_at = NOW
        if obj.expires_at is None:
            obj.expires_at = None
        return obj

    db = db_dispatch({"invites": None})
    db.add = MagicMock(side_effect=apply_defaults)
    db.refresh = AsyncMock()
    db.commit = AsyncMock()
    user = make_user(role="owner")

    async for client in _make_client(db, user):
        resp = await client.post("/api/v1/users/me/company/invites", json={"max_uses": 5, "expires_in_days": 30})

    assert resp.status_code == 201
    body = resp.json()
    assert len(body["code"]) == 8
    assert body["max_uses"] == 5
    assert body["active"] is True


@pytest.mark.asyncio
async def test_create_invite_requires_owner():
    db = db_dispatch({})
    user = make_user(role="member")

    async for client in _make_client(db, user):
        resp = await client.post("/api/v1/users/me/company/invites", json={"max_uses": 1, "expires_in_days": 1})

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_and_disable_invites():
    invite = Invite(
        id=uuid.uuid4(),
        code="ABC12345",
        company_id=DUMMY_COMPANY_ID,
        created_by=OWNER_ID,
        max_uses=5,
        uses=1,
        expires_at=None,
        active=True,
        created_at=NOW,
    )
    db = db_dispatch({"invites": [invite]})
    user = make_user(role="owner")

    async for client in _make_client(db, user):
        resp = await client.get("/api/v1/users/me/company/invites")

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["code"] == "ABC12345"
    assert body[0]["active"] is True

    invite2 = Invite(
        id=invite.id,
        code="ABC12345",
        company_id=DUMMY_COMPANY_ID,
        created_by=OWNER_ID,
        max_uses=5,
        uses=1,
        expires_at=None,
        active=True,
        created_at=NOW,
    )
    db2 = db_dispatch({"invites": invite2})
    user2 = make_user(role="owner")

    async for client in _make_client(db2, user2):
        resp2 = await client.delete(f"/api/v1/users/me/company/invites/{invite2.id}")

    assert resp2.status_code == 204
    assert invite2.active is False
