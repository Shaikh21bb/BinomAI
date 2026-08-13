import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.company import Company

# Test Data
DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DUMMY_PROJECT_ID = uuid.uuid4()

@pytest.fixture
async def client():
    async def override_get_db():
        db = AsyncMock()
        db.get = AsyncMock(return_value=Company(id=DUMMY_COMPANY_ID, name="Тест", plan="enterprise"))
        yield db
    async def override_get_current_user():
        return User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_project(client, mock_project_repo):
    # Setup mock
    mock_project = Project(
        id=DUMMY_PROJECT_ID,
        company_id=DUMMY_COMPANY_ID,
        created_by=DUMMY_USER_ID,
        name="Test Tender",
        status="draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    mock_project_repo.create = AsyncMock(return_value=mock_project)

    response = await client.post("/api/v1/projects/", json={
        "name": "Test Tender",
        "customer_name": "Test Customer"
    })

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Tender"
    assert data["status"] == "draft"
    mock_project_repo.create.assert_called_once()

@pytest.mark.asyncio
async def test_get_project_not_found(client, mock_project_repo):
    mock_project_repo.get = AsyncMock(return_value=None)

    response = await client.get(f"/api/v1/projects/{DUMMY_PROJECT_ID}")

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "HTTP_404"


def make_project():
    return Project(
        id=DUMMY_PROJECT_ID,
        company_id=DUMMY_COMPANY_ID,
        created_by=DUMMY_USER_ID,
        name="Test Tender",
        status="draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


async def _delete_client(db, path):
    async def override_get_db():
        yield db

    async def override_get_current_user():
        return User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield await c.delete(path)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_projects_success(client):
    from app.schemas.project import ProjectResponse
    from app.schemas.pagination import CursorPaginatedResponse, CursorPaginationMeta

    page = CursorPaginatedResponse[ProjectResponse](
        data=[make_project()],
        pagination=CursorPaginationMeta(
            page_size=20, has_next=False, next_cursor=None, total=1
        ),
    )

    with patch("app.api.v1.endpoints.projects.ProjectService.get_projects_by_company",
               new_callable=AsyncMock, return_value=page) as mock_list:
        response = await client.get("/api/v1/projects/")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "Test Tender"
    assert body["pagination"]["total"] == 1
    mock_list.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_project_success(client, mock_project_repo):
    mock_project_repo.get = AsyncMock(return_value=make_project())

    response = await client.get(f"/api/v1/projects/{DUMMY_PROJECT_ID}")

    assert response.status_code == 200
    assert response.json()["name"] == "Test Tender"
    assert response.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_get_project_foreign_company_404(client, mock_project_repo):
    other = Project(
        id=DUMMY_PROJECT_ID,
        company_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        created_by=DUMMY_USER_ID,
        name="Чужой",
        status="draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    mock_project_repo.get = AsyncMock(return_value=other)

    response = await client.get(f"/api/v1/projects/{DUMMY_PROJECT_ID}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_204(mock_project_repo):
    from tests.conftest import db_dispatch
    db = db_dispatch({"documents": []})
    mock_project_repo.get = AsyncMock(return_value=make_project())
    mock_project_repo.remove = AsyncMock()

    async for response in _delete_client(db, f"/api/v1/projects/{DUMMY_PROJECT_ID}"):
        assert response.status_code == 204
    mock_project_repo.remove.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_project_not_found_404(mock_project_repo):
    db = AsyncMock()
    mock_project_repo.get = AsyncMock(return_value=None)
    mock_project_repo.remove = AsyncMock()

    async for response in _delete_client(db, f"/api/v1/projects/{DUMMY_PROJECT_ID}"):
        assert response.status_code == 404
    mock_project_repo.remove.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_project_foreign_company_404(mock_project_repo):
    other = Project(
        id=DUMMY_PROJECT_ID,
        company_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        created_by=DUMMY_USER_ID,
        name="Чужой",
        status="draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db = AsyncMock()
    mock_project_repo.get = AsyncMock(return_value=other)
    mock_project_repo.remove = AsyncMock()

    async for response in _delete_client(db, f"/api/v1/projects/{DUMMY_PROJECT_ID}"):
        assert response.status_code == 404
    mock_project_repo.remove.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_projects_applies_search_and_status(client):
    from app.schemas.project import ProjectResponse
    from app.schemas.pagination import CursorPaginatedResponse, CursorPaginationMeta

    page = CursorPaginatedResponse[ProjectResponse](
        data=[],
        pagination=CursorPaginationMeta(page_size=20, has_next=False, next_cursor=None, total=0),
    )

    with patch("app.api.v1.endpoints.projects.ProjectService.get_projects_by_company",
               new_callable=AsyncMock, return_value=page) as mock_list:
        response = await client.get(
            "/api/v1/projects/?search=медоборудование&status=analyzing"
        )

    assert response.status_code == 200
    called_kwargs = mock_list.await_args.kwargs
    assert called_kwargs["search"] == "медоборудование"
    assert called_kwargs["status"] == "analyzing"


@pytest.mark.asyncio
async def test_update_project_success(client, mock_project_repo):
    original = make_project()
    updated = make_project()
    updated.name = "Новое название"
    updated.status = "ready"
    mock_project_repo.get = AsyncMock(return_value=original)
    mock_project_repo.update = AsyncMock(return_value=updated)

    response = await client.patch(
        f"/api/v1/projects/{DUMMY_PROJECT_ID}",
        json={"name": "Новое название", "status": "ready"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Новое название"
    assert body["status"] == "ready"
    mock_project_repo.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_project_not_found(client, mock_project_repo):
    mock_project_repo.get = AsyncMock(return_value=None)
    mock_project_repo.update = AsyncMock()

    response = await client.patch(
        f"/api/v1/projects/{DUMMY_PROJECT_ID}",
        json={"name": "Новое название"},
    )

    assert response.status_code == 404
    mock_project_repo.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_project_foreign_company_404(client, mock_project_repo):
    foreign = Project(
        id=DUMMY_PROJECT_ID,
        company_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        created_by=DUMMY_USER_ID,
        name="Чужой",
        status="draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    mock_project_repo.get = AsyncMock(return_value=foreign)
    mock_project_repo.update = AsyncMock()

    response = await client.patch(
        f"/api/v1/projects/{DUMMY_PROJECT_ID}",
        json={"name": "Новое название"},
    )

    assert response.status_code == 404
    mock_project_repo.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_document_returns_signed_url(client, mock_project_repo):
    from tests.conftest import db_dispatch, scalar_first
    from app.db.models.document import Document

    doc = Document(
        id=uuid.uuid4(),
        project_id=DUMMY_PROJECT_ID,
        company_id=DUMMY_COMPANY_ID,
        uploaded_by=DUMMY_USER_ID,
        filename="tz.pdf",
        file_size_bytes=123,
        mime_type="application/pdf",
        storage_path="1111/2222/abc.pdf",
    )
    db = db_dispatch({"documents": doc})
    mock_project_repo.get = AsyncMock(return_value=make_project())

    with patch(
        "app.services.document_service.DocumentService.get_signed_download_url",
        new_callable=AsyncMock, return_value="https://signed/url",
    ) as mock_sign:
        async def override_get_db():
            yield db

        async def override_get_current_user():
            return User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.get(f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/{doc.id}/download")
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["url"] == "https://signed/url"
    assert body["filename"] == "tz.pdf"
    mock_sign.assert_awaited_once()
