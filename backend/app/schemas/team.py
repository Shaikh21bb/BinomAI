from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
import uuid

class MemberResponse(BaseModel):
    id: uuid.UUID
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    job_title: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    last_login_at: Optional[datetime] = None

class MemberRoleUpdate(BaseModel):
    role: Literal["member", "limited"]
