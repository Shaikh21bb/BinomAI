from typing import Optional
from pydantic import BaseModel, ConfigDict
import uuid
from datetime import datetime, date

class DocumentBase(BaseModel):
    doc_title: Optional[str] = None
    doc_number: Optional[str] = None
    doc_date: Optional[date] = None

class DocumentResponse(DocumentBase):
    id: uuid.UUID
    project_id: uuid.UUID
    company_id: uuid.UUID
    uploaded_by: uuid.UUID
    filename: str
    file_size_bytes: int
    mime_type: str
    storage_path: str
    extracted_text_path: Optional[str]
    page_count: Optional[int]
    token_count: Optional[int]
    language: Optional[str]
    processing_status: str
    error_message: Optional[str]
    version: int
    is_current: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
