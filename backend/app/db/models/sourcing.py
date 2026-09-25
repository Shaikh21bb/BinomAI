import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourcingPlan(Base):
    """Project-level commercial assumptions for supplier comparison."""

    __tablename__ = "sourcing_plans"
    __table_args__ = (UniqueConstraint("project_id", name="uq_sourcing_plans_project"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_margin_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="15"
    )
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="KZT")


class SupplierOffer(Base):
    """A supplier quote row. Original values are retained beside normalized values."""

    __tablename__ = "supplier_offers"
    __table_args__ = (
        Index(
            "uq_supplier_offers_selected_item",
            "item_id",
            unique=True,
            postgresql_where=text("is_selected AND item_id IS NOT NULL"),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("product_search_items.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("public.users.id"), nullable=False
    )

    supplier_name: Mapped[str] = mapped_column(String(500), nullable=False)
    supplier_bin: Mapped[Optional[str]] = mapped_column(String(12))
    supplier_contact: Mapped[Optional[str]] = mapped_column(String(500))

    original_item_name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_item_name: Mapped[Optional[str]] = mapped_column(String(500))
    original_unit: Mapped[Optional[str]] = mapped_column(String(80))
    normalized_unit: Mapped[Optional[str]] = mapped_column(String(30))

    quoted_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default="1"
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="KZT")
    exchange_rate_to_kzt: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    vat_included: Mapped[Optional[bool]] = mapped_column(Boolean)
    vat_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    moq: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    available_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    delivery_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer)
    warranty_months: Mapped[Optional[int]] = mapped_column(Integer)
    certificates: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    characteristics: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    compliance_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="unknown", index=True
    )
    compliance_notes: Mapped[Optional[str]] = mapped_column(Text)
    quote_date: Mapped[Optional[date]] = mapped_column(Date)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)

    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="manual"
    )
    source_filename: Mapped[Optional[str]] = mapped_column(String(500))
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    match_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="matched", index=True
    )
    match_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))

    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    selection_note: Mapped[Optional[str]] = mapped_column(Text)
