from fastapi import Body, FastAPI, HTTPException, Query
from datetime import date
import sqlite3
from db import (
    delete_managed_property,
    init_db,
    insert_managed_property,
    list_contracts,
    list_dashboard_items,
    list_managed_properties,
    list_rentals_for_adjustments,
    list_tenants,
    update_managed_property,
)
from models import (
    AdjustmentFrequency,
    ContractListItem,
    DashboardItem,
    ErrorResponse,
    ManagedPropertyCreate,
    ManagedPropertyListItem,
    ManagedPropertyResponse,
    PropertyStatus,
    RentAdjustmentItem,
    TenantListItem,
)

from adjustments import (
    calculate_adjustment_notice_date,
    calculate_due_adjustment_date,
    calculate_next_adjustment_date,
    months_between,
)
from fastapi.middleware.cors import CORSMiddleware




# Crea la aplicación FastAPI.
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializa la base al cargar la aplicación.
init_db()


# Endpoint simple para comprobar que la API está viva.
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}

# Endpoint para listar propiedades guardadas.
@app.get(
    "/managed-properties",
    tags=["managed-properties"],
    summary="List managed properties",
    response_model=list[ManagedPropertyListItem],
)
def get_managed_properties():
    return list_managed_properties()

# Endpoint para mostrar una vista operativa consolidada.
@app.get(
    "/dashboard",
    tags=["dashboard"],
    summary="Get operational dashboard",
    response_model=list[DashboardItem],
)
def get_dashboard():
    items = list_dashboard_items()
    today = date.today()

    results = []

    for item in items:
        next_adjustment_date = None
        adjustment_notice_date = None
        requires_adjustment_notice = False

        last_adj_str = item["last_adjustment_date"]
        last_adjustment_date = date.fromisoformat(last_adj_str) if last_adj_str else None
        months_since_last = (
            months_between(last_adjustment_date, today) if last_adjustment_date else None
        )

        if item["adjustment_frequency"] and item["start_date"]:
            next_adjustment_date = calculate_next_adjustment_date(
                start_date=date.fromisoformat(item["start_date"]),
                adjustment_frequency=AdjustmentFrequency(
                    item["adjustment_frequency"]
                ),
                today=today,
            )

            adjustment_notice_date = calculate_adjustment_notice_date(
                next_adjustment_date
            )

            requires_adjustment_notice = today >= adjustment_notice_date

        results.append(
            {
                "id": item["id"],
                "rol": item["rol"],
                "comuna": item["comuna"],
                "status": item["status"],
                "property_label": item["property_label"],
                "tenant_name": item["tenant_name"],
                "payment_day": item["payment_day"],
                "current_rent": item["current_rent"],
                "next_adjustment_date": next_adjustment_date,
                "adjustment_notice_date": adjustment_notice_date,
                "requires_adjustment_notice": requires_adjustment_notice,
                "start_date": item["start_date"],
                "adjustment_frequency": item["adjustment_frequency"],
                "last_adjustment_date": last_adjustment_date,
                "months_since_last_adjustment": months_since_last,
            }
        )

    return results

# Endpoint para recibir una propiedad gestionada y devolver una respuesta clara.
@app.post(
    "/managed-property",
    tags=["managed-properties"],
    summary="Create a managed property",
    description=(
        "Receives property inventory data and, optionally, current rental data. "
        "Also enforces business rules between property status and rental presence."
    ),
    response_model=ManagedPropertyResponse,
    response_description="Managed property accepted successfully",
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Business rule validation error",
        },
        422: {
            "description": "Schema validation error",
        },
        409: {
            "model": ErrorResponse,
            "description": "Duplicate rol conflict",
        },
    },
)
def create_managed_property(
data: ManagedPropertyCreate = Body(
    ...,
    examples=[
        {
            "property": {
                "comuna": "LA SERENA",
                "rol": "02162-00036",
                "address": "BALMACEDA EDIF 1 4095",
                "destination": "HABITACIONAL",
                "status": "occupied",
                "fojas": "2933",
                "property_number": "2121",
                "year": 2016,
                "fiscal_appraisal": 142935366,
            },
            "rental": {
                "tenant_name": "Arrendatario La Serena",
                "payment_day": 5,
                "property_label": "depto serena",
                "current_rent": 801875,
                "adjustment_frequency": "annual",
                "start_date": "2022-03-12",
                "notice_days": 60,
                "adjustment_month": "march",
            },
        }
    ],
)
):
    # Regla: si está ocupada, debe traer datos de arriendo.
    if data.property.status == PropertyStatus.occupied and data.rental is None:
        raise HTTPException(
            status_code=400,
            detail="Occupied properties must include rental data."
        )

    # Regla: si está vacante, no debe traer datos de arriendo.
    if data.property.status == PropertyStatus.vacant and data.rental is not None:
        raise HTTPException(
            status_code=400,
            detail="Vacant properties cannot include rental data."
        )

    # Evalúa si el input viene con datos de arriendo.
    has_rental = data.rental is not None

    # Si hay rental, toma el label; si no, deja None.
    property_label = data.rental.property_label if has_rental else None

    # Guarda la propiedad en la base y obtiene el id creado.
    try:
        new_id = insert_managed_property(data)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A property with this rol already exists."
        )

    # Devuelve una respuesta validada por el response_model.
    return {
        "id": new_id,
        "message": "managed property saved successfully",
        "rol": data.property.rol,
        "comuna": data.property.comuna,
        "has_rental": has_rental,
        "property_label": property_label,
    }

# Endpoint para listar próximos reajustes de arriendo.
@app.get(
    "/rent-adjustments",
    tags=["rent-adjustments"],
    summary="List upcoming rent adjustments",
    response_model=list[RentAdjustmentItem],
)
def get_rent_adjustments(
    as_of: date | None = Query(
        default=None,
        description="Reference date to evaluate adjustment notices",
    )
    ):
    rentals = list_rentals_for_adjustments()
    today = as_of or date.today()

    results = []

    for rental in rentals:
        start = date.fromisoformat(rental["start_date"])
        freq  = AdjustmentFrequency(rental["adjustment_frequency"])

        next_adjustment_date = calculate_next_adjustment_date(
            start_date=start,
            adjustment_frequency=freq,
            today=today,
        )
        adjustment_notice_date = calculate_adjustment_notice_date(next_adjustment_date)

        due_date = calculate_due_adjustment_date(
            start_date=start, adjustment_frequency=freq, today=today
        )
        months_until_next = months_between(today, due_date)

        last_adj_str = rental["last_adjustment_date"]
        last_adjustment_date = date.fromisoformat(last_adj_str) if last_adj_str else None
        months_since_last = (
            months_between(last_adjustment_date, today) if last_adjustment_date else None
        )

        results.append(
            {
                "id": rental["id"],
                "rol": rental["rol"],
                "comuna": rental["comuna"],
                "property_label": rental["property_label"],
                "tenant_name": rental["tenant_name"],
                "payment_day": rental["payment_day"],
                "current_rent": rental["current_rent"],
                "next_adjustment_date": next_adjustment_date,
                "adjustment_notice_date": adjustment_notice_date,
                "requires_adjustment_notice": today >= adjustment_notice_date,
                "last_adjustment_date": last_adjustment_date,
                "months_since_last_adjustment": months_since_last,
                "months_until_next_adjustment": months_until_next,
            }
        )
        

    return results

# Endpoint para actualizar una propiedad gestionada existente.
@app.put(
    "/managed-property/{property_id}",
    tags=["managed-properties"],
    summary="Update a managed property",
    description="Replaces the stored data of an existing managed property by id.",
    response_model=ManagedPropertyResponse,
    response_description="Managed property updated successfully",
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Business rule validation error",
        },
        404: {
            "model": ErrorResponse,
            "description": "Managed property not found",
        },
        409: {
            "model": ErrorResponse,
            "description": "Duplicate rol conflict",
        },
        422: {
            "description": "Schema validation error",
        },
    },
)
def update_managed_property_endpoint(
    property_id: int,
    data: ManagedPropertyCreate = Body(...),
):
    # Regla: si está ocupada, debe traer datos de arriendo.
    if data.property.status == PropertyStatus.occupied and data.rental is None:
        raise HTTPException(
            status_code=400,
            detail="Occupied properties must include rental data."
        )

    # Regla: si está vacante, no debe traer datos de arriendo.
    if data.property.status == PropertyStatus.vacant and data.rental is not None:
        raise HTTPException(
            status_code=400,
            detail="Vacant properties cannot include rental data."
        )

    # Evalúa si el input viene con datos de arriendo.
    has_rental = data.rental is not None

    # Si hay rental, toma el label; si no, deja None.
    property_label = data.rental.property_label if has_rental else None

    # Intenta actualizar la propiedad en la base.
    try:
        updated = update_managed_property(property_id, data)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A property with this rol already exists."
        )

    # Si no encontró la fila, devuelve 404.
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Managed property not found."
        )

    return {
        "id": property_id,
        "message": "managed property updated successfully",
        "rol": data.property.rol,
        "comuna": data.property.comuna,
        "has_rental": has_rental,
        "property_label": property_label,
    }

# Endpoint para listar contratos activos.
@app.get(
    "/contracts",
    tags=["contracts"],
    summary="List active contracts",
    response_model=list[ContractListItem],
)
def get_contracts():
    return list_contracts()


# Endpoint para listar arrendatarios activos.
@app.get(
    "/tenants",
    tags=["tenants"],
    summary="List active tenants",
    response_model=list[TenantListItem],
)
def get_tenants():
    items = list_tenants()
    today = date.today()
    results = []
    for item in items:
        start_str = item["start_date"]
        start = date.fromisoformat(start_str) if start_str else None
        tenancy_months = months_between(start, today) if start else None

        last_adj_str = item["last_adjustment_date"]
        last_adjustment_date = date.fromisoformat(last_adj_str) if last_adj_str else None
        months_since_last = (
            months_between(last_adjustment_date, today) if last_adjustment_date else None
        )

        results.append(
            {
                **item,
                "last_adjustment_date": last_adjustment_date,
                "months_since_last_adjustment": months_since_last,
                "tenancy_months": tenancy_months,
                "tenancy_years": tenancy_months // 12 if tenancy_months is not None else None,
            }
        )
    return results


# Endpoint para eliminar una propiedad gestionada existente.
@app.delete(
    "/managed-property/{property_id}",
    tags=["managed-properties"],
    summary="Delete a managed property",
    response_model=ErrorResponse,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Managed property not found",
        }
    },
)
def delete_managed_property_endpoint(property_id: int):
    deleted = delete_managed_property(property_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Managed property not found."
        )

    return {"detail": "Managed property deleted successfully."}