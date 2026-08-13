from typing import List, Optional
import uuid
from sqlalchemy import String, Text, ForeignKey, DateTime, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.db.base import Base

class Project(Base):
    __tablename__ = "projects"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("public.users.id"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(500))
    customer_bin: Mapped[Optional[str]] = mapped_column(String(12))
    
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="draft", index=True)
    
    deadline_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    submission_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    tender_type: Mapped[Optional[str]] = mapped_column(String(100))
    tender_number: Mapped[Optional[str]] = mapped_column(String(255))
    complexity: Mapped[Optional[str]] = mapped_column(String(20))
    
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="projects")
    creator: Mapped["User"] = relationship(back_populates="projects")
    documents: Mapped[List["Document"]] = relationship(back_populates="project", cascade="all, delete-orphan")
