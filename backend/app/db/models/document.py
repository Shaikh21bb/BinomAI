from typing import Optional
import uuid
from sqlalchemy import String, Boolean, Text, ForeignKey, BigInteger, Integer, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date

from app.db.base import Base

class Document(Base):
    __tablename__ = "documents"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("public.users.id"), nullable=False)
    
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    
    extracted_text_path: Mapped[Optional[str]] = mapped_column(Text)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    language: Mapped[Optional[str]] = mapped_column(String(10))
    
    processing_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="uploading")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    doc_title: Mapped[Optional[str]] = mapped_column(String(500))
    doc_number: Mapped[Optional[str]] = mapped_column(String(255))
    doc_date: Mapped[Optional[date]] = mapped_column(Date)
    
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="documents")
    company: Mapped["Company"] = relationship()
    uploader: Mapped["User"] = relationship(back_populates="documents")
