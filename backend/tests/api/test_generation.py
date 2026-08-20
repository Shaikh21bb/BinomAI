import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.company import Company
from app.db.models.generated_document import GeneratedDocument
from app.services.generation_service import GenerationService
from tests.conftest import db_dispatch

DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DUMMY_PROJECT_ID = uuid.uuid4()


def make_project(status="clarifying"):
    return Project(
        id=DUMMY_PROJECT_ID,
        company_id=DUMMY_COMPANY_ID,
        created_by=DUMMY_USER_ID,
        name="Тендер",
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def make_company():
    return Company(id=DUMMY_COMPANY_ID, name="ТОО Тест")


def make_gendoc(generation_status="ready", exported_formats=None):
    return GeneratedDocument(
        id=uuid.uuid4(),
        project_id=DUMMY_PROJECT_ID,
        company_id=DUMMY_COMPANY_ID,
        doc_type="tech_spec",
        version=1,
        title="Техническая спецификация",
        content_md="# Спецификация",
        content_html="<h1>Спецификация</h1>",
        generation_status=generation_status,
        exported_formats=exported_formats,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def scalar_first(obj):
    r = MagicMock()
    r.scalars.return_value.first.return_value = obj
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
async def test_generate_returns_document():
    db = db_dispatch({"companies": make_company()})
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")
    gendoc = make_gendoc(generation_status="generating")

    with patch("app.api.v1.endpoints.generation.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()), \
         patch.object(GenerationService, "ensure_pending", new_callable=AsyncMock,
                      return_value=gendoc) as mock_ensure:
        async for client in _make_client(db, user):
            resp = await client.post(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/generate",
                json={"doc_type": "tech_spec"},
            )

    assert resp.status_code == 200
    assert resp.json()["generation_status"] == "generating"
    mock_ensure.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_invalid_doc_type_422():
    db = AsyncMock()
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    async for client in _make_client(db, user):
        resp = await client.post(
            f"/api/v1/projects/{DUMMY_PROJECT_ID}/generate",
            json={"doc_type": "invoice"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_company_missing_404():
    db = db_dispatch({"companies": None})
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    with patch("app.api.v1.endpoints.generation.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()):
        async for client in _make_client(db, user):
            resp = await client.post(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/generate",
                json={"doc_type": "cover_letter"},
            )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_generated_documents():
    db = AsyncMock()
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    with patch("app.api.v1.endpoints.generation.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()), \
         patch.object(GenerationService, "list_generated", new_callable=AsyncMock,
                      return_value=[make_gendoc()]) as mock_list:
        async for client in _make_client(db, user):
            resp = await client.get(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/generated"
            )

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["exported_formats"] == []
    mock_list.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_generated_documents_legacy_null_exported_formats():
    db = AsyncMock()
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    with patch("app.api.v1.endpoints.generation.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()), \
         patch.object(GenerationService, "list_generated", new_callable=AsyncMock,
                      return_value=[make_gendoc(exported_formats=None)]):
        async for client in _make_client(db, user):
            resp = await client.get(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/generated"
            )

    assert resp.status_code == 200
    assert resp.json()[0]["exported_formats"] == []


@pytest.mark.asyncio
async def test_get_generated_content_ready_200():
    db = AsyncMock()
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")
    gendoc = make_gendoc(generation_status="ready")

    with patch("app.api.v1.endpoints.generation.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()), \
         patch.object(GenerationService, "get_latest", new_callable=AsyncMock,
                      return_value=gendoc):
        async for client in _make_client(db, user):
            resp = await client.get(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/generated/tech_spec/content"
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["content_md"] == "# Спецификация"


@pytest.mark.asyncio
async def test_get_generated_content_not_ready_404():
    db = AsyncMock()
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    with patch("app.api.v1.endpoints.generation.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()), \
         patch.object(GenerationService, "get_latest", new_callable=AsyncMock,
                      return_value=make_gendoc(generation_status="failed")):
        async for client in _make_client(db, user):
            resp = await client.get(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/generated/tech_spec/content"
            )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_returns_attachment():
    db = AsyncMock()
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    with patch("app.api.v1.endpoints.generation.ProjectService.get_project",
               new_callable=AsyncMock, return_value=make_project()), \
         patch.object(GenerationService, "export", new_callable=AsyncMock,
                      return_value=(b"PK\x03\x04mock", "tech_spec.docx",
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document")) as mock_export:
        async for client in _make_client(db, user):
            resp = await client.post(
                f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/generated/tech_spec/export",
                json={"format": "docx"},
            )

    assert resp.status_code == 200
    assert resp.content == b"PK\x03\x04mock"
    assert "attachment" in resp.headers["content-disposition"]
    assert "tech_spec.docx" in resp.headers["content-disposition"]
    mock_export.assert_awaited_once()


@pytest.mark.asyncio
async def test_export_invalid_format_422():
    db = AsyncMock()
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    async for client in _make_client(db, user):
        resp = await client.post(
            f"/api/v1/projects/{DUMMY_PROJECT_ID}/documents/generated/tech_spec/export",
            json={"format": "xls"},
        )

    assert resp.status_code == 422