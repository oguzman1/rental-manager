from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


# Catálogo de estados permitidos para una propiedad.
class PropertyStatus(str, Enum):
    occupied = "occupied"
    vacant = "vacant"


# Catálogo de valores válidos para la frecuencia de reajuste.
class AdjustmentFrequency(str, Enum):
    annual = "annual"
    semiannual = "semiannual"


# Modelo base para los datos de inventario de una propiedad.
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


# Modelo para los datos del arriendo vigente.
class RentalInfo(BaseModel):
    tenant_name: str
    payment_day: int = Field(ge=1, le=31)
    property_label: str
    current_rent: int = Field(gt=0)
    adjustment_frequency: AdjustmentFrequency
    start_date: date
    notice_days: int = Field(ge=0)
    adjustment_month: str


# Modelo de entrada principal: una propiedad puede venir con o sin arriendo.
class ManagedPropertyCreate(BaseModel):
    property: PropertyInfo
    rental: RentalInfo | None = None


# Modelo de salida: define la respuesta limpia que devolverá la API.
class ManagedPropertyResponse(BaseModel):
    id: int
    message: str
    rol: str
    comuna: str
    has_rental: bool
    property_label: str | None = None


# Modelo simple para documentar errores de negocio.
class ErrorResponse(BaseModel):
    detail: str

# Modelo simple para listar propiedades guardadas.
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

# Modelo para mostrar una vista operativa consolidada de propiedades y arriendos.
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
    adjustment_frequency: str | None = None
    last_adjustment_date: date | None = None
    months_since_last_adjustment: int | None = None


class ContractListItem(BaseModel):
    id: int
    property_id: int
    rol: str
    property_label: str | None = None
    tenant_name: str | None = None
    start_date: date | None = None
    payment_day: int | None = None
    adjustment_frequency: str | None = None
    adjustment_month: str | None = None
    current_rent: int | None = None


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
