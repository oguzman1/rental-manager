import re
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class PropertyStatus(str, Enum):
    occupied = "occupied"
    vacant = "vacant"


class AdjustmentFrequency(str, Enum):
    annual = "annual"
    semiannual = "semiannual"


class PaymentStatus(str, Enum):
    pending = "pending"
    partial = "partial"
    paid = "paid"


class DashboardPaymentStatus(str, Enum):
    paid_up             = "paid_up"
    outstanding_balance = "outstanding_balance"
    missing_period      = "missing_period"


class PropertyInfo(BaseModel):
    comuna: str
    rol: str
    address: str
    destination: str
    status: PropertyStatus
    fojas: str | None = None
    property_number: str | None = None
    year: int | None = None
    fiscal_appraisal: int | None = None


class RentalInfo(BaseModel):
    tenant_name: str
    payment_day: int = Field(ge=1, le=31)
    property_label: str
    current_rent: int = Field(gt=0)
    adjustment_frequency: AdjustmentFrequency
    start_date: date
    notice_days: int = Field(ge=0)
    adjustment_month: str


class ManagedPropertyCreate(BaseModel):
    property: PropertyInfo
    rental: RentalInfo | None = None


class ManagedPropertyResponse(BaseModel):
    id: int
    message: str
    rol: str
    comuna: str
    has_rental: bool
    property_label: str | None = None


class ErrorResponse(BaseModel):
    detail: str


class ManagedPropertyListItem(BaseModel):
    id: int
    rol: str
    comuna: str
    status: PropertyStatus
    has_rental: bool
    property_label: str | None = None
    tenant_name: str | None = None
    payment_day: int | None = None


class RentAdjustmentItem(BaseModel):
    id: int
    contract_id: int
    rol: str
    comuna: str
    property_label: str
    current_rent: int
    next_adjustment_date: date
    adjustment_notice_date: date
    requires_adjustment_notice: bool
    tenant_name: str | None = None
    payment_day: int | None = None
    last_adjustment_date: date | None = None
    months_since_last_adjustment: int | None = None
    months_until_next_adjustment: int | None = None
    notice_sent_at: date | None = None
    notice_registered: bool = False
    adjustment_due: bool = False
    due_adjustment_date: date | None = None


class RentChangeItem(BaseModel):
    id: int
    contract_id: int
    effective_from: date
    amount: int
    adjustment_pct: float | None = None
    comment: str | None = None


class RentChangeCreate(BaseModel):
    effective_from: date
    amount: int = Field(gt=0)
    adjustment_pct: float | None = None
    comment: str | None = None


class DashboardItem(BaseModel):
    id: int
    rol: str
    comuna: str
    status: PropertyStatus
    property_label: str | None = None
    tenant_name: str | None = None
    payment_day: int | None = None
    current_rent: int | None = None
    next_adjustment_date: date | None = None
    adjustment_notice_date: date | None = None
    requires_adjustment_notice: bool = False
    start_date: date | None = None
    adjustment_frequency: AdjustmentFrequency | None = None
    last_adjustment_date: date | None = None
    months_since_last_adjustment: int | None = None
    current_payment_status: PaymentStatus | None = None
    payment_status: DashboardPaymentStatus | None = None
    period_amount: int | None = None
    latest_period: str | None = None
    actionable_payment_period: str | None = None
    actionable_payment_status: PaymentStatus | None = None
    actionable_payment_amount: int | None = None
    contract_id: int | None = None
    due_adjustment_date: date | None = None
    notice_sent_at: date | None = None
    notice_registered: bool = False
    adjustment_due: bool = False


class ContractListItem(BaseModel):
    id: int
    property_id: int
    property_label: str
    rol: str
    tenant_name: str
    start_date: date
    current_rent: int
    payment_day: int
    adjustment_frequency: AdjustmentFrequency
    notice_days: int
    adjustment_month: str | None = None
    comment: str | None = None


class ContractCreate(BaseModel):
    property_id: int
    tenant_id: int
    start_date: date
    payment_day: int = Field(ge=1, le=31)
    notice_days: int = Field(ge=0)
    adjustment_frequency: AdjustmentFrequency
    adjustment_month: str | None = None
    current_rent: int = Field(gt=0)
    comment: str | None = None


class ContractUpdate(BaseModel):
    payment_day: int | None = Field(default=None, ge=1, le=31)
    notice_days: int | None = Field(default=None, ge=0)
    adjustment_frequency: AdjustmentFrequency | None = None
    adjustment_month: str | None = None
    current_rent: int | None = Field(default=None, gt=0)
    comment: str | None = None


class ContractCloseRequest(BaseModel):
    end_date: date


class ContractDetailResponse(BaseModel):
    id: int
    property_id: int
    property_label: str
    rol: str
    tenant_name: str
    start_date: date
    end_date: date | None
    current_rent: int
    payment_day: int
    adjustment_frequency: AdjustmentFrequency
    notice_days: int
    adjustment_month: str | None
    comment: str | None
    is_active: bool


class TenantListItem(BaseModel):
    id: int
    display_name: str
    property_id: int | None = None
    rol: str | None = None
    property_label: str | None = None
    payment_day: int | None = None
    start_date: date | None = None
    current_rent: int | None = None
    last_adjustment_date: date | None = None
    months_since_last_adjustment: int | None = None
    tenancy_months: int | None = None
    tenancy_years: int | None = None


class PropertyDetailResponse(BaseModel):
    id: int
    property: PropertyInfo
    rental: RentalInfo | None


class PaymentSource(str, Enum):
    manual = "manual"


class PaymentCreate(BaseModel):
    period: str
    paid_amount: int | None = Field(default=None, ge=0)
    paid_at: date | None = None
    comment: str | None = None

    @field_validator("period")
    @classmethod
    def period_must_be_yyyy_mm(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
            raise ValueError("period must be in YYYY-MM format (e.g. 2025-04)")
        return value


class PaymentUpdate(BaseModel):
    paid_amount: int | None = None
    paid_at: date | None = None
    comment: str | None = None


class PaymentResponse(BaseModel):
    id: int
    contract_id: int
    period: str
    due_date: date
    expected_amount: int
    paid_amount: int | None = None
    paid_at: date | None = None
    status: PaymentStatus
    source: PaymentSource
    comment: str | None = None
    created_at: date
    overpayment: int = 0


class TenantCreate(BaseModel):
    display_name: str
    tenant_type: str | None = None
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class TenantDetailResponse(BaseModel):
    id: int
    display_name: str
    tenant_type: str | None = None
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class NoticeSentResponse(BaseModel):
    contract_id: int
    notice_sent_at: date