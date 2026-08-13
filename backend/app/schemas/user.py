from typing import Optional
from pydantic import BaseModel, ConfigDict
import uuid
from datetime import datetime

class UserBase(BaseModel):
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    language: str = "ru"
    timezone: str = "Asia/Almaty"
    email_notifications: bool = True

class UserCreate(UserBase):
    id: uuid.UUID
    company_id: uuid.UUID
    role: str = "user"

class UserUpdate(UserBase):
    pass

class UserResponse(UserBase):
    id: uuid.UUID
    company_id: uuid.UUID
    role: str
    onboarding_completed: bool
    last_login_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UserProfileResponse(UserResponse):
    email: str = ""
    company_name: str = ""

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class NotificationsUpdate(BaseModel):
    email_notifications: bool
