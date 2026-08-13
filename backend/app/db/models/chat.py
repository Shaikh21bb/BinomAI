from typing import Optional, Dict, Any
import uuid
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    context: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="text")