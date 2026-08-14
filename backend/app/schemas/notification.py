import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    message: Optional[str] = None
    link_url: Optional[str] = None
    is_read: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: List[NotificationOut]
    unread_count: int
