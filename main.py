from calendar import monthrange
from datetime import date, datetime, timezone
import hashlib
import sqlite3
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from adjustments import (
    calculate_adjustment_notice_date,
    calculate_due_adjustment_date,
    calculate_next_adjustment_date,
    months_between,
)
from bank_statement_parser import StatementParseError, parse_xls
from db import (
    apply_overpayment_to_next_period,
    close_contract,
    create_contract,
    delete_bank_statement,
    delete_managed_property,
    delete_payment,
    delete_rent_change,
    delete_tenant,
    dismiss_adjustment_alert,
    get_bank_movement_by_dedup_key,
    get_bank_statement,
    get_bank_statement_by_file_hash,
    get_contract,
    get_contract_for_payment,
    get_managed_property,
    get_payment,
    get_rent_change,
    get_tenant,
    init_db,
    insert_bank_movement,
    insert_bank_statement,
    insert_managed_property,
    insert_payment,
    insert_rent_change,
    insert_tenant,
    is_adjustment_alert_dismissed,
    list_bank_movements,
    list_bank_statements,
    list_contracts,
    complete_payment_from_audit_finding,
    list_payment_audit_findings,
    resolve_missing_payment_finding,
    resolve_amount_mismatch_finding,
    resolve_unmatched_movement_finding,
    list_dashboard_items,
    list_managed_properties,
    list_payments_for_contract,
    list_rent_changes,
    list_notice_events,
    list_rentals_for_adjustments,
    list_tenants,
    mark_notice_sent,
    rent_change_payment_atomic,
    revert_notice_sent,
    tenant_has_any_contract,
    update_bank_statement_parse_result,
    update_contract,
    update_contract_document,
    update_managed_property,
    update_payment,
    update_tenant,
)
import payment_audit_engine
from models import (
    AdjustmentFrequency,
    AdjustmentDismissResponse,
    BankMovementResponse,
    BankStatementResponse,
    PaymentAuditCompletePaymentResponse,
    PaymentAuditFindingResponse,
    PaymentAuditResolveFindingRequest,
    PaymentAuditRunRequest,
    PaymentAuditRunResponse,
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
    NoticeEventItem,
    NoticeRevertResponse,
    NoticeSentRequest,
    NoticeSentResponse,
    OwnerExpenseInput,
    OwnerExpenseResponse,
    PaymentCreate,
    PaymentResponse,
    PaymentUpdate,
    PropertyDetailResponse,
    PropertyInfo,
    PropertyStatus,
    RentAdjustmentItem,
    RentChangeCreate,
    RentChangeItem,
    RentChangePaymentCreate,
    RentChangePaymentResponse,
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

_UPLOADS_DIR = Path("uploads/contracts")
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
_MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB

_CARTOLAS_DIR = Path("uploads/cartolas")
_CARTOLAS_DIR.mkdir(parents=True, exist_ok=True)

_CARTOLA_ALLOWED_EXTENSIONS = {".pdf", ".xls"}
_CARTOLA_MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB


def _current_adjustment_state(
    *,
    contract_id: int,
    start_date: date,
    adjustment_frequency: AdjustmentFrequency,
    notice_days: int | None,
    last_adjustment_date: date | None,
    notice_sent_at: date | None,
    today: date,
) -> dict:
    next_adjustment_date = calculate_next_adjustment_date(
        start_date=start_date,
        adjustment_frequency=adjustment_frequency,
        today=today,
    )
    adjustment_notice_date = calculate_adjustment_notice_date(next_adjustment_date, notice_days)
    due_adjustment_date = calculate_due_adjustment_date(
        start_date=start_date,
        adjustment_frequency=adjustment_frequency,
        today=today,
    )
    current_cycle_notice_date = calculate_adjustment_notice_date(due_adjustment_date, notice_days)

    adjustment_resolved = (
        last_adjustment_date is not None
        and last_adjustment_date >= current_cycle_notice_date
    )
    adjustment_due = today >= due_adjustment_date and not adjustment_resolved
    notice_registered = (
        notice_sent_at is not None
        and notice_sent_at >= current_cycle_notice_date
        and not adjustment_resolved
    )
    adjustment_dismissed = (
        not adjustment_resolved
        and is_adjustment_alert_dismissed(contract_id, due_adjustment_date)
    )
    requires_adjustment_notice = (
        not adjustment_resolved
        and not adjustment_dismissed
        and (today >= adjustment_notice_date or adjustment_due)
    )

    if adjustment_resolved:
        adjustment_alert_state = "resolved"
    elif adjustment_dismissed:
        adjustment_alert_state = "dismissed"
    elif notice_registered:
        adjustment_alert_state = "notice_sent"
    elif adjustment_due:
        adjustment_alert_state = "pending_adjustment"
    elif requires_adjustment_notice:
        adjustment_alert_state = "pending_notice"
    else:
        adjustment_alert_state = "upcoming"

    return {
        "next_adjustment_date": next_adjustment_date,
        "adjustment_notice_date": adjustment_notice_date,
        "due_adjustment_date": due_adjustment_date,
        "adjustment_due": adjustment_due,
        "notice_registered": notice_registered,
        "requires_adjustment_notice": requires_adjustment_notice,
        "adjustment_resolved": adjustment_resolved,
        "adjustment_dismissed": adjustment_dismissed,
        "adjustment_alert_state": adjustment_alert_state,
    }


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
        notice_registered = False
        adjustment_due = False
        due_adjustment_date = None
        adjustment_resolved = False
        adjustment_dismissed = False
        adjustment_alert_state = "upcoming"

        last_adj_str = item["last_adjustment_date"]
        last_adjustment_date = date.fromisoformat(last_adj_str) if last_adj_str else None
        months_since_last = (
            months_between(last_adjustment_date, today) if last_adjustment_date else None
        )

        notice_sent_at_str = item.get("notice_sent_at")
        notice_sent_at = date.fromisoformat(notice_sent_at_str) if notice_sent_at_str else None

        if item["adjustment_frequency"] and item["start_date"]:
            start = date.fromisoformat(item["start_date"])
            freq = AdjustmentFrequency(item["adjustment_frequency"])
            notice_days = item.get("notice_days")
            adjustment_state = _current_adjustment_state(
                contract_id=item["contract_id"],
                start_date=start,
                adjustment_frequency=freq,
                notice_days=notice_days,
                last_adjustment_date=last_adjustment_date,
                notice_sent_at=notice_sent_at,
                today=today,
            )
            next_adjustment_date = adjustment_state["next_adjustment_date"]
            adjustment_notice_date = adjustment_state["adjustment_notice_date"]
            due_adjustment_date = adjustment_state["due_adjustment_date"]
            adjustment_due = adjustment_state["adjustment_due"]
            notice_registered = adjustment_state["notice_registered"]
            requires_adjustment_notice = adjustment_state["requires_adjustment_notice"]
            adjustment_resolved = adjustment_state["adjustment_resolved"]
            adjustment_dismissed = adjustment_state["adjustment_dismissed"]
            adjustment_alert_state = adjustment_state["adjustment_alert_state"]

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
                "current_payment_period": item.get("current_payment_period"),
                "current_payment_amount": item.get("current_payment_amount"),
                "current_payment_paid_amount": item.get("current_payment_paid_amount"),
                "payment_status": item.get("payment_status"),
                "period_amount": item.get("period_amount"),
                "latest_period": item.get("latest_period"),
                "actionable_payment_period": item.get("actionable_payment_period"),
                "actionable_payment_status": item.get("actionable_payment_status"),
                "actionable_payment_amount": item.get("actionable_payment_amount"),
                "actionable_payment_paid_amount": item.get("actionable_payment_paid_amount"),
                "actionable_payment_recognized_amount": item.get("actionable_payment_recognized_amount"),
                "contract_id": item.get("contract_id"),
                "due_adjustment_date": due_adjustment_date,
                "notice_sent_at": notice_sent_at,
                "notice_registered": notice_registered,
                "adjustment_due": adjustment_due,
                "adjustment_resolved": adjustment_resolved,
                "adjustment_dismissed": adjustment_dismissed,
                "adjustment_alert_state": adjustment_alert_state,
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
    today = as_of if isinstance(as_of, date) else date.today()
    rentals = list_rentals_for_adjustments(today)
    results = []

    for rental in rentals:
        start = date.fromisoformat(rental["start_date"])
        freq = AdjustmentFrequency(rental["adjustment_frequency"])

        notice_days = rental.get("notice_days")
        last_adj_str = rental["last_adjustment_date"]
        last_adjustment_date = date.fromisoformat(last_adj_str) if last_adj_str else None
        months_since_last = (
            months_between(last_adjustment_date, today) if last_adjustment_date else None
        )

        notice_sent_at_str = rental.get("notice_sent_at")
        notice_sent_at = date.fromisoformat(notice_sent_at_str) if notice_sent_at_str else None

        adjustment_state = _current_adjustment_state(
            contract_id=rental["contract_id"],
            start_date=start,
            adjustment_frequency=freq,
            notice_days=notice_days,
            last_adjustment_date=last_adjustment_date,
            notice_sent_at=notice_sent_at,
            today=today,
        )
        next_adjustment_date = adjustment_state["next_adjustment_date"]
        adjustment_notice_date = adjustment_state["adjustment_notice_date"]
        due_date = adjustment_state["due_adjustment_date"]
        months_until_next = months_between(today, due_date)

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
                "requires_adjustment_notice": adjustment_state["requires_adjustment_notice"],
                "last_adjustment_date": last_adjustment_date,
                "months_since_last_adjustment": months_since_last,
                "months_until_next_adjustment": months_until_next,
                "notice_sent_at": notice_sent_at,
                "notice_registered": adjustment_state["notice_registered"],
                "adjustment_due": adjustment_state["adjustment_due"],
                "due_adjustment_date": due_date,
                "adjustment_resolved": adjustment_state["adjustment_resolved"],
                "adjustment_dismissed": adjustment_state["adjustment_dismissed"],
                "adjustment_alert_state": adjustment_state["adjustment_alert_state"],
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


@app.post(
    "/contracts/{contract_id}/document",
    tags=["contracts"],
    summary="Upload a document file for a contract",
    response_model=ContractDetailResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Unsupported file type or file too large"},
        404: {"model": ErrorResponse, "description": "Contract not found or inactive"},
    },
)
async def upload_contract_document(contract_id: int, file: UploadFile = File(...)):
    contract = get_contract(contract_id)
    if contract is None or not contract["is_active"]:
        raise HTTPException(status_code=404, detail="Active contract not found.")

    original_filename = file.filename or ""
    ext = Path(original_filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: .pdf, .doc, .docx",
        )

    content = await file.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds maximum size of 20 MB.")

    old_path_str = contract.get("contract_document_path")

    safe_name = f"{contract_id}_{uuid.uuid4().hex[:8]}{ext}"
    dest = _UPLOADS_DIR / safe_name
    dest.write_bytes(content)

    mime = (file.content_type or "application/octet-stream").split(";")[0].strip()
    uploaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    stored_path = f"uploads/contracts/{safe_name}"

    try:
        success = update_contract_document(
            contract_id=contract_id,
            path=stored_path,
            filename=original_filename,
            mime_type=mime,
            size_bytes=len(content),
            uploaded_at=uploaded_at,
        )
    except Exception:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Failed to update contract record.")

    if not success:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="Active contract not found.")

    if old_path_str and old_path_str != stored_path:
        try:
            Path(old_path_str).unlink(missing_ok=True)
        except Exception:
            pass

    return get_contract(contract_id)


@app.get(
    "/contracts/{contract_id}/document",
    tags=["contracts"],
    summary="Download the uploaded document for a contract",
    responses={
        404: {"model": ErrorResponse, "description": "Contract or document not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    },
)
def get_contract_document(contract_id: int):
    contract = get_contract(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")

    doc_path_str = contract.get("contract_document_path")
    if not doc_path_str:
        raise HTTPException(status_code=404, detail="No uploaded document for this contract.")

    doc_path = Path(doc_path_str).resolve()
    try:
        doc_path.relative_to(_UPLOADS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied.")

    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found on server.")

    filename = contract.get("contract_document_filename") or doc_path.name
    mime = contract.get("contract_document_mime_type") or "application/octet-stream"
    return FileResponse(path=str(doc_path), filename=filename, media_type=mime)


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


@app.post(
    "/contracts/{contract_id}/notice-sent",
    tags=["rent-adjustments"],
    summary="Record that tenant was manually notified of upcoming adjustment",
    response_model=NoticeSentResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found or inactive"},
    },
)
def mark_notice_sent_endpoint(
    contract_id: int,
    payload: NoticeSentRequest | None = None,
):
    today = date.today()
    comment = payload.comment if payload else None

    contract = get_contract(contract_id)
    if contract is None or not contract["is_active"]:
        raise HTTPException(status_code=404, detail="Active contract not found.")

    start_date = date.fromisoformat(contract["start_date"])
    freq = AdjustmentFrequency(contract["adjustment_frequency"])
    due_adj_date = calculate_due_adjustment_date(start_date, freq, today)

    if not mark_notice_sent(contract_id, today, comment, due_adj_date):
        raise HTTPException(status_code=404, detail="Active contract not found.")
    return {"contract_id": contract_id, "notice_sent_at": today}


@app.post(
    "/contracts/{contract_id}/notice-revert",
    tags=["rent-adjustments"],
    summary="Revert a notice previously marked as sent",
    response_model=NoticeRevertResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found or inactive"},
        409: {"model": ErrorResponse, "description": "No active notice to revert"},
    },
)
def revert_notice_sent_endpoint(
    contract_id: int,
    payload: NoticeSentRequest | None = None,
):
    today = date.today()
    comment = payload.comment if payload else None

    contract = get_contract(contract_id)
    if contract is None or not contract["is_active"]:
        raise HTTPException(status_code=404, detail="Active contract not found.")

    start_date = date.fromisoformat(contract["start_date"])
    freq = AdjustmentFrequency(contract["adjustment_frequency"])
    fallback_due_date = calculate_due_adjustment_date(start_date, freq, today)

    try:
        revert_notice_sent(contract_id, today, comment, fallback_due_date)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"contract_id": contract_id}


@app.post(
    "/contracts/{contract_id}/adjustment-alert-dismiss",
    tags=["rent-adjustments"],
    summary="Dismiss the current adjustment alert without changing the rent schedule",
    response_model=AdjustmentDismissResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found or inactive"},
    },
)
def dismiss_adjustment_alert_endpoint(
    contract_id: int,
    payload: NoticeSentRequest | None = None,
):
    today = date.today()
    comment = payload.comment if payload else None

    contract = get_contract(contract_id)
    if contract is None or not contract["is_active"]:
        raise HTTPException(status_code=404, detail="Active contract not found.")

    start_date = date.fromisoformat(contract["start_date"])
    freq = AdjustmentFrequency(contract["adjustment_frequency"])
    due_adj_date = calculate_due_adjustment_date(start_date, freq, today)

    if not dismiss_adjustment_alert(contract_id, today, comment, due_adj_date):
        raise HTTPException(status_code=404, detail="Active contract not found.")
    return {"contract_id": contract_id}


@app.get(
    "/contracts/{contract_id}/notice-events",
    tags=["rent-adjustments"],
    summary="List notice events for a contract",
    response_model=list[NoticeEventItem],
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found"},
    },
)
def list_notice_events_endpoint(contract_id: int):
    try:
        return list_notice_events(contract_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


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

    valid_entries = [e for e in data.payment_entries if e.amount > 0]
    if valid_entries:
        paid_amount = sum(e.amount for e in valid_entries)
        paid_at_dates = [str(e.paid_at) for e in valid_entries if e.paid_at is not None]
        paid_at = max(paid_at_dates) if paid_at_dates else None
        entries_to_save = [e.model_dump() for e in valid_entries]
    else:
        paid_amount = data.paid_amount
        paid_at = str(data.paid_at) if data.paid_at is not None else None
        entries_to_save = []

    paid = paid_amount or 0
    deductions = [d.model_dump() for d in data.deductions]
    owner_expenses = [e.model_dump() for e in data.owner_expenses]
    total_deductions = sum(d["amount"] for d in deductions)
    recognized = paid + total_deductions
    if recognized == 0:
        status = "pending"
    elif recognized >= expected_amount:
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
            deductions=deductions,
            owner_expenses=owner_expenses,
            carry_forward_waived=data.carry_forward_waived,
            payment_entries=entries_to_save,
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

    if "payment_entries" in data.model_fields_set and data.payment_entries is not None:
        valid_entries = [e for e in data.payment_entries if e.amount > 0]
        paid_amount = sum(e.amount for e in valid_entries) or None
        paid_at_dates = [str(e.paid_at) for e in valid_entries if e.paid_at is not None]
        paid_at = max(paid_at_dates) if paid_at_dates else None
        entries_to_save = [e.model_dump() for e in valid_entries]
    else:
        paid_amount = (
            data.paid_amount if data.paid_amount is not None else payment["paid_amount"]
        )
        paid_at = str(data.paid_at) if data.paid_at is not None else payment["paid_at"]
        entries_to_save = None
    comment = data.comment if "comment" in data.model_fields_set else payment["comment"]

    # deductions absent → None (no change); [] → clear; [...] → replace
    deductions = (
        [d.model_dump() for d in data.deductions]
        if "deductions" in data.model_fields_set
        else None
    )
    # owner_expenses absent → None (no change); [] → clear; [...] → replace
    owner_expenses = (
        [e.model_dump() for e in data.owner_expenses]
        if "owner_expenses" in data.model_fields_set
        else None
    )
    # expected_amount absent → keep stored value; provided → replace
    expected_amount = (
        data.expected_amount
        if "expected_amount" in data.model_fields_set and data.expected_amount is not None
        else None
    )
    # carry_forward_waived absent → no change; provided → replace
    carry_forward_waived = (
        data.carry_forward_waived
        if "carry_forward_waived" in data.model_fields_set
        else None
    )

    # Use updated deductions list (or existing ones from DB) for recognized_amount status calc
    if deductions is not None:
        effective_deductions = deductions
    else:
        effective_deductions = payment.get("deductions", [])
    effective_expected = expected_amount if expected_amount is not None else payment["expected_amount"]
    paid = paid_amount or 0
    total_deductions = sum(d["amount"] for d in effective_deductions)
    recognized = paid + total_deductions
    if recognized == 0:
        status = "pending"
    elif recognized >= effective_expected:
        status = "paid"
    else:
        status = "partial"

    update_payment(
        payment_id,
        paid_amount,
        paid_at,
        status,
        comment,
        deductions=deductions,
        owner_expenses=owner_expenses,
        expected_amount=expected_amount,
        carry_forward_waived=carry_forward_waived,
        payment_entries=entries_to_save,
    )
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


@app.post(
    "/contracts/{contract_id}/rent-change-payment",
    tags=["rent-adjustments", "payments"],
    summary="Atomically create a rent change and save/update the payment for that period",
    response_model=RentChangePaymentResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Chronological violation or period conflict"},
        404: {"model": ErrorResponse, "description": "Contract or payment not found"},
    },
)
def rent_change_payment_endpoint(contract_id: int, data: RentChangePaymentCreate):
    try:
        result = rent_change_payment_atomic(
            contract_id=contract_id,
            period=data.period,
            new_rent_amount=data.new_rent_amount,
            paid_amount=data.paid_amount,
            paid_at=str(data.paid_at) if data.paid_at is not None else None,
            comment=data.comment,
            payment_id=data.payment_id,
            deductions=[d.model_dump() for d in data.deductions],
            owner_expenses=[e.model_dump() for e in data.owner_expenses],
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    rc = get_rent_change(result["rent_change_id"])
    return {"rent_change": rc, "payment": result["payment"]}


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


# --- Payment audit: bank statements -----------------------------------------


@app.post(
    "/payment-audit/statements",
    tags=["payment-audit"],
    summary="Upload a bank statement file (cartola)",
    response_model=BankStatementResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Unsupported file type, empty file, or file too large"},
    },
)
async def upload_bank_statement(file: UploadFile = File(...)):
    original_filename = file.filename or ""
    ext = Path(original_filename).suffix.lower()
    if ext not in _CARTOLA_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: .pdf, .xls",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")
    if len(content) > _CARTOLA_MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds maximum size of 20 MB.")

    file_hash = hashlib.sha256(content).hexdigest()

    existing = get_bank_statement_by_file_hash(file_hash)
    if existing is not None:
        return existing

    mime = (file.content_type or "application/octet-stream").split(";")[0].strip()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = _CARTOLAS_DIR / safe_name
    dest.write_bytes(content)

    try:
        statement_id = insert_bank_statement(
            {
                "original_filename": original_filename,
                "stored_path": f"uploads/cartolas/{safe_name}",
                "mime_type": mime,
                "size_bytes": len(content),
                "file_hash": file_hash,
            }
        )
    except Exception:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Failed to save bank statement record.")

    return get_bank_statement(statement_id)


@app.get(
    "/payment-audit/statements",
    tags=["payment-audit"],
    summary="List uploaded bank statements",
    response_model=list[BankStatementResponse],
)
def list_bank_statements_endpoint():
    return list_bank_statements()


@app.delete(
    "/payment-audit/statements/{statement_id}",
    tags=["payment-audit"],
    summary="Delete an uploaded bank statement",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Statement not found"},
        409: {"model": ErrorResponse, "description": "Statement is parsed or has associated movements"},
    },
)
def delete_bank_statement_endpoint(statement_id: int):
    statement = get_bank_statement(statement_id)
    if statement is None:
        raise HTTPException(status_code=404, detail="Bank statement not found.")

    if statement["status"] != "uploaded":
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a statement that has already been parsed.",
        )

    if statement["movements_count"] > 0 or list_bank_movements(statement_id=statement_id):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a statement with associated bank movements.",
        )

    delete_bank_statement(statement_id)

    stored_path = statement.get("stored_path")
    if stored_path:
        file_path = Path(stored_path).resolve()
        try:
            file_path.relative_to(_CARTOLAS_DIR.resolve())
        except ValueError:
            file_path = None
        if file_path is not None:
            file_path.unlink(missing_ok=True)

    return Response(status_code=204)


@app.post(
    "/payment-audit/statements/{statement_id}/parse",
    tags=["payment-audit"],
    summary="Parse an uploaded bank statement into movements",
    response_model=BankStatementResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Statement file type cannot be parsed"},
        404: {"model": ErrorResponse, "description": "Statement not found"},
        409: {"model": ErrorResponse, "description": "Statement already has movements"},
    },
)
def parse_bank_statement_endpoint(statement_id: int):
    statement = get_bank_statement(statement_id)
    if statement is None:
        raise HTTPException(status_code=404, detail="Bank statement not found.")

    ext = Path(statement["stored_path"]).suffix.lower()
    if ext != ".xls":
        raise HTTPException(
            status_code=400,
            detail="Only .xls statements can be parsed.",
        )

    if statement["movements_count"] > 0 or list_bank_movements(statement_id=statement_id):
        raise HTTPException(
            status_code=409,
            detail="Statement already has movements; re-parsing is not supported.",
        )

    parsed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    try:
        content = Path(statement["stored_path"]).read_bytes()
        movements = parse_xls(content)
    except (StatementParseError, OSError) as exc:
        update_bank_statement_parse_result(
            statement_id,
            status="error",
            movements_count=0,
            parse_error=str(exc),
            parsed_at=parsed_at,
        )
        return get_bank_statement(statement_id)

    inserted = 0
    for movement in movements:
        if get_bank_movement_by_dedup_key(movement["dedup_key"]) is not None:
            continue
        insert_bank_movement({**movement, "statement_id": statement_id})
        inserted += 1

    update_bank_statement_parse_result(
        statement_id,
        status="parsed",
        movements_count=inserted,
        parse_error=None,
        parsed_at=parsed_at,
    )
    return get_bank_statement(statement_id)


@app.get(
    "/payment-audit/movements",
    tags=["payment-audit"],
    summary="List parsed bank movements",
    response_model=list[BankMovementResponse],
)
def list_bank_movements_endpoint(statement_id: int | None = None):
    return list_bank_movements(statement_id=statement_id)


@app.post(
    "/payment-audit/run",
    tags=["payment-audit"],
    summary="Run the payment audit engine and produce findings",
    response_model=PaymentAuditRunResponse,
)
def run_payment_audit(body: PaymentAuditRunRequest):
    return payment_audit_engine.run_audit(
        period_from=body.period_from,
        period_to=body.period_to,
    )


@app.get(
    "/payment-audit/findings",
    tags=["payment-audit"],
    summary="List payment audit findings",
    response_model=list[PaymentAuditFindingResponse],
)
def list_payment_audit_findings_endpoint(
    status: str | None = None,
    finding_type: str | None = None,
):
    return list_payment_audit_findings(status=status, finding_type=finding_type)


_COMPLETE_PAYMENT_ERRORS: dict[str, tuple[int, str]] = {
    "not_found": (404, "Finding not found."),
    "not_open": (409, "Finding is not open."),
    "not_match_found": (400, "Only match_found findings can be completed."),
    "movement_not_found": (409, "Bank movement not found."),
    "movement_already_matched": (409, "Bank movement is already matched to a payment."),
    "payment_not_found": (409, "No payment row found for this contract and period."),
    "already_paid": (409, "Payment is already fully paid."),
    "amount_exceeds_remaining": (409, "Movement amount exceeds the remaining balance."),
}


@app.post(
    "/payment-audit/findings/{finding_id}/complete-payment",
    tags=["payment-audit"],
    summary="Complete a payment from a match_found audit finding",
    response_model=PaymentAuditCompletePaymentResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Finding is not of type match_found"},
        404: {"model": ErrorResponse, "description": "Finding not found"},
        409: {"model": ErrorResponse, "description": "Completion not allowed"},
    },
)
def complete_payment_endpoint(finding_id: int):
    try:
        return complete_payment_from_audit_finding(finding_id)
    except ValueError as exc:
        status_code, detail = _COMPLETE_PAYMENT_ERRORS.get(str(exc), (409, str(exc)))
        raise HTTPException(status_code=status_code, detail=detail)


_RESOLVE_MISSING_ERRORS: dict[str, tuple[int, str]] = {
    "not_found": (404, "Finding not found."),
    "not_open": (409, "Finding is not open."),
    "not_missing_payment": (400, "Only missing_payment findings can be resolved here."),
    "note_required": (400, "resolution_note must not be blank."),
}


@app.post(
    "/payment-audit/findings/{finding_id}/resolve-missing-payment",
    tags=["payment-audit"],
    summary="Resolve a missing_payment finding without payment mutation",
    response_model=PaymentAuditFindingResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Wrong finding type or blank note"},
        404: {"model": ErrorResponse, "description": "Finding not found"},
        409: {"model": ErrorResponse, "description": "Finding is not open"},
    },
)
def resolve_missing_payment_endpoint(finding_id: int, body: PaymentAuditResolveFindingRequest):
    try:
        return resolve_missing_payment_finding(finding_id, body.resolution_note)
    except ValueError as exc:
        status_code, detail = _RESOLVE_MISSING_ERRORS.get(str(exc), (409, str(exc)))
        raise HTTPException(status_code=status_code, detail=detail)


_RESOLVE_UNMATCHED_ERRORS: dict[str, tuple[int, str]] = {
    "not_found": (404, "Finding not found."),
    "not_open": (409, "Finding is not open."),
    "not_unmatched_movement": (400, "Only unmatched_movement findings can be resolved here."),
    "note_required": (400, "resolution_note must not be blank."),
}

_RESOLVE_AMOUNT_MISMATCH_ERRORS: dict[str, tuple[int, str]] = {
    "not_found": (404, "Finding not found."),
    "not_open": (409, "Finding is not open."),
    "not_amount_mismatch": (400, "Only amount_mismatch findings can be resolved here."),
    "note_required": (400, "resolution_note must not be blank."),
}


@app.post(
    "/payment-audit/findings/{finding_id}/resolve-unmatched-movement",
    tags=["payment-audit"],
    summary="Resolve an unmatched_movement finding without payment mutation",
    response_model=PaymentAuditFindingResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Wrong finding type or blank note"},
        404: {"model": ErrorResponse, "description": "Finding not found"},
        409: {"model": ErrorResponse, "description": "Finding is not open"},
    },
)
def resolve_unmatched_movement_endpoint(finding_id: int, body: PaymentAuditResolveFindingRequest):
    try:
        return resolve_unmatched_movement_finding(finding_id, body.resolution_note)
    except ValueError as exc:
        status_code, detail = _RESOLVE_UNMATCHED_ERRORS.get(str(exc), (409, str(exc)))
        raise HTTPException(status_code=status_code, detail=detail)


@app.post(
    "/payment-audit/findings/{finding_id}/resolve-amount-mismatch",
    tags=["payment-audit"],
    summary="Resolve an amount_mismatch finding without payment mutation",
    response_model=PaymentAuditFindingResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Wrong finding type or blank note"},
        404: {"model": ErrorResponse, "description": "Finding not found"},
        409: {"model": ErrorResponse, "description": "Finding is not open"},
    },
)
def resolve_amount_mismatch_endpoint(finding_id: int, body: PaymentAuditResolveFindingRequest):
    try:
        return resolve_amount_mismatch_finding(finding_id, body.resolution_note)
    except ValueError as exc:
        status_code, detail = _RESOLVE_AMOUNT_MISMATCH_ERRORS.get(str(exc), (409, str(exc)))
        raise HTTPException(status_code=status_code, detail=detail)
