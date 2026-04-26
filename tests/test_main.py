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


def test_list_contracts_returns_active_contracts():
    response = client.get("/contracts")
    assert response.status_code == 200
    contracts = response.json()
    assert len(contracts) > 0
    first = contracts[0]
    assert "id" in first
    assert "property_id" in first
    assert "property_label" in first
    assert "rol" in first
    assert "tenant_name" in first
    assert "current_rent" in first
    assert "payment_day" in first
    assert "adjustment_frequency" in first


def test_list_tenants_returns_active_tenants():
    response = client.get("/tenants")
    assert response.status_code == 200
    tenants = response.json()
    assert len(tenants) > 0
    first = tenants[0]
    assert "id" in first
    assert "display_name" in first
    assert "property_label" in first
    assert "rol" in first
    assert "current_rent" in first
    assert "payment_day" in first


def test_create_payment_for_contract():
    contracts_response = client.get("/contracts")
    contract_id = contracts_response.json()[0]["id"]

    response = client.post(
        f"/contracts/{contract_id}/payments",
        json={"period": "2025-01", "comment": "test payment"},
    )
    assert response.status_code == 201
    payment = response.json()
    assert payment["contract_id"] == contract_id
    assert payment["period"] == "2025-01"
    assert payment["status"] == "pending"
    assert payment["source"] == "manual"
    assert payment["comment"] == "test payment"
    assert payment["expected_amount"] > 0
    assert "due_date" in payment


def test_create_payment_duplicate_period_returns_409():
    contracts_response = client.get("/contracts")
    contract_id = contracts_response.json()[0]["id"]

    client.post(
        f"/contracts/{contract_id}/payments",
        json={"period": "2025-02"},
    )
    response = client.post(
        f"/contracts/{contract_id}/payments",
        json={"period": "2025-02"},
    )
    assert response.status_code == 409


def test_create_payment_unknown_contract_returns_404():
    response = client.post(
        "/contracts/99999/payments",
        json={"period": "2025-03"},
    )
    assert response.status_code == 404


def test_list_payments_for_contract():
    contracts_response = client.get("/contracts")
    contract_id = contracts_response.json()[0]["id"]

    response = client.get(f"/contracts/{contract_id}/payments")
    assert response.status_code == 200
    payments = response.json()
    assert isinstance(payments, list)
    if payments:
        assert "period" in payments[0]
        assert "status" in payments[0]


def test_patch_payment_marks_paid():
    contracts_response = client.get("/contracts")
    contract_id = contracts_response.json()[0]["id"]

    create_response = client.post(
        f"/contracts/{contract_id}/payments",
        json={"period": "2025-04"},
    )
    assert create_response.status_code == 201
    payment = create_response.json()
    payment_id = payment["id"]
    expected = payment["expected_amount"]

    patch_response = client.patch(
        f"/payments/{payment_id}",
        json={"paid_amount": expected, "paid_at": "2025-04-05"},
    )
    assert patch_response.status_code == 200
    updated = patch_response.json()
    assert updated["status"] == "paid"
    assert updated["paid_amount"] == expected
    assert updated["paid_at"] == "2025-04-05"


def test_patch_payment_partial():
    contracts_response = client.get("/contracts")
    contract_id = contracts_response.json()[0]["id"]

    create_response = client.post(
        f"/contracts/{contract_id}/payments",
        json={"period": "2025-05"},
    )
    payment_id = create_response.json()["id"]
    expected = create_response.json()["expected_amount"]

    patch_response = client.patch(
        f"/payments/{payment_id}",
        json={"paid_amount": expected - 1},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "partial"


def test_patch_payment_unknown_returns_404():
    response = client.patch(
        "/payments/99999",
        json={"paid_amount": 100000},
    )
    assert response.status_code == 404


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