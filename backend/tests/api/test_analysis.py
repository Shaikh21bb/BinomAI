import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.document import Document

DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DUMMY_PROJECT_ID = uuid.uuid4()
DOC_ID = uuid.uuid4()


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


def make_document(processing_status="ready"):
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
        is_current=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def scalar_first(obj):
    r = MagicMock()
    r.scalars.return_value.first.return_value = obj
    return r


def mapping_first(obj):
    r = MagicMock()
    r.mappings.return_value.first.return_value = obj
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
async def test_get_analysis_results_200():
    row = {
        "id": str(uuid.uuid4()),
        "status": "completed",
        "is_current": True,
        "executive_summary": "Краткое резюме",
    }
    db = AsyncMock()
    db.execute.side_effect = [scalar_first(make_project()), mapping_first(row)]
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    async for client in _make_client(db, user):
        resp = await client.get(f"/api/v1/analysis/{DUMMY_PROJECT_ID}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["is_current"] is True


@pytest.mark.asyncio
async def test_get_analysis_results_foreign_project_404():
    db = AsyncMock()
    db.execute.side_effect = [scalar_first(None)]
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    async for client in _make_client(db, user):
        resp = await client.get(f"/api/v1/analysis/{DUMMY_PROJECT_ID}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_analysis_results_no_active_analysis_404():
    db = AsyncMock()
    db.execute.side_effect = [scalar_first(make_project()), mapping_first(None)]
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    async for client in _make_client(db, user):
        resp = await client.get(f"/api/v1/analysis/{DUMMY_PROJECT_ID}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retry_analysis_ready_202():
    db = AsyncMock()
    db.execute.side_effect = [scalar_first(make_project()), scalar_first(make_document())]
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    with patch("app.api.v1.endpoints.analysis.run_analysis_task.delay") as mock_delay:
        async for client in _make_client(db, user):
            resp = await client.post(f"/api/v1/analysis/{DUMMY_PROJECT_ID}/retry")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    mock_delay.assert_called_once()


@pytest.mark.asyncio
async def test_retry_analysis_no_ready_document_400():
    db = AsyncMock()
    db.execute.side_effect = [
        scalar_first(make_project()),
        scalar_first(make_document(processing_status="processing")),
    ]
    user = User(id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin")

    with patch("app.api.v1.endpoints.analysis.run_analysis_task.delay") as mock_delay:
        async for client in _make_client(db, user):
            resp = await client.post(f"/api/v1/analysis/{DUMMY_PROJECT_ID}/retry")

    assert resp.status_code == 400
    mock_delay.assert_not_called()