import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.product_search import ProductSearchItem
from tests.conftest import db_dispatch

DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DUMMY_PROJECT_ID = uuid.uuid4()
OTHER_COMPANY_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def make_project(company_id=DUMMY_COMPANY_ID):
    return Project(
        id=DUMMY_PROJECT_ID,
        company_id=company_id,
        created_by=DUMMY_USER_ID,
        name="Тендер",
        status="ready",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
async def test_start_product_search_202_and_dispatches_task():
    db = db_dispatch({"projects": make_project()})
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    with patch("app.api.v1.endpoints.products.search_products_task.delay") as mock_delay:
        async for client in _make_client(db, user):
            resp = await client.post(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/products/search"
            )

    assert resp.status_code == 202
    assert resp.json()["status"] == "started"
    mock_delay.assert_called_once_with(str(DUMMY_PROJECT_ID))


@pytest.mark.asyncio
async def test_start_product_search_foreign_project_404():
    # SQL WHERE company_id = user.company_id filters — mock returns nothing
    db = db_dispatch({"projects": None})
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    with patch("app.api.v1.endpoints.products.search_products_task.delay") as mock_delay:
        async for client in _make_client(db, user):
            resp = await client.post(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/products/search"
            )

    assert resp.status_code == 404
    mock_delay.assert_not_called()


@pytest.mark.asyncio
async def test_list_products_200():
    item = ProductSearchItem(
        id=uuid.uuid4(),
        project_id=DUMMY_PROJECT_ID,
        company_id=DUMMY_COMPANY_ID,
        product_name="Цемент",
        status="ready",
        results=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    def items_entry(stmt):
        return scalar_first(make_project())

    db = db_dispatch({"projects": items_entry, "product_search_items": [item]})
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    async for client in _make_client(db, user):
        resp = await client.get(f"/api/v1/projects/{DUMMY_PROJECT_ID}/products")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["product_name"] == "Цемент"


@pytest.mark.asyncio
async def test_list_products_foreign_project_404():
    db = db_dispatch({"projects": None})
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    async for client in _make_client(db, user):
        resp = await client.get(f"/api/v1/projects/{DUMMY_PROJECT_ID}/products")

    assert resp.status_code == 404