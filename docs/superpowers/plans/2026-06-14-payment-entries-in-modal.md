# Payment Entries in Modal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow each payment period to store multiple internal abonos (payment_entries), each with its own amount, date, and note, while keeping one row per period in the table.

**Architecture:** New `payment_entries` table stores individual abonos; `payments.paid_amount` becomes the computed sum of entries; `payments.paid_at` becomes the latest entry date. Legacy payments with `paid_amount > 0` and no entries synthesize one virtual entry on read. All overpayment/carry-forward/rent-change logic continues using period-level `paid_amount`.

**Tech Stack:** SQLite + FastAPI (db.py, models.py, main.py) · React (frontend/src/PaymentsView.jsx) · pytest

---

## File Map

| File | Change |
|------|--------|
| `db.py` | Add `payment_entries` table + 4 helpers; update `_payment_row_to_dict`, `insert_payment`, `update_payment`, `get_payment`, `list_payments_for_contract`, `apply_overpayment_to_next` |
| `models.py` | Add `PaymentEntryInput`, `PaymentEntryResponse`; extend `PaymentCreate`, `PaymentUpdate`, `PaymentResponse` |
| `main.py` | Update `create_payment`, `patch_payment` to derive `paid_amount`/`paid_at` from entries |
| `frontend/src/PaymentsView.jsx` | Replace `formAmount`/`formDate` state with `formEntries`; replace `editAmount`/`editDate` with `editEntries`; render entry rows in modal; update overpayment draft + save handlers |
| `tests/test_main.py` | Add 10 tests for payment_entries feature |

---

## Task 1 — DB: payment_entries table

**Files:** Modify `db.py`

- [ ] **Step 1: Add table creation to init_db**

In `db.py`, inside the `init_db()` function, after the block that creates `payment_deductions` (search for `CREATE TABLE IF NOT EXISTS payment_deductions`), add:

```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_entries (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
                amount     INTEGER NOT NULL CHECK(amount > 0),
                paid_at    TEXT,
                note       TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_payment_entries_payment_id
            ON payment_entries(payment_id)
            """
        )
```

- [ ] **Step 2: Verify table is created**

```bash
cd ~/Documentos/Proyectos/rental-manager
source venv/bin/activate
python -c "
from db import init_db, get_connection
init_db()
with get_connection() as c:
    rows = c.execute(\"PRAGMA table_info(payment_entries)\").fetchall()
    print(rows)
"
```

Expected: 6 columns printed (id, payment_id, amount, paid_at, note, created_at).

---

## Task 2 — DB: helper functions for payment_entries

**Files:** Modify `db.py`

- [ ] **Step 1: Add 4 helper functions after `_replace_owner_expenses`**

Find the line `def insert_payment(` and insert the following block *before* it:

```python
def _load_payment_entries(conn, payment_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, amount, paid_at, note
        FROM payment_entries
        WHERE payment_id = ?
        ORDER BY id
        """,
        (payment_id,),
    ).fetchall()
    return [{"id": r[0], "amount": r[1], "paid_at": r[2], "note": r[3]} for r in rows]


def _load_payment_entries_batch(conn, payment_ids: list[int]) -> dict[int, list[dict]]:
    if not payment_ids:
        return {}
    placeholders = ",".join("?" * len(payment_ids))
    rows = conn.execute(
        f"""
        SELECT payment_id, id, amount, paid_at, note
        FROM payment_entries
        WHERE payment_id IN ({placeholders})
        ORDER BY payment_id, id
        """,
        payment_ids,
    ).fetchall()
    result: dict[int, list[dict]] = {}
    for r in rows:
        result.setdefault(r[0], []).append(
            {"id": r[1], "amount": r[2], "paid_at": r[3], "note": r[4]}
        )
    return result


def _insert_payment_entries(conn, payment_id: int, entries: list[dict]) -> None:
    for e in entries:
        conn.execute(
            """
            INSERT INTO payment_entries (payment_id, amount, paid_at, note)
            VALUES (?, ?, ?, ?)
            """,
            (payment_id, e["amount"], e.get("paid_at") or None, e.get("note") or None),
        )


def _replace_payment_entries(conn, payment_id: int, entries: list[dict]) -> None:
    conn.execute("DELETE FROM payment_entries WHERE payment_id = ?", (payment_id,))
    _insert_payment_entries(conn, payment_id, entries)
```

- [ ] **Step 2: Verify helpers import/run without error**

```bash
python -c "from db import _load_payment_entries; print('ok')"
```

Expected: `ok`

---

## Task 3 — DB: update _payment_row_to_dict to include entries

**Files:** Modify `db.py`

- [ ] **Step 1: Update `_payment_row_to_dict` signature and body**

Find the function starting at:
```python
def _payment_row_to_dict(
    row,
    deductions: list[dict] | None = None,
    owner_expenses: list[dict] | None = None,
) -> dict:
```

Replace with:
```python
def _payment_row_to_dict(
    row,
    deductions: list[dict] | None = None,
    owner_expenses: list[dict] | None = None,
    payment_entries: list[dict] | None = None,
) -> dict:
    paid = row[5]
    expected = row[4]
    deductions = deductions or []
    owner_expenses = owner_expenses or []
    payment_entries = payment_entries or []
    # Legacy synthesis: if no real entries exist, synthesize one from paid_amount
    if not payment_entries and paid is not None and paid > 0:
        payment_entries = [{"id": None, "amount": paid, "paid_at": row[6], "note": row[9]}]
    total_deductions = sum(d["amount"] for d in deductions)
    total_owner_expenses = sum(e["amount"] for e in owner_expenses)
    recognized = (paid or 0) + total_deductions
    overpayment = max(0, paid - expected) if paid is not None else 0
    net_owner_amount = (paid or 0) - total_owner_expenses
    return {
        "id": row[0],
        "contract_id": row[1],
        "period": row[2],
        "due_date": row[3],
        "expected_amount": expected,
        "paid_amount": paid,
        "paid_at": row[6],
        "status": row[7],
        "source": row[8],
        "comment": row[9],
        "created_at": row[10],
        "deductions": deductions,
        "owner_expenses": owner_expenses,
        "payment_entries": payment_entries,
        "recognized_amount": recognized,
        "overpayment": overpayment,
        "net_owner_amount": net_owner_amount,
        "carry_forward_waived": bool(row[14]),
    }
```

- [ ] **Step 2: Update `get_payment` to load and pass entries**

Find `def get_payment(payment_id: int) -> dict | None:` and update it:

```python
def get_payment(payment_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM payments WHERE id = ?",
            (payment_id,),
        ).fetchone()
        if row is None:
            return None
        deductions = _load_deductions(conn, payment_id)
        owner_expenses = _load_owner_expenses(conn, payment_id)
        entries = _load_payment_entries(conn, payment_id)

    return _payment_row_to_dict(row, deductions, owner_expenses, entries)
```

- [ ] **Step 3: Update `list_payments_for_contract` to batch-load entries**

Find `def list_payments_for_contract(contract_id: int) -> list[dict]:` and update:

```python
def list_payments_for_contract(contract_id: int) -> list[dict]:
    _ensure_payment_periods(contract_id)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM payments WHERE contract_id = ? ORDER BY period DESC",
            (contract_id,),
        ).fetchall()
        payment_ids = [r[0] for r in rows]
        deductions_map = _load_deductions_batch(conn, payment_ids)
        owner_expenses_map = _load_owner_expenses_batch(conn, payment_ids)
        entries_map = _load_payment_entries_batch(conn, payment_ids)

    return [
        _payment_row_to_dict(
            row,
            deductions_map.get(row[0], []),
            owner_expenses_map.get(row[0], []),
            entries_map.get(row[0], []),
        )
        for row in rows
    ]
```

- [ ] **Step 4: Update the 4 other `_payment_row_to_dict` call sites that don't load entries**

These are in `apply_overpayment_to_next` and `rent_change_payment_atomic`. They don't need to load entries (the next period that receives carry-forward doesn't have entries, and rent-change uses paid_amount directly). Pass an explicit `payment_entries=[]` so legacy synthesis applies:

Find and update (4 locations in `apply_overpayment_to_next` and `rent_change_payment_atomic`):
```python
# Each of these 4 calls:
_payment_row_to_dict(row, _load_deductions(conn, row[0]), _load_owner_expenses(conn, row[0]))
# → becomes:
_payment_row_to_dict(row, _load_deductions(conn, row[0]), _load_owner_expenses(conn, row[0]), [])
```

Specifically update these lines in db.py:
- Line ~1981: `current = _payment_row_to_dict(row, _load_deductions(conn, row[0]), _load_owner_expenses(conn, row[0]))`
- Line ~2046: `next_dict = _payment_row_to_dict(next_row, _load_deductions(conn, next_row[0]), _load_owner_expenses(conn, next_row[0]))`
- Line ~2069: `updated_current = _payment_row_to_dict(cur_row, _load_deductions(conn, payment_id), _load_owner_expenses(conn, payment_id))`
- Line ~2070: `updated_next = _payment_row_to_dict(nxt_row, _load_deductions(conn, next_id), _load_owner_expenses(conn, next_id))`
- Line ~2340 (rent_change_payment_atomic): `"payment": _payment_row_to_dict(row, deductions_out, owner_expenses_out)`

Also update `list_payments_for_contract` call inside list comprehension:
- Line ~2151: `_payment_row_to_dict(row, deductions_map.get(row[0], []), owner_expenses_map.get(row[0], []))` → already handled in Step 3 above.

- [ ] **Step 5: Add `apply_overpayment_to_next` entry-sync fix**

When `apply_overpayment_to_next` reduces current period's `paid_amount` to `expected_amount`, delete the period's entries so legacy synthesis returns the correct amount.

Inside `apply_overpayment_to_next`, after the line:
```python
conn.execute(
    "UPDATE payments SET paid_amount = ?, status = 'paid' WHERE id = ?",
    (current["expected_amount"], payment_id),
)
```
Add:
```python
        conn.execute("DELETE FROM payment_entries WHERE payment_id = ?", (payment_id,))
```

---

## Task 4 — DB: update insert_payment and update_payment to handle entries

**Files:** Modify `db.py`

- [ ] **Step 1: Update `insert_payment` signature and body**

Find `def insert_payment(` and update the signature to add `payment_entries`:

```python
def insert_payment(
    contract_id: int,
    period: str,
    due_date: str,
    expected_amount: int,
    comment: str | None,
    paid_amount: int | None = None,
    paid_at: str | None = None,
    status: str = "pending",
    deductions: list[dict] | None = None,
    owner_expenses: list[dict] | None = None,
    carry_forward_waived: bool = False,
    payment_entries: list[dict] | None = None,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO payments
                (contract_id, period, due_date, expected_amount, paid_amount, paid_at, status, comment, carry_forward_waived)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (contract_id, period, due_date, expected_amount, paid_amount, paid_at, status, comment, int(carry_forward_waived)),
        )
        payment_id = cursor.lastrowid
        if deductions:
            _insert_deductions(conn, payment_id, deductions)
        if owner_expenses:
            _insert_owner_expenses(conn, payment_id, owner_expenses)
        if payment_entries:
            _insert_payment_entries(conn, payment_id, payment_entries)
        conn.commit()
        return payment_id
```

- [ ] **Step 2: Update `update_payment` signature and body**

Find `def update_payment(` and add `payment_entries` parameter + replace logic:

```python
def update_payment(
    payment_id: int,
    paid_amount: int | None,
    paid_at: str | None,
    status: str,
    comment: str | None,
    deductions: list[dict] | None = None,
    owner_expenses: list[dict] | None = None,
    expected_amount: int | None = None,
    carry_forward_waived: bool | None = None,
    payment_entries: list[dict] | None = None,
) -> None:
    with get_connection() as conn:
        if expected_amount is not None:
            conn.execute(
                """
                UPDATE payments
                SET paid_amount = ?, paid_at = ?, status = ?, comment = ?, expected_amount = ?
                WHERE id = ?
                """,
                (paid_amount, paid_at, status, comment, expected_amount, payment_id),
            )
        else:
            conn.execute(
                """
                UPDATE payments
                SET paid_amount = ?, paid_at = ?, status = ?, comment = ?
                WHERE id = ?
                """,
                (paid_amount, paid_at, status, comment, payment_id),
            )
        if carry_forward_waived is not None:
            conn.execute(
                "UPDATE payments SET carry_forward_waived = ? WHERE id = ?",
                (int(carry_forward_waived), payment_id),
            )
        if deductions is not None:
            _replace_deductions(conn, payment_id, deductions)
        if owner_expenses is not None:
            _replace_owner_expenses(conn, payment_id, owner_expenses)
        if payment_entries is not None:
            _replace_payment_entries(conn, payment_id, payment_entries)
        conn.commit()
```

---

## Task 5 — Models: PaymentEntryInput + PaymentEntryResponse

**Files:** Modify `models.py`

- [ ] **Step 1: Add entry models before `PaymentCreate`**

Find the line `class PaymentCreate(BaseModel):` and insert before it:

```python
class PaymentEntryInput(BaseModel):
    amount: int = Field(gt=0)
    paid_at: date | None = None
    note: str | None = None


class PaymentEntryResponse(BaseModel):
    id: int | None = None
    amount: int
    paid_at: date | None = None
    note: str | None = None
```

- [ ] **Step 2: Extend `PaymentCreate` with `payment_entries`**

Find `class PaymentCreate(BaseModel):` and add the field after `carry_forward_waived`:

```python
class PaymentCreate(BaseModel):
    period: str
    paid_amount: int | None = Field(default=None, ge=0)
    paid_at: date | None = None
    comment: str | None = None
    deductions: list[PaymentDeductionInput] = Field(default_factory=list)
    owner_expenses: list[OwnerExpenseInput] = Field(default_factory=list)
    carry_forward_waived: bool = False
    payment_entries: list[PaymentEntryInput] = Field(default_factory=list)

    @field_validator("period")
    @classmethod
    def period_must_be_yyyy_mm(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
            raise ValueError("period must be in YYYY-MM format (e.g. 2025-04)")
        return value
```

- [ ] **Step 3: Extend `PaymentUpdate` with `payment_entries`**

```python
class PaymentUpdate(BaseModel):
    paid_amount: int | None = None
    paid_at: date | None = None
    comment: str | None = None
    deductions: list[PaymentDeductionInput] | None = None
    owner_expenses: list[OwnerExpenseInput] | None = None
    expected_amount: int | None = Field(default=None, gt=0)
    carry_forward_waived: bool | None = None
    payment_entries: list[PaymentEntryInput] | None = None
```

- [ ] **Step 4: Extend `PaymentResponse` with `payment_entries`**

```python
class PaymentResponse(BaseModel):
    id: int
    contract_id: int
    period: str
    due_date: date
    expected_amount: int
    paid_amount: int | None = None
    paid_at: date | None = None
    status: PaymentStatus
    source: PaymentSource
    comment: str | None = None
    created_at: date
    deductions: list[PaymentDeductionResponse] = Field(default_factory=list)
    owner_expenses: list[OwnerExpenseResponse] = Field(default_factory=list)
    payment_entries: list[PaymentEntryResponse] = Field(default_factory=list)
    recognized_amount: int = 0
    overpayment: int = 0
    net_owner_amount: int = 0
    carry_forward_waived: bool = False
```

---

## Task 6 — API: update create_payment and patch_payment

**Files:** Modify `main.py`

- [ ] **Step 1: Update `create_payment` to derive paid_amount/paid_at from entries**

Find `def create_payment(contract_id: int, data: PaymentCreate):` and replace the body (from after `contract = get_contract_for_payment(...)` to before `try:`) with:

```python
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
```

Then update the `insert_payment(...)` call inside `try:` to add `payment_entries=entries_to_save`:

```python
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
```

- [ ] **Step 2: Update `patch_payment` to derive paid_amount/paid_at from entries**

Find `def patch_payment(payment_id: int, data: PaymentUpdate):` and replace the section that computes `paid_amount`/`paid_at`/`comment` (the first block after `payment = get_payment(payment_id)`):

```python
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
```

Then update the `update_payment(...)` call to pass `payment_entries=entries_to_save`:

```python
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
```

Note: The status computation (which uses `effective_deductions` and `paid`) in `patch_payment` uses `paid = paid_amount or 0`. This naturally uses the entry-derived `paid_amount` when entries are present.

- [ ] **Step 3: Also add `db.py` import for the new helper functions in main.py**

Find the imports block in `main.py` that imports from `db`:

```python
from db import (
    get_payment,
    ...
)
```

No new db functions are called directly from `main.py` — `insert_payment` and `update_payment` already accept `payment_entries`, so no import changes needed.

---

## Task 7 — Backend tests for payment_entries

**Files:** Modify `tests/test_main.py`

- [ ] **Step 1: Find a test that creates a reusable contract**

Search for `def test_create_managed_property_returns_id` — this creates contract id=1. The tests that follow use contract id=1. Add the new tests at the END of `test_main.py`.

- [ ] **Step 2: Add helper to get a fresh contract id for isolated tests**

At the end of `tests/test_main.py`, add:

```python
# ──────────────────────────────────────────────
# payment_entries feature tests
# ──────────────────────────────────────────────

def _create_disposable_contract():
    """Create a fresh managed property+contract and return its contract_id."""
    payload = {
        "property": {
            "comuna": "TEST",
            "rol": "99999-ENTRIES",
            "address": "ENTRIES TEST ADDR",
            "destination": "HABITACIONAL",
            "status": "occupied",
            "fojas": "1",
            "property_number": "1",
            "year": 2024,
            "fiscal_appraisal": 1000000,
        },
        "rental": {
            "tenant_name": "Entries Test Tenant",
            "payment_day": 5,
            "property_label": "entries-test-prop",
            "current_rent": 800000,
            "adjustment_frequency": "annual",
            "start_date": "2024-01-01",
            "notice_days": 30,
            "adjustment_month": "march",
        },
    }
    r = client.post("/managed-property", json=payload)
    assert r.status_code == 200
    contract_id = r.json()["active_contract_id"]
    assert contract_id is not None
    return contract_id


def test_create_payment_with_two_entries_returns_both():
    cid = _create_disposable_contract()
    r = client.post(
        f"/contracts/{cid}/payments",
        json={
            "period": "2026-01",
            "payment_entries": [
                {"amount": 600000, "paid_at": "2026-01-16", "note": "Primer abono"},
                {"amount": 200000, "paid_at": "2026-01-30", "note": "Segundo abono"},
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["paid_amount"] == 800000
    assert body["paid_at"] == "2026-01-30"
    entries = body["payment_entries"]
    assert len(entries) == 2
    assert entries[0]["amount"] == 600000
    assert entries[1]["amount"] == 200000


def test_create_payment_entries_sum_is_paid_amount():
    cid = _create_disposable_contract()
    r = client.post(
        f"/contracts/{cid}/payments",
        json={
            "period": "2026-02",
            "payment_entries": [
                {"amount": 500000, "paid_at": "2026-02-10"},
                {"amount": 300000, "paid_at": "2026-02-20"},
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["paid_amount"] == 800000
    assert body["paid_at"] == "2026-02-20"


def test_update_payment_entries_replaces_not_duplicates():
    cid = _create_disposable_contract()
    r = client.post(
        f"/contracts/{cid}/payments",
        json={
            "period": "2026-03",
            "payment_entries": [
                {"amount": 600000, "paid_at": "2026-03-10"},
            ],
        },
    )
    pid = r.json()["id"]

    r2 = client.patch(
        f"/payments/{pid}",
        json={
            "payment_entries": [
                {"amount": 400000, "paid_at": "2026-03-05"},
                {"amount": 400000, "paid_at": "2026-03-20"},
            ],
        },
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["paid_amount"] == 800000
    assert body["paid_at"] == "2026-03-20"
    assert len(body["payment_entries"]) == 2


def test_legacy_payment_synthesizes_one_entry():
    cid = _create_disposable_contract()
    r = client.post(
        f"/contracts/{cid}/payments",
        json={"period": "2026-04", "paid_amount": 700000, "paid_at": "2026-04-15", "comment": "legacy note"},
    )
    assert r.status_code == 200
    body = r.json()
    entries = body["payment_entries"]
    assert len(entries) == 1
    assert entries[0]["amount"] == 700000
    assert entries[0]["paid_at"] == "2026-04-15"
    assert entries[0]["note"] == "legacy note"
    assert entries[0]["id"] is None


def test_partial_status_when_entries_sum_below_expected():
    cid = _create_disposable_contract()
    r = client.post(
        f"/contracts/{cid}/payments",
        json={
            "period": "2026-05",
            "payment_entries": [
                {"amount": 400000, "paid_at": "2026-05-10"},
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "partial"
    assert body["paid_amount"] == 400000


def test_paid_status_when_entries_sum_equals_expected():
    cid = _create_disposable_contract()
    r = client.post(
        f"/contracts/{cid}/payments",
        json={
            "period": "2026-06",
            "payment_entries": [
                {"amount": 600000, "paid_at": "2026-06-05"},
                {"amount": 200000, "paid_at": "2026-06-25"},
            ],
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "paid"


def test_carry_forward_waived_preserved_with_entries():
    cid = _create_disposable_contract()
    r = client.post(
        f"/contracts/{cid}/payments",
        json={
            "period": "2026-07",
            "payment_entries": [
                {"amount": 850000, "paid_at": "2026-07-10"},
            ],
            "carry_forward_waived": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["carry_forward_waived"] is True
    assert body["paid_amount"] == 850000


def test_list_payments_returns_payment_entries():
    cid = _create_disposable_contract()
    client.post(
        f"/contracts/{cid}/payments",
        json={
            "period": "2026-08",
            "payment_entries": [
                {"amount": 300000, "paid_at": "2026-08-10"},
                {"amount": 500000, "paid_at": "2026-08-20"},
            ],
        },
    )
    r = client.get(f"/contracts/{cid}/payments")
    assert r.status_code == 200
    payments = r.json()
    p = next((x for x in payments if x["period"] == "2026-08"), None)
    assert p is not None
    assert len(p["payment_entries"]) == 2
    assert p["paid_amount"] == 800000


def test_apply_overpayment_uses_total_paid_amount():
    cid = _create_disposable_contract()
    r = client.post(
        f"/contracts/{cid}/payments",
        json={
            "period": "2026-09",
            "payment_entries": [
                {"amount": 600000, "paid_at": "2026-09-10"},
                {"amount": 300000, "paid_at": "2026-09-20"},
            ],
        },
    )
    pid = r.json()["id"]
    assert r.json()["overpayment"] == 100000

    r2 = client.post(f"/payments/{pid}/apply-overpayment")
    assert r2.status_code == 200
    body = r2.json()
    assert body["current"]["paid_amount"] == 800000
    assert body["current"]["overpayment"] == 0
    next_p = body["next"]
    assert next_p["paid_amount"] == 100000
```

- [ ] **Step 3: Run tests**

```bash
cd ~/Documentos/Proyectos/rental-manager
source venv/bin/activate
python -m pytest tests/test_main.py -q 2>&1 | tail -20
```

Expected: All tests pass. If any existing test fails, investigate before proceeding — do not change existing test behavior.

---

## Task 8 — Frontend: state refactor for formEntries / editEntries

**Files:** Modify `frontend/src/PaymentsView.jsx`

This task replaces the single `formAmount`/`formDate` state variables (add form) and `editAmount`/`editDate` (edit form) with `formEntries` / `editEntries` arrays. `formNote` and `editNote` remain for the period-level "Nota general" field.

- [ ] **Step 1: Replace state declarations**

Find the state block (lines ~103-113):
```javascript
  const [formAmount, setFormAmount] = useState('')
  const [formDate, setFormDate] = useState(todayLocal())
  const [formNote, setFormNote] = useState('')
  ...
  const [editAmount, setEditAmount] = useState('')
  const [editDate, setEditDate] = useState('')
  const [editNote, setEditNote] = useState('')
```

Replace with:
```javascript
  const [formEntries, setFormEntries] = useState([{ amount: '', paid_at: todayLocal(), note: '' }])
  const [formNote, setFormNote] = useState('')
  ...
  const [editEntries, setEditEntries] = useState([])
  const [editNote, setEditNote] = useState('')
```

- [ ] **Step 2: Update openAdd — new period case**

Find the `openAdd()` function. Every branch that currently does:
```javascript
setFormAmount(...)
setFormDate(todayLocal())
setFormNote('')
```

Replace each with:
```javascript
setFormEntries([{ amount: '', paid_at: todayLocal(), note: '' }])
setFormNote('')
```

Specifically, in the branch `if (payments.length === 0)`:
```javascript
setFormEntries([{
  amount: contract.current_rent != null ? formatAmountInput(contract.current_rent) : '',
  paid_at: todayLocal(),
  note: '',
}])
setFormNote('')
```

In the branch `if (targetPeriod)` when `p` exists (partial/pending payment):
```javascript
setFormEntries(
  p.payment_entries?.length > 0
    ? p.payment_entries.map(e => ({
        amount: formatAmountInput(e.amount ?? 0),
        paid_at: e.paid_at ?? todayLocal(),
        note: e.note ?? '',
      }))
    : [{ amount: formatAmountInput(getPrefillAmount(p)), paid_at: p.paid_at ?? todayLocal(), note: '' }]
)
setFormNote(p.comment ?? '')
```

In the branch `if (targetPeriod)` when `p` is null:
```javascript
setFormEntries([{ amount: formatAmountInput(contract.current_rent), paid_at: todayLocal(), note: '' }])
setFormNote('')
```

In the default branch (getNextPayablePeriod):
```javascript
setFormEntries(
  !isVirtual && payment && payment.payment_entries?.length > 0
    ? payment.payment_entries.map(e => ({
        amount: formatAmountInput(e.amount ?? 0),
        paid_at: e.paid_at ?? todayLocal(),
        note: e.note ?? '',
      }))
    : [{ amount: formatAmountInput(isVirtual ? contract.current_rent : getPrefillAmount(payment)), paid_at: todayLocal(), note: '' }]
)
setFormNote(!isVirtual && payment ? (payment.comment ?? '') : '')
```

- [ ] **Step 3: Update handlePeriodSelect**

Find `function handlePeriodSelect(value)`. Replace the `if (p)` / `else` block:

```javascript
    if (p) {
      setFormEntries(
        p.payment_entries?.length > 0
          ? p.payment_entries.map(e => ({
              amount: formatAmountInput(e.amount ?? 0),
              paid_at: e.paid_at ?? todayLocal(),
              note: e.note ?? '',
            }))
          : [{ amount: formatAmountInput(getPrefillAmount(p)), paid_at: p.paid_at ?? todayLocal(), note: '' }]
      )
      setFormNote(p.comment ?? '')
      setFormDeductions(
        (p.deductions ?? []).map(d => ({
          label: d.label,
          amount: d.amount ? formatAmountInput(String(d.amount)) : '',
          note: d.note ?? '',
        }))
      )
      const existingGgcc = (p.owner_expenses ?? []).find(e => isGgccExpense(e))
      setFormGgcc(existingGgcc ? formatAmountInput(String(existingGgcc.amount)) : '')
    } else {
      setFormEntries([{ amount: formatAmountInput(contract.current_rent), paid_at: todayLocal(), note: '' }])
      setFormNote('')
    }
```

- [ ] **Step 4: Update openEdit**

Find `function openEdit(payment)`. Replace:
```javascript
  setEditAmount(formatAmountInput(payment.paid_amount ?? payment.expected_amount))
  setEditDate(payment.paid_at ?? todayLocal())
  setEditNote(payment.comment ?? '')
```

With:
```javascript
  setEditEntries(
    payment.payment_entries?.length > 0
      ? payment.payment_entries.map(e => ({
          amount: formatAmountInput(e.amount ?? 0),
          paid_at: e.paid_at ?? todayLocal(),
          note: e.note ?? '',
        }))
      : [{ amount: formatAmountInput(payment.paid_amount ?? payment.expected_amount), paid_at: payment.paid_at ?? todayLocal(), note: '' }]
  )
  setEditNote(payment.comment ?? '')
```

- [ ] **Step 5: Update computed values that depended on formAmount / editAmount**

Find the block that starts:
```javascript
  const addPaidAmt = formAmount !== '' ? parseAmountInput(formAmount) : 0
  const addExpected = addFormExistingPayment?.expected_amount ?? contract.current_rent ?? 0
  const addExistingPaid = addFormExistingPayment ? (addFormExistingPayment.paid_amount ?? 0) : 0
  const addCumulativePaid = addExistingPaid + addPaidAmt
```

Replace with:
```javascript
  const addPaidAmt = formEntries.reduce(
    (sum, e) => sum + (e.amount !== '' ? parseAmountInput(e.amount) : 0), 0
  )
  const addExpected = addFormExistingPayment?.expected_amount ?? contract.current_rent ?? 0
  const addCumulativePaid = addPaidAmt
```

Find:
```javascript
  const editPaidAmt = editAmount !== '' ? parseAmountInput(editAmount) : 0
```

Replace with:
```javascript
  const editPaidAmt = editEntries.reduce(
    (sum, e) => sum + (e.amount !== '' ? parseAmountInput(e.amount) : 0), 0
  )
```

All downstream computations (`addBrokerDiff`, `addRecognized`, `addMissing`, `editRecognized`, `editMissing`, etc.) naturally use these values and need no changes.

- [ ] **Step 6: Update handleAdd**

Find `async function handleAdd(e)`. The section that computes `amount` and `originPaidAfter`:

```javascript
    const amount = parseAmountInput(formAmount)
    const existing = payments.find(p => p.period === period)
    ...
    const alreadyPaid = existing ? (existing.paid_amount ?? 0) : 0
    const originPaidAfter = alreadyPaid + amount
    const overpaymentAmount = Math.max(0, originPaidAfter - expectedAmount)
    if (overpaymentAmount > 0) {
      ...
      setPendingOverpaymentDraft({
        ...
        enteredAmount: amount,
        ...
        originPaidBefore: alreadyPaid,
        originPaidAfter,
        ...
        formDate,
        formNote,
        ...
      })
```

Replace with:
```javascript
    const validEntries = formEntries
      .filter(e => e.amount !== '' && parseAmountInput(e.amount) > 0)
      .map(e => ({ amount: parseAmountInput(e.amount), paid_at: e.paid_at || null, note: e.note || null }))
    const totalEntered = validEntries.reduce((s, e) => s + e.amount, 0)
    const existing = payments.find(p => p.period === period)
    ...
    const expectedAmount = existing ? existing.expected_amount : (contract.current_rent ?? 0)
    const originPaidAfter = totalEntered
    const overpaymentAmount = Math.max(0, originPaidAfter - expectedAmount)
    if (overpaymentAmount > 0) {
      const nextPeriod = addOneMonth(period)
      const nextPayment = payments.find(p => p.period === nextPeriod) ?? null
      setPendingOverpaymentDraft({
        source: 'add',
        period,
        enteredAmount: totalEntered,
        expectedAmount,
        originPaidBefore: 0,
        originPaidAfter,
        overpaymentAmount,
        formEntries: validEntries,
        formNote,
        formDeductions: normalizedDeds,
        formOwnerExpenses: mergeGgccOwnerExpense([], formGgcc),
        paymentId: existing?.id ?? null,
        nextPeriod,
        nextPayment,
      })
      setIsSubmitting(false)
      return
    }
```

Then the no-overpayment submit section:
```javascript
    try {
      if (existing) {
        const res = await fetch(`${API_BASE}/payments/${existing.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            payment_entries: validEntries,
            comment: formNote !== '' ? formNote : null,
            deductions: normalizedDeds,
            owner_expenses: mergeGgccOwnerExpense(existing.owner_expenses, formGgcc),
          }),
        })
        if (!res.ok) throw new Error(`Error ${res.status}`)
      } else {
        const res = await fetch(`${API_BASE}/contracts/${contract.id}/payments`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            period,
            payment_entries: validEntries,
            comment: formNote || null,
            deductions: normalizedDeds,
            owner_expenses: mergeGgccOwnerExpense([], formGgcc),
          }),
        })
        if (res.status === 409) {
          setFormError(`Ya existe un pago para el período ${period}.`)
          return
        }
        if (!res.ok) throw new Error(`Error ${res.status}`)
      }
```

- [ ] **Step 7: Update handleEdit**

Find `async function handleEdit(e)`. Replace the `newTotal`/`originPaidBefore` computation and draft:

```javascript
    const validEntries = editEntries
      .filter(e => e.amount !== '' && parseAmountInput(e.amount) > 0)
      .map(e => ({ amount: parseAmountInput(e.amount), paid_at: e.paid_at || null, note: e.note || null }))
    const newTotal = validEntries.reduce((s, e) => s + e.amount, 0)
    const originPaidBefore = editPayment.paid_amount ?? 0
    const expectedAmount = editPayment.expected_amount
    const overpaymentAmount = Math.max(0, newTotal - expectedAmount)
    if (overpaymentAmount > 0) {
      const period = editPayment.period
      const nextPeriod = addOneMonth(period)
      const nextPayment = payments.find(p => p.period === nextPeriod) ?? null
      setPendingOverpaymentDraft({
        source: 'edit',
        period,
        enteredAmount: newTotal,
        expectedAmount,
        originPaidBefore,
        originPaidAfter: newTotal,
        overpaymentAmount,
        formEntries: validEntries,
        formNote: editNote,
        paymentId: editPayment.id,
        nextPeriod,
        nextPayment,
      })
      setIsSubmitting(false)
      return
    }
    try {
      const body = {}
      if (validEntries.length > 0) body.payment_entries = validEntries
      body.comment = editNote !== '' ? editNote : null
      body.deductions = dedResult.deductions
      body.owner_expenses = mergeGgccOwnerExpense(editPayment.owner_expenses, editGgcc)
```

- [ ] **Step 8: Update saveFromDraft**

Find `async function saveFromDraft(applyAfter)`. Update the destructure + body-building:

```javascript
    const { period, paymentId, originPaidAfter, formEntries: draftEntries, formNote, formDeductions: draftDeductions, formOwnerExpenses: draftOwnerExpenses } = pendingOverpaymentDraft
    ...
      if (paymentId != null) {
        const res = await fetch(`${API_BASE}/payments/${paymentId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            payment_entries: draftEntries,
            comment: formNote !== '' ? formNote : null,
          }),
        })
      } else {
        const res = await fetch(`${API_BASE}/contracts/${contract.id}/payments`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            period,
            payment_entries: draftEntries,
            comment: formNote || null,
            deductions: draftDeductions ?? [],
            owner_expenses: draftOwnerExpenses ?? [],
          }),
        })
```

- [ ] **Step 9: Update saveCurrentPaymentOnly**

Find `async function saveCurrentPaymentOnly()`. Update the destructure + body:

```javascript
    const {
      source,
      period,
      paymentId,
      originPaidAfter,
      formEntries: draftEntries,
      formNote,
      formDeductions: draftDeductions,
      formOwnerExpenses: draftOwnerExpenses,
    } = pendingOverpaymentDraft
    ...
      if (paymentId != null) {
        const res = await fetch(`${API_BASE}/payments/${paymentId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            payment_entries: source === 'edit'
              ? editEntries.filter(e => parseAmountInput(e.amount) > 0).map(e => ({ amount: parseAmountInput(e.amount), paid_at: e.paid_at || null, note: e.note || null }))
              : draftEntries,
            comment: source === 'edit' ? (editNote !== '' ? editNote : null) : (formNote !== '' ? formNote : null),
            deductions,
            owner_expenses,
            carry_forward_waived: true,
          }),
        })
      } else {
        const res = await fetch(`${API_BASE}/contracts/${contract.id}/payments`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            period,
            payment_entries: draftEntries,
            comment: formNote || null,
            deductions,
            owner_expenses,
            carry_forward_waived: true,
          }),
        })
```

- [ ] **Step 10: Update saveAsRentChange**

Find `async function saveAsRentChange()`. This function uses `enteredAmount`/`originPaidAfter`/`formDate`/`formNote`. Update the destructure to use `formNote` from draft (already stored):

```javascript
    const {
      source,
      period,
      enteredAmount,
      originPaidAfter,
      formEntries: draftEntries,
      formNote,
      ...
    } = pendingOverpaymentDraft

    ...
    const body = {
      period,
      new_rent_amount: enteredAmount,
      paid_amount: originPaidAfter,
      comment: formNote !== '' ? formNote : null,
      payment_id: paymentId ?? null,
      deductions,
      owner_expenses,
    }
    // Note: paid_at for rent-change uses latest entry date if available
    const latestDate = draftEntries?.length
      ? draftEntries.filter(e => e.paid_at).map(e => e.paid_at).sort().pop() ?? null
      : null
    if (latestDate) body.paid_at = latestDate
```

---

## Task 9 — Frontend: render entry rows in modal

**Files:** Modify `frontend/src/PaymentsView.jsx`

- [ ] **Step 1: Add a small helper function for rendering entry rows**

Before the `return (` at line ~976, add:

```javascript
  function renderEntryRows(entries, setEntries, disabled) {
    return (
      <div className="payment-entries-section">
        <span className="deductions-section-label">Pagos recibidos</span>
        {entries.map((entry, i) => (
          <div key={i} className="deduction-row">
            <input
              className="payment-form-input deduction-input-amount"
              type="text"
              inputMode="numeric"
              value={entry.amount}
              onChange={e => setEntries(prev => prev.map((r, j) => j === i ? { ...r, amount: formatAmountInput(e.target.value) } : r))}
              placeholder="Monto"
              disabled={disabled}
            />
            <input
              className="payment-form-input"
              type="date"
              value={entry.paid_at}
              onChange={e => setEntries(prev => prev.map((r, j) => j === i ? { ...r, paid_at: e.target.value } : r))}
              disabled={disabled}
            />
            <input
              className="payment-form-input deduction-input-note"
              type="text"
              value={entry.note}
              onChange={e => setEntries(prev => prev.map((r, j) => j === i ? { ...r, note: e.target.value } : r))}
              placeholder="Nota (opcional)"
              disabled={disabled}
            />
            {!disabled && entries.length > 1 && (
              <button
                type="button"
                className="btn-link-secondary"
                onClick={() => setEntries(prev => prev.filter((_, j) => j !== i))}
              >
                ×
              </button>
            )}
          </div>
        ))}
        {!disabled && (
          <button
            type="button"
            className="btn-link-secondary"
            onClick={() => setEntries(prev => [...prev, { amount: '', paid_at: todayLocal(), note: '' }])}
          >
            + Agregar abono
          </button>
        )}
      </div>
    )
  }
```

- [ ] **Step 2: Replace "Arriendo cobrado" inputs in ADD form**

In the add form (inside `{activeForm === 'add' && (`), find:

```jsx
                    <label className="payment-form-label">
                      Arriendo cobrado / total ingresos
                      <input
                        className="payment-form-input"
                        type="text"
                        inputMode="numeric"
                        value={formAmount}
                        onChange={e => setFormAmount(formatAmountInput(e.target.value))}
                        placeholder={`ej. ${formatAmountInput(contract.current_rent)}`}
                        required
                        disabled={!!pendingOverpaymentDraft}
                      />
                    </label>
                    <label className="payment-form-label">
                      Fecha pago
                      <input
                        className="payment-form-input"
                        type="date"
                        value={formDate}
                        onChange={e => setFormDate(e.target.value)}
                        required
                        disabled={!!pendingOverpaymentDraft}
                      />
                    </label>
                    <label className="payment-form-label">
                      Nota
                      <input
                        className="payment-form-input"
                        type="text"
                        value={formNote}
                        onChange={e => setFormNote(e.target.value)}
                        placeholder="opcional"
                        disabled={!!pendingOverpaymentDraft}
                      />
                    </label>
```

Replace with:
```jsx
                    {renderEntryRows(formEntries, setFormEntries, !!pendingOverpaymentDraft)}
                    <label className="payment-form-label">
                      Nota general
                      <input
                        className="payment-form-input"
                        type="text"
                        value={formNote}
                        onChange={e => setFormNote(e.target.value)}
                        placeholder="opcional"
                        disabled={!!pendingOverpaymentDraft}
                      />
                    </label>
```

- [ ] **Step 3: Replace "Arriendo cobrado" inputs in EDIT form**

In the edit form (inside `{activeForm === 'edit' && (`), find the equivalent block:

```jsx
                    <label className="payment-form-label">
                      Arriendo cobrado / total ingresos
                      <input ... value={editAmount} ... />
                    </label>
                    <label className="payment-form-label">
                      Fecha pago
                      <input ... value={editDate} ... />
                    </label>
                    <label className="payment-form-label">
                      Nota
                      <input ... value={editNote} ... />
                    </label>
```

Replace with:
```jsx
                    {renderEntryRows(editEntries, setEditEntries, !!pendingOverpaymentDraft)}
                    <label className="payment-form-label">
                      Nota general
                      <input
                        className="payment-form-input"
                        type="text"
                        value={editNote}
                        onChange={e => setEditNote(e.target.value)}
                        placeholder="opcional"
                        disabled={!!pendingOverpaymentDraft}
                      />
                    </label>
```

- [ ] **Step 4: Update the modal summary "Pagado" to show entry sum**

In the add form summary line, find:
```jsx
{' · '}Pagado: {formatCLP(addPaidAmt)}
```

This already uses `addPaidAmt` which we updated to be the sum of entries. No change needed.

Same for edit form's `editPaidAmt`. No change needed.

---

## Task 10 — Validation: run tests

- [ ] **Step 1: Run backend tests**

```bash
cd ~/Documentos/Proyectos/rental-manager
source venv/bin/activate
python -m pytest tests/ -q 2>&1 | tail -20
```

Expected: All tests pass with no failures.

- [ ] **Step 2: If any test fails, read the error and fix the relevant code**

Do not proceed until all tests pass.

---

## Task 11 — Validation: frontend build

- [ ] **Step 1: Build frontend**

```bash
cd ~/Documentos/Proyectos/rental-manager/frontend
npm run build 2>&1 | tail -30
```

Expected: Build completes without errors. Warnings are acceptable if they were pre-existing.

- [ ] **Step 2: If build fails, fix the error and re-run**

Common issues: references to removed state vars (`formAmount`, `formDate`, `editAmount`, `editDate`). Search the file and ensure all references are replaced.

```bash
grep -n "formAmount\|editAmount\|formDate\|editDate" frontend/src/PaymentsView.jsx
```

Expected: no matches (all removed).

---

## Task 12 — Git: checkout + branch + smoke prep

- [ ] **Step 1: Verify clean state on main**

```bash
cd ~/Documentos/Proyectos/rental-manager
git checkout main
git pull --ff-only origin main
git status -sb
```

Expected: `## main...origin/main` and clean working tree. If dirty, stop and report.

- [ ] **Step 2: Create feature branch**

```bash
git checkout -b feature/payment-entries-in-modal
```

---

## Task 13 — Browser smoke with disposable data

Start the backend and dev server, then test manually:

- [ ] **Step 1: Start backend**

```bash
cd ~/Documentos/Proyectos/rental-manager
source venv/bin/activate
uvicorn main:app --reload &
```

- [ ] **Step 2: Start frontend**

```bash
cd frontend && npm run dev &
```

- [ ] **Step 3: Smoke A — two abonos, partial status**

1. Create a **disposable** property+contract (NOT Serena, Las Condes, Temuco, Estación Central).
2. Open payments for that contract.
3. Click "+ Agregar pago".
4. Select any period with expected > 800000 (or set expected to 900000 via a disposable contract with current_rent=900000).
5. Add entry: 600000, date 2026-05-16, note "Primer abono".
6. Click "+ Agregar abono". Add: 200000, date 2026-05-30.
7. Click "Guardar".
8. **Verify**: table shows one row, Pagado = 800000, fecha = 2026-05-30, Estado = Parcial.
9. Click "Editar". **Verify**: both abonos appear in the modal.

- [ ] **Step 4: Smoke B — edit entries, no duplication**

1. Edit the payment from Smoke A.
2. Change the first abono to 500000 and add a third entry: 100000.
3. Click "Guardar".
4. **Verify**: table shows Pagado = 600000, three entries stored.
5. Reopen and confirm exactly 3 entries (not 5 from duplication).

- [ ] **Step 5: Smoke C — overpayment, Guardar solo este pago**

1. Create a new disposable payment (or use Smoke A's contract with expected = 800000).
2. Add entries summing to 900000 (e.g., 700000 + 200000).
3. Overpayment panel appears — click "Guardar solo este pago".
4. **Verify**: table shows Pagado = 900000, status = Pagado (if 900000 ≥ expected then paid, else check deductions).
5. **Verify**: no "Sobrepago / Abonar al próximo período" after saving.
6. **Verify**: next period not created from carry-forward.

- [ ] **Step 6: Smoke D — Pasar diferencia al siguiente mes**

1. New disposable payment, entries sum 900000, expected 800000.
2. Overpayment panel → "Pasar diferencia al siguiente mes".
3. **Verify**: current period Pagado = 800000 (expected), next period gets 100000 abono.

- [ ] **Step 7: Clean up disposable data**

Delete or reset all disposable contracts/properties created during smoke testing via the UI or:

```bash
# Only if a dedicated test cleanup is available — otherwise use UI delete
```

---

## Task 14 — Commit, push, PR

- [ ] **Step 1: Stage and review changes**

```bash
cd ~/Documentos/Proyectos/rental-manager
git status -sb
git diff --stat
```

- [ ] **Step 2: Commit**

```bash
git add db.py main.py models.py frontend/src/PaymentsView.jsx tests/test_main.py
git commit -m "$(cat <<'EOF'
feat: support multiple payment entries in payment modal

Each payment period can now hold multiple abonos (payment_entries), each
with its own amount, date, and optional note. Period-level paid_amount is
derived as the sum of entries; paid_at is the latest entry date.

Legacy payments with paid_amount > 0 and no entries return one synthesized
entry for backward compatibility. All overpayment, carry-forward, and
rent-change flows continue to use period-level paid_amount unchanged.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Push**

```bash
git push -u origin feature/payment-entries-in-modal
```

- [ ] **Step 4: Open PR (do NOT merge)**

```bash
gh pr create \
  --base main \
  --head feature/payment-entries-in-modal \
  --title "feat: support multiple payment entries in payment modal" \
  --body "$(cat <<'EOF'
## Summary

- Adds `payment_entries` table to store individual abonos per payment period.
- Each abono has its own amount, date, and optional note.
- Period-level `paid_amount` = sum of entries; `paid_at` = latest entry date.
- Legacy payments with no entries return one synthesized entry (backward compatible).
- Keeps one row per period in the payments table.
- Preserves deductions, GG.CC., carry-forward, \"Guardar solo este pago\", and rent-change flows.
- All overpayment/carry-forward logic continues to use period-level `paid_amount`.

## What changed

| Layer | Change |
|-------|--------|
| `db.py` | New `payment_entries` table + 4 helpers; updated `insert_payment`, `update_payment`, `get_payment`, `list_payments_for_contract` |
| `models.py` | `PaymentEntryInput`, `PaymentEntryResponse`; extended `PaymentCreate`, `PaymentUpdate`, `PaymentResponse` |
| `main.py` | `create_payment` and `patch_payment` derive `paid_amount`/`paid_at` from entries |
| `PaymentsView.jsx` | Multi-entry rows replace single amount/date inputs in add + edit modal forms |
| `tests/test_main.py` | 10 new tests for payment_entries feature |

## Validation

- Backend tests: passed
- Frontend build: passed
- Browser smoke with disposable data: passed (Smoke A–D)
- Disposable data cleaned up
- Real property data not touched
EOF
)"
```

- [ ] **Step 5: Confirm PR is NOT merged — stop here**

Print the PR URL and stop. Do not merge.
