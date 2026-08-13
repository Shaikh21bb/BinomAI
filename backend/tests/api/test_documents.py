import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.document import Document
from app.db.models.company import Company
from tests.conftest import scalar_first, db_dispatch

DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DUMMY_PROJECT_ID = uuid.uuid4()
DOC_ID = uuid.uuid4()
OTHER_COMPANY_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def make_project(company_id=DUMMY_COMPANY_ID):
    return Project(
        id=DUMMY_PROJECT_ID,
        company_id=company_id,
        created_by=DUMMY_USER_ID,
        name="Тендер",
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def make_document(processing_status="ready", is_current=True):
    return Document(
        id=DOC_ID,
        project_id=DUMMY_PROJECT_ID,
        company_id=DUMMY_COMPANY_ID,
        uploaded_by=DUMMY_USER_ID,
        filename="tz.pdf",
        file_size_bytes=1024,
        mime_type="application/pdf",
        storage_path=f"tender-documents/{DOC_ID}/source.pdf",
        processing_status=processing_status,
        version=1,
        is_current=is_current,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _other_company():
    return Project(
        id=DUMMY_PROJECT_ID,
        company_id=OTHER_COMPANY_ID,
        created_by=DUMMY_USER_ID,
        name="Чужой",
        status="draft",
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


def _user():
    return User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")


@pytest.mark.asyncio
async def test_upload_document_201_and_pipeline_dispatched():
    db = AsyncMock()
    db.get = AsyncMock(return_value=Company(id=DUMMY_COMPANY_ID, name="Тест", plan="enterprise"))
    user = _user()

    with patch("app.api.v1.endpoints.documents.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()) as mock_proj, \
         patch("app.api.v1.endpoints.documents.DocumentService.create_document",
               new_callable=AsyncMock, return_value=make_document()) as mock_create:
        async for client in _make_client(db, user):
            files = {"file": ("tz.pdf", b"%PDF-1.4 mock", "application/pdf")}
            resp = await client.post(f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents", files=files)

    assert resp.status_code == 201
    assert resp.json()["id"] == str(DOC_ID)
    mock_create.assert_awaited_once()
    mock_proj.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_document_foreign_project_404():
    db = AsyncMock()
    user = _user()

    with patch("app.api.v1.endpoints.documents.ProjectService.get_project",
               new_callable=AsyncMock, return_value=_other_company()) as mock_proj, \
         patch("app.api.v1.endpoints.documents.DocumentService.create_document",
               new_callable=AsyncMock) as mock_create:
        async for client in _make_client(db, user):
            files = {"file": ("tz.pdf", b"%PDF-1.4 mock", "application/pdf")}
            resp = await client.post(f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents", files=files)

    assert resp.status_code == 404
    mock_create.assert_not_awaited()
    mock_proj.assert_awaited_once()


@pytest.mark.asyncio
async def test_document_status_200():
    db = db_dispatch({"documents": make_document(processing_status="ready")})
    user = _user()

    with patch("app.api.v1.endpoints.documents.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()):
        async for client in _make_client(db, user):
            resp = await client.get(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/{DOC_ID}/status"
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["processing_status"] == "ready"
    assert body["filename"] == "tz.pdf"


@pytest.mark.asyncio
async def test_document_status_not_found_404():
    db = db_dispatch({"documents": None})
    user = _user()

    with patch("app.api.v1.endpoints.documents.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()):
        async for client in _make_client(db, user):
            resp = await client.get(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/{DOC_ID}/status"
            )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_204_and_promotes_next():
    doc = make_document(is_current=True)
    calls = {"n": 0}

    def docs_entry(stmt):
        calls["n"] += 1
        return scalar_first(doc if calls["n"] == 1 else None)

    db = db_dispatch({"documents": docs_entry})
    user = _user()

    with patch("app.api.v1.endpoints.documents.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()), \
         patch("app.api.v1.endpoints.documents.DocumentService.delete_from_storage",
               new_callable=AsyncMock) as mock_del:
        async for client in _make_client(db, user):
            resp = await client.delete(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/{DOC_ID}"
            )

    assert resp.status_code == 204
    assert mock_del.await_count == 1


@pytest.mark.asyncio
async def test_delete_document_processing_conflict_409():
    db = db_dispatch({"documents": make_document(processing_status="processing")})
    user = _user()

    with patch("app.api.v1.endpoints.documents.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()):
        async for client in _make_client(db, user):
            resp = await client.delete(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/{DOC_ID}"
            )

    assert resp.status_code == 409
    assert "being processed" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_delete_document_foreign_project_404():
    db = AsyncMock()
    user = _user()

    with patch("app.api.v1.endpoints.documents.ProjectService.get_project",
               new_callable=AsyncMock, return_value=_other_company()):
        async for client in _make_client(db, user):
            resp = await client.delete(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/{DOC_ID}"
            )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_documents_current_200():
    db = AsyncMock()
    user = _user()

    with patch("app.api.v1.endpoints.documents.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()), \
         patch("app.api.v1.endpoints.documents.DocumentService.get_current_documents",
               new_callable=AsyncMock,
               return_value=[make_document(), make_document(is_current=False)]) as mock_cur:
        async for client in _make_client(db, user):
            resp = await client.get(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/current"
            )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["filename"] == "tz.pdf"
    assert body[0]["is_current"] is True
    mock_cur.assert_awaited_once()


@pytest.mark.asyncio
async def test_documents_current_foreign_project_404():
    db = AsyncMock()
    user = _user()

    with patch("app.api.v1.endpoints.documents.ProjectService.get_project",
               new_callable=AsyncMock, return_value=_other_company()), \
         patch("app.api.v1.endpoints.documents.DocumentService.get_current_documents",
               new_callable=AsyncMock) as mock_cur:
        async for client in _make_client(db, user):
            resp = await client.get(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/current"
            )

    assert resp.status_code == 404
    mock_cur.assert_not_awaited()


@pytest.mark.asyncio
async def test_documents_history_200():
    db = AsyncMock()
    user = _user()

    with patch("app.api.v1.endpoints.documents.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()), \
         patch("app.api.v1.endpoints.documents.DocumentService.get_document_history",
               new_callable=AsyncMock,
               return_value=[make_document(is_current=False), make_document()]) as mock_hist:
        async for client in _make_client(db, user):
            resp = await client.get(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/history"
            )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["version"] == 1
    mock_hist.assert_awaited_once()


@pytest.mark.asyncio
async def test_documents_history_foreign_project_404():
    db = AsyncMock()
    user = _user()

    with patch("app.api.v1.endpoints.documents.ProjectService.get_project",
               new_callable=AsyncMock, return_value=_other_company()), \
         patch("app.api.v1.endpoints.documents.DocumentService.get_document_history",
               new_callable=AsyncMock) as mock_hist:
        async for client in _make_client(db, user):
            resp = await client.get(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/history"
            )

    assert resp.status_code == 404
    mock_hist.assert_not_awaited()