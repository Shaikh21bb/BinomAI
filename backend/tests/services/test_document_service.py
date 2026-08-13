import pytest
from unittest.mock import AsyncMock
from fastapi import UploadFile
from app.services.document_service import DocumentService
from fastapi.exceptions import HTTPException
import uuid

@pytest.mark.asyncio
async def test_validate_file_size_exceeded():
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.size = 100 * 1024 * 1024 # 100MB
    mock_file.content_type = "application/pdf"
    
    with pytest.raises(HTTPException) as exc_info:
        await DocumentService.validate_file(mock_file)
        
    assert exc_info.value.status_code == 413
    assert "exceeds maximum allowed size" in exc_info.value.detail

@pytest.mark.asyncio
async def test_validate_file_invalid_mime():
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.size = 10 * 1024 * 1024 # 10MB
    mock_file.content_type = "image/png"
    
    with pytest.raises(HTTPException) as exc_info:
        await DocumentService.validate_file(mock_file)
        
    assert exc_info.value.status_code == 415
    assert "Unsupported file type" in exc_info.value.detail

@pytest.mark.asyncio
async def test_validate_file_success():
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.size = 10 * 1024 * 1024 # 10MB
    mock_file.content_type = "application/pdf"
    
    # Should not raise
    await DocumentService.validate_file(mock_file)
