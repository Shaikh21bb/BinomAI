from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator
import uuid
from datetime import datetime

class GeneratedDocumentResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    doc_type: str
    version: int
    title: str
    generation_status: str
    error_message: Optional[str] = None
    llm_model: Optional[str] = None
    exported_formats: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("exported_formats", mode="before")
    @classmethod
    def _coerce_none_exported_formats(cls, v):
        return v or []

class GenerateRequest(BaseModel):
    doc_type: str = Field(pattern="^(commercial_proposal|tech_spec|cover_letter)$")

class GenerateResponse(GeneratedDocumentResponse):
    content_md: Optional[str] = None
    content_html: Optional[str] = None

class ExportRequest(BaseModel):
    format: str = Field(pattern="^(docx|pdf)$")

class GeneratedContent(BaseModel):
    title: str = "Документ"
    content_md: str = ""