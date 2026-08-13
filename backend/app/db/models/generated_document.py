from typing import Optional
import uuid
from sqlalchemy import String, Text, Integer, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)

    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    content_md: Mapped[Optional[str]] = mapped_column(Text)
    content_html: Mapped[Optional[str]] = mapped_column(Text)

    generation_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="generating")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    llm_model: Mapped[Optional[str]] = mapped_column(String(255))

    exported_formats: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")