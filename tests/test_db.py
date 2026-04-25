from datetime import date
from pathlib import Path

import pytest

import db
from models import AdjustmentFrequency, ManagedPropertyCreate, PropertyInfo, RentalInfo


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
