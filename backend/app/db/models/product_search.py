from datetime import date
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, ForeignKey, Boolean, Date
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import Float as FloatType
import uuid

from app.db.base import Base

FloatNullable = FloatType


class ProductSearchItem(Base):
    """A product extracted from the tender spec, with market search results."""

    __tablename__ = "product_search_items"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )

    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    specs: Mapped[Optional[str]] = mapped_column(Text)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    quantity: Mapped[Optional[float]] = mapped_column(FloatNullable)
    source_section: Mapped[Optional[str]] = mapped_column(String(255))

    # Normalized values are deliberately stored alongside the source values.
    # The original tender wording is evidence and must never be overwritten by
    # a best-effort normalization.
    normalized_name: Mapped[Optional[str]] = mapped_column(String(500))
    normalized_unit: Mapped[Optional[str]] = mapped_column(String(50))
    required_certificates: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    warranty_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    desired_delivery_date: Mapped[Optional[date]] = mapped_column(Date)
    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="document"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    results: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    best_match: Mapped[Optional[dict]] = mapped_column(JSONB)
    search_region: Mapped[Optional[str]] = mapped_column(String(255))
