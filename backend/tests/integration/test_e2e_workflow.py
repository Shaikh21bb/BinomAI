import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.models.user import User

DUMMY_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

@pytest.fixture
async def async_client():
    async def override_get_db():
        fake_project = MagicMock()
        fake_project.company_id = DUMMY_COMPANY_ID
        mock_result = MagicMock()
        mock_result.scalars().first.return_value = fake_project
        session = AsyncMock()
        session.execute.return_value = mock_result
        session.get = AsyncMock(return_value=MagicMock(plan="enterprise"))
        yield session
    async def override_get_current_user():
        return User(
            id=DUMMY_USER_ID, company_id=DUMMY_COMPANY_ID, role="admin"
        )
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()

def fake_document(mime_type="application/pdf"):
    doc = MagicMock()
    doc.id = str(uuid.uuid4())
    doc.company_id = DUMMY_COMPANY_ID
    doc.mime_type = mime_type
    doc.storage_path = f"tender-documents/{doc.id}/source.pdf"
    return doc

@pytest.mark.asyncio
async def test_end_to_end_workflow(async_client):
    """Simulates the E2E flow: create project, upload document, process pipeline."""
    from app.db.models.project import Project
    from datetime import datetime

    project = Project(
        id=uuid.uuid4(),
        company_id=DUMMY_COMPANY_ID,
        created_by=DUMMY_USER_ID,
        name="Test Tender",
        status="draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    with patch("app.services.project_service.project_repo") as mock_repo:
        mock_repo.create = AsyncMock(return_value=project)

        resp = await async_client.post("/api/v1/projects/", json={"name": "Test Tender"})
        assert resp.status_code == 201, f"Create project failed: {resp.text}"
        project_id = resp.json()["id"]

    # 2. Upload document (mock storage upload + celery delay)
    from datetime import datetime
    from app.db.models.document import Document

    doc_id = uuid.uuid4()
    uploaded = Document(
        id=doc_id,
        project_id=project.id,
        company_id=DUMMY_COMPANY_ID,
        uploaded_by=DUMMY_USER_ID,
        filename="test.pdf",
        file_size_bytes=len(b"Mock PDF Content"),
        mime_type="application/pdf",
        storage_path=f"tender-documents/{doc_id}/source.pdf",
        processing_status="processing",
        version=1,
        is_current=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    with patch("app.services.document_service.supabase_admin.get_client") as mock_storage, \
         patch("app.api.v1.endpoints.documents.DocumentService.create_document",
               new_callable=AsyncMock, return_value=uploaded) as mock_create, \
         patch("app.tasks.document_tasks.process_document.delay") as mock_delay:
        inst = mock_storage.return_value.__aenter__.return_value
        inst.headers = {"apikey": "test", "Authorization": "Bearer test", "Content-Type": "application/json"}

        files = {"file": ("test.pdf", b"Mock PDF Content", "application/pdf")}
        resp = await async_client.post(f"/api/v1/projects/{project_id}/documents", files=files)
        assert resp.status_code in (200, 201), f"Upload failed: {resp.text}"
        document_id = resp.json()["id"]
        assert mock_create.called

    # 3. Simulate Celery execution: process_document_async
    from app.tasks.document_tasks import process_document_async

    db_mock = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars().first.side_effect = [uploaded, project]
    db_mock.execute.return_value = result_mock

    with patch("app.core.parsers.DocumentParser.extract_from_pdf", return_value="Test extracted text"), \
         patch("app.tasks.document_tasks.async_session_factory") as mock_factory, \
         patch("app.tasks.analysis_tasks.run_analysis_task.delay") as mock_analysis_delay, \
         patch("app.tasks.document_tasks.supabase_admin.get_client") as mock_storage:
        mock_factory.return_value.__aenter__.return_value = db_mock
        inst = mock_storage.return_value.__aenter__.return_value
        inst.headers = {"apikey": "test", "Authorization": "Bearer test"}
        inst.get.return_value = AsyncMock(status_code=200)
        inst.post.return_value = AsyncMock(status_code=200)

        mock_task = MagicMock()
        result = await process_document_async(mock_task, str(uploaded.id))
        assert result["status"] == "success"
        mock_analysis_delay.assert_called_once()

    # 4. Simulate Celery execution: run_analysis_async
    from app.tasks.analysis_tasks import run_analysis_async
    from app.schemas.analysis import TenderAnalysisOutput

    analysis = TenderAnalysisOutput(
        executive_summary="E2E Success",
        tender_type="Construction",
        complexity_level="medium",
        estimated_duration_days=30,
        technical_requirements=[],
        commercial_requirements=[],
        legal_requirements=[],
        required_documents=[],
        key_deadlines=[],
        risks=[],
        missing_info_from_tender=[],
        missing_company_data=[],
    )

    db_mock2 = AsyncMock()
    result_mock2 = MagicMock()
    company = MagicMock()
    company.name = "Test Company"
    result_mock2.scalars().first.side_effect = [company, project]
    db_mock2.execute.return_value = result_mock2

    with patch("app.tasks.analysis_tasks.async_session_factory") as mock_factory, \
         patch("app.ai.analysis_agent.AnalysisAgent.run_analysis", new_callable=AsyncMock) as mock_generate:
        mock_factory.return_value.__aenter__.return_value = db_mock2
        mock_generate.return_value = (analysis, {"model": "mock", "latency_ms": 1})

        mock_task = MagicMock()
        result = await run_analysis_async(mock_task, str(project.id), str(uploaded.id), str(DUMMY_COMPANY_ID))
        assert result["status"] == "success"
        assert result["analysis_id"]
