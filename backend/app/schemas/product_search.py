from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
import uuid
from datetime import date, datetime


class ProductSearchItemCreate(BaseModel):
    product_name: str = Field(min_length=2, max_length=500)
    specs: Optional[str] = Field(None, max_length=5000)
    unit: Optional[str] = Field(None, max_length=50)
    quantity: Optional[float] = Field(None, gt=0)
    source_section: Optional[str] = Field(None, max_length=255)
    required_certificates: List[str] = Field(default_factory=list, max_length=50)
    warranty_required: bool = False
    desired_delivery_date: Optional[date] = None

    @field_validator("required_certificates")
    @classmethod
    def clean_certificates(cls, value: List[str]) -> List[str]:
        return [item.strip() for item in value if item and item.strip()]


class ProductSearchItemUpdate(BaseModel):
    product_name: Optional[str] = Field(None, min_length=2, max_length=500)
    specs: Optional[str] = Field(None, max_length=5000)
    unit: Optional[str] = Field(None, max_length=50)
    quantity: Optional[float] = Field(None, gt=0)
    required_certificates: Optional[List[str]] = Field(None, max_length=50)
    warranty_required: Optional[bool] = None
    desired_delivery_date: Optional[date] = None


class ProductSearchItemResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    company_id: uuid.UUID
    product_name: str
    specs: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    source_section: Optional[str] = None
    normalized_name: Optional[str] = None
    normalized_unit: Optional[str] = None
    required_certificates: List[str] = Field(default_factory=list)
    warranty_required: bool = False
    desired_delivery_date: Optional[date] = None
    source_type: str = "document"
    is_active: bool = True
    status: str
    error_message: Optional[str] = None
    results: List[Any] = Field(default_factory=list)
    best_match: Optional[dict] = None
    search_region: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("required_certificates", mode="before")
    @classmethod
    def default_certificates(cls, value):
        return value or []

    @field_validator("warranty_required", "is_active", mode="before")
    @classmethod
    def default_bools(cls, value, info):
        if value is not None:
            return value
        return info.field_name == "is_active"

    @field_validator("source_type", mode="before")
    @classmethod
    def default_source_type(cls, value):
        return value or "document"

    model_config = ConfigDict(from_attributes=True)
