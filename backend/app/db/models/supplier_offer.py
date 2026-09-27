from datetime import date
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SupplierOffer(Base):
    """A supplier quote line. Source values remain intact for audit/review."""

    __tablename__ = "supplier_offers"
    __table_args__ = (
        CheckConstraint(
            "unit_price IS NOT NULL OR total_price IS NOT NULL",
            name="supplier_offers_price_present",
        ),
        CheckConstraint(
            "(unit_price IS NULL OR unit_price >= 0) AND (total_price IS NULL OR total_price >= 0)",
            name="supplier_offers_nonnegative_price",
        ),
        Index(
            "uq_supplier_offer_selected_item",
            "product_item_id",
            unique=True,
            postgresql_where=text("is_selected = true AND product_item_id IS NOT NULL"),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("product_search_items.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("public.users.id"), nullable=False
    )

    supplier_name: Mapped[str] = mapped_column(String(500), nullable=False)
    supplier_bin: Mapped[Optional[str]] = mapped_column(String(12))
    supplier_contact: Mapped[Optional[str]] = mapped_column(String(500))
    supplier_sku: Mapped[Optional[str]] = mapped_column(String(255))

    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    quoted_unit: Mapped[Optional[str]] = mapped_column(String(50))
    offered_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    unit_conversion_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    total_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="KZT")
    exchange_rate_to_kzt: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    exchange_rate_date: Mapped[Optional[date]] = mapped_column(Date)

    vat_included: Mapped[Optional[bool]] = mapped_column(Boolean)
    vat_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3))
    min_order_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    availability_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="unknown"
    )
    available_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    delivery_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    delivery_days: Mapped[Optional[int]] = mapped_column(Integer)
    warranty_months: Mapped[Optional[int]] = mapped_column(Integer)
    certificates: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    specification_compliant: Mapped[Optional[bool]] = mapped_column(Boolean)
    compliance_notes: Mapped[Optional[str]] = mapped_column(Text)

    quote_date: Mapped[Optional[date]] = mapped_column(Date)
    price_valid_until: Mapped[Optional[date]] = mapped_column(Date)
    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="manual"
    )
    source_reference: Mapped[Optional[str]] = mapped_column(Text)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    match_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="confirmed"
    )
    match_candidates: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_selected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )


class SourcingSettings(Base):
    __tablename__ = "sourcing_settings"
    __table_args__ = (
        CheckConstraint(
            "target_margin_percent >= 0 AND target_margin_percent < 100",
            name="sourcing_margin_range",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("public.users.id"), nullable=False
    )
    target_margin_percent: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), nullable=False, server_default="15"
    )
    base_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="KZT"
    )
