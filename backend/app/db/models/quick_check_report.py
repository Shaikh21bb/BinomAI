"""Saved results of a quick PDF check; the source PDF is not retained."""

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuickCheckReport(Base):
    __tablename__ = "quick_check_reports"
    __table_args__ = (
        CheckConstraint("page_count BETWEEN 1 AND 60", name="quick_check_reports_page_count_check"),
        CheckConstraint("ocr_pages BETWEEN 0 AND 12", name="quick_check_reports_ocr_pages_check"),
        CheckConstraint("total_items >= 0", name="quick_check_reports_total_items_check"),
        CheckConstraint(
            "processing_state IN ('pending', 'queued', 'running', 'completed', 'error')",
            name="quick_check_reports_processing_state_check",
        ),
        Index("idx_quick_check_reports_owner_created", "created_by", "created_at"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr_pages: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_items: Mapped[int] = mapped_column(Integer, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    items: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    processing_state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default=text("'pending'"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
