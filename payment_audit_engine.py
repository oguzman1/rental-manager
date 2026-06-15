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

        best_match = None
        best_kind: str | None = None
        best_confidence: str | None = None

        for m in period_movements:
            amount_eq = m["amount"] == expected
            name_ok = _names_match(m["description"], candidate_names)

            if amount_eq and name_ok:
                best_match, best_kind, best_confidence = m, "match_found", "high"
                break
            if amount_eq and best_confidence not in ("high",):
                best_match, best_kind, best_confidence = m, "match_found", "medium"
            elif name_ok and best_confidence not in ("high", "medium"):
                best_match, best_kind, best_confidence = m, "amount_mismatch", "low"

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
