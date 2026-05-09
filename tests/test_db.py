from datetime import date
from pathlib import Path

import pytest

import db
from models import AdjustmentFrequency, ManagedPropertyCreate, PropertyInfo, RentalInfo


def _get_contract_id(property_id: int) -> int:
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM contracts WHERE property_id = ?", (property_id,)
        ).fetchone()
    assert row is not None
    return row[0]


def _get_payments(contract_id: int) -> list[dict]:
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM payments WHERE contract_id = ? ORDER BY period",
            (contract_id,),
        ).fetchall()
    return [db._payment_row_to_dict(r) for r in rows]


def _make_property(rol="00001-00001", status="occupied"):
    return PropertyInfo(
        comuna="TEST",
        rol=rol,
        address="Calle Test 123",
        destination="HABITACIONAL",
        status=status,
    )


def _make_rental(label="depto test", tenant="Test Tenant", rent=500000):
    return RentalInfo(
        property_label=label,
        tenant_name=tenant,
        payment_day=5,
        current_rent=rent,
        adjustment_frequency=AdjustmentFrequency.annual,
        start_date=date(2024, 1, 1),
        notice_days=30,
        adjustment_month="january",
    )


@pytest.fixture(autouse=True)
def fresh_db():
    db_path = Path(db.DB_NAME)
    if db_path.exists():
        db_path.unlink()
    db.init_db()
    yield
    if db_path.exists():
        db_path.unlink()
    db.init_db()


def test_insert_creates_all_related_rows():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    property_id = db.insert_managed_property(data)

    with db.get_connection() as conn:
        prop = conn.execute(
            "SELECT id FROM properties WHERE id = ?", (property_id,)
        ).fetchone()
        contract = conn.execute(
            "SELECT id FROM contracts WHERE property_id = ?", (property_id,)
        ).fetchone()
        assert contract is not None
        contract_id = contract[0]

        tenant = conn.execute(
            """
            SELECT t.id FROM tenants t
            JOIN contract_tenants ct ON ct.tenant_id = t.id
            WHERE ct.contract_id = ?
            """,
            (contract_id,),
        ).fetchone()
        rent_change = conn.execute(
            "SELECT id FROM rent_changes WHERE contract_id = ?", (contract_id,)
        ).fetchone()

    assert prop is not None
    assert tenant is not None
    assert rent_change is not None


def test_update_does_not_create_new_rent_change():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental(rent=500000))
    property_id = db.insert_managed_property(data)

    updated = ManagedPropertyCreate(
        property=_make_property(), rental=_make_rental(rent=999999)
    )
    db.update_managed_property(property_id, updated)

    with db.get_connection() as conn:
        contract_id = conn.execute(
            "SELECT id FROM contracts WHERE property_id = ?", (property_id,)
        ).fetchone()[0]
        count = conn.execute(
            "SELECT COUNT(*) FROM rent_changes WHERE contract_id = ?", (contract_id,)
        ).fetchone()[0]

    assert count == 1


def test_inventory_fields_persist():
    prop = PropertyInfo(
        comuna="TEST",
        rol="00001-00001",
        address="Calle Test 123",
        destination="HABITACIONAL",
        status="occupied",
        fojas="2933",
        property_number="2121",
        year=2016,
        fiscal_appraisal=142935366,
    )
    data = ManagedPropertyCreate(property=prop, rental=_make_rental())
    property_id = db.insert_managed_property(data)

    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT fojas, property_number, year, fiscal_appraisal FROM properties WHERE id = ?",
            (property_id,),
        ).fetchone()

    assert row[0] == "2933"
    assert row[1] == "2121"
    assert row[2] == 2016
    assert row[3] == 142935366


def test_latest_rent_change_with_tiebreak():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental(rent=500000))
    property_id = db.insert_managed_property(data)

    with db.get_connection() as conn:
        contract_id = conn.execute(
            "SELECT id FROM contracts WHERE property_id = ?", (property_id,)
        ).fetchone()[0]

        # Pin the initial entry to a known date/amount
        conn.execute(
            "UPDATE rent_changes SET effective_from = '2024-01-01', amount = 500000 WHERE contract_id = ?",
            (contract_id,),
        )
        # Two entries with the same effective_from — lower id inserted first
        conn.execute(
            "INSERT INTO rent_changes (contract_id, effective_from, amount) VALUES (?, '2024-06-01', 600000)",
            (contract_id,),
        )
        # Higher id, same effective_from → tiebreak winner between these two
        conn.execute(
            "INSERT INTO rent_changes (contract_id, effective_from, amount) VALUES (?, '2024-06-01', 650000)",
            (contract_id,),
        )
        # Latest by date — overall winner
        conn.execute(
            "INSERT INTO rent_changes (contract_id, effective_from, amount) VALUES (?, '2025-01-01', 700000)",
            (contract_id,),
        )
        conn.commit()

    items = db.list_dashboard_items()
    item = next(i for i in items if i["id"] == property_id)
    assert item["current_rent"] == 700000

    # Remove 2025-01-01 to isolate the same-date tiebreak
    with db.get_connection() as conn:
        conn.execute(
            "DELETE FROM rent_changes WHERE contract_id = ? AND effective_from = '2025-01-01'",
            (contract_id,),
        )
        conn.commit()

    items = db.list_dashboard_items()
    item = next(i for i in items if i["id"] == property_id)
    assert item["current_rent"] == 650000


def test_delete_removes_all_related_rows():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    property_id = db.insert_managed_property(data)

    with db.get_connection() as conn:
        contract_id = conn.execute(
            "SELECT id FROM contracts WHERE property_id = ?", (property_id,)
        ).fetchone()[0]

    db.delete_managed_property(property_id)

    with db.get_connection() as conn:
        assert conn.execute(
            "SELECT id FROM properties WHERE id = ?", (property_id,)
        ).fetchone() is None
        assert conn.execute(
            "SELECT id FROM contracts WHERE property_id = ?", (property_id,)
        ).fetchone() is None
        assert conn.execute(
            "SELECT id FROM rent_changes WHERE contract_id = ?", (contract_id,)
        ).fetchone() is None
        assert conn.execute(
            "SELECT id FROM contract_tenants WHERE contract_id = ?", (contract_id,)
        ).fetchone() is None


def test_update_syncs_display_name_with_property_label():
    data = ManagedPropertyCreate(
        property=_make_property(), rental=_make_rental(label="label original")
    )
    property_id = db.insert_managed_property(data)

    updated = ManagedPropertyCreate(
        property=_make_property(), rental=_make_rental(label="label actualizado")
    )
    db.update_managed_property(property_id, updated)

    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT display_name FROM properties WHERE id = ?", (property_id,)
        ).fetchone()

    assert row[0] == "label actualizado"


# ============================================================
# Payment period generation
# ============================================================

def test_insert_managed_property_generates_12_periods():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)
    payments = _get_payments(cid)
    assert len(payments) == 12


def test_generated_periods_start_from_contract_start_date():
    rental = _make_rental()  # start_date = 2024-01-01
    data = ManagedPropertyCreate(property=_make_property(), rental=rental)
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)
    payments = _get_payments(cid)
    periods = [p["period"] for p in payments]
    assert periods[0] == "2024-01"
    assert periods[-1] == "2024-12"


def test_generated_periods_use_payment_day_for_due_date():
    rental = _make_rental()  # payment_day = 5, start_date = 2024-01-01
    data = ManagedPropertyCreate(property=_make_property(), rental=rental)
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)
    payments = _get_payments(cid)
    jan = next(p for p in payments if p["period"] == "2024-01")
    assert jan["due_date"] == "2024-01-05"


def test_generated_periods_clamp_due_date_for_short_months():
    rental = RentalInfo(
        property_label="test",
        tenant_name="T",
        payment_day=31,
        current_rent=500000,
        adjustment_frequency=AdjustmentFrequency.annual,
        start_date=date(2024, 2, 1),
        notice_days=0,
        adjustment_month="february",
    )
    data = ManagedPropertyCreate(property=_make_property(), rental=rental)
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)
    payments = _get_payments(cid)
    feb = next(p for p in payments if p["period"] == "2024-02")
    assert feb["due_date"] == "2024-02-29"  # 2024 is a leap year


def test_generated_periods_status_is_pending():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)
    payments = _get_payments(cid)
    assert all(p["status"] == "pending" for p in payments)
    assert all(p["paid_amount"] is None for p in payments)


def test_generated_periods_expected_amount_matches_rent():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental(rent=750000))
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)
    payments = _get_payments(cid)
    assert all(p["expected_amount"] == 750000 for p in payments)


def test_generate_periods_with_end_date():
    rental = RentalInfo(
        property_label="test",
        tenant_name="T",
        payment_day=5,
        current_rent=500000,
        adjustment_frequency=AdjustmentFrequency.annual,
        start_date=date(2024, 1, 1),
        notice_days=0,
        adjustment_month="january",
    )
    data = ManagedPropertyCreate(property=_make_property(), rental=rental)
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)

    # Manually invoke with end_date to verify the logic
    with db.get_connection() as conn:
        # Clear auto-generated and re-generate with end_date
        conn.execute("DELETE FROM payments WHERE contract_id = ?", (cid,))
        db.generate_payment_periods(
            conn,
            contract_id=cid,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            payment_day=5,
            current_rent=500000,
        )
        conn.commit()

    payments = _get_payments(cid)
    periods = [p["period"] for p in payments]
    assert periods == ["2024-01", "2024-02", "2024-03"]


def test_generate_periods_idempotent():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)

    # Run again — INSERT OR IGNORE should not create duplicates
    with db.get_connection() as conn:
        db.generate_payment_periods(
            conn,
            contract_id=cid,
            start_date=date(2024, 1, 1),
            end_date=None,
            payment_day=5,
            current_rent=500000,
        )
        conn.commit()

    payments = _get_payments(cid)
    assert len(payments) == 12


# ============================================================
# Overpayment
# ============================================================

def _setup_paid_period(contract_id: int, period: str, paid_amount: int) -> int:
    """Set paid_amount on a period (creating it if needed). Returns payment id."""
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT c.payment_day, (
                SELECT amount FROM rent_changes WHERE contract_id = c.id
                ORDER BY effective_from DESC, id DESC LIMIT 1
            ) FROM contracts c WHERE c.id = ?
            """,
            (contract_id,),
        ).fetchone()
        payment_day, expected = row[0], row[1]
        status = "paid" if paid_amount >= expected else "partial" if paid_amount > 0 else "pending"

        existing = conn.execute(
            "SELECT id FROM payments WHERE contract_id = ? AND period = ?",
            (contract_id, period),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE payments SET paid_amount = ?, paid_at = '2024-06-05', status = ? WHERE id = ?",
                (paid_amount, status, existing[0]),
            )
            pid = existing[0]
        else:
            year, month = int(period[:4]), int(period[5:7])
            from calendar import monthrange
            last_day = monthrange(year, month)[1]
            day = min(payment_day, last_day)
            due_date = f"{year}-{month:02d}-{day:02d}"
            cursor = conn.execute(
                """
                INSERT INTO payments
                    (contract_id, period, due_date, expected_amount, paid_amount, paid_at, status, source)
                VALUES (?, ?, ?, ?, ?, '2024-06-05', ?, 'manual')
                """,
                (contract_id, period, due_date, expected, paid_amount, status),
            )
            pid = cursor.lastrowid
        conn.commit()
    return pid


def test_overpayment_computed_in_payment_row():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental(rent=500000))
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)

    # Overpay 2024-01 by 100000
    pid = _setup_paid_period(cid, "2024-01", 600000)
    payment = db.get_payment(pid)
    assert payment["overpayment"] == 100000
    assert payment["status"] == "paid"


def test_overpayment_zero_when_not_overpaid():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental(rent=500000))
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)
    pid = _setup_paid_period(cid, "2024-01", 500000)
    payment = db.get_payment(pid)
    assert payment["overpayment"] == 0


def test_apply_overpayment_reduces_current_to_expected():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental(rent=500000))
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)
    pid = _setup_paid_period(cid, "2024-01", 600000)

    updated_current, _ = db.apply_overpayment_to_next_period(pid)
    assert updated_current["paid_amount"] == 500000
    assert updated_current["overpayment"] == 0
    assert updated_current["status"] == "paid"


def test_apply_overpayment_moves_excess_to_next_period():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental(rent=500000))
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)
    pid = _setup_paid_period(cid, "2024-01", 600000)

    _, updated_next = db.apply_overpayment_to_next_period(pid)
    assert updated_next["period"] == "2024-02"
    assert updated_next["paid_amount"] == 100000
    assert updated_next["status"] == "partial"


def test_apply_overpayment_adds_to_existing_next_period():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental(rent=500000))
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)

    pid_jan = _setup_paid_period(cid, "2024-01", 600000)

    # Pre-seed 2024-02 with some payment already
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE payments SET paid_amount = 200000, status = 'partial' WHERE contract_id = ? AND period = '2024-02'",
            (cid,),
        )
        conn.commit()

    _, updated_next = db.apply_overpayment_to_next_period(pid_jan)
    assert updated_next["period"] == "2024-02"
    # 200000 existing + 100000 excess = 300000
    assert updated_next["paid_amount"] == 300000
    assert updated_next["status"] == "partial"


def test_apply_overpayment_raises_when_no_overpayment():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental(rent=500000))
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)
    pid = _setup_paid_period(cid, "2024-01", 500000)

    with pytest.raises(ValueError, match="No overpayment"):
        db.apply_overpayment_to_next_period(pid)


# ============================================================
# close_contract pruning
# ============================================================

def test_close_contract_removes_future_pending_periods():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)
    # start_date 2024-01-01 → periods 2024-01 to 2024-12

    # Mark 2024-03 as paid
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE payments SET paid_amount = 500000, status = 'paid' WHERE contract_id = ? AND period = '2024-03'",
            (cid,),
        )
        conn.commit()

    # Close with end_date 2024-03-31 → remove pending periods > 2024-03
    db.close_contract(cid, "2024-03-31")

    payments = _get_payments(cid)
    remaining_periods = {p["period"] for p in payments}

    assert "2024-04" not in remaining_periods
    assert "2024-12" not in remaining_periods
    assert "2024-03" in remaining_periods  # paid — kept
    assert "2024-01" in remaining_periods  # pending but within range — kept
    assert "2024-02" in remaining_periods


def test_close_contract_keeps_all_paid_periods():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    property_id = db.insert_managed_property(data)
    cid = _get_contract_id(property_id)

    # Pay all 12 periods
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE payments SET paid_amount = 500000, status = 'paid' WHERE contract_id = ?",
            (cid,),
        )
        conn.commit()

    db.close_contract(cid, "2024-12-31")

    payments = _get_payments(cid)
    assert len(payments) == 12


# ============================================================
# bootstrap_payment_periods_for_active_contracts
# ============================================================

def _make_rental_with_start(start: date, rent: int = 500000) -> RentalInfo:
    return RentalInfo(
        property_label="depto test",
        tenant_name="Test Tenant",
        payment_day=5,
        current_rent=rent,
        adjustment_frequency=AdjustmentFrequency.annual,
        start_date=start,
        notice_days=30,
        adjustment_month="january",
    )


def _make_property_unique(rol: str) -> PropertyInfo:
    return PropertyInfo(
        comuna="TEST",
        rol=rol,
        address="Calle Test 123",
        destination="HABITACIONAL",
        status="occupied",
    )


def _clear_payments(contract_id: int) -> None:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM payments WHERE contract_id = ?", (contract_id,))
        conn.commit()


def test_bootstrap_creates_historical_periods_as_paid():
    TODAY = date(2024, 3, 1)
    data = ManagedPropertyCreate(
        property=_make_property_unique("99001-00001"),
        rental=_make_rental_with_start(date(2024, 1, 1)),
    )
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)
    _clear_payments(cid)

    db.bootstrap_payment_periods_for_active_contracts(today=TODAY)

    historical = [p for p in _get_payments(cid) if p["period"] < "2024-03"]
    assert len(historical) == 2  # 2024-01, 2024-02
    for p in historical:
        assert p["status"] == "paid"
        assert p["source"] == "manual"
        assert p["paid_amount"] == p["expected_amount"]
        assert p["paid_at"] == p["due_date"]
        assert p["comment"] == "Carga histórica inicial"


def test_bootstrap_creates_operational_periods_as_pending():
    TODAY = date(2024, 3, 1)
    data = ManagedPropertyCreate(
        property=_make_property_unique("99002-00001"),
        rental=_make_rental_with_start(date(2024, 1, 1)),
    )
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)
    _clear_payments(cid)

    db.bootstrap_payment_periods_for_active_contracts(today=TODAY)

    operational = [p for p in _get_payments(cid) if p["period"] >= "2024-03"]
    assert len(operational) == 13  # 2024-03 through 2025-03
    for p in operational:
        assert p["status"] == "pending"
        assert p["source"] == "manual"
        assert p["paid_amount"] is None
        assert p["paid_at"] is None
        assert p["comment"] is None


def test_bootstrap_does_not_modify_existing_rows():
    TODAY = date(2024, 3, 1)
    data = ManagedPropertyCreate(
        property=_make_property_unique("99003-00001"),
        rental=_make_rental_with_start(date(2024, 1, 1)),
    )
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)

    # Set 2024-01 to a custom partial state (auto-generated, already exists)
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE payments
            SET paid_amount = 300000, status = 'partial', comment = 'pago parcial'
            WHERE contract_id = ? AND period = '2024-01'
            """,
            (cid,),
        )
        conn.commit()

    db.bootstrap_payment_periods_for_active_contracts(today=TODAY)

    jan = next(p for p in _get_payments(cid) if p["period"] == "2024-01")
    assert jan["status"] == "partial"
    assert jan["paid_amount"] == 300000
    assert jan["comment"] == "pago parcial"


def test_bootstrap_is_idempotent():
    TODAY = date(2024, 3, 1)
    data = ManagedPropertyCreate(
        property=_make_property_unique("99004-00001"),
        rental=_make_rental_with_start(date(2024, 1, 1)),
    )
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)
    _clear_payments(cid)

    db.bootstrap_payment_periods_for_active_contracts(today=TODAY)
    count_first = len(_get_payments(cid))

    db.bootstrap_payment_periods_for_active_contracts(today=TODAY)
    count_second = len(_get_payments(cid))

    assert count_first == count_second
    assert count_first == 15  # 2 historical + 13 operational


def test_bootstrap_ignores_inactive_contracts():
    TODAY = date(2024, 3, 1)
    data = ManagedPropertyCreate(
        property=_make_property_unique("99005-00001"),
        rental=_make_rental_with_start(date(2024, 1, 1)),
    )
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)

    with db.get_connection() as conn:
        conn.execute("UPDATE contracts SET is_active = 0 WHERE id = ?", (cid,))
        conn.execute("DELETE FROM payments WHERE contract_id = ?", (cid,))
        conn.commit()

    db.bootstrap_payment_periods_for_active_contracts(today=TODAY)

    assert len(_get_payments(cid)) == 0


def test_bootstrap_clears_dashboard_historical_gap():
    # Use a start_date well in the past so there are guaranteed historical gaps.
    start_date = date(2024, 1, 1)
    data = ManagedPropertyCreate(
        property=_make_property_unique("99006-00001"),
        rental=_make_rental_with_start(start_date),
    )
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)
    _clear_payments(cid)

    today_ym = date.today().strftime("%Y-%m")

    # Before bootstrap: dashboard shows a historical gap
    items = db.list_dashboard_items()
    item = next(i for i in items if i["id"] == pid)
    assert item["actionable_payment_period"] is not None
    assert item["actionable_payment_period"] < today_ym

    db.bootstrap_payment_periods_for_active_contracts()

    # After bootstrap: earliest unpaid period is current month, not historical
    items = db.list_dashboard_items()
    item = next(i for i in items if i["id"] == pid)
    if item["actionable_payment_period"] is not None:
        assert item["actionable_payment_period"] >= today_ym


# ─── Payment deductions ────────────────────────────────────────────────────────

def _insert_test_payment(contract_id: int, period: str = "2030-01", paid: int | None = None) -> int:
    return db.insert_payment(
        contract_id=contract_id,
        period=period,
        due_date=f"{period}-05",
        expected_amount=500000,
        comment=None,
        paid_amount=paid,
        paid_at=None,
        status="paid" if paid and paid >= 500000 else ("partial" if paid else "pending"),
    )


def test_insert_payment_with_deductions_stores_rows():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)

    payment_id = db.insert_payment(
        contract_id=cid,
        period="2030-01",
        due_date="2030-01-05",
        expected_amount=500000,
        comment=None,
        paid_amount=500000,
        status="paid",
        deductions=[
            {"label": "Comisión corredora", "amount": 22647, "note": "Liquidación"},
            {"label": "Reparación cocina", "amount": 35700, "note": None},
        ],
    )

    result = db.get_payment(payment_id)
    assert result is not None
    assert len(result["deductions"]) == 2
    labels = [d["label"] for d in result["deductions"]]
    assert "Comisión corredora" in labels
    assert "Reparación cocina" in labels
    assert result["net_owner_amount"] == 500000 - 22647 - 35700


def test_insert_payment_no_deductions_net_equals_paid():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)

    payment_id = _insert_test_payment(cid, period="2030-02", paid=500000)
    result = db.get_payment(payment_id)
    assert result["deductions"] == []
    assert result["net_owner_amount"] == 500000


def test_update_payment_replaces_deductions():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)

    payment_id = db.insert_payment(
        contract_id=cid,
        period="2030-03",
        due_date="2030-03-05",
        expected_amount=500000,
        comment=None,
        paid_amount=500000,
        status="paid",
        deductions=[{"label": "Original", "amount": 10000}],
    )

    db.update_payment(
        payment_id=payment_id,
        paid_amount=500000,
        paid_at=None,
        status="paid",
        comment=None,
        deductions=[
            {"label": "Nueva comisión", "amount": 25000},
            {"label": "Reparación", "amount": 15000},
        ],
    )

    result = db.get_payment(payment_id)
    assert len(result["deductions"]) == 2
    labels = [d["label"] for d in result["deductions"]]
    assert "Original" not in labels
    assert "Nueva comisión" in labels
    assert result["net_owner_amount"] == 500000 - 25000 - 15000


def test_update_payment_none_deductions_keeps_existing():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)

    payment_id = db.insert_payment(
        contract_id=cid,
        period="2030-04",
        due_date="2030-04-05",
        expected_amount=500000,
        comment=None,
        paid_amount=500000,
        status="paid",
        deductions=[{"label": "Honorarios corredora", "amount": 50000}],
    )

    db.update_payment(
        payment_id=payment_id,
        paid_amount=600000,
        paid_at=None,
        status="paid",
        comment=None,
        deductions=None,  # no change
    )

    result = db.get_payment(payment_id)
    assert len(result["deductions"]) == 1
    assert result["deductions"][0]["label"] == "Honorarios corredora"


def test_update_payment_empty_list_clears_deductions():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)

    payment_id = db.insert_payment(
        contract_id=cid,
        period="2030-05",
        due_date="2030-05-05",
        expected_amount=500000,
        comment=None,
        paid_amount=500000,
        status="paid",
        deductions=[{"label": "Honorarios corredora", "amount": 50000}],
    )

    db.update_payment(
        payment_id=payment_id,
        paid_amount=500000,
        paid_at=None,
        status="paid",
        comment=None,
        deductions=[],
    )

    result = db.get_payment(payment_id)
    assert result["deductions"] == []
    assert result["net_owner_amount"] == 500000


def test_delete_payment_removes_deduction_rows():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)

    payment_id = db.insert_payment(
        contract_id=cid,
        period="2030-06",
        due_date="2030-06-05",
        expected_amount=500000,
        comment=None,
        deductions=[{"label": "Honorarios corredora", "amount": 50000}],
    )

    db.delete_payment(payment_id)

    with db.get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM payment_deductions WHERE payment_id = ?", (payment_id,)
        ).fetchone()[0]
    assert count == 0


def test_net_owner_amount_negative_when_deductions_exceed_paid():
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)

    payment_id = db.insert_payment(
        contract_id=cid,
        period="2030-07",
        due_date="2030-07-05",
        expected_amount=500000,
        comment=None,
        paid_amount=500000,
        status="paid",
        deductions=[{"label": "Gran descuento", "amount": 600000}],
    )

    result = db.get_payment(payment_id)
    assert result["net_owner_amount"] == 500000 - 600000  # -100000
    assert result["net_owner_amount"] < 0


def test_list_payments_includes_deductions_no_n_plus_one():
    """list_payments_for_contract loads deductions without N+1 queries."""
    data = ManagedPropertyCreate(property=_make_property(), rental=_make_rental())
    pid = db.insert_managed_property(data)
    cid = _get_contract_id(pid)

    db.insert_payment(
        contract_id=cid, period="2030-08", due_date="2030-08-05",
        expected_amount=500000, comment=None, paid_amount=500000, status="paid",
        deductions=[{"label": "Comisión A", "amount": 10000}],
    )
    db.insert_payment(
        contract_id=cid, period="2030-09", due_date="2030-09-05",
        expected_amount=500000, comment=None, paid_amount=500000, status="paid",
        deductions=[{"label": "Comisión B", "amount": 20000}, {"label": "Reparación B", "amount": 5000}],
    )

    payments = db.list_payments_for_contract(cid)
    # Payments are ordered period DESC, so 2030-09 first
    p1 = next(p for p in payments if p["period"] == "2030-08")
    p2 = next(p for p in payments if p["period"] == "2030-09")
    assert len(p1["deductions"]) == 1
    assert p1["deductions"][0]["label"] == "Comisión A"
    assert len(p2["deductions"]) == 2
    assert p2["net_owner_amount"] == 500000 - 20000 - 5000


def _get_any_contract_id() -> int:
    """Return the id of the first contract in the DB, creating one if none exist."""
    with db.get_connection() as conn:
        row = conn.execute("SELECT id FROM contracts LIMIT 1").fetchone()
    if row:
        return row[0]
    from models import ManagedPropertyCreate
    data = ManagedPropertyCreate(property=_make_property(rol="MIGR-00001"), rental=_make_rental())
    pid = db.insert_managed_property(data)
    return _get_contract_id(pid)


def test_legacy_migration_converts_fixed_columns_to_deduction_rows():
    """init_db migrates non-zero brokerage_fee/repair_discount/other_discount into
    payment_deductions and zeroes the legacy columns."""
    cid = _get_any_contract_id()

    with db.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO payments
                (contract_id, period, due_date, expected_amount, paid_amount, status,
                 source, brokerage_fee, repair_discount, other_discount)
            VALUES (?, '2029-01', '2029-01-05', 500000, 500000, 'paid', 'manual',
                   22647, 35700, 0)
            """,
            (cid,),
        )
        conn.commit()
        payment_id = cursor.lastrowid

    db.init_db()

    with db.get_connection() as conn:
        ded_rows = conn.execute(
            "SELECT label, amount FROM payment_deductions WHERE payment_id = ? ORDER BY sort_order",
            (payment_id,),
        ).fetchall()
        legacy_row = conn.execute(
            "SELECT brokerage_fee, repair_discount, other_discount FROM payments WHERE id = ?",
            (payment_id,),
        ).fetchone()

    assert len(ded_rows) == 2
    assert ded_rows[0] == ("Honorarios corredora", 22647)
    assert ded_rows[1] == ("Descuento reparación", 35700)
    assert legacy_row == (0, 0, 0)


def test_legacy_migration_is_idempotent():
    """Running init_db a second time does not duplicate deduction rows."""
    cid = _get_any_contract_id()

    with db.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO payments
                (contract_id, period, due_date, expected_amount, paid_amount, status,
                 source, brokerage_fee, repair_discount, other_discount)
            VALUES (?, '2029-02', '2029-02-05', 500000, 500000, 'paid', 'manual',
                   10000, 0, 0)
            """,
            (cid,),
        )
        conn.commit()
        payment_id = cursor.lastrowid

    db.init_db()  # first run: migrates
    db.init_db()  # second run: guard fires (legacy cols already zero), no duplicates

    with db.get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM payment_deductions WHERE payment_id = ?",
            (payment_id,),
        ).fetchone()[0]

    assert count == 1
