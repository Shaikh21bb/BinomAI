from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Literal
import uuid

class InviteCreate(BaseModel):
    max_uses: int = 1
    expires_in_days: int = 30

class InviteResponse(BaseModel):
    id: uuid.UUID
    code: str
    max_uses: int
    uses: int
    expires_at: Optional[datetime]
    active: bool
    created_at: datetime

class UserAdminResponse(BaseModel):
    id: uuid.UUID
    email: Optional[str]
    full_name: Optional[str]
    role: str
    company_id: uuid.UUID
    company_name: Optional[str]
    project_count: int
    created_at: datetime

class RoleUpdate(BaseModel):
    role: str

class CompanyAdminResponse(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    plan_expires_at: Optional[datetime] = None
    user_count: int
    project_count: int
    created_at: datetime

class PlanUpdate(BaseModel):
    plan: str
    plan_expires_at: Optional[datetime] = None

class AdminAccountCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    role: Literal["member", "limited"] = "member"