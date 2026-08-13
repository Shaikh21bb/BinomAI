import pytest
import os
import tempfile
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.parsers import DocumentParser
from app.tasks.document_tasks import process_document_async

# --- Parser Tests ---
def test_clean_text():
    raw = "This   is  a test.\n\n\nToo many lines.\nWord-\nbroken."
    cleaned = DocumentParser.clean_text(raw)
    assert "This is a test." in cleaned
    assert "Wordbroken" in cleaned
    assert "\n\n\n" not in cleaned

def test_extract_metadata():
    text = (
        "Техническая спецификация № 123-А\n"
        "г. Астана\n"
        "от 15.03.2024\n"
        "Общие требования к поставке товаров..."
    )
    meta = DocumentParser.extract_metadata(text)
    assert meta["title"] == "Техническая спецификация № 123-А"
    assert meta["number"] == "123-А"
    assert str(meta["date"]) == "2024-03-15"

def test_extract_metadata_empty():
    assert DocumentParser.extract_metadata("") == {}
    assert DocumentParser.extract_metadata("   \n\n  ") == {}

def test_extract_metadata_iso_date():
    text = "Документ от 2024-05-02, номер N 4567"
    meta = DocumentParser.extract_metadata(text)
    assert meta["number"] == "4567"
    assert str(meta["date"]) == "2024-05-02"

def test_detect_language():
    assert DocumentParser.detect_language("Это русский текст о поставке товаров") == "ru"
    assert DocumentParser.detect_language("This is English tender text") == "en"
    assert DocumentParser.detect_language("Бұл қазақ тіліндегі мәтін, тендер туралы ақпарат") == "kk"
    assert DocumentParser.detect_language("") is None
    assert DocumentParser.detect_language("12345 ### +++") is None

def test_chunk_text():
    text = "A" * 2000
    chunks = DocumentParser.chunk_text(text, chunk_size=1000, overlap=200)
    assert len(chunks) > 1
    assert chunks[0]["char_length"] == 1000
    assert chunks[1]["char_length"] > 0

# --- Task Tests ---
@pytest.fixture
def mock_supabase_storage():
    with patch("app.tasks.document_tasks.supabase_admin.get_client") as mock:
        yield mock

@pytest.mark.asyncio
async def test_process_document_success(mock_db_session, mock_supabase_storage):
    # Setup mock document
    mock_doc = MagicMock()
    mock_doc.id = "123e4567-e89b-12d3-a456-426614174000"
    mock_doc.mime_type = "application/pdf"
    mock_doc.storage_path = "test/path.pdf"
    
    # Mock DB select
    mock_result = MagicMock()
    mock_result.scalars().first.side_effect = [mock_doc, None] # doc then proj
    mock_db_session.execute.return_value = mock_result
    
    # Mock Supabase get
    mock_response = AsyncMock()
    mock_response.status_code = 200
    
    # Mock upload responses (txt + chunks)
    mock_upload = AsyncMock()
    mock_upload.status_code = 200
    
    # Minimal valid PDF bytes (magic number) to pass PyMuPDF open, or mock parser
    with patch("app.core.parsers.DocumentParser.extract_from_pdf", return_value="Test extracted text"), \
         patch("app.tasks.document_tasks.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_db_session
        mock_client_instance = mock_supabase_storage.return_value.__aenter__.return_value
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.post.return_value = mock_upload
        mock_client_instance.headers = {"apikey": "test", "Authorization": "Bearer test", "Content-Type": "application/json"}
        
        mock_task = MagicMock()
        
        result = await process_document_async(mock_task, str(mock_doc.id))
        
        assert result["status"] == "success"
        assert mock_doc.processing_status == "ready"
        assert mock_doc.token_count > 0
        assert mock_task.update_state.call_count >= 4
