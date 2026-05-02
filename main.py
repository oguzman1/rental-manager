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
    apply_overpayment_to_next_period,
    close_contract,
    create_contract,
    delete_managed_property,
    delete_payment,
    delete_rent_change,
    delete_tenant,
    get_contract,
    get_contract_for_payment,
    get_managed_property,
    get_payment,
    get_rent_change,
    get_tenant,
    init_db,
    insert_managed_property,
    insert_payment,
    insert_rent_change,
    insert_tenant,
    list_contracts,
    list_dashboard_items,
    list_managed_properties,
    list_payments_for_contract,
    list_rent_changes,
    list_rentals_for_adjustments,
    list_tenants,
    tenant_has_any_contract,
    update_contract,
    update_managed_property,
    update_payment,
    update_tenant,
)
from models import (
    AdjustmentFrequency,
    ContractCloseRequest,
    ContractCreate,
    ContractDetailResponse,
    ContractListItem,
    ContractUpdate,
    DashboardItem,
    ErrorResponse,
    ManagedPropertyCreate,
    ManagedPropertyListItem,
    ManagedPropertyResponse,
    PaymentCreate,
    PaymentResponse,
    PaymentUpdate,
    PropertyDetailResponse,
    PropertyInfo,
    PropertyStatus,
    RentAdjustmentItem,
    RentChangeCreate,
    RentChangeItem,
    RentalInfo,
    TenantCreate,
    TenantDetailResponse,
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
    "/managed-property/{property_id}",
    tags=["managed-properties"],
    summary="Get a managed property by ID",
    response_model=PropertyDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Managed property not found"},
    },
)
def get_managed_property_endpoint(property_id: int):
    data = get_managed_property(property_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Managed property not found.")

    property_info = PropertyInfo(
        rol=data["rol"],
        comuna=data["comuna"],
        address=data["address"],
        destination=data["destination"],
        status=data["status"],
        fojas=data["fojas"],
        property_number=data["property_number"],
        year=data["year"],
        fiscal_appraisal=data["fiscal_appraisal"],
    )

    rental_info = None
    if data["payment_day"] is not None:
        rental_info = RentalInfo(
            tenant_name=data["tenant_name"],
            payment_day=data["payment_day"],
            property_label=data["property_label"],
            current_rent=data["current_rent"],
            adjustment_frequency=data["adjustment_frequency"],
            start_date=data["start_date"],
            notice_days=data["notice_days"],
            adjustment_month=data["adjustment_month"],
        )

    return PropertyDetailResponse(
        id=data["id"],
        property=property_info,
        rental=rental_info,
    )


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
            requires_adjustment_notice = (
                today >= adjustment_notice_date
                and (last_adjustment_date is None or last_adjustment_date < adjustment_notice_date)
            )

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
                "payment_status": item.get("payment_status"),
                "period_amount": item.get("period_amount"),
                "latest_period": item.get("latest_period"),
                "actionable_payment_period": item.get("actionable_payment_period"),
                "actionable_payment_status": item.get("actionable_payment_status"),
                "actionable_payment_amount": item.get("actionable_payment_amount"),
                "contract_id": item.get("contract_id"),
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
                "contract_id": rental["contract_id"],
                "rol": rental["rol"],
                "comuna": rental["comuna"],
                "property_label": rental["property_label"],
                "tenant_name": rental["tenant_name"],
                "payment_day": rental["payment_day"],
                "current_rent": rental["current_rent"],
                "next_adjustment_date": next_adjustment_date,
                "adjustment_notice_date": adjustment_notice_date,
                "requires_adjustment_notice": (
                    today >= adjustment_notice_date
                    and (last_adjustment_date is None or last_adjustment_date < adjustment_notice_date)
                ),
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
    "/contracts/{contract_id}",
    tags=["contracts"],
    summary="Get a contract by ID",
    response_model=ContractDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found"},
    },
)
def get_contract_endpoint(contract_id: int):
    contract = get_contract(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    return contract


@app.post(
    "/contracts",
    tags=["contracts"],
    summary="Create a new contract",
    response_model=ContractDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Property or tenant not found"},
        409: {"model": ErrorResponse, "description": "Property already has an active contract"},
    },
)
def create_contract_endpoint(data: ContractCreate):
    try:
        contract_id = create_contract(data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return get_contract(contract_id)


@app.patch(
    "/contracts/{contract_id}",
    tags=["contracts"],
    summary="Update an active contract",
    response_model=ContractDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found or inactive"},
    },
)
def update_contract_endpoint(contract_id: int, data: ContractUpdate):
    if not update_contract(contract_id, data):
        raise HTTPException(status_code=404, detail="Active contract not found.")
    return get_contract(contract_id)


@app.patch(
    "/contracts/{contract_id}/close",
    tags=["contracts"],
    summary="Close a contract",
    response_model=ContractDetailResponse,
    responses={
        400: {"model": ErrorResponse, "description": "end_date before start_date"},
        404: {"model": ErrorResponse, "description": "Contract not found or already inactive"},
    },
)
def close_contract_endpoint(contract_id: int, data: ContractCloseRequest):
    contract = get_contract(contract_id)
    if contract is None or not contract["is_active"]:
        raise HTTPException(status_code=404, detail="Active contract not found.")
    if data.end_date < date.fromisoformat(contract["start_date"]):
        raise HTTPException(
            status_code=400,
            detail="end_date must be on or after the contract start_date.",
        )
    close_contract(contract_id, str(data.end_date))
    return get_contract(contract_id)


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


@app.get(
    "/tenants/{tenant_id}",
    tags=["tenants"],
    summary="Get a tenant by ID",
    response_model=TenantDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Tenant not found"},
    },
)
def get_tenant_endpoint(tenant_id: int):
    tenant = get_tenant(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return tenant


@app.post(
    "/tenants",
    tags=["tenants"],
    summary="Create a standalone tenant",
    response_model=TenantDetailResponse,
)
def create_tenant(data: TenantCreate):
    new_id = insert_tenant(data)
    return get_tenant(new_id)


@app.patch(
    "/tenants/{tenant_id}",
    tags=["tenants"],
    summary="Update a tenant",
    response_model=TenantDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Tenant not found"},
    },
)
def update_tenant_endpoint(tenant_id: int, data: TenantCreate):
    if not update_tenant(tenant_id, data):
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return get_tenant(tenant_id)


@app.delete(
    "/tenants/{tenant_id}",
    tags=["tenants"],
    summary="Delete a tenant",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Tenant not found"},
        409: {"model": ErrorResponse, "description": "Tenant has an active contract"},
    },
)
def delete_tenant_endpoint(tenant_id: int):
    if get_tenant(tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    if tenant_has_any_contract(tenant_id):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a tenant with contract history.",
        )
    delete_tenant(tenant_id)
    return Response(status_code=204)


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
    expected_amount = contract["current_rent"]

    paid_amount = data.paid_amount
    paid_at = str(data.paid_at) if data.paid_at is not None else None

    if paid_amount is None or paid_amount == 0:
        status = "pending"
    elif paid_amount >= expected_amount:
        status = "paid"
    else:
        status = "partial"

    try:
        payment_id = insert_payment(
            contract_id=contract_id,
            period=data.period,
            due_date=str(due_date),
            expected_amount=expected_amount,
            comment=data.comment,
            paid_amount=paid_amount,
            paid_at=paid_at,
            status=status,
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
    elif paid_amount == 0:
        status = "pending"
    elif paid_amount >= payment["expected_amount"]:
        status = "paid"
    else:
        status = "partial"

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


@app.post(
    "/payments/{payment_id}/apply-overpayment",
    tags=["payments"],
    summary="Apply overpayment from this period to the next monthly period",
    responses={
        400: {"model": ErrorResponse, "description": "No overpayment to apply"},
        404: {"model": ErrorResponse, "description": "Payment not found"},
    },
)
def apply_payment_overpayment(payment_id: int):
    try:
        current, next_payment = apply_overpayment_to_next_period(payment_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"current": current, "next": next_payment}


@app.get(
    "/contracts/{contract_id}/rent-changes",
    tags=["rent-adjustments"],
    summary="List rent change history for a contract",
    response_model=list[RentChangeItem],
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found"},
    },
)
def list_rent_changes_endpoint(contract_id: int):
    try:
        return list_rent_changes(contract_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post(
    "/contracts/{contract_id}/rent-changes",
    tags=["rent-adjustments"],
    summary="Add a rent change to a contract",
    response_model=RentChangeItem,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Chronological violation or invalid date"},
        404: {"model": ErrorResponse, "description": "Contract not found or inactive"},
    },
)
def create_rent_change_endpoint(contract_id: int, data: RentChangeCreate):
    try:
        new_id = insert_rent_change(contract_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return get_rent_change(new_id)


@app.delete(
    "/rent-changes/{rent_change_id}",
    tags=["rent-adjustments"],
    summary="Delete a rent change",
    status_code=204,
    responses={
        400: {"model": ErrorResponse, "description": "Cannot delete sole rent change"},
        404: {"model": ErrorResponse, "description": "Rent change not found"},
        409: {"model": ErrorResponse, "description": "Not the most recent rent change"},
    },
)
def delete_rent_change_endpoint(rent_change_id: int):
    try:
        delete_rent_change(rent_change_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return Response(status_code=204)