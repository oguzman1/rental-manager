import datetime
import os
from pathlib import Path
import sqlite3 as _sqlite3

from fastapi.testclient import TestClient

os.environ["DB_NAME"] = "test_rental_manager.db"

test_db = Path("test_rental_manager.db")
if test_db.exists():
    test_db.unlink()

from main import app  # noqa: E402


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

    response = client.get("/rent-adjustments", params={"as_of": "2026-12-15"})
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
    response = client.get("/dashboard")
    assert response.status_code == 200
    items = response.json()
    item = next(i for i in items if i["rol"] == "02162-00036")
    assert item["last_adjustment_date"] is None
    assert item["months_since_last_adjustment"] is None


def test_dashboard_last_adjustment_date_reflects_real_adjustment():
    conn = _sqlite3.connect("test_rental_manager.db")
    row = conn.execute(
        """
        SELECT c.id FROM contracts c
        JOIN properties p ON p.id = c.property_id
        WHERE p.rol = '02162-00036'
        """
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
    response = client.get("/rent-adjustments", params={"as_of": "2025-06-15"})
    assert response.status_code == 200
    items = response.json()
    item = next(i for i in items if i["rol"] == "09999-00001")
    assert item["months_until_next_adjustment"] > 0


def test_rent_adjustments_months_until_next_is_negative_when_overdue():
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
    response = client.get("/tenants")
    items = response.json()
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


def test_list_contracts_returns_active_contracts_with_correct_shape():
    client.post(
        "/managed-property",
        json={
            "property": {
                "comuna": "VALPARAÍSO",
                "rol": "05555-00099",
                "address": "Cerro Alegre 10",
                "destination": "HABITACIONAL",
                "status": "occupied",
                "fojas": "5",
                "property_number": "99",
                "year": 2019,
                "fiscal_appraisal": 80000000,
            },
            "rental": {
                "tenant_name": "Arrendatario Contratos Test",
                "payment_day": 3,
                "property_label": "depto valpo test",
                "current_rent": 620000,
                "adjustment_frequency": "semiannual",
                "start_date": "2024-06-01",
                "notice_days": 30,
                "adjustment_month": "june",
            },
        },
    )

    r = client.get("/contracts")
    assert r.status_code == 200

    items = r.json()
    item = next(i for i in items if i["rol"] == "05555-00099")

    assert item["id"] >= 1
    assert item["property_id"] >= 1
    assert item["property_label"] == "depto valpo test"
    assert item["tenant_name"] == "Arrendatario Contratos Test"
    assert item["current_rent"] == 620000
    assert item["payment_day"] == 3
    assert item["adjustment_frequency"] == "semiannual"
    assert item["start_date"] == "2024-06-01"


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


def _setup_payment_property() -> int:
    client.post("/managed-property", json=_PAYMENT_PROPERTY)
    return _get_contract_id_for_rol(_PAYMENT_ROL)


def test_create_payment_derives_due_date_from_payment_day():
    cid = _setup_payment_property()
    r = client.post(f"/contracts/{cid}/payments", json={"period": "2025-04"})
    assert r.status_code == 200
    body = r.json()
    assert body["period"] == "2025-04"
    assert body["due_date"] == "2025-04-05"
    assert body["expected_amount"] == 500000
    assert body["status"] == "pending"
    assert body["source"] == "manual"
    assert body["paid_amount"] is None


def test_create_payment_clamps_due_date_when_payment_day_exceeds_month_length():
    client.post(
        "/managed-property",
        json={
            "property": {
                "comuna": "TEMUCO",
                "rol": "09001-00002",
                "address": "Calle Larga 1",
                "destination": "HABITACIONAL",
                "status": "occupied",
                "fojas": "2",
                "property_number": "2",
                "year": 2021,
                "fiscal_appraisal": 70000000,
            },
            "rental": {
                "tenant_name": "Arrendatario Clamp",
                "payment_day": 31,
                "property_label": "depto clamp",
                "current_rent": 300000,
                "adjustment_frequency": "annual",
                "start_date": "2023-03-01",
                "notice_days": 30,
                "adjustment_month": "march",
            },
        },
    )
    cid = _get_contract_id_for_rol("09001-00002")
    r = client.post(f"/contracts/{cid}/payments", json={"period": "2025-04"})
    assert r.status_code == 200
    assert r.json()["due_date"] == "2025-04-30"


def test_list_payments_for_contract():
    cid = _setup_payment_property()
    client.post(f"/contracts/{cid}/payments", json={"period": "2025-04"})
    r = client.get(f"/contracts/{cid}/payments")
    assert r.status_code == 200
    items = r.json()
    assert any(p["period"] == "2025-04" for p in items)


def test_patch_payment_full_amount_marks_paid():
    cid = _setup_payment_property()
    client.post(f"/contracts/{cid}/payments", json={"period": "2025-05"})
    payments = client.get(f"/contracts/{cid}/payments").json()
    pid = next(p["id"] for p in payments if p["period"] == "2025-05")

    r = client.patch(
        f"/payments/{pid}",
        json={"paid_amount": 500000, "paid_at": "2025-05-05"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "paid"
    assert body["paid_amount"] == 500000


def test_patch_payment_partial_amount_marks_partial():
    cid = _setup_payment_property()
    client.post(f"/contracts/{cid}/payments", json={"period": "2025-06"})
    payments = client.get(f"/contracts/{cid}/payments").json()
    pid = next(p["id"] for p in payments if p["period"] == "2025-06")

    r = client.patch(f"/payments/{pid}", json={"paid_amount": 250000})
    assert r.status_code == 200
    assert r.json()["status"] == "partial"


def test_patch_payment_comment_only_leaves_status_unchanged():
    cid = _setup_payment_property()
    client.post(f"/contracts/{cid}/payments", json={"period": "2025-07"})
    payments = client.get(f"/contracts/{cid}/payments").json()
    pid = next(p["id"] for p in payments if p["period"] == "2025-07")

    r = client.patch(
        f"/payments/{pid}",
        json={"comment": "pendiente verificación"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["comment"] == "pendiente verificación"


def test_create_payment_duplicate_period_returns_409():
    cid = _setup_payment_property()
    client.post(f"/contracts/{cid}/payments", json={"period": "2025-08"})
    r = client.post(f"/contracts/{cid}/payments", json={"period": "2025-08"})
    assert r.status_code == 409


def test_create_payment_nonexistent_contract_returns_404():
    r = client.post("/contracts/99999/payments", json={"period": "2025-09"})
    assert r.status_code == 404


def test_create_payment_inactive_contract_returns_404():
    client.post(
        "/managed-property",
        json={
            "property": {
                "comuna": "VALDIVIA",
                "rol": "09001-00003",
                "address": "Sin contrato 1",
                "destination": "SITIO ERIAZO",
                "status": "vacant",
                "fojas": "3",
                "property_number": "3",
                "year": 2021,
                "fiscal_appraisal": 50000000,
            },
            "rental": None,
        },
    )
    r = client.post("/contracts/99998/payments", json={"period": "2025-10"})
    assert r.status_code == 404


def test_create_payment_invalid_period_returns_422():
    cid = _setup_payment_property()
    for bad in ("2025-13", "25-04", "2025/04", "abril", ""):
        r = client.post(f"/contracts/{cid}/payments", json={"period": bad})
        assert r.status_code == 422, f"Expected 422 for period={bad!r}, got {r.status_code}"


def test_delete_payment_returns_204():
    cid = _setup_payment_property()
    payment = client.post(
        f"/contracts/{cid}/payments", json={"period": "2025-11"}
    ).json()

    response = client.delete(f"/payments/{payment['id']}")
    assert response.status_code == 204
    assert response.content == b""


def test_delete_payment_unknown_returns_404():
    response = client.delete("/payments/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found."


def test_delete_payment_actually_removes_it():
    cid = _setup_payment_property()
    payment = client.post(
        f"/contracts/{cid}/payments", json={"period": "2025-12"}
    ).json()
    payment_id = payment["id"]

    client.delete(f"/payments/{payment_id}")

    remaining = client.get(f"/contracts/{cid}/payments").json()
    assert payment_id not in [p["id"] for p in remaining]


def test_dashboard_current_payment_status_none_when_no_payment():
    payload = {
        "property": {
            "comuna": "VALDIVIA",
            "rol": "09004-00001",
            "address": "TEST VALDIVIA 1",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "901",
            "property_number": "901",
            "year": 2023,
            "fiscal_appraisal": 90000000,
        },
        "rental": {
            "tenant_name": "Test Payment None",
            "payment_day": 10,
            "property_label": "depto pago none",
            "current_rent": 500000,
            "adjustment_frequency": "annual",
            "start_date": "2023-01-01",
            "notice_days": 60,
            "adjustment_month": "january",
        },
    }
    create_response = client.post("/managed-property", json=payload)
    assert create_response.status_code == 200

    items = client.get("/dashboard").json()
    item = next(i for i in items if i["rol"] == "09004-00001")

    assert item["current_payment_status"] is None


def test_dashboard_current_payment_status_pending():
    current_period = datetime.date.today().strftime("%Y-%m")

    payload = {
        "property": {
            "comuna": "VALDIVIA",
            "rol": "09005-00001",
            "address": "TEST VALDIVIA 2",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "902",
            "property_number": "902",
            "year": 2023,
            "fiscal_appraisal": 90000000,
        },
        "rental": {
            "tenant_name": "Test Payment Pending",
            "payment_day": 10,
            "property_label": "depto pago pending",
            "current_rent": 500000,
            "adjustment_frequency": "annual",
            "start_date": "2023-01-01",
            "notice_days": 60,
            "adjustment_month": "january",
        },
    }
    create_response = client.post("/managed-property", json=payload)
    assert create_response.status_code == 200

    contracts = client.get("/contracts").json()
    contract = next(c for c in contracts if c["rol"] == "09005-00001")
    payment_response = client.post(
        f"/contracts/{contract['id']}/payments",
        json={"period": current_period},
    )
    assert payment_response.status_code == 200

    items = client.get("/dashboard").json()
    item = next(i for i in items if i["rol"] == "09005-00001")

    assert item["current_payment_status"] == "pending"


def test_dashboard_current_payment_status_paid():
    current_period = datetime.date.today().strftime("%Y-%m")

    payload = {
        "property": {
            "comuna": "VALDIVIA",
            "rol": "09006-00001",
            "address": "TEST VALDIVIA 3",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "903",
            "property_number": "903",
            "year": 2023,
            "fiscal_appraisal": 90000000,
        },
        "rental": {
            "tenant_name": "Test Payment Paid",
            "payment_day": 10,
            "property_label": "depto pago paid",
            "current_rent": 500000,
            "adjustment_frequency": "annual",
            "start_date": "2023-01-01",
            "notice_days": 60,
            "adjustment_month": "january",
        },
    }
    create_response = client.post("/managed-property", json=payload)
    assert create_response.status_code == 200

    contracts = client.get("/contracts").json()
    contract = next(c for c in contracts if c["rol"] == "09006-00001")
    create_resp = client.post(
        f"/contracts/{contract['id']}/payments",
        json={"period": current_period},
    )
    assert create_resp.status_code == 200

    payment_id = create_resp.json()["id"]
    expected = create_resp.json()["expected_amount"]
    patch_resp = client.patch(f"/payments/{payment_id}", json={"paid_amount": expected})
    assert patch_resp.status_code == 200

    items = client.get("/dashboard").json()
    item = next(i for i in items if i["rol"] == "09006-00001")

    assert item["current_payment_status"] == "paid"


# --- GET /managed-property/{id} ---

def test_get_managed_property_by_id_returns_occupied_with_rental():
    client.post(
        "/managed-property",
        json={
            "property": {
                "comuna": "ANTOFAGASTA",
                "rol": "10001-00001",
                "address": "Matta 100",
                "destination": "HABITACIONAL",
                "status": "occupied",
                "fojas": "10",
                "property_number": "10",
                "year": 2020,
                "fiscal_appraisal": 80000000,
            },
            "rental": {
                "tenant_name": "Inquilino Detail",
                "payment_day": 7,
                "property_label": "depto antofagasta",
                "current_rent": 450000,
                "adjustment_frequency": "annual",
                "start_date": "2023-06-01",
                "notice_days": 30,
                "adjustment_month": "june",
            },
        },
    )
    props = client.get("/managed-properties").json()
    pid = next(p["id"] for p in props if p["rol"] == "10001-00001")

    r = client.get(f"/managed-property/{pid}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == pid
    assert data["property"]["rol"] == "10001-00001"
    assert data["property"]["status"] == "occupied"
    assert data["rental"]["tenant_name"] == "Inquilino Detail"
    assert data["rental"]["payment_day"] == 7
    assert data["rental"]["current_rent"] == 450000
    assert data["rental"]["adjustment_month"] == "june"


def test_get_managed_property_by_id_returns_vacant_with_null_rental():
    client.post(
        "/managed-property",
        json={
            "property": {
                "comuna": "ARICA",
                "rol": "10002-00001",
                "address": "Lynch 200",
                "destination": "SITIO ERIAZO",
                "status": "vacant",
                "fojas": None,
                "property_number": None,
                "year": None,
                "fiscal_appraisal": None,
            },
            "rental": None,
        },
    )
    props = client.get("/managed-properties").json()
    pid = next(p["id"] for p in props if p["rol"] == "10002-00001")

    r = client.get(f"/managed-property/{pid}")
    assert r.status_code == 200
    data = r.json()
    assert data["property"]["status"] == "vacant"
    assert data["rental"] is None


def test_get_managed_property_by_id_not_found():
    r = client.get("/managed-property/99999")
    assert r.status_code == 404


# --- DELETE cascade includes payments ---

def test_delete_managed_property_also_removes_payments():
    client.post(
        "/managed-property",
        json={
            "property": {
                "comuna": "RANCAGUA",
                "rol": "10003-00001",
                "address": "O'Higgins 300",
                "destination": "HABITACIONAL",
                "status": "occupied",
                "fojas": "20",
                "property_number": "20",
                "year": 2018,
                "fiscal_appraisal": 70000000,
            },
            "rental": {
                "tenant_name": "Inquilino Cascade",
                "payment_day": 5,
                "property_label": "depto rancagua",
                "current_rent": 380000,
                "adjustment_frequency": "annual",
                "start_date": "2022-01-01",
                "notice_days": 30,
                "adjustment_month": "january",
            },
        },
    )
    props = client.get("/managed-properties").json()
    pid = next(p["id"] for p in props if p["rol"] == "10003-00001")
    contracts = client.get("/contracts").json()
    cid = next(c["id"] for c in contracts if c["rol"] == "10003-00001")

    client.post(f"/contracts/{cid}/payments", json={"period": "2024-01"})
    client.post(f"/contracts/{cid}/payments", json={"period": "2024-02"})

    r = client.delete(f"/managed-property/{pid}")
    assert r.status_code == 200

    import sqlite3 as _sqlite3
    conn = _sqlite3.connect("test_rental_manager.db")
    payments = conn.execute(
        "SELECT id FROM payments WHERE contract_id = ?", (cid,)
    ).fetchall()
    conn.close()
    assert payments == [], "Los pagos deben eliminarse al borrar la propiedad"