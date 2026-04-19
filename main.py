from fastapi import Body, FastAPI, HTTPException, Query
from datetime import date
import sqlite3
from db import (
    delete_managed_property,
    init_db,
    insert_managed_property,
    list_managed_properties,
    update_managed_property,
    list_rentals_for_adjustments
)
from models import (
    ErrorResponse,
    ManagedPropertyCreate,
    ManagedPropertyResponse,
    PropertyStatus,
    ManagedPropertyListItem,
    AdjustmentFrequency,
    RentAdjustmentItem
)

from adjustments import (
    calculate_adjustment_notice_date,
    calculate_next_adjustment_date,
)




# Crea la aplicación FastAPI.
app = FastAPI()

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
        example={
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
                "property_label": "depto serena",
                "current_rent": 801875,
                "adjustment_frequency": "annual",
                "start_date": "2022-03-12",
                "notice_days": 60,
                "adjustment_month": "march",
            },
        },
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
        next_adjustment_date = calculate_next_adjustment_date(
            start_date=date.fromisoformat(rental["start_date"]),
            adjustment_frequency=AdjustmentFrequency(rental["adjustment_frequency"]),
            today=today,
        )

        adjustment_notice_date = calculate_adjustment_notice_date(
            next_adjustment_date
        )

        results.append(
            {
                "id": rental["id"],
                "rol": rental["rol"],
                "comuna": rental["comuna"],
                "property_label": rental["property_label"],
                "current_rent": rental["current_rent"],
                "next_adjustment_date": next_adjustment_date,
                "adjustment_notice_date": adjustment_notice_date,
                "requires_adjustment_notice": today >= adjustment_notice_date,
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