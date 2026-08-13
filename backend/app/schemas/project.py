from typing import Optional, List
from pydantic import BaseModel, ConfigDict
import uuid
from datetime import datetime

class ProjectBase(BaseModel):
    name: str
    customer_name: Optional[str] = None
    customer_bin: Optional[str] = None
    deadline_at: Optional[datetime] = None
    submission_at: Optional[datetime] = None
    tender_type: Optional[str] = None
    tender_number: Optional[str] = None
    complexity: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    name: Optional[str] = None
    status: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: uuid.UUID
    company_id: uuid.UUID
    created_by: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
