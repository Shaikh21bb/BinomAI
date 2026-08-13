from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field
import uuid
from datetime import datetime


class ProductSearchItemResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    company_id: uuid.UUID
    product_name: str
    specs: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    source_section: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    results: List[Any] = Field(default_factory=list)
    best_match: Optional[dict] = None
    search_region: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
