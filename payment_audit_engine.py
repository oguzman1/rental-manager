import sqlite3
import unicodedata
from datetime import date

import db as _db


def _normalize(s: str) -> str:
    """Uppercase, strip accents, collapse whitespace."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFD", s)
    without_accents = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return " ".join(without_accents.upper().split())


def _names_match(description: str, candidate_names: list[str]) -> bool:
    desc = _normalize(description)
    return any(_normalize(n) and _normalize(n) in desc for n in candidate_names)


def _default_period_range() -> tuple[str, str]:
    today = date.today()
    year, month = today.year, today.month
    start_month = month - 5
    start_year = year
    if start_month <= 0:
        start_month += 12
        start_year -= 1
    return f"{start_year}-{start_month:02d}", f"{year}-{month:02d}"


def _month_range(period_from: str, period_to: str) -> list[str]:
    """Inclusive list of YYYY-MM periods between period_from and period_to."""
    start_year, start_month = int(period_from[:4]), int(period_from[5:7])
    end_year, end_month = int(period_to[:4]), int(period_to[5:7])

    periods = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        periods.append(f"{year}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return periods


def _find_best_match(period_movements: list[dict], expected_amount: int, candidate_names: list[str]):
    """Return (movement, kind, confidence) for the best matching bank movement, or (None, None, None)."""
    best_match = None
    best_kind: str | None = None
    best_confidence: str | None = None

    for m in period_movements:
        amount_eq = m["amount"] == expected_amount
        name_ok = _names_match(m["description"], candidate_names)

        if amount_eq and name_ok:
            return m, "match_found", "high"
        if amount_eq and best_confidence not in ("high",):
            best_match, best_kind, best_confidence = m, "match_found", "medium"
        elif name_ok and best_confidence not in ("high", "medium"):
            best_match, best_kind, best_confidence = m, "amount_mismatch", "low"

    return best_match, best_kind, best_confidence


def _safe_insert(data: dict) -> bool:
    """Insert a finding. Returns False if a duplicate open finding already exists."""
    try:
        _db.insert_payment_audit_finding(data)
        return True
    except (sqlite3.IntegrityError, Exception):
        return False


def run_audit(period_from: str | None = None, period_to: str | None = None) -> dict:
    if not period_from or not period_to:
        default_from, default_to = _default_period_range()
        period_from = period_from or default_from
        period_to = period_to or default_to

    contracts = _db.list_contracts()
    payments = _db.list_payments_in_range(period_from, period_to)
    all_movements = _db.list_bank_movements()

    # Only positive (credit) movements within the audit period
    movements_in_period = [
        m for m in all_movements
        if m["amount"] > 0 and period_from[:7] <= m["movement_date"][:7] <= period_to[:7]
    ]

    contract_map = {c["id"]: c for c in contracts}

    created = 0
    skipped = 0
    summary = {k: 0 for k in ("missing_payment", "match_found", "amount_mismatch")}
    matched_movement_ids: set[int] = set()

    for payment in payments:
        contract = contract_map.get(payment["contract_id"])
        if not contract:
            continue

        expected = payment["expected_amount"]
        paid_amount = payment["paid_amount"] or 0
        remaining = expected - paid_amount
        if payment["status"] == "paid" or paid_amount >= expected or remaining <= 0:
            continue

        period = payment["period"]
        candidate_names = [contract["tenant_name"]]

        period_movements = [m for m in movements_in_period if m["movement_date"][:7] == period]

        best_match, best_kind, best_confidence = _find_best_match(period_movements, expected, candidate_names)

        if best_match is not None:
            matched_movement_ids.add(best_match["id"])
            ok = _safe_insert({
                "finding_type": best_kind,
                "contract_id": payment["contract_id"],
                "period": period,
                "bank_movement_id": best_match["id"],
                "expected_amount": expected,
                "candidate_amount": best_match["amount"],
                "confidence": best_confidence,
            })
            if ok:
                created += 1
                summary[best_kind] += 1
            else:
                skipped += 1
        elif payment["status"] in ("pending", "partial"):
            ok = _safe_insert({
                "finding_type": "missing_payment",
                "contract_id": payment["contract_id"],
                "period": period,
                "bank_movement_id": None,
                "expected_amount": expected,
                "candidate_amount": None,
                "confidence": "high",
            })
            if ok:
                created += 1
                summary["missing_payment"] += 1
            else:
                skipped += 1

    return {
        "created": created,
        "skipped_duplicates": skipped,
        "period_from": period_from,
        "period_to": period_to,
        "summary": summary,
    }


# Worst-to-best ordering for collapsing a contract's month statuses into one.
_MONTH_STATUS_RANK = {
    "matched_registered": 0,
    "found_not_registered": 1,
    "registered_not_found": 1,
    "missing": 2,
}


def build_contract_summary(period_from: str | None = None, period_to: str | None = None) -> dict:
    """Per-contract, per-month audit status for the given period.

    For each active contract and each period in range that has a payment row,
    two independent signals are checked: whether the payment is registered in
    Rental Manager, and whether a compatible bank movement was found in the
    uploaded/processed cartolas.

    - "matched_registered": the payment is registered AND a compatible
      movement was found.
    - "registered_not_found": the payment is registered but no compatible
      movement was found in the cartola data.
    - "found_not_registered": a compatible bank movement exists but the
      payment is not yet registered.
    - "missing": the payment is expected but neither a registration nor a
      compatible movement was found.

    A contract's overall_status is the worst of its month statuses, or
    "no_data" if it has no payment rows in the period.
    """
    if not period_from or not period_to:
        default_from, default_to = _default_period_range()
        period_from = period_from or default_from
        period_to = period_to or default_to

    contracts = _db.list_contracts()
    payments = _db.list_payments_in_range(period_from, period_to)
    all_movements = _db.list_bank_movements()

    movements_in_period = [
        m for m in all_movements
        if m["amount"] > 0 and period_from[:7] <= m["movement_date"][:7] <= period_to[:7]
    ]

    payments_by_contract: dict[int, dict[str, dict]] = {}
    for payment in payments:
        payments_by_contract.setdefault(payment["contract_id"], {})[payment["period"]] = payment

    contract_rows = []
    for contract in contracts:
        candidate_names = [contract["tenant_name"]]
        contract_payments = payments_by_contract.get(contract["id"], {})

        months = []
        for period in _month_range(period_from, period_to):
            payment = contract_payments.get(period)
            if payment is None:
                continue

            expected = payment["expected_amount"]
            paid_amount = payment["paid_amount"] or 0
            remaining = expected - paid_amount
            registered = payment["status"] == "paid" or paid_amount >= expected or remaining <= 0

            period_movements = [m for m in movements_in_period if m["movement_date"][:7] == period]
            best_match, _, _ = _find_best_match(period_movements, expected, candidate_names)
            movement_found = best_match is not None

            if registered and movement_found:
                status = "matched_registered"
            elif registered and not movement_found:
                status = "registered_not_found"
            elif not registered and movement_found:
                status = "found_not_registered"
            else:
                status = "missing"

            months.append({
                "period": period,
                "status": status,
                "expected_amount": expected,
                "paid_amount": paid_amount,
            })

        if months:
            overall_status = max(months, key=lambda mo: _MONTH_STATUS_RANK[mo["status"]])["status"]
        else:
            overall_status = "no_data"

        contract_rows.append({
            "contract_id": contract["id"],
            "property_label": contract["property_label"],
            "tenant_name": contract["tenant_name"],
            "overall_status": overall_status,
            "months": months,
        })

    return {
        "period_from": period_from,
        "period_to": period_to,
        "contracts": contract_rows,
    }
