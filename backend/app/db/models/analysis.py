from typing import Optional
import uuid
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)

    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50))

    executive_summary: Mapped[Optional[str]] = mapped_column(Text)
    tender_type: Mapped[Optional[str]] = mapped_column(String(255))
    complexity_level: Mapped[Optional[str]] = mapped_column(String(50))
    estimated_duration_days: Mapped[Optional[int]] = mapped_column(Integer)

    technical_requirements: Mapped[Optional[list]] = mapped_column(JSONB)
    commercial_requirements: Mapped[Optional[list]] = mapped_column(JSONB)
    legal_requirements: Mapped[Optional[list]] = mapped_column(JSONB)
    required_documents: Mapped[Optional[list]] = mapped_column(JSONB)
    key_deadlines: Mapped[Optional[list]] = mapped_column(JSONB)
    risks: Mapped[Optional[list]] = mapped_column(JSONB)
    missing_info_from_tender: Mapped[Optional[list]] = mapped_column(JSONB)
    missing_company_data: Mapped[Optional[list]] = mapped_column(JSONB)

    llm_model: Mapped[Optional[str]] = mapped_column(String(255))
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)