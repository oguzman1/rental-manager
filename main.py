from calendar import monthrange
from datetime import date
import sqlite3

from fastapi import Body, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from adjustments import (
    calculate_adjustment_notice_date,
    calculate_due_adjustment_date,
    calculate_next_adjustment_date,
    months_between,
)
from db import (
    delete_managed_property,
    delete_payment,
    get_contract_for_payment,
    get_payment,
    init_db,
    insert_managed_property,
    insert_payment,
    list_contracts,
    list_dashboard_items,
    list_managed_properties,
    list_payments_for_contract,
    list_rentals_for_adjustments,
    list_tenants,
    update_managed_property,
    update_payment,
)
from models import (
    AdjustmentFrequency,
    ContractListItem,
    DashboardItem,
    ErrorResponse,
    ManagedPropertyCreate,
    ManagedPropertyListItem,
    ManagedPropertyResponse,
    PaymentCreate,
    PaymentResponse,
    PaymentUpdate,
    PropertyStatus,
    RentAdjustmentItem,
    TenantListItem,
)


def _derive_due_date(period: str, payment_day: int) -> date:
    year, month = int(period[:4]), int(period[5:7])
    last_day = monthrange(year, month)[1]
    return date(year, month, min(payment_day, last_day))


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

init_db()


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


@app.get(
    "/managed-properties",
    tags=["managed-properties"],
    summary="List managed properties",
    response_model=list[ManagedPropertyListItem],
)
def get_managed_properties():
    return list_managed_properties()


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
                adjustment_frequency=AdjustmentFrequency(item["adjustment_frequency"]),
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
                "current_payment_status": item.get("current_payment_status"),
            }
        )

    return results


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
    if data.property.status == PropertyStatus.occupied and data.rental is None:
        raise HTTPException(
            status_code=400,
            detail="Occupied properties must include rental data.",
        )

    if data.property.status == PropertyStatus.vacant and data.rental is not None:
        raise HTTPException(
            status_code=400,
            detail="Vacant properties cannot include rental data.",
        )

    has_rental = data.rental is not None
    property_label = data.rental.property_label if has_rental else None

    try:
        new_id = insert_managed_property(data)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A property with this rol already exists.",
        )

    return {
        "id": new_id,
        "message": "managed property saved successfully",
        "rol": data.property.rol,
        "comuna": data.property.comuna,
        "has_rental": has_rental,
        "property_label": property_label,
    }


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
        freq = AdjustmentFrequency(rental["adjustment_frequency"])

        next_adjustment_date = calculate_next_adjustment_date(
            start_date=start,
            adjustment_frequency=freq,
            today=today,
        )
        adjustment_notice_date = calculate_adjustment_notice_date(next_adjustment_date)

        due_date = calculate_due_adjustment_date(
            start_date=start,
            adjustment_frequency=freq,
            today=today,
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
    if data.property.status == PropertyStatus.occupied and data.rental is None:
        raise HTTPException(
            status_code=400,
            detail="Occupied properties must include rental data.",
        )

    if data.property.status == PropertyStatus.vacant and data.rental is not None:
        raise HTTPException(
            status_code=400,
            detail="Vacant properties cannot include rental data.",
        )

    has_rental = data.rental is not None
    property_label = data.rental.property_label if has_rental else None

    try:
        updated = update_managed_property(property_id, data)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A property with this rol already exists.",
        )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Managed property not found.",
        )

    return {
        "id": property_id,
        "message": "managed property updated successfully",
        "rol": data.property.rol,
        "comuna": data.property.comuna,
        "has_rental": has_rental,
        "property_label": property_label,
    }


@app.get(
    "/contracts",
    tags=["contracts"],
    summary="List active contracts",
    response_model=list[ContractListItem],
)
def get_contracts():
    return list_contracts()


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
            detail="Managed property not found.",
        )

    return {"detail": "Managed property deleted successfully."}


@app.post(
    "/contracts/{contract_id}/payments",
    tags=["payments"],
    summary="Create a manual payment record",
    response_model=PaymentResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found or inactive"},
        409: {"model": ErrorResponse, "description": "Payment for this period already exists"},
    },
)
def create_payment(contract_id: int, data: PaymentCreate):
    contract = get_contract_for_payment(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Active contract not found.")

    due_date = _derive_due_date(data.period, contract["payment_day"])

    try:
        payment_id = insert_payment(
            contract_id=contract_id,
            period=data.period,
            due_date=str(due_date),
            expected_amount=contract["current_rent"],
            comment=data.comment,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"A payment for period {data.period} already exists on this contract.",
        )

    return get_payment(payment_id)


@app.get(
    "/contracts/{contract_id}/payments",
    tags=["payments"],
    summary="List payments for a contract",
    response_model=list[PaymentResponse],
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found or inactive"},
    },
)
def list_payments(contract_id: int):
    if get_contract_for_payment(contract_id) is None:
        raise HTTPException(status_code=404, detail="Active contract not found.")

    return list_payments_for_contract(contract_id)


@app.patch(
    "/payments/{payment_id}",
    tags=["payments"],
    summary="Update payment with actual paid amount",
    response_model=PaymentResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Payment not found"},
    },
)
def patch_payment(payment_id: int, data: PaymentUpdate):
    payment = get_payment(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")

    paid_amount = (
        data.paid_amount if data.paid_amount is not None else payment["paid_amount"]
    )
    paid_at = str(data.paid_at) if data.paid_at is not None else payment["paid_at"]
    comment = data.comment if data.comment is not None else payment["comment"]

    if paid_amount is None:
        status = payment["status"]
    elif paid_amount >= payment["expected_amount"]:
        status = "paid"
    elif paid_amount > 0:
        status = "partial"
    else:
        status = payment["status"]

    update_payment(payment_id, paid_amount, paid_at, status, comment)
    return get_payment(payment_id)


@app.delete(
    "/payments/{payment_id}",
    tags=["payments"],
    summary="Delete a payment record",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Payment not found"},
    },
)
def delete_payment_endpoint(payment_id: int):
    deleted = delete_payment(payment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return Response(status_code=204)