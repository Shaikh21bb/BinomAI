import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps import get_db, get_current_user
from app.core.plans import PLANS, get_plan
from app.db.models.user import User
from app.db.models.company import Company
from app.db.models.project import Project
from app.db.models.plan_request import PlanRequest
from tests.conftest import scalar_first, db_dispatch

DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def make_user(role="owner"):
    return User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role=role, email="owner@test.kz")


def make_company(plan="trial"):
    return Company(
        id=DUMMY_COMPANY_ID,
        name="ТОО Тест",
        plan=plan,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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


def test_plan_catalog_has_expected_plans():
    assert set(PLANS.keys()) == {"trial", "starter", "pro", "enterprise"}
    assert PLANS["trial"].max_projects == 2
    assert PLANS["pro"].max_documents is None
    assert get_plan(None).key == "trial"
    assert get_plan("unknown").key == "trial"


@pytest.mark.asyncio
async def test_plan_usage_returns_plan_and_usage():
    count_res = MagicMock()
    count_res.scalar.return_value = 1
    db = db_dispatch({
        "companies": make_company("starter"),
        "projects": lambda stmt: count_res,
        "users": lambda stmt: count_res,
        "documents": lambda stmt: count_res,
    })
    db.get = AsyncMock(return_value=make_company("starter"))
    user = make_user()

    async for client in _make_client(db, user):
        resp = await client.get("/api/v1/users/me/company/plan-usage")

    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "starter"
    assert body["plan_name"] == "Старт"
    assert body["limits"]["max_projects"] == 10
    assert body["usage"]["projects"] == 1


@pytest.mark.asyncio
async def test_plan_usage_company_not_found_404():
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    user = make_user()

    async for client in _make_client(db, user):
        resp = await client.get("/api/v1/users/me/company/plan-usage")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_project_plan_limit_reached_403():
    count_res = MagicMock()
    count_res.scalar.return_value = 2  # trial limit = 2
    db = db_dispatch({"projects": lambda stmt: count_res})
    db.get = AsyncMock(return_value=make_company("trial"))
    user = make_user()

    async for client in _make_client(db, user):
        resp = await client.post("/api/v1/projects/", json={"name": "Тендер 3"})

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PROJECT_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_create_project_within_plan_limit_201(mock_project_repo):
    count_res = MagicMock()
    count_res.scalar.return_value = 1
    db = db_dispatch({"projects": lambda stmt: count_res})
    db.get = AsyncMock(return_value=make_company("trial"))
    user = make_user()

    project = Project(
        id=uuid.uuid4(),
        company_id=DUMMY_COMPANY_ID,
        created_by=DUMMY_USER_ID,
        name="Тендер 2",
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_project_repo.create = AsyncMock(return_value=project)

    async for client in _make_client(db, user):
        resp = await client.post("/api/v1/projects/", json={"name": "Тендер 2"})

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_admin_update_company_plan_success():
    company = make_company("trial")
    count_res = MagicMock()
    count_res.scalar.return_value = 0
    db = db_dispatch({"users": lambda stmt: count_res, "projects": lambda stmt: count_res})
    db.get = AsyncMock(return_value=company)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    owner = make_user()

    async for client in _make_client(db, owner):
        resp = await client.patch(
            f"/api/v1/admin/companies/{DUMMY_COMPANY_ID}/plan",
            json={"plan": "pro"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "pro"
    assert company.plan == "pro"


@pytest.mark.asyncio
async def test_admin_update_company_plan_unknown_plan_400():
    db = AsyncMock()
    owner = make_user()

    async for client in _make_client(db, owner):
        resp = await client.patch(
            f"/api/v1/admin/companies/{DUMMY_COMPANY_ID}/plan",
            json={"plan": "ultra"},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_update_company_plan_not_found_404():
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    owner = make_user()

    async for client in _make_client(db, owner):
        resp = await client.patch(
            f"/api/v1/admin/companies/{DUMMY_COMPANY_ID}/plan",
            json={"plan": "pro"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_list_companies_200():
    row = MagicMock()
    row.id = DUMMY_COMPANY_ID
    row.name = "ТОО Тест"
    row.plan = "trial"
    row.plan_expires_at = None
    row.created_at = datetime.now(timezone.utc)
    row.user_count = 3
    row.project_count = 2
    result = MagicMock()
    result.all.return_value = [row]
    db = db_dispatch({"default": lambda stmt: result})
    owner = make_user()

    async for client in _make_client(db, owner):
        resp = await client.get("/api/v1/admin/companies")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "ТОО Тест"
    assert body[0]["plan"] == "trial"
    assert body[0]["user_count"] == 3


def make_plan_request():
    return PlanRequest(
        id=uuid.uuid4(),
        company_id=DUMMY_COMPANY_ID,
        user_id=DUMMY_USER_ID,
        current_plan="trial",
        requested_plan="pro",
        message="Нужно больше проектов",
        status="pending",
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_plan_request_201():
    db = db_dispatch({"plan_requests": None})
    db.get = AsyncMock(side_effect=lambda model, pk: make_company("trial") if model is Company else make_user())
    db.refresh = AsyncMock()

    def on_add(obj):
        if isinstance(obj, PlanRequest):
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(timezone.utc)
            obj.status = "pending"
        return None

    db.add = MagicMock(side_effect=on_add)
    user = make_user()

    async for client in _make_client(db, user):
        resp = await client.post(
            "/api/v1/users/me/plan-requests",
            json={"requested_plan": "pro", "message": "Нужно больше проектов"},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["requested_plan"] == "pro"
    assert body["current_plan"] == "trial"
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_create_plan_request_already_pending_409():
    existing = make_plan_request()
    db = db_dispatch({"plan_requests": existing})
    db.get = AsyncMock(side_effect=lambda model, pk: make_company("trial") if model is Company else make_user())
    user = make_user()

    async for client in _make_client(db, user):
        resp = await client.post(
            "/api/v1/users/me/plan-requests",
            json={"requested_plan": "pro"},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_list_plan_requests_200():
    req = make_plan_request()
    row = MagicMock()
    row.id = req.id
    row.company_id = req.company_id
    row.current_plan = req.current_plan
    row.requested_plan = req.requested_plan
    row.message = req.message
    row.status = req.status
    row.created_at = req.created_at
    result = MagicMock()
    result.all.return_value = [(row, "ТОО Тест", "Иван", "user@test.kz")]
    db = db_dispatch({"default": lambda stmt: result})
    owner = make_user()

    async for client in _make_client(db, owner):
        resp = await client.get("/api/v1/admin/plan-requests")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["company_name"] == "ТОО Тест"
    assert body[0]["requested_plan"] == "pro"


@pytest.mark.asyncio
async def test_admin_approve_plan_request_upgrades_company():
    req = make_plan_request()
    company = make_company("trial")
    db = db_dispatch({"plan_requests": req})
    db.get = AsyncMock(side_effect=lambda model, pk: company if model is Company else make_user())
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    owner = make_user()

    async for client in _make_client(db, owner):
        resp = await client.patch(
            f"/api/v1/admin/plan-requests/{req.id}/status",
            json={"status": "done"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert req.status == "done"
    assert company.plan == "pro"


@pytest.mark.asyncio
async def test_admin_plan_request_not_found_404():
    db = db_dispatch({"plan_requests": None})
    owner = make_user()

    async for client in _make_client(db, owner):
        resp = await client.patch(
            f"/api/v1/admin/plan-requests/{uuid.uuid4()}/status",
            json={"status": "done"},
        )

    assert resp.status_code == 404
