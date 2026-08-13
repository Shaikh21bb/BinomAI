from typing import List, Optional
from sqlalchemy import String, Boolean, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.db.base import Base

class Company(Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bin_iin: Mapped[Optional[str]] = mapped_column(String(12), unique=True, index=True)
    legal_address: Mapped[Optional[str]] = mapped_column(Text)
    actual_address: Mapped[Optional[str]] = mapped_column(Text)
    
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    
    logo_url: Mapped[Optional[str]] = mapped_column(Text)
    
    specialization: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    founded_year: Mapped[Optional[int]] = mapped_column(Integer)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    
    director_name: Mapped[Optional[str]] = mapped_column(String(255))
    director_title: Mapped[Optional[str]] = mapped_column(String(255))
    bank_name: Mapped[Optional[str]] = mapped_column(String(255))
    bank_account: Mapped[Optional[str]] = mapped_column(String(50))
    bank_bik: Mapped[Optional[str]] = mapped_column(String(20))
    
    plan: Mapped[str] = mapped_column(String(50), nullable=False, server_default="trial")
    plan_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Relationships
    users: Mapped[List["User"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    projects: Mapped[List["Project"]] = relationship(back_populates="company", cascade="all, delete-orphan")
