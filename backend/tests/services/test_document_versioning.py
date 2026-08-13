import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.repositories.document_repo import document_repo
from app.services.document_service import DocumentService


@pytest.fixture
def mock_doc_repo():
    with patch("app.services.document_service.document_repo") as mock:
        yield mock


@pytest.mark.asyncio
async def test_get_document_history_delegates(mock_doc_repo):
    mock_doc_repo.get_all_for_project = AsyncMock(return_value=[MagicMock()])
    db = AsyncMock()

    docs = await DocumentService.get_document_history(db, project_id=uuid.uuid4())

    assert len(docs) == 1
    mock_doc_repo.get_all_for_project.assert_called_once()


@pytest.mark.asyncio
async def test_supersede_previous_marks_docs(mock_db_session):
    old_doc = MagicMock()
    old_doc.is_current = True
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [old_doc]
    mock_db_session.execute.return_value = mock_result

    count = await document_repo.supersede_previous(
        mock_db_session, project_id=uuid.uuid4()
    )

    assert count == 1
    assert old_doc.is_current is False
    mock_db_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_get_max_version_returns_zero_when_empty(mock_db_session):
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = None
    mock_db_session.execute.return_value = mock_result

    version = await document_repo.get_max_version(mock_db_session, project_id=uuid.uuid4())

    assert version == 0
