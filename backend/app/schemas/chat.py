from typing import Optional, Dict, Any, List
import uuid
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    message_type: str = "text"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatReplyRequest(BaseModel):
    content: str


class ChatSessionOut(BaseModel):
    is_complete: bool
    message_count: int
    clarification_context: Dict[str, Any] = {}


class ChatThreadOut(BaseModel):
    messages: List[ChatMessageOut]
    session: ChatSessionOut


class ChatReplyOut(BaseModel):
    assistant_message: ChatMessageOut
    session_status: ChatSessionOut


class ChatReplyOutput(BaseModel):
    """Structured reply produced by the AI agent.

    `message_field` — the clarification field the *user message* answers
    (classified by content: experience/price/deadline_plan/licenses), None if not.
    """

    text: str
    message_field: Optional[str] = None
    is_complete: bool = False