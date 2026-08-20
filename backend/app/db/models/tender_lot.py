import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Text, ForeignKey, DateTime, Numeric, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TenderLot(Base):
    """A procurement lot watched by a company (source: public portal pages)."""

    __tablename__ = "tender_lots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_host: Mapped[str] = mapped_column(String(255), nullable=False)
    lot_number: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    name: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)

    customer_name: Mapped[Optional[str]] = mapped_column(String(500))
    customer_bin: Mapped[Optional[str]] = mapped_column(String(12))
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    status: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    prev_status: Mapped[Optional[str]] = mapped_column(String(255))
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 0 = not warned, 1 = warned about 3 days left, 2 = 1 day left, 3 = deadline passed
    deadline_warn_level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    last_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
