import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl


class TenderLotCreate(BaseModel):
    url: str = Field(..., description="Public lot page URL on goszakup.gov.kz or zakupki.sk.kz")


class TenderLotOut(BaseModel):
    id: uuid.UUID
    source_url: str
    source_host: str
    lot_number: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    customer_name: Optional[str] = None
    customer_bin: Optional[str] = None
    amount: Optional[Decimal] = None
    status: Optional[str] = None
    prev_status: Optional[str] = None
    status_changed_at: Optional[datetime] = None
    start_date: Optional[datetime] = None
    deadline_at: Optional[datetime] = None
    last_check_at: Optional[datetime] = None
    next_check_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TenderLotListResponse(BaseModel):
    items: List[TenderLotOut]
    total: int
