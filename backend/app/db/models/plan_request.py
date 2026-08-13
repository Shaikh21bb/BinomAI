from typing import Optional
import uuid
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PlanRequest(Base):
    """A request from a company to upgrade their subscription plan."""
    __tablename__ = "plan_requests"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("public.users.id"), index=True, nullable=False
    )

    requested_plan: Mapped[str] = mapped_column(String(50), nullable=False)
    current_plan: Mapped[str] = mapped_column(String(50), nullable=False, server_default="trial")
    message: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending", index=True)

    company: Mapped["Company"] = relationship()
    user: Mapped["User"] = relationship()
