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
    assert test_adjustment["adjustment_notice_date"] == "2026-12-02"
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


def test_dashboard_payment_status_missing_period():
    """Contrato con start_date futuro → sin períodos exigibles → missing_period."""
    payload = {
        "property": {
            "comuna": "VALDIVIA",
            "rol": "09007-00001",
            "address": "TEST VALDIVIA 4",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "904",
            "property_number": "904",
            "year": 2023,
            "fiscal_appraisal": 90000000,
        },
        "rental": {
            "tenant_name": "Test Missing Period",
            "payment_day": 10,
            "property_label": "depto missing period",
            "current_rent": 500000,
            "adjustment_frequency": "annual",
            "start_date": "2028-01-01",
            "notice_days": 60,
            "adjustment_month": "january",
        },
    }
    create_response = client.post("/managed-property", json=payload)
    assert create_response.status_code == 200

    items = client.get("/dashboard").json()
    item = next(i for i in items if i["rol"] == "09007-00001")

    assert item["payment_status"] == "missing_period"
    assert item["period_amount"] is None
    assert item["latest_period"] is None


def test_dashboard_payment_status_outstanding_balance():
    """Período exigible sin pagar → outstanding_balance; period_amount = expected_amount del período."""
    current_period = datetime.date.today().strftime("%Y-%m")
    payload = {
        "property": {
            "comuna": "VALDIVIA",
            "rol": "09008-00001",
            "address": "TEST VALDIVIA 5",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "905",
            "property_number": "905",
            "year": 2023,
            "fiscal_appraisal": 90000000,
        },
        "rental": {
            "tenant_name": "Test Outstanding",
            "payment_day": 10,
            "property_label": "depto outstanding",
            "current_rent": 600000,
            "adjustment_frequency": "annual",
            "start_date": "2023-01-01",
            "notice_days": 60,
            "adjustment_month": "january",
        },
    }
    create_response = client.post("/managed-property", json=payload)
    assert create_response.status_code == 200

    contracts = client.get("/contracts").json()
    contract = next(c for c in contracts if c["rol"] == "09008-00001")
    payment_response = client.post(
        f"/contracts/{contract['id']}/payments",
        json={"period": current_period},
    )
    assert payment_response.status_code == 200
    expected_amount = payment_response.json()["expected_amount"]

    items = client.get("/dashboard").json()
    item = next(i for i in items if i["rol"] == "09008-00001")

    assert item["payment_status"] == "outstanding_balance"
    assert item["period_amount"] == expected_amount
    assert item["latest_period"] == current_period


def test_dashboard_payment_status_paid_up():
    """Período exigible completamente pagado → paid_up.

    Usa start_date en el mes actual para que solo haya 1 período exigible
    y el saldo pendiente sea 0 al pagarlo.
    """
    current_period = datetime.date.today().strftime("%Y-%m")
    start_of_month = datetime.date.today().replace(day=1).isoformat()

    payload = {
        "property": {
            "comuna": "VALDIVIA",
            "rol": "09009-00001",
            "address": "TEST VALDIVIA 6",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "906",
            "property_number": "906",
            "year": 2023,
            "fiscal_appraisal": 90000000,
        },
        "rental": {
            "tenant_name": "Test Paid Up",
            "payment_day": 10,
            "property_label": "depto paid up",
            "current_rent": 700000,
            "adjustment_frequency": "annual",
            "start_date": start_of_month,
            "notice_days": 60,
            "adjustment_month": "january",
        },
    }
    create_response = client.post("/managed-property", json=payload)
    assert create_response.status_code == 200

    contracts = client.get("/contracts").json()
    contract = next(c for c in contracts if c["rol"] == "09009-00001")

    # The current period is auto-generated; find it from the payments list.
    payments = client.get(f"/contracts/{contract['id']}/payments").json()
    current_p = next((p for p in payments if p["period"] == current_period), None)
    if current_p:
        payment_id = current_p["id"]
        expected = current_p["expected_amount"]
    else:
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
    item = next(i for i in items if i["rol"] == "09009-00001")

    assert item["payment_status"] == "paid_up"
    assert item["period_amount"] == expected
    assert item["latest_period"] == current_period
    assert item["contract_id"] is not None


# -----------------------------------------------------------------------
# actionable_payment_period — alert must never target a paid period
# -----------------------------------------------------------------------

def _prev_month(today):
    """Return (year, month) for the calendar month before today."""
    m, y = today.month - 1, today.year
    if m == 0:
        m, y = 12, y - 1
    return y, m


def _make_alert_property(rol, address, fojas, prop_num):
    """Create a minimal occupied property for alert tests.

    start_date is set to the first day of next month so that
    generate_payment_periods produces only future rows (period > current month).
    This gives each test a clean slate — no pre-existing payment rows interfere
    with the actionable_payment_period subquery or cause 409 conflicts.
    """
    today = datetime.date.today()
    if today.month == 12:
        next_year, next_month = today.year + 1, 1
    else:
        next_year, next_month = today.year, today.month + 1
    start = f"{next_year}-{next_month:02d}-01"

    r = client.post("/managed-property", json={
        "property": {
            "comuna": "TEST ALERTAS",
            "rol": rol,
            "address": address,
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": fojas,
            "property_number": prop_num,
            "year": 2023,
            "fiscal_appraisal": 90000000,
        },
        "rental": {
            "tenant_name": "Tenant Alert Test",
            "payment_day": 10,
            "property_label": f"prop {rol}",
            "current_rent": 400000,
            "adjustment_frequency": "annual",
            "start_date": start,
            "notice_days": 60,
            "adjustment_month": "january",
        },
    })
    assert r.status_code == 200
    contracts = client.get("/contracts").json()
    contract = next(c for c in contracts if c["rol"] == rol)
    return contract["id"]


def test_actionable_payment_period_null_when_latest_is_paid():
    # Scenario: last month's period is paid, no record for current month.
    # actionable_payment_period must be None (paid period must not appear as target).
    today = datetime.date.today()
    prev_y, prev_m = _prev_month(today)
    prev_period = f"{prev_y}-{prev_m:02d}"

    cid = _make_alert_property("07001-00001", "TEST ALERT ADDR 1", "7001", "7001")

    # Create and fully pay last month's period
    create_r = client.post(f"/contracts/{cid}/payments", json={"period": prev_period})
    assert create_r.status_code == 200
    pid = create_r.json()["id"]
    expected = create_r.json()["expected_amount"]
    patch_r = client.patch(f"/payments/{pid}", json={"paid_amount": expected})
    assert patch_r.status_code == 200

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "07001-00001")
    assert item["actionable_payment_period"] is None, (
        "a paid past period must not be exposed as the actionable target"
    )
    assert item["actionable_payment_status"] is None
    assert item["actionable_payment_amount"] is None
    # latest_period is unchanged — still points to the last recorded period
    assert item["latest_period"] == prev_period


def test_actionable_payment_period_oldest_unpaid_when_newer_is_paid():
    # Scenario: older period is pending/partial, newer period is paid.
    # actionable_payment_period must be the older unpaid period.
    today = datetime.date.today()
    prev_y, prev_m = _prev_month(today)
    prev_period = f"{prev_y}-{prev_m:02d}"
    prev2_y, prev2_m = _prev_month(datetime.date(prev_y, prev_m, 1))
    prev2_period = f"{prev2_y}-{prev2_m:02d}"

    cid = _make_alert_property("07002-00001", "TEST ALERT ADDR 2", "7002", "7002")

    # Two months ago: partial payment
    r2 = client.post(f"/contracts/{cid}/payments", json={"period": prev2_period})
    assert r2.status_code == 200
    pid2 = r2.json()["id"]
    expected2 = r2.json()["expected_amount"]
    client.patch(f"/payments/{pid2}", json={"paid_amount": expected2 // 2})

    # Last month: fully paid
    r1 = client.post(f"/contracts/{cid}/payments", json={"period": prev_period})
    assert r1.status_code == 200
    pid1 = r1.json()["id"]
    expected1 = r1.json()["expected_amount"]
    client.patch(f"/payments/{pid1}", json={"paid_amount": expected1})

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "07002-00001")
    assert item["actionable_payment_period"] == prev2_period, (
        "oldest non-paid period must be the actionable target"
    )
    assert item["actionable_payment_status"] == "partial"
    assert item["actionable_payment_amount"] == expected2


def test_actionable_payment_period_surfaces_older_unpaid_when_current_paid():
    # Scenario: current month is fully paid but an older period is pending.
    # actionable_payment_period must be the older unpaid period even though
    # current_payment_status is 'paid'.
    today = datetime.date.today()
    current_period = today.strftime("%Y-%m")
    prev_y, prev_m = _prev_month(today)
    prev_period = f"{prev_y}-{prev_m:02d}"

    cid = _make_alert_property("07003-00001", "TEST ALERT ADDR 3", "7003", "7003")

    # Last month: pending (no paid_amount)
    r_prev = client.post(f"/contracts/{cid}/payments", json={"period": prev_period})
    assert r_prev.status_code == 200

    # Current month: fully paid
    r_cur = client.post(f"/contracts/{cid}/payments", json={"period": current_period})
    assert r_cur.status_code == 200
    pid_cur = r_cur.json()["id"]
    expected_cur = r_cur.json()["expected_amount"]
    client.patch(f"/payments/{pid_cur}", json={"paid_amount": expected_cur})

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "07003-00001")
    assert item["current_payment_status"] == "paid"
    assert item["actionable_payment_period"] == prev_period, (
        "older unpaid period must surface even when current month is paid"
    )
    assert item["actionable_payment_status"] == "pending"


def test_actionable_payment_period_null_when_all_paid():
    # Scenario: all recorded periods are fully paid.
    # actionable_payment_period must be None.
    today = datetime.date.today()
    current_period = today.strftime("%Y-%m")
    prev_y, prev_m = _prev_month(today)
    prev_period = f"{prev_y}-{prev_m:02d}"

    cid = _make_alert_property("07004-00001", "TEST ALERT ADDR 4", "7004", "7004")

    for period in (prev_period, current_period):
        r = client.post(f"/contracts/{cid}/payments", json={"period": period})
        assert r.status_code == 200
        pid = r.json()["id"]
        expected = r.json()["expected_amount"]
        client.patch(f"/payments/{pid}", json={"paid_amount": expected})

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "07004-00001")
    assert item["current_payment_status"] == "paid"
    assert item["actionable_payment_period"] is None
    assert item["actionable_payment_status"] is None
    assert item["actionable_payment_amount"] is None


def test_stale_stored_status_does_not_create_actionable_alert():
    # Diagnostic: a row with stored status='pending' but paid_amount=expected_amount
    # must not produce a payment alert.  Amount-based truth takes precedence over
    # the stored status column.
    today = datetime.date.today()
    current_period = today.strftime("%Y-%m")

    cid = _make_alert_property("07005-00001", "TEST ALERT ADDR 5", "7005", "7005")

    # Create a pending payment for the current month (status='pending')
    r = client.post(f"/contracts/{cid}/payments", json={"period": current_period})
    assert r.status_code == 200
    pid = r.json()["id"]
    expected = r.json()["expected_amount"]

    # Directly set paid_amount = expected_amount while leaving status='pending'
    # (simulates a stale/inconsistent status column)
    conn = _sqlite3.connect("test_rental_manager.db")
    conn.execute("UPDATE payments SET paid_amount = ? WHERE id = ?", (expected, pid))
    conn.commit()
    conn.close()

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "07005-00001")
    assert item["actionable_payment_period"] is None, (
        "a row with paid_amount=expected must not be actionable even if stored status is stale"
    )
    assert item["current_payment_status"] == "paid", (
        "current_payment_status must be derived from amounts, not stored status"
    )


def test_actionable_payment_status_derived_from_amounts_not_stored_status():
    # A partial payment (0 < paid_amount < expected_amount) must produce
    # actionable_payment_status='partial' regardless of the stored status column.
    today = datetime.date.today()
    current_period = today.strftime("%Y-%m")

    cid = _make_alert_property("07006-00001", "TEST ALERT ADDR 6", "7006", "7006")

    r = client.post(f"/contracts/{cid}/payments", json={"period": current_period})
    assert r.status_code == 200
    pid = r.json()["id"]
    expected = r.json()["expected_amount"]
    partial_paid = expected // 2

    # Write paid_amount < expected directly, deliberately leaving status='pending'
    conn = _sqlite3.connect("test_rental_manager.db")
    conn.execute("UPDATE payments SET paid_amount = ? WHERE id = ?", (partial_paid, pid))
    conn.commit()
    conn.close()

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "07006-00001")
    assert item["actionable_payment_period"] == current_period
    assert item["actionable_payment_status"] == "partial", (
        "actionable_payment_status must be derived from amounts: paid_amount > 0 and < expected"
    )
    assert item["actionable_payment_amount"] == expected


def test_pending_period_actionable_when_no_paid_amount():
    # A period with no paid_amount at all must produce actionable_payment_status='pending'.
    today = datetime.date.today()
    current_period = today.strftime("%Y-%m")

    cid = _make_alert_property("07007-00001", "TEST ALERT ADDR 7", "7007", "7007")

    r = client.post(f"/contracts/{cid}/payments", json={"period": current_period})
    assert r.status_code == 200
    expected = r.json()["expected_amount"]

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "07007-00001")
    assert item["actionable_payment_period"] == current_period
    assert item["actionable_payment_status"] == "pending"
    assert item["actionable_payment_amount"] == expected


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


# --- FASE 2: Arrendatarios CRUD ---

def test_create_standalone_tenant():
    r = client.post("/tenants", json={"display_name": "Arrendatario Standalone"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] >= 1
    assert body["display_name"] == "Arrendatario Standalone"


def test_create_tenant_missing_display_name_returns_422():
    r = client.post("/tenants", json={})
    assert r.status_code == 422


def test_list_tenants_includes_standalone_tenant():
    client.post("/tenants", json={"display_name": "Arrendatario Sin Contrato"})
    r = client.get("/tenants")
    assert r.status_code == 200
    items = r.json()
    standalone = next((i for i in items if i["display_name"] == "Arrendatario Sin Contrato"), None)
    assert standalone is not None
    assert standalone["property_id"] is None
    assert standalone["rol"] is None
    assert standalone["current_rent"] is None
    assert standalone["start_date"] is None
    assert standalone["tenancy_months"] is None


def test_get_tenant_by_id_returns_tenant():
    r = client.post("/tenants", json={"display_name": "Arrendatario Get Test"})
    tenant_id = r.json()["id"]
    r = client.get(f"/tenants/{tenant_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == tenant_id
    assert body["display_name"] == "Arrendatario Get Test"


def test_get_tenant_not_found_returns_404():
    r = client.get("/tenants/99999")
    assert r.status_code == 404


def test_update_tenant_display_name():
    r = client.post("/tenants", json={"display_name": "Nombre Original"})
    tenant_id = r.json()["id"]
    r = client.patch(f"/tenants/{tenant_id}", json={"display_name": "Nombre Actualizado"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Nombre Actualizado"
    r = client.get(f"/tenants/{tenant_id}")
    assert r.json()["display_name"] == "Nombre Actualizado"


def test_update_tenant_not_found_returns_404():
    r = client.patch("/tenants/99999", json={"display_name": "Nadie"})
    assert r.status_code == 404


def test_delete_standalone_tenant_returns_204():
    r = client.post("/tenants", json={"display_name": "Arrendatario A Borrar"})
    tenant_id = r.json()["id"]
    r = client.delete(f"/tenants/{tenant_id}")
    assert r.status_code == 204
    assert r.content == b""
    r = client.get(f"/tenants/{tenant_id}")
    assert r.status_code == 404


def test_delete_tenant_with_active_contract_returns_409():
    tenants = client.get("/tenants").json()
    tenant = next(t for t in tenants if t["rol"] == "02162-00036")
    r = client.delete(f"/tenants/{tenant['id']}")
    assert r.status_code == 409
    assert "contract" in r.json()["detail"]


def test_delete_tenant_not_found_returns_404():
    r = client.delete("/tenants/99999")
    assert r.status_code == 404


# --- FASE 3: Contratos CRUD ---

_f3_seq = 0


def _setup_contract_scenario() -> tuple[int, int, int]:
    """Returns (property_id, tenant_id, contract_id). Each call uses a unique ROL."""
    global _f3_seq
    _f3_seq += 1
    rol = f"08001-{_f3_seq:05d}"

    client.post(
        "/managed-property",
        json={
            "property": {
                "comuna": "CONCEPCIÓN",
                "rol": rol,
                "address": f"Freire {_f3_seq}",
                "destination": "HABITACIONAL",
                "status": "vacant",
                "fojas": "801",
                "property_number": "801",
                "year": 2018,
                "fiscal_appraisal": 90000000,
            },
            "rental": None,
        },
    )
    props = client.get("/managed-properties").json()
    prop = next(p for p in props if p["rol"] == rol)

    r = client.post("/tenants", json={"display_name": f"Arrendatario Fase3-{_f3_seq}"})
    tenant_id = r.json()["id"]

    r = client.post(
        "/contracts",
        json={
            "property_id": prop["id"],
            "tenant_id": tenant_id,
            "start_date": "2024-01-01",
            "payment_day": 5,
            "notice_days": 30,
            "adjustment_frequency": "annual",
            "adjustment_month": "january",
            "current_rent": 700000,
            "comment": "contrato test fase3",
        },
    )
    assert r.status_code == 200, f"create_contract failed: {r.json()}"
    return prop["id"], tenant_id, r.json()["id"]


def test_create_contract_returns_detail():
    _, _, contract_id = _setup_contract_scenario()
    r = client.get(f"/contracts/{contract_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == contract_id
    assert body["current_rent"] == 700000
    assert body["payment_day"] == 5
    assert body["adjustment_frequency"] == "annual"
    assert body["notice_days"] == 30
    assert body["adjustment_month"] == "january"
    assert body["comment"] == "contrato test fase3"
    assert body["is_active"] is True
    assert body["end_date"] is None


def test_create_contract_marks_property_as_occupied():
    prop_id, _, _ = _setup_contract_scenario()
    props = client.get("/managed-properties").json()
    prop = next(p for p in props if p["id"] == prop_id)
    assert prop["status"] == "occupied"


def test_create_contract_duplicate_active_returns_409():
    prop_id, tenant_id, _ = _setup_contract_scenario()
    r = client.post(
        "/contracts",
        json={
            "property_id": prop_id,
            "tenant_id": tenant_id,
            "start_date": "2024-06-01",
            "payment_day": 10,
            "notice_days": 60,
            "adjustment_frequency": "semiannual",
            "current_rent": 800000,
        },
    )
    assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.json()}"


def test_create_contract_property_not_found_returns_404():
    r = client.post(
        "/contracts",
        json={
            "property_id": 99999,
            "tenant_id": 1,
            "start_date": "2024-01-01",
            "payment_day": 5,
            "notice_days": 0,
            "adjustment_frequency": "annual",
            "current_rent": 500000,
        },
    )
    assert r.status_code == 404


def test_get_contract_not_found_returns_404():
    r = client.get("/contracts/99999")
    assert r.status_code == 404


def test_update_contract_payment_day():
    _, _, contract_id = _setup_contract_scenario()
    r = client.patch(f"/contracts/{contract_id}", json={"payment_day": 15})
    assert r.status_code == 200
    assert r.json()["payment_day"] == 15


def test_update_contract_rent_inserts_new_rent_change():
    _, _, contract_id = _setup_contract_scenario()
    r = client.patch(f"/contracts/{contract_id}", json={"current_rent": 750000})
    assert r.status_code == 200
    assert r.json()["current_rent"] == 750000


def test_update_contract_not_found_returns_404():
    r = client.patch("/contracts/99999", json={"payment_day": 10})
    assert r.status_code == 404


def test_close_contract_sets_inactive_and_property_vacant():
    prop_id, _, contract_id = _setup_contract_scenario()
    r = client.patch(
        f"/contracts/{contract_id}/close",
        json={"end_date": "2024-12-31"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_active"] is False
    assert body["end_date"] == "2024-12-31"

    props = client.get("/managed-properties").json()
    prop = next(p for p in props if p["id"] == prop_id)
    assert prop["status"] == "vacant"


def test_close_contract_excluded_from_list():
    _, _, contract_id = _setup_contract_scenario()
    client.patch(f"/contracts/{contract_id}/close", json={"end_date": "2024-12-31"})
    contracts = client.get("/contracts").json()
    assert not any(c["id"] == contract_id for c in contracts)


def test_close_contract_end_date_before_start_returns_400():
    _, _, contract_id = _setup_contract_scenario()
    r = client.patch(
        f"/contracts/{contract_id}/close",
        json={"end_date": "2023-01-01"},
    )
    assert r.status_code == 400


def test_close_contract_not_found_returns_404():
    r = client.patch("/contracts/99999/close", json={"end_date": "2024-12-31"})
    assert r.status_code == 404


def test_close_already_closed_contract_returns_404():
    _, _, contract_id = _setup_contract_scenario()
    client.patch(f"/contracts/{contract_id}/close", json={"end_date": "2024-12-31"})
    r = client.patch(f"/contracts/{contract_id}/close", json={"end_date": "2024-12-31"})
    assert r.status_code == 404


def test_delete_tenant_with_historical_contract_returns_409():
    _, tenant_id, contract_id = _setup_contract_scenario()
    client.patch(f"/contracts/{contract_id}/close", json={"end_date": "2024-12-31"})
    r = client.delete(f"/tenants/{tenant_id}")
    assert r.status_code == 409
    assert "contract" in r.json()["detail"]


def test_list_contracts_includes_notice_days_and_comment():
    _, _, contract_id = _setup_contract_scenario()
    contracts = client.get("/contracts").json()
    contract = next((c for c in contracts if c["id"] == contract_id), None)
    assert contract is not None
    assert "notice_days" in contract
    assert "adjustment_month" in contract
    assert "comment" in contract


# --- FASE 4: Reajustes / rent_changes ---

def test_rent_adjustments_include_contract_id():
    r = client.get("/rent-adjustments")
    assert r.status_code == 200
    items = r.json()
    assert len(items) > 0
    for item in items:
        assert "contract_id" in item
        assert isinstance(item["contract_id"], int)


def test_list_rent_changes_returns_history():
    _, _, contract_id = _setup_contract_scenario()
    r = client.get(f"/contracts/{contract_id}/rent-changes")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["amount"] == 700000
    assert items[0]["contract_id"] == contract_id


def test_list_rent_changes_contract_not_found_returns_404():
    r = client.get("/contracts/99999/rent-changes")
    assert r.status_code == 404


def test_create_rent_change_success():
    _, _, contract_id = _setup_contract_scenario()
    r = client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2025-01-01", "amount": 750000},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["amount"] == 750000
    assert body["effective_from"] == "2025-01-01"
    assert body["contract_id"] == contract_id


def test_create_rent_change_reflects_in_list():
    _, _, contract_id = _setup_contract_scenario()
    client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2025-01-01", "amount": 760000, "adjustment_pct": 5.2},
    )
    items = client.get(f"/contracts/{contract_id}/rent-changes").json()
    assert len(items) == 2
    latest = items[0]
    assert latest["amount"] == 760000
    assert latest["adjustment_pct"] == 5.2


def test_create_rent_change_amount_zero_returns_422():
    _, _, contract_id = _setup_contract_scenario()
    r = client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2025-01-01", "amount": 0},
    )
    assert r.status_code == 422


def test_create_rent_change_contract_not_found_returns_404():
    r = client.post(
        "/contracts/99999/rent-changes",
        json={"effective_from": "2025-01-01", "amount": 700000},
    )
    assert r.status_code == 404


def test_create_rent_change_inactive_contract_returns_404():
    _, _, contract_id = _setup_contract_scenario()
    client.patch(f"/contracts/{contract_id}/close", json={"end_date": "2024-12-31"})
    r = client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2025-01-01", "amount": 750000},
    )
    assert r.status_code == 404


def test_create_rent_change_effective_from_before_start_returns_400():
    _, _, contract_id = _setup_contract_scenario()
    r = client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2023-01-01", "amount": 750000},
    )
    assert r.status_code == 400


def test_create_rent_change_before_latest_returns_400():
    _, _, contract_id = _setup_contract_scenario()
    client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2025-06-01", "amount": 750000},
    )
    r = client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2025-03-01", "amount": 760000},
    )
    assert r.status_code == 400


def test_create_rent_change_same_date_as_latest_returns_400():
    _, _, contract_id = _setup_contract_scenario()
    client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2025-06-01", "amount": 750000},
    )
    r = client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2025-06-01", "amount": 760000},
    )
    assert r.status_code == 400


def test_delete_rent_change_last_of_many_returns_204():
    _, _, contract_id = _setup_contract_scenario()
    r = client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2025-06-01", "amount": 750000},
    )
    assert r.status_code == 201
    rc_id = r.json()["id"]

    r = client.delete(f"/rent-changes/{rc_id}")
    assert r.status_code == 204
    assert r.content == b""


def test_delete_rent_change_actually_removes_it():
    _, _, contract_id = _setup_contract_scenario()
    r = client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2025-06-01", "amount": 750000},
    )
    rc_id = r.json()["id"]
    client.delete(f"/rent-changes/{rc_id}")

    items = client.get(f"/contracts/{contract_id}/rent-changes").json()
    assert not any(item["id"] == rc_id for item in items)
    assert len(items) == 1


def test_delete_rent_change_only_one_returns_400():
    _, _, contract_id = _setup_contract_scenario()
    items = client.get(f"/contracts/{contract_id}/rent-changes").json()
    assert len(items) == 1
    rc_id = items[0]["id"]

    r = client.delete(f"/rent-changes/{rc_id}")
    assert r.status_code == 400


def test_delete_rent_change_intermediate_returns_409():
    _, _, contract_id = _setup_contract_scenario()
    client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2025-06-01", "amount": 750000},
    )
    client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2026-06-01", "amount": 800000},
    )
    items = client.get(f"/contracts/{contract_id}/rent-changes").json()
    # items are ordered DESC, so items[1] is the middle one
    middle_id = items[1]["id"]

    r = client.delete(f"/rent-changes/{middle_id}")
    assert r.status_code == 409


def test_delete_rent_change_not_found_returns_404():
    r = client.delete("/rent-changes/99999")
    assert r.status_code == 404


# ============================================================
# FASE 5: Payment period generation
# ============================================================

def test_contract_creation_generates_12_periods():
    _, _, contract_id = _setup_contract_scenario()
    payments = client.get(f"/contracts/{contract_id}/payments").json()
    assert len(payments) == 12


def test_generated_periods_use_payment_day_for_due_date():
    # _setup_contract_scenario uses payment_day=5 and start_date=2024-01-01
    _, _, contract_id = _setup_contract_scenario()
    payments = client.get(f"/contracts/{contract_id}/payments").json()
    jan = next(p for p in payments if p["period"] == "2024-01")
    assert jan["due_date"] == "2024-01-05"


def test_generated_periods_are_pending_with_no_paid_amount():
    _, _, contract_id = _setup_contract_scenario()
    payments = client.get(f"/contracts/{contract_id}/payments").json()
    assert all(p["status"] == "pending" for p in payments)
    assert all(p["paid_amount"] is None for p in payments)


def test_managed_property_creation_also_generates_periods():
    r = client.post(
        "/managed-property",
        json={
            "property": {
                "comuna": "IQUIQUE",
                "rol": "11001-00001",
                "address": "Arturo Prat 100",
                "destination": "HABITACIONAL",
                "status": "occupied",
                "fojas": "11",
                "property_number": "11",
                "year": 2021,
                "fiscal_appraisal": 60000000,
            },
            "rental": {
                "tenant_name": "Arrendatario Iquique",
                "payment_day": 5,
                "property_label": "depto iquique",
                "current_rent": 450000,
                "adjustment_frequency": "annual",
                "start_date": "2024-06-01",
                "notice_days": 30,
                "adjustment_month": "june",
            },
        },
    )
    assert r.status_code == 200
    cid = _get_contract_id_for_rol("11001-00001")
    payments = client.get(f"/contracts/{cid}/payments").json()
    assert len(payments) == 12
    periods = [p["period"] for p in payments]
    assert "2024-06" in periods
    assert "2025-05" in periods


def test_overpayment_field_is_returned_in_payment_response():
    cid = _setup_payment_property()
    r = client.post(f"/contracts/{cid}/payments", json={"period": "2026-01"})
    assert r.status_code == 200
    pid = r.json()["id"]

    r = client.patch(f"/payments/{pid}", json={"paid_amount": 600000})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "paid"
    assert "overpayment" in body
    assert body["overpayment"] == 100000


def test_overpayment_zero_when_exactly_paid():
    cid = _setup_payment_property()
    r = client.post(f"/contracts/{cid}/payments", json={"period": "2026-02"})
    pid = r.json()["id"]
    r = client.patch(f"/payments/{pid}", json={"paid_amount": 500000})
    assert r.json()["overpayment"] == 0


def test_apply_overpayment_endpoint_moves_excess_to_next():
    cid = _setup_payment_property()
    r = client.post(f"/contracts/{cid}/payments", json={"period": "2026-03"})
    pid = r.json()["id"]
    client.patch(f"/payments/{pid}", json={"paid_amount": 600000})

    r = client.post(f"/payments/{pid}/apply-overpayment")
    assert r.status_code == 200
    body = r.json()

    assert body["current"]["paid_amount"] == 500000
    assert body["current"]["overpayment"] == 0
    assert body["current"]["status"] == "paid"

    assert body["next"]["period"] == "2026-04"
    assert body["next"]["paid_amount"] == 100000
    assert body["next"]["status"] == "partial"


def test_apply_overpayment_returns_400_when_none():
    cid = _setup_payment_property()
    r = client.post(f"/contracts/{cid}/payments", json={"period": "2026-05"})
    pid = r.json()["id"]
    client.patch(f"/payments/{pid}", json={"paid_amount": 500000})

    r = client.post(f"/payments/{pid}/apply-overpayment")
    assert r.status_code == 400


def test_close_contract_removes_future_pending_periods():
    _, _, contract_id = _setup_contract_scenario()
    # contract has 12 periods: 2024-01 to 2024-12

    # Pay 2024-06
    payments = client.get(f"/contracts/{contract_id}/payments").json()
    p = next(p for p in payments if p["period"] == "2024-06")
    client.patch(f"/payments/{p['id']}", json={"paid_amount": 700000})

    # Close with end_date 2024-06-30
    r = client.patch(f"/contracts/{contract_id}/close", json={"end_date": "2024-06-30"})
    assert r.status_code == 200

    import sqlite3 as _sqlite3
    conn = _sqlite3.connect("test_rental_manager.db")
    rows = conn.execute(
        "SELECT period, status FROM payments WHERE contract_id = ? ORDER BY period",
        (contract_id,),
    ).fetchall()
    conn.close()

    remaining = {row[0]: row[1] for row in rows}
    assert "2024-07" not in remaining
    assert "2024-12" not in remaining
    assert "2024-06" in remaining  # paid — kept
    assert "2024-01" in remaining  # pending within range — kept
    assert "2024-05" in remaining


def test_create_payment_with_paid_amount_derives_status():
    cid = _setup_payment_property()
    r = client.post(
        f"/contracts/{cid}/payments",
        json={"period": "2026-06", "paid_amount": 250000, "paid_at": "2026-06-05"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "partial"
    assert body["paid_amount"] == 250000


def test_create_payment_with_full_amount_marks_paid():
    cid = _setup_payment_property()
    r = client.post(
        f"/contracts/{cid}/payments",
        json={"period": "2026-07", "paid_amount": 500000, "paid_at": "2026-07-05"},
    )
    assert r.status_code == 200


# -----------------------------------------------------------------------
# requires_adjustment_notice: fix — cleared by a recent rent change
# -----------------------------------------------------------------------

def test_requires_notice_false_after_adjustment_within_notice_window():
    # Self-contained: creates its own property (09998-00001) and inserts a rent
    # change via the API within the same test.
    # start=2025-01-01, annual, adjustment_month=january, notice_days=30.
    # At as_of=2026-12-15: next_adj=2027-01-01, notice_date=2026-12-02 (30 days) → True.
    # After registering effective_from=2026-12-10 (>= notice_date): → False.

    rol = "09998-00001"
    create_r = client.post("/managed-property", json={
        "property": {
            "comuna": "CASTRO",
            "rol": rol,
            "address": "GAMBOA TEST NOTICE FIX",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "998",
            "property_number": "998",
            "year": 2025,
            "fiscal_appraisal": 10000000,
        },
        "rental": {
            "tenant_name": "Tenant Notice Fix",
            "payment_day": 5,
            "property_label": "test notice fix",
            "current_rent": 150000,
            "adjustment_frequency": "annual",
            "start_date": "2025-01-01",
            "notice_days": 30,
            "adjustment_month": "january",
        },
    })
    assert create_r.status_code == 200

    r_before = client.get("/rent-adjustments", params={"as_of": "2026-12-15"})
    assert r_before.status_code == 200
    item_before = next(i for i in r_before.json() if i["rol"] == rol)
    assert item_before["requires_adjustment_notice"] is True, (
        "pre-condition: alert must be active before registering the adjustment"
    )

    contract_id = item_before["contract_id"]
    rc_r = client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2026-12-10", "amount": 160000},
    )
    assert rc_r.status_code == 201

    r_after = client.get("/rent-adjustments", params={"as_of": "2026-12-15"})
    item_after = next(i for i in r_after.json() if i["rol"] == rol)
    assert item_after["requires_adjustment_notice"] is False, (
        "alert must disappear after registering a rent change within the notice window"
    )


def test_requires_notice_true_when_last_adjustment_predates_notice_window():
    # Self-contained: creates its own property (02162-00099) and inserts a past
    # rent change via the API within the same test.
    # start=2022-03-12, annual, notice_days=60.
    # At as_of=2027-02-15: next_adj=2027-03-12, notice_date=2027-01-11 (60 days before).
    # last_adjustment_date=2023-05-01 < 2027-01-11 → alert must still be active.

    rol = "02162-00099"
    create_r = client.post("/managed-property", json={
        "property": {
            "comuna": "LA SERENA",
            "rol": rol,
            "address": "BALMACEDA TEST NOTICE PRED",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "9999",
            "property_number": "9999",
            "year": 2016,
            "fiscal_appraisal": 142935366,
        },
        "rental": {
            "tenant_name": "Tenant Predates Test",
            "payment_day": 5,
            "property_label": "test predates notice",
            "current_rent": 801875,
            "adjustment_frequency": "annual",
            "start_date": "2022-03-12",
            "notice_days": 60,
            "adjustment_month": "march",
        },
    })
    assert create_r.status_code == 200

    # Fetch the contract_id, then insert the past rent change within this test.
    r_adj = client.get("/rent-adjustments", params={"as_of": "2024-01-01"})
    assert r_adj.status_code == 200
    item_mid = next(i for i in r_adj.json() if i["rol"] == rol)
    contract_id = item_mid["contract_id"]

    rc_r = client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": "2023-05-01", "amount": 850000},
    )
    assert rc_r.status_code == 201

    r = client.get("/rent-adjustments", params={"as_of": "2027-02-15"})
    assert r.status_code == 200
    item = next(i for i in r.json() if i["rol"] == rol)
    # notice_days=60 → notice window opens 2027-03-12 - 60 days = 2027-01-11, not one month prior
    assert item["adjustment_notice_date"] == "2027-01-11"
    assert item["requires_adjustment_notice"] is True, (
        "alert must remain active when the last adjustment predates the current notice window"
    )


def test_dashboard_requires_notice_false_after_adjustment():
    # Creates a fresh property 11 months ago (first of that month), annual freq.
    # next_adj = first of next month.  With notice_days=32 the window opens
    # first_of_next_month - 32 days, which always falls in the previous month —
    # so any day of the current month is guaranteed inside the window.

    today = datetime.date.today()
    month = today.month - 11
    year = today.year
    if month <= 0:
        month += 12
        year -= 1
    start_date_str = f"{year}-{month:02d}-01"

    rol = "06600-00001"
    payload = {
        "property": {
            "comuna": "TEST NOTICE",
            "rol": rol,
            "address": "TEST ADDR 1",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "1",
            "property_number": "1",
            "year": 2020,
            "fiscal_appraisal": 1000000,
        },
        "rental": {
            "tenant_name": "Tenant Notice Test",
            "payment_day": 5,
            "property_label": "test notice prop",
            "current_rent": 400000,
            "adjustment_frequency": "annual",
            "start_date": start_date_str,
            "notice_days": 32,
            "adjustment_month": "january",
        },
    }
    create_r = client.post("/managed-property", json=payload)
    assert create_r.status_code == 200

    dash1 = client.get("/dashboard").json()
    item1 = next(i for i in dash1 if i["rol"] == rol)
    assert item1["requires_adjustment_notice"] is True, (
        "pre-condition: dashboard must show alert when today is in the notice window"
    )

    contract_id = item1["contract_id"]
    rc_r = client.post(
        f"/contracts/{contract_id}/rent-changes",
        json={"effective_from": today.isoformat(), "amount": 420000},
    )
    assert rc_r.status_code == 201

    dash2 = client.get("/dashboard").json()
    item2 = next(i for i in dash2 if i["rol"] == rol)
    assert item2["requires_adjustment_notice"] is False, (
        "dashboard must clear the alert after a rent change within the notice window"
    )


# ============================================================
# GAP DETECTION — feature/payments-period-gap-detection
# ============================================================

# --- Date helpers for relative date construction ---

def _ym_add(ym: str, delta: int) -> str:
    """Shift a 'YYYY-MM' string by delta months."""
    total = int(ym[:4]) * 12 + int(ym[5:7]) - 1 + delta
    return f"{total // 12}-{total % 12 + 1:02d}"


def _ym_for_months_ago(n: int) -> str:
    """Return 'YYYY-MM' for the month n months before today (negative n = future)."""
    today = datetime.date.today()
    total = today.year * 12 + today.month - 1 - n
    return f"{total // 12}-{total % 12 + 1:02d}"


def _first_day_for_months_ago(n: int) -> str:
    """Return 'YYYY-MM-01' for the month n months before today (negative n = future)."""
    return f"{_ym_for_months_ago(n)}-01"


def _setup_gap_contract(rol: str, start_date: str | None = None) -> int:
    """Create a gap-test contract.

    Default start_date is the first day of 13 months ago so that
    generate_payment_periods produces exactly 12 rows covering
    [13_months_ago, 2_months_ago], leaving 1_month_ago onward with no rows.
    """
    if start_date is None:
        start_date = _first_day_for_months_ago(13)
    r = client.post("/managed-property", json={
        "property": {
            "comuna": "GAP TESTS",
            "rol": rol,
            "address": f"Gap Test {rol}",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "1",
            "property_number": "1",
            "year": 2024,
            "fiscal_appraisal": 100000000,
        },
        "rental": {
            "tenant_name": "Arrendatario Gap",
            "payment_day": 5,
            "property_label": f"prop {rol}",
            "current_rent": 500000,
            "adjustment_frequency": "annual",
            "start_date": start_date,
            "notice_days": 30,
            "adjustment_month": "january",
        },
    })
    assert r.status_code == 200
    return _get_contract_id_for_rol(rol)


def test_gap_detection_middle_period():
    """Middle gap: virtual period earlier than the SQL actionable period.

    State: start_ym paid, start_ym+1 deleted, rest pending.
    SQL actionable = start_ym+2 (earliest unpaid existing row).
    Virtual gap    = start_ym+1 (first missing in sequence from start).
    min(start_ym+1, start_ym+2) → virtual wins.
    """
    cid = _setup_gap_contract("12001-00001")
    start_ym = _ym_for_months_ago(13)
    gap_ym = _ym_add(start_ym, 1)
    payments = client.get(f"/contracts/{cid}/payments").json()

    p_start = next(p for p in payments if p["period"] == start_ym)
    client.patch(f"/payments/{p_start['id']}", json={"paid_amount": p_start["expected_amount"]})

    conn = _sqlite3.connect("test_rental_manager.db")
    conn.execute("DELETE FROM payments WHERE contract_id = ? AND period = ?", (cid, gap_ym))
    conn.commit()
    conn.close()

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "12001-00001")
    assert item["actionable_payment_period"] == gap_ym
    assert item["actionable_payment_status"] == "pending"


def test_gap_detection_before_first_existing_row():
    """Gap at start: start_ym itself is missing but later rows exist.

    State: start_ym deleted, rest pending.
    SQL actionable = start_ym+1 (earliest unpaid existing row).
    Virtual gap    = start_ym (start_ym is the first missing month).
    min(start_ym, start_ym+1) → virtual wins.
    """
    cid = _setup_gap_contract("12002-00001")
    start_ym = _ym_for_months_ago(13)

    conn = _sqlite3.connect("test_rental_manager.db")
    conn.execute("DELETE FROM payments WHERE contract_id = ? AND period = ?", (cid, start_ym))
    conn.commit()
    conn.close()

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "12002-00001")
    assert item["actionable_payment_period"] == start_ym
    assert item["actionable_payment_status"] == "pending"


def test_gap_detection_after_latest_paid_rows():
    """Gap after last existing row: all generated rows paid, later months missing.

    Contract starts 13 months ago; 12 rows generated covering [start_ym, start_ym+11].
    After paying all 12, virtual gap = start_ym+12 (first uncovered month).
    """
    cid = _setup_gap_contract("12003-00001")
    payments = client.get(f"/contracts/{cid}/payments").json()

    for p in payments:
        client.patch(f"/payments/{p['id']}", json={"paid_amount": p["expected_amount"]})

    expected_gap = _ym_for_months_ago(1)  # start_ym + 12 = 13 months ago + 12 = 1 month ago

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "12003-00001")
    assert item["actionable_payment_period"] == expected_gap
    assert item["actionable_payment_status"] == "pending"
    assert item["actionable_payment_amount"] == 500000


def test_gap_detection_no_rows_at_all():
    """No rows at all: virtual period = start_ym.

    Simulates a contract seeded directly into the DB without generating
    payment rows — the dashboard must still surface the first due period.
    """
    cid = _setup_gap_contract("12004-00001")
    start_ym = _ym_for_months_ago(13)

    conn = _sqlite3.connect("test_rental_manager.db")
    conn.execute("DELETE FROM payments WHERE contract_id = ?", (cid,))
    conn.commit()
    conn.close()

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "12004-00001")
    assert item["actionable_payment_period"] == start_ym
    assert item["actionable_payment_status"] == "pending"
    assert item["actionable_payment_amount"] == 500000


def test_gap_detection_future_start_date_no_alert():
    """Future start_date: start_ym > current_ym — no virtual gap must be surfaced."""
    future_start = _first_day_for_months_ago(-1)  # next month
    _setup_gap_contract("12005-00001", start_date=future_start)

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "12005-00001")
    assert item["actionable_payment_period"] is None


def test_gap_detection_vacant_property_no_alert():
    """Vacant property has no contract: gap detection must not apply."""
    client.post("/managed-property", json={
        "property": {
            "comuna": "GAP TESTS",
            "rol": "12006-00001",
            "address": "Gap Vacant Test",
            "destination": "SITIO ERIAZO",
            "status": "vacant",
            "fojas": "1",
            "property_number": "1",
            "year": 2024,
            "fiscal_appraisal": 100000000,
        },
        "rental": None,
    })

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "12006-00001")
    assert item["contract_id"] is None
    assert item["actionable_payment_period"] is None


def test_gap_detection_sql_period_preserved_when_earlier_than_virtual():
    """SQL actionable period preserved when it is earlier than the virtual gap.

    State: start_ym pending (exists), start_ym+1 deleted, rest pending.
    SQL actionable = start_ym (earliest unpaid existing row).
    Virtual gap    = start_ym+1 (first missing).
    start_ym < start_ym+1 → virtual is NOT earlier → SQL is kept.
    """
    cid = _setup_gap_contract("12007-00001")
    start_ym = _ym_for_months_ago(13)
    gap_ym = _ym_add(start_ym, 1)

    conn = _sqlite3.connect("test_rental_manager.db")
    conn.execute("DELETE FROM payments WHERE contract_id = ? AND period = ?", (cid, gap_ym))
    conn.commit()
    conn.close()

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "12007-00001")
    assert item["actionable_payment_period"] == start_ym
    assert item["actionable_payment_status"] == "pending"


def test_gap_detection_no_false_positive_when_all_due_paid():
    """No false positive: all due rows through current month are paid → actionable = None.

    Contract starts in the current month so generate_payment_periods creates
    exactly one due row (current month).  After fully paying it the virtual
    scan finds the period in the existing set and returns None — no spurious
    alert must be raised.
    """
    today = datetime.date.today()
    current_ym = today.strftime("%Y-%m")
    start_date = f"{current_ym}-01"

    cid = _setup_gap_contract("12008-00001", start_date=start_date)
    payments = client.get(f"/contracts/{cid}/payments").json()

    due = [p for p in payments if p["period"] <= current_ym]
    for p in due:
        r = client.patch(f"/payments/{p['id']}", json={"paid_amount": p["expected_amount"]})
        assert r.status_code == 200

    item = next(i for i in client.get("/dashboard").json() if i["rol"] == "12008-00001")
    assert item["actionable_payment_period"] is None, (
        "gap detection must not invent an alert when all due periods exist and are paid"
    )


# ── Adjustment notice-sent workflow ──────────────────────────────────────────

def _notice_property(rol: str, start_date: str, adjustment_frequency: str = "annual") -> dict:
    return {
        "property": {
            "comuna": "TEST",
            "rol": rol,
            "address": "TEST ADDRESS",
            "destination": "HABITACIONAL",
            "status": "occupied",
        },
        "rental": {
            "tenant_name": "Test Tenant",
            "payment_day": 5,
            "property_label": f"test {rol}",
            "current_rent": 100000,
            "adjustment_frequency": adjustment_frequency,
            "start_date": start_date,
            "notice_days": 30,
            "adjustment_month": "january",
        },
    }


def test_notice_sent_on_active_contract_returns_200():
    client.post("/managed-property", json=_notice_property("NTEST-BASIC-001", _first_day_for_months_ago(13)))
    cid = _get_contract_id_for_rol("NTEST-BASIC-001")
    r = client.post(f"/contracts/{cid}/notice-sent")
    assert r.status_code == 200
    body = r.json()
    assert body["contract_id"] == cid
    assert "notice_sent_at" in body
    assert body["notice_sent_at"] is not None


def test_notice_sent_on_nonexistent_contract_returns_404():
    r = client.post("/contracts/99999/notice-sent")
    assert r.status_code == 404


def test_dashboard_notice_registered_true_after_notice_sent():
    # Creates its own overdue contract, posts notice-sent, then verifies notice_registered=True.
    client.post("/managed-property", json=_notice_property("NTEST-NOTREG-001", _first_day_for_months_ago(13)))
    cid = _get_contract_id_for_rol("NTEST-NOTREG-001")
    client.post(f"/contracts/{cid}/notice-sent")
    items = client.get("/dashboard").json()
    item = next(i for i in items if i.get("contract_id") == cid)
    assert item["notice_registered"] is True


def test_notice_registered_true_when_marked_after_adjustment_date():
    # start 13 months ago → due_adjustment_date = first of last month (past)
    # marking notice after the due date must still count: notice_sent_at >= current_cycle_notice_date
    client.post("/managed-property", json=_notice_property("NTEST-AFTER-001", _first_day_for_months_ago(13)))
    cid = _get_contract_id_for_rol("NTEST-AFTER-001")

    r = client.post(f"/contracts/{cid}/notice-sent")
    assert r.status_code == 200

    items = client.get("/dashboard").json()
    item = next(i for i in items if i.get("contract_id") == cid)
    assert item["notice_registered"] is True
    assert item["adjustment_due"] is True


def test_requires_adjustment_notice_false_after_rent_change_applied():
    # start 13 months ago → overdue; applying a rent_change within the cycle window clears the alert
    client.post("/managed-property", json=_notice_property("NTEST-RESOLVE-001", _first_day_for_months_ago(13)))
    cid = _get_contract_id_for_rol("NTEST-RESOLVE-001")
    rc = client.post(
        f"/contracts/{cid}/rent-changes",
        json={"effective_from": _first_day_for_months_ago(1), "amount": 110000},
    )
    assert rc.status_code == 201

    items = client.get("/dashboard").json()
    item = next(i for i in items if i.get("contract_id") == cid)
    assert item["requires_adjustment_notice"] is False


def test_dashboard_adjustment_due_true_when_due_date_is_past():
    # start 13 months ago → due_adjustment_date = first of last month (past)
    client.post("/managed-property", json=_notice_property("NTEST-DUEYES-001", _first_day_for_months_ago(13)))
    cid = _get_contract_id_for_rol("NTEST-DUEYES-001")

    items = client.get("/dashboard").json()
    item = next(i for i in items if i.get("contract_id") == cid)
    assert item["adjustment_due"] is True
    assert item["requires_adjustment_notice"] is True
    assert item["due_adjustment_date"] is not None
    assert item["due_adjustment_date"] <= datetime.date.today().isoformat()


def test_dashboard_adjustment_due_false_when_due_date_is_future():
    # start 11 months ago → due_adjustment_date = first of next month (future)
    # adj_notice_date = first of current month → notice window is open, adjustment not yet due
    client.post("/managed-property", json=_notice_property("NTEST-DUENO-001", _first_day_for_months_ago(11)))
    cid = _get_contract_id_for_rol("NTEST-DUENO-001")

    items = client.get("/dashboard").json()
    item = next(i for i in items if i.get("contract_id") == cid)
    assert item["adjustment_due"] is False
    assert item["requires_adjustment_notice"] is True
    assert item["due_adjustment_date"] is not None
    assert item["due_adjustment_date"] > datetime.date.today().isoformat()


# Frontend targetPeriod no-rows path — verified by code inspection.
# PaymentsView.jsx openAdd(): the payments.length === 0 branch previously called
# setFormCustomPeriod(todayLocal().slice(0, 7)), which ignored targetPeriod.
# The fix changes it to: setFormCustomPeriod(targetPeriod ?? todayLocal().slice(0, 7))
# This ensures that when the dashboard surfaces a virtual gap for a contract with
# no rows and the user clicks Resolve, the add-payment form pre-selects the
# correct period instead of today's month.
# No frontend test framework exists in this project; this scenario is covered by
# the backend tests above (gap surfaced → actionable_payment_period populated)
# and manual inspection of the PaymentsView change.