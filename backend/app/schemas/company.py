from typing import Optional
from pydantic import BaseModel, ConfigDict
import uuid
from datetime import datetime

class CompanyBase(BaseModel):
    name: str
    bin_iin: Optional[str] = None
    legal_address: Optional[str] = None
    actual_address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    specialization: Optional[str] = None
    description: Optional[str] = None
    founded_year: Optional[int] = None
    employee_count: Optional[int] = None
    director_name: Optional[str] = None
    director_title: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_bik: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(CompanyBase):
    name: Optional[str] = None

class CompanyResponse(CompanyBase):
    id: uuid.UUID
    plan: str
    plan_expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
