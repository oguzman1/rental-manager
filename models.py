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
    property_label: str

    # El arriendo actual debe ser un entero positivo.
    current_rent: int = Field(gt=0)

    adjustment_frequency: AdjustmentFrequency
    start_date: date

    # Los días de aviso no pueden ser negativos.
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
    