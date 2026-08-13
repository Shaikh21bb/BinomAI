from typing import Optional, Literal
from pydantic import BaseModel
from datetime import datetime
import uuid


class PlanLimits(BaseModel):
    max_projects: Optional[int]
    max_users: Optional[int]
    max_documents: Optional[int]
    features: dict


class PlanUsage(BaseModel):
    plan: str
    plan_name: str
    plan_price_monthly_kzt: int
    plan_expires_at: Optional[datetime]
    limits: PlanLimits
    usage: dict


class PlanUpdate(BaseModel):
    plan: str
    plan_expires_at: Optional[datetime] = None


class PlanRequestCreate(BaseModel):
    requested_plan: Literal["starter", "pro", "enterprise"]
    message: Optional[str] = None


class PlanRequestResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    current_plan: str
    requested_plan: str
    message: Optional[str]
    status: str
    created_at: datetime


class PlanRequestStatusUpdate(BaseModel):
    status: Literal["pending", "done", "declined"]
