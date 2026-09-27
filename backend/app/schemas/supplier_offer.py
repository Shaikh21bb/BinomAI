from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AvailabilityStatus = Literal["available", "limited", "unavailable", "unknown"]
MatchStatus = Literal["confirmed", "review", "unmatched", "rejected"]
SourceType = Literal["manual", "csv", "discovery"]


class SupplierOfferBase(BaseModel):
    product_item_id: Optional[uuid.UUID] = None
    supplier_name: str = Field(min_length=2, max_length=500)
    supplier_bin: Optional[str] = Field(None, pattern=r"^\d{12}$")
    supplier_contact: Optional[str] = Field(None, max_length=500)
    supplier_sku: Optional[str] = Field(None, max_length=255)
    product_name: str = Field(min_length=2, max_length=500)
    quoted_unit: Optional[str] = Field(None, max_length=50)
    offered_quantity: Optional[Decimal] = Field(None, gt=0)
    unit_conversion_factor: Optional[Decimal] = Field(None, gt=0)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    total_price: Optional[Decimal] = Field(None, ge=0)
    currency: str = Field("KZT", min_length=1, max_length=10)
    exchange_rate_to_kzt: Optional[Decimal] = Field(None, gt=0)
    exchange_rate_date: Optional[date] = None
    vat_included: Optional[bool] = None
    vat_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    min_order_quantity: Optional[Decimal] = Field(None, gt=0)
    availability_status: AvailabilityStatus = "unknown"
    available_quantity: Optional[Decimal] = Field(None, ge=0)
    delivery_cost: Optional[Decimal] = Field(None, ge=0)
    delivery_days: Optional[int] = Field(None, ge=0, le=3650)
    warranty_months: Optional[int] = Field(None, ge=0, le=600)
    certificates: list[str] = Field(default_factory=list, max_length=100)
    specification_compliant: Optional[bool] = None
    compliance_notes: Optional[str] = Field(None, max_length=5000)
    quote_date: Optional[date] = None
    price_valid_until: Optional[date] = None
    source_type: SourceType = "manual"
    source_reference: Optional[str] = Field(None, max_length=2000)
    match_status: MatchStatus = "confirmed"
    notes: Optional[str] = Field(None, max_length=5000)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("certificates")
    @classmethod
    def clean_certificates(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]

    @model_validator(mode="after")
    def validate_price(self):
        if self.unit_price is None and self.total_price is None:
            raise ValueError("Укажите цену за единицу или общую сумму")
        if self.total_price is not None and self.unit_price is None and self.offered_quantity is None:
            raise ValueError("Для общей суммы без цены за единицу укажите объём предложения")
        return self


class SupplierOfferCreate(SupplierOfferBase):
    pass


class SupplierOfferUpdate(BaseModel):
    product_item_id: Optional[uuid.UUID] = None
    supplier_name: Optional[str] = Field(None, min_length=2, max_length=500)
    supplier_bin: Optional[str] = Field(None, pattern=r"^\d{12}$")
    supplier_contact: Optional[str] = Field(None, max_length=500)
    supplier_sku: Optional[str] = Field(None, max_length=255)
    product_name: Optional[str] = Field(None, min_length=2, max_length=500)
    quoted_unit: Optional[str] = Field(None, max_length=50)
    offered_quantity: Optional[Decimal] = Field(None, gt=0)
    unit_conversion_factor: Optional[Decimal] = Field(None, gt=0)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    total_price: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=1, max_length=10)
    exchange_rate_to_kzt: Optional[Decimal] = Field(None, gt=0)
    exchange_rate_date: Optional[date] = None
    vat_included: Optional[bool] = None
    vat_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    min_order_quantity: Optional[Decimal] = Field(None, gt=0)
    availability_status: Optional[AvailabilityStatus] = None
    available_quantity: Optional[Decimal] = Field(None, ge=0)
    delivery_cost: Optional[Decimal] = Field(None, ge=0)
    delivery_days: Optional[int] = Field(None, ge=0, le=3650)
    warranty_months: Optional[int] = Field(None, ge=0, le=600)
    certificates: Optional[list[str]] = Field(None, max_length=100)
    specification_compliant: Optional[bool] = None
    compliance_notes: Optional[str] = Field(None, max_length=5000)
    quote_date: Optional[date] = None
    price_valid_until: Optional[date] = None
    source_type: Optional[SourceType] = None
    source_reference: Optional[str] = Field(None, max_length=2000)
    match_status: Optional[MatchStatus] = None
    notes: Optional[str] = Field(None, max_length=5000)


class SupplierOfferResponse(SupplierOfferBase):
    id: uuid.UUID
    project_id: uuid.UUID
    company_id: uuid.UUID
    created_by: uuid.UUID
    source_payload: dict[str, Any] = Field(default_factory=dict)
    match_candidates: list[dict[str, Any]] = Field(default_factory=list)
    is_selected: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SourcingSettingsUpdate(BaseModel):
    target_margin_percent: Decimal = Field(Decimal("15"), ge=0, lt=100)


class OfferSelectionRequest(BaseModel):
    offer_id: Optional[uuid.UUID] = None


class RFQDraftRequest(BaseModel):
    supplier_name: Optional[str] = Field(None, max_length=500)
    contact_name: Optional[str] = Field(None, max_length=500)
    delivery_address: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = Field(None, max_length=5000)
    item_ids: Optional[list[uuid.UUID]] = None
