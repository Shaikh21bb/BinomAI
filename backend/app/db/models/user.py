from typing import Optional
import uuid
from sqlalchemy import String, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.db.base import Base

class User(Base):
    __tablename__ = "users"
    # Overriding standard table arguments to specify schema public (Supabase auth.users is elsewhere)
    __table_args__ = {"schema": "public"}

    # Foreign keys
    # Supabase uses auth.users, but SQLAlchemy doesn't strictly need to model cross-schema FK checks locally if managed by Supabase,
    # however we will keep the standard schema public.users behavior here.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default="user", index=True)
    
    language: Mapped[str] = mapped_column(String(10), nullable=False, server_default="ru")
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, server_default="Asia/Almaty")
    email_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="users")
    projects: Mapped[list["Project"]] = relationship(back_populates="creator")
    documents: Mapped[list["Document"]] = relationship(back_populates="uploader")
