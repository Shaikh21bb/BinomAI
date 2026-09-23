import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ComplianceStatus = Literal["compliant", "partial", "noncompliant", "unknown"]
MatchStatus = Literal["matched", "needs_review", "unmatched"]


class TenderLineItemCreate(BaseModel):
    product_name: str = Field(min_length=2, max_length=500)
    specs: Optional[str] = Field(default=None, max_length=5000)
    unit: Optional[str] = Field(default=None, max_length=50)
    quantity: Optional[Decimal] = Field(default=None, gt=0)
    source_section: Optional[str] = Field(default="Ручной ввод", max_length=255)


class TenderLineItemUpdate(BaseModel):
    product_name: Optional[str] = Field(default=None, min_length=2, max_length=500)
    specs: Optional[str] = Field(default=None, max_length=5000)
    unit: Optional[str] = Field(default=None, max_length=50)
    quantity: Optional[Decimal] = Field(default=None, gt=0)


class SupplierOfferBase(BaseModel):
    item_id: Optional[uuid.UUID] = None
    supplier_name: str = Field(min_length=2, max_length=500)
    supplier_bin: Optional[str] = Field(default=None, pattern=r"^\d{12}$")
    supplier_contact: Optional[str] = Field(default=None, max_length=500)
    original_item_name: str = Field(min_length=2, max_length=500)
    original_unit: Optional[str] = Field(default=None, max_length=80)
    quoted_quantity: Optional[Decimal] = Field(default=None, ge=0)
    unit_price: Decimal = Field(ge=0)
    price_quantity: Decimal = Field(default=Decimal("1"), gt=0)
    currency: str = Field(default="KZT", min_length=3, max_length=3)
    exchange_rate_to_kzt: Optional[Decimal] = Field(default=None, gt=0)
    vat_included: Optional[bool] = None
    vat_rate: Optional[Decimal] = Field(default=None, ge=0, le=100)
    moq: Optional[Decimal] = Field(default=None, ge=0)
    available_quantity: Optional[Decimal] = Field(default=None, ge=0)
    delivery_cost: Optional[Decimal] = Field(default=None, ge=0)
    lead_time_days: Optional[int] = Field(default=None, ge=0, le=3650)
    warranty_months: Optional[int] = Field(default=None, ge=0, le=1200)
    certificates: list[str] = Field(default_factory=list, max_length=100)
    characteristics: dict[str, str] = Field(default_factory=dict)
    compliance_status: ComplianceStatus = "unknown"
    compliance_notes: Optional[str] = Field(default=None, max_length=5000)
    quote_date: Optional[date] = None
    valid_until: Optional[date] = None
    source_url: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> str:
        text = str(value).strip().upper()
        aliases = {"ТГ": "KZT", "ТЕНГЕ": "KZT", "₸": "KZT", "$": "USD", "€": "EUR"}
        normalized = aliases.get(text, text)
        if len(normalized) != 3:
            raise ValueError("Use a three-letter currency code such as KZT, USD or EUR")
        return normalized

    @model_validator(mode="after")
    def validate_vat(self):
        if self.vat_included is False and self.vat_rate is None:
            raise ValueError("vat_rate is required when VAT is not included")
        if self.valid_until and self.quote_date and self.valid_until < self.quote_date:
            raise ValueError("valid_until cannot be before quote_date")
        return self


class SupplierOfferCreate(SupplierOfferBase):
    pass


class SupplierOfferUpdate(BaseModel):
    item_id: Optional[uuid.UUID] = None
    supplier_name: Optional[str] = Field(default=None, min_length=2, max_length=500)
    supplier_bin: Optional[str] = Field(default=None, pattern=r"^\d{12}$")
    supplier_contact: Optional[str] = Field(default=None, max_length=500)
    original_item_name: Optional[str] = Field(default=None, min_length=2, max_length=500)
    original_unit: Optional[str] = Field(default=None, max_length=80)
    quoted_quantity: Optional[Decimal] = Field(default=None, ge=0)
    unit_price: Optional[Decimal] = Field(default=None, ge=0)
    price_quantity: Optional[Decimal] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    exchange_rate_to_kzt: Optional[Decimal] = Field(default=None, gt=0)
    vat_included: Optional[bool] = None
    vat_rate: Optional[Decimal] = Field(default=None, ge=0, le=100)
    moq: Optional[Decimal] = Field(default=None, ge=0)
    available_quantity: Optional[Decimal] = Field(default=None, ge=0)
    delivery_cost: Optional[Decimal] = Field(default=None, ge=0)
    lead_time_days: Optional[int] = Field(default=None, ge=0, le=3650)
    warranty_months: Optional[int] = Field(default=None, ge=0, le=1200)
    certificates: Optional[list[str]] = Field(default=None, max_length=100)
    characteristics: Optional[dict[str, str]] = None
    compliance_status: Optional[ComplianceStatus] = None
    compliance_notes: Optional[str] = Field(default=None, max_length=5000)
    quote_date: Optional[date] = None
    valid_until: Optional[date] = None
    source_url: Optional[str] = Field(default=None, max_length=4000)
    is_selected: Optional[bool] = None
    selection_note: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        return SupplierOfferBase.normalize_currency(value)

    @model_validator(mode="after")
    def reject_nulls_for_required_fields(self):
        required_fields = {
            "supplier_name",
            "original_item_name",
            "unit_price",
            "price_quantity",
            "currency",
            "compliance_status",
        }
        explicit_nulls = [
            field for field in required_fields if field in self.model_fields_set and getattr(self, field) is None
        ]
        if explicit_nulls:
            raise ValueError(f"Fields cannot be null: {', '.join(sorted(explicit_nulls))}")
        if self.valid_until and self.quote_date and self.valid_until < self.quote_date:
            raise ValueError("valid_until cannot be before quote_date")
        return self


class SourcingPlanUpdate(BaseModel):
    target_margin_pct: Decimal = Field(ge=0, lt=95)


class SupplierOfferResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    company_id: uuid.UUID
    item_id: Optional[uuid.UUID]
    supplier_name: str
    supplier_bin: Optional[str]
    supplier_contact: Optional[str]
    original_item_name: str
    normalized_item_name: Optional[str]
    original_unit: Optional[str]
    normalized_unit: Optional[str]
    quoted_quantity: Optional[Decimal]
    unit_price: Decimal
    price_quantity: Decimal
    currency: str
    exchange_rate_to_kzt: Optional[Decimal]
    vat_included: Optional[bool]
    vat_rate: Optional[Decimal]
    moq: Optional[Decimal]
    available_quantity: Optional[Decimal]
    delivery_cost: Optional[Decimal]
    lead_time_days: Optional[int]
    warranty_months: Optional[int]
    certificates: list
    characteristics: dict
    compliance_status: str
    compliance_notes: Optional[str]
    quote_date: Optional[date]
    valid_until: Optional[date]
    source_type: str
    source_filename: Optional[str]
    source_url: Optional[str]
    match_status: str
    match_confidence: Optional[Decimal]
    is_selected: bool
    selection_note: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuoteImportResult(BaseModel):
    imported: int
    matched: int
    needs_review: int
    unmatched: int
    errors: list[str] = Field(default_factory=list)


class RfqDraftRequest(BaseModel):
    item_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    response_deadline: Optional[date] = None
    delivery_location: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=3000)


class RfqDraftResponse(BaseModel):
    subject: str
    body: str
    disclaimer: str
