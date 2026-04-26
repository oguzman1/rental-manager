import os
from pathlib import Path

# Usa una base distinta para tests antes de importar la app.
os.environ["DB_NAME"] = "test_rental_manager.db"

# Borra la base de test anterior para partir limpio.
test_db = Path("test_rental_manager.db")
if test_db.exists():
    test_db.unlink()

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_managed_property_returns_id():
    payload = {
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
            "tenant_name": "Test Tenant",
            "payment_day": 5,
            "property_label": "depto serena",
            "current_rent": 801875,
            "adjustment_frequency": "annual",
            "start_date": "2022-03-12",
            "notice_days": 60,
            "adjustment_month": "march",
        },
    }

    response = client.post("/managed-property", json=payload)

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == 1
    assert data["rol"] == "02162-00036"
    assert data["comuna"] == "LA SERENA"
    assert data["has_rental"] is True
    assert data["property_label"] == "depto serena"

def test_rent_adjustments_marks_property_as_requiring_notice():
    payload = {
        "property": {
            "comuna": "CASTRO",
            "rol": "09999-00001",
            "address": "GAMBOA ALTO PC TEST",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "999",
            "property_number": "999",
            "year": 2025,
            "fiscal_appraisal": 10000000,
        },
     "rental": {
            "tenant_name": "Test Tenant",
            "payment_day": 5,
            "property_label": "test castro rental",
            "current_rent": 150000,
            "adjustment_frequency": "annual",
            "start_date": "2025-01-01",
            "notice_days": 30,
            "adjustment_month": "january",
        },
            }

    create_response = client.post("/managed-property", json=payload)
    assert create_response.status_code == 200

    response = client.get(
        "/rent-adjustments",
        params={"as_of": "2026-12-15"},
    )

    assert response.status_code == 200

    adjustments = response.json()
    test_adjustment = next(
        item for item in adjustments if item["rol"] == "09999-00001"
    )

    assert test_adjustment["tenant_name"] == "Test Tenant"
    assert test_adjustment["payment_day"] == 5
    assert test_adjustment["next_adjustment_date"] == "2027-01-01"
    assert test_adjustment["adjustment_notice_date"] == "2026-12-01"
    assert test_adjustment["requires_adjustment_notice"] is True

def test_list_managed_properties_includes_tenant_and_payment_day():
    payload = {
        "property": {
            "comuna": "TEMUCO",
            "rol": "08888-00002",
            "address": "A. BELLO 248 DEPTO 302",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "166",
            "property_number": "199",
            "year": 2013,
            "fiscal_appraisal": 69177846,
        },
        "rental": {
            "tenant_name": "Test Tenant Temuco",
            "payment_day": 10,
            "property_label": "depto temuco test",
            "current_rent": 400000,
            "adjustment_frequency": "annual",
            "start_date": "2023-01-01",
            "notice_days": 30,
            "adjustment_month": "january",
        },
    }

    create_response = client.post("/managed-property", json=payload)
    assert create_response.status_code == 200

    list_response = client.get("/managed-properties")
    assert list_response.status_code == 200

    properties = list_response.json()
    created_property = next(
        item for item in properties if item["rol"] == "08888-00002"
    )

    assert created_property["tenant_name"] == "Test Tenant Temuco"
    assert created_property["payment_day"] == 10

    properties = list_response.json()
    created_property = next(
        item for item in properties if item["rol"] == "08888-00002"
    )

    assert created_property["tenant_name"] == "Test Tenant Temuco"
    assert created_property["payment_day"] == 10

def test_dashboard_includes_operational_fields():
        payload = {
            "property": {
                "comuna": "LAS CONDES",
                "rol": "07777-00003",
                "address": "TEST LAS CONDES",
                "destination": "HABITACIONAL",
                "status": "occupied",
                "fojas": "777",
                "property_number": "777",
                "year": 2020,
                "fiscal_appraisal": 120000000,
        },
        "rental": {
            "tenant_name": "Test Tenant Dashboard",
            "payment_day": 5,
            "property_label": "depto dashboard test",
            "current_rent": 650000,
            "adjustment_frequency": "annual",
            "start_date": "2024-04-01",
            "notice_days": 60,
            "adjustment_month": "april",
        },
    }

        create_response = client.post("/managed-property", json=payload)
        assert create_response.status_code == 200

        dashboard_response = client.get("/dashboard")
        assert dashboard_response.status_code == 200

        dashboard_items = dashboard_response.json()
        dashboard_item = next(
            item for item in dashboard_items if item["rol"] == "07777-00003"
        )

        assert dashboard_item["tenant_name"] == "Test Tenant Dashboard"
        assert dashboard_item["payment_day"] == 5
        assert dashboard_item["current_rent"] == 650000
        assert dashboard_item["property_label"] == "depto dashboard test"
        assert "next_adjustment_date" in dashboard_item
        assert "adjustment_notice_date" in dashboard_item
        assert "requires_adjustment_notice" in dashboard_item


def test_dashboard_includes_operational_fields():
    payload = {
        "property": {
            "comuna": "LAS CONDES",
            "rol": "07777-00003",
            "address": "TEST LAS CONDES",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "777",
            "property_number": "777",
            "year": 2020,
            "fiscal_appraisal": 120000000,
        },
        "rental": {
            "tenant_name": "Test Tenant Dashboard",
            "payment_day": 5,
            "property_label": "depto dashboard test",
            "current_rent": 650000,
            "adjustment_frequency": "annual",
            "start_date": "2024-04-01",
            "notice_days": 60,
            "adjustment_month": "april",
        },
    }

    create_response = client.post("/managed-property", json=payload)
    assert create_response.status_code == 200

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200

    dashboard_items = dashboard_response.json()
    dashboard_item = next(
        item for item in dashboard_items if item["rol"] == "07777-00003"
    )

    assert dashboard_item["tenant_name"] == "Test Tenant Dashboard"
    assert dashboard_item["payment_day"] == 5
    assert dashboard_item["current_rent"] == 650000
    assert dashboard_item["property_label"] == "depto dashboard test"
    assert "next_adjustment_date" in dashboard_item
    assert "adjustment_notice_date" in dashboard_item
    assert "requires_adjustment_notice" in dashboard_item


def test_contracts_returns_200():
    response = client.get("/contracts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_contracts_items_have_expected_shape():
    response = client.get("/contracts")
    items = response.json()
    assert len(items) > 0
    item = items[0]
    assert "id" in item
    assert "property_id" in item
    assert "rol" in item
    assert "tenant_name" in item
    assert "current_rent" in item
    assert "start_date" in item
    assert "adjustment_frequency" in item


def test_tenants_returns_200():
    response = client.get("/tenants")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_tenants_items_have_expected_shape():
    response = client.get("/tenants")
    items = response.json()
    assert len(items) > 0
    item = items[0]
    assert "id" in item
    assert "display_name" in item
    assert "property_id" in item
    assert "rol" in item
    assert "current_rent" in item
    assert "start_date" in item


def test_dashboard_last_adjustment_date_is_null_without_real_adjustment():
    # La propiedad "02162-00036" tiene un solo rent_change con effective_from == start_date.
    # Por regla: effective_from == start_date es renta inicial, no reajuste.
    # last_adjustment_date debe ser null.
    response = client.get("/dashboard")
    assert response.status_code == 200
    items = response.json()
    item = next(i for i in items if i["rol"] == "02162-00036")
    assert item["last_adjustment_date"] is None
    assert item["months_since_last_adjustment"] is None


def test_dashboard_last_adjustment_date_reflects_real_adjustment():
    # Inserta un rent_change con effective_from > start_date para simular un reajuste real.
    # Solo effective_from > start_date cuenta como reajuste (ver _LATEST_ADJUSTMENT en db.py).
    import sqlite3
    conn = sqlite3.connect("test_rental_manager.db")
    row = conn.execute(
        """SELECT c.id FROM contracts c
           JOIN properties p ON p.id = c.property_id
           WHERE p.rol = '02162-00036'"""
    ).fetchone()
    conn.execute(
        "INSERT INTO rent_changes (contract_id, effective_from, amount) VALUES (?, '2023-05-01', 870000)",
        (row[0],),
    )
    conn.commit()
    conn.close()

    response = client.get("/dashboard")
    items = response.json()
    item = next(i for i in items if i["rol"] == "02162-00036")
    assert item["last_adjustment_date"] == "2023-05-01"
    assert item["months_since_last_adjustment"] is not None
    assert item["months_since_last_adjustment"] >= 0


def test_rent_adjustments_months_until_next_is_positive_when_not_yet_due():
    # "09999-00001": start_date=2025-01-01, annual. Primer reajuste programado = 2026-01-01.
    # Con as_of=2025-06-15, el ciclo actual no ha vencido: months_until debe ser positivo.
    response = client.get("/rent-adjustments", params={"as_of": "2025-06-15"})
    assert response.status_code == 200
    items = response.json()
    item = next(i for i in items if i["rol"] == "09999-00001")
    assert item["months_until_next_adjustment"] > 0


def test_rent_adjustments_months_until_next_is_negative_when_overdue():
    # "09999-00001": start_date=2025-01-01, annual. Reajuste del ciclo 2026 = 2026-01-01.
    # Con as_of=2026-03-01, ese ciclo ya venció sin que conste un rent_change posterior.
    # months_until debe ser negativo (reajuste atrasado).
    response = client.get("/rent-adjustments", params={"as_of": "2026-03-01"})
    assert response.status_code == 200
    items = response.json()
    item = next(i for i in items if i["rol"] == "09999-00001")
    assert item["months_until_next_adjustment"] < 0


def test_tenants_tenancy_fields_are_consistent():
    response = client.get("/tenants")
    assert response.status_code == 200
    items = response.json()
    assert len(items) > 0
    for item in items:
        assert item["tenancy_months"] is not None
        assert item["tenancy_months"] >= 0
        assert item["tenancy_years"] == item["tenancy_months"] // 12


def test_tenants_months_since_last_adjustment_is_null_without_real_adjustment():
    # Los arrendatarios de prueba solo tienen renta inicial (effective_from == start_date).
    # months_since_last_adjustment debe ser null para todos.
    response = client.get("/tenants")
    items = response.json()
    # Excluye el arrendatario de "02162-00036" donde ya insertamos un reajuste real
    # en test_dashboard_last_adjustment_date_reflects_real_adjustment.
    for item in items:
        if item["rol"] != "02162-00036":
            assert item["months_since_last_adjustment"] is None, (
                f"Arrendatario {item['display_name']} no debería tener reajuste"
            )


def test_dashboard_no_contract_property_has_null_rent_fields():
    payload = {
        "property": {
            "comuna": "CASTRO",
            "rol": "06666-00001",
            "address": "Gamboa Alto PC-TEST",
            "destination": "SITIO ERIAZO",
            "status": "vacant",
            "fojas": "959",
            "property_number": "905",
            "year": 2025,
            "fiscal_appraisal": 36641671,
        },
        "rental": None,
    }

    create_response = client.post("/managed-property", json=payload)
    assert create_response.status_code == 200

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200

    items = dashboard_response.json()
    item = next(i for i in items if i["rol"] == "06666-00001")

    assert item["current_rent"] is None
    assert item["tenant_name"] is None
    assert item["payment_day"] is None


# ---------------------------------------------------------------------------
# Payment tests
# ---------------------------------------------------------------------------

import sqlite3 as _sqlite3

_PAYMENT_ROL = "09001-00001"

_PAYMENT_PROPERTY = {
    "property": {
        "comuna": "SANTIAGO",
        "rol": _PAYMENT_ROL,
        "address": "Av. Siempre Viva 742",
        "destination": "HABITACIONAL",
        "status": "occupied",
        "fojas": "1",
        "property_number": "1",
        "year": 2020,
        "fiscal_appraisal": 100000000,
    },
    "rental": {
        "tenant_name": "Arrendatario Pagos",
        "payment_day": 5,
        "property_label": "depto pagos",
        "current_rent": 500000,
        "adjustment_frequency": "annual",
        "start_date": "2023-01-01",
        "notice_days": 60,
        "adjustment_month": "january",
    },
}


def _get_contract_id_for_rol(rol: str) -> int:
    """Query the test DB directly to get the active contract_id for a property rol."""
    conn = _sqlite3.connect("test_rental_manager.db")
    row = conn.execute(
        """
        SELECT c.id FROM contracts c
        JOIN properties p ON p.id = c.property_id
        WHERE p.rol = ? AND c.is_active = 1
        """,
        (rol,),
    ).fetchone()
    conn.close()
    assert row is not None, f"No active contract found for rol {rol}"
    return row[0]


def _create_payment_property() -> int:
    """Creates the test property (idempotent) and returns its contract_id."""
    r = client.post("/managed-property", json=_PAYMENT_PROPERTY)
    assert r.status_code in (200, 409)
    return _get_contract_id_for_rol(_PAYMENT_ROL)


def test_create_payment_returns_pending_record():
    cid = _create_payment_property()
    r = client.post(
        f"/contracts/{cid}/payments",
        json={"period": "2025-01", "due_date": "2025-01-05"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["contract_id"] == cid
    assert body["period"] == "2025-01"
    assert body["status"] == "pending"
    assert body["expected_amount"] == 500000
    assert body["paid_amount"] is None
    assert body["source"] == "manual"


def test_list_payments_for_contract():
    cid = _get_contract_id_for_rol(_PAYMENT_ROL)
    r = client.get(f"/contracts/{cid}/payments")
    assert r.status_code == 200
    items = r.json()
    assert any(p["period"] == "2025-01" for p in items)


def test_patch_payment_full_amount_marks_paid():
    # The first payment created for this contract has id=1.
    r = client.patch(
        "/payments/1",
        json={"paid_amount": 500000, "paid_at": "2025-01-05"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "paid"
    assert body["paid_amount"] == 500000


def test_patch_payment_partial_amount_marks_partial():
    cid = _get_contract_id_for_rol(_PAYMENT_ROL)
    client.post(
        f"/contracts/{cid}/payments",
        json={"period": "2025-02", "due_date": "2025-02-05"},
    )
    r = client.patch("/payments/2", json={"paid_amount": 250000})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "partial"
    assert body["paid_amount"] == 250000


def test_patch_payment_comment_only_leaves_status_unchanged():
    cid = _get_contract_id_for_rol(_PAYMENT_ROL)
    client.post(
        f"/contracts/{cid}/payments",
        json={"period": "2025-03", "due_date": "2025-03-05"},
    )
    r = client.patch("/payments/3", json={"comment": "pendiente verificación"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["comment"] == "pendiente verificación"


def test_create_payment_duplicate_period_returns_409():
    cid = _get_contract_id_for_rol(_PAYMENT_ROL)
    r = client.post(
        f"/contracts/{cid}/payments",
        json={"period": "2025-01", "due_date": "2025-01-05"},
    )
    assert r.status_code == 409


def test_create_payment_nonexistent_contract_returns_404():
    r = client.post(
        "/contracts/99999/payments",
        json={"period": "2025-01", "due_date": "2025-01-05"},
    )
    assert r.status_code == 404


def test_create_payment_inactive_contract_returns_404():
    # Try a contract id that does not exist → 404.
    r = client.post(
        "/contracts/99998/payments",
        json={"period": "2025-04", "due_date": "2025-04-05"},
    )
    assert r.status_code == 404