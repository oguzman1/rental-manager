import os
import sqlite3
from calendar import monthrange
from datetime import date

from models import ManagedPropertyCreate


DB_NAME = os.getenv("DB_NAME", "rental_manager.db")


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT    NOT NULL UNIQUE,
                full_name   TEXT    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'active',
                created_at  TEXT    NOT NULL DEFAULT (date('now'))
            )
            """
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, email, full_name)
            VALUES (1, 'default@rental-manager.local', 'Default User')
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS properties (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER NOT NULL REFERENCES users(id),
                parent_property_id  INTEGER REFERENCES properties(id),
                display_name        TEXT    NOT NULL,
                rol                 TEXT    NOT NULL UNIQUE,
                comuna              TEXT    NOT NULL,
                address             TEXT    NOT NULL,
                destination         TEXT    NOT NULL,
                status              TEXT    NOT NULL,
                fojas               TEXT,
                property_number     TEXT,
                year                INTEGER,
                fiscal_appraisal    INTEGER,
                notes               TEXT,
                created_at          TEXT    NOT NULL DEFAULT (date('now'))
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                tenant_type  TEXT,
                tax_id       TEXT,
                email        TEXT,
                phone        TEXT,
                notes        TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contracts (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id          INTEGER NOT NULL REFERENCES properties(id),
                start_date           TEXT    NOT NULL,
                end_date             TEXT,
                payment_day          INTEGER NOT NULL,
                notice_days          INTEGER NOT NULL DEFAULT 0,
                adjustment_frequency TEXT    NOT NULL,
                adjustment_month     TEXT,
                is_active            INTEGER NOT NULL DEFAULT 1,
                comment              TEXT,
                contract_file_name   TEXT,
                contract_file_path   TEXT,
                contract_signed_at   TEXT,
                notice_sent_at       TEXT,
                contract_document_url TEXT,
                created_at           TEXT    NOT NULL DEFAULT (date('now'))
            )
            """
        )

        existing_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(contracts)").fetchall()
        }
        if "notice_sent_at" not in existing_cols:
            conn.execute("ALTER TABLE contracts ADD COLUMN notice_sent_at TEXT")
        if "contract_document_url" not in existing_cols:
            conn.execute("ALTER TABLE contracts ADD COLUMN contract_document_url TEXT")
        for col, col_type in [
            ("contract_document_path", "TEXT"),
            ("contract_document_filename", "TEXT"),
            ("contract_document_mime_type", "TEXT"),
            ("contract_document_size_bytes", "INTEGER"),
            ("contract_document_uploaded_at", "TEXT"),
            ("broker_fee_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("usual_broker_fee", "INTEGER"),
            ("owner_pays_ggcc", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE contracts ADD COLUMN {col} {col_type}")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contract_tenants (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL REFERENCES contracts(id),
                tenant_id   INTEGER NOT NULL REFERENCES tenants(id),
                is_primary  INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rent_changes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id    INTEGER NOT NULL REFERENCES contracts(id),
                effective_from TEXT    NOT NULL,
                amount         INTEGER NOT NULL,
                adjustment_pct REAL,
                comment        TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id     INTEGER NOT NULL REFERENCES contracts(id),
                period          TEXT    NOT NULL,
                due_date        TEXT    NOT NULL,
                expected_amount INTEGER NOT NULL,
                paid_amount     INTEGER,
                paid_at         TEXT,
                status          TEXT    NOT NULL DEFAULT 'pending',
                source          TEXT    NOT NULL DEFAULT 'manual',
                comment         TEXT,
                created_at      TEXT    NOT NULL DEFAULT (date('now')),
                UNIQUE(contract_id, period)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS adjustment_notice_events (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id         INTEGER NOT NULL REFERENCES contracts(id),
                due_adjustment_date TEXT    NOT NULL,
                event_type          TEXT    NOT NULL CHECK(event_type IN ('sent', 'reverted', 'dismissed')),
                event_at            TEXT    NOT NULL,
                comment             TEXT,
                created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        notice_events_sql = conn.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name = 'adjustment_notice_events'
            """
        ).fetchone()[0]
        if "'dismissed'" not in notice_events_sql:
            conn.execute("ALTER TABLE adjustment_notice_events RENAME TO adjustment_notice_events_old")
            conn.execute(
                """
                CREATE TABLE adjustment_notice_events (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id         INTEGER NOT NULL REFERENCES contracts(id),
                    due_adjustment_date TEXT    NOT NULL,
                    event_type          TEXT    NOT NULL CHECK(event_type IN ('sent', 'reverted', 'dismissed')),
                    event_at            TEXT    NOT NULL,
                    comment             TEXT,
                    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                INSERT INTO adjustment_notice_events
                    (id, contract_id, due_adjustment_date, event_type, event_at, comment, created_at)
                SELECT id, contract_id, due_adjustment_date, event_type, event_at, comment, created_at
                FROM adjustment_notice_events_old
                """
            )
            conn.execute("DROP TABLE adjustment_notice_events_old")

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_adjustment_notice_events_contract_id
            ON adjustment_notice_events(contract_id)
            """
        )

        payment_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(payments)").fetchall()
        }
        for col, col_type in [
            ("brokerage_fee",   "INTEGER NOT NULL DEFAULT 0"),
            ("repair_discount", "INTEGER NOT NULL DEFAULT 0"),
            ("other_discount",  "INTEGER NOT NULL DEFAULT 0"),
            ("carry_forward_waived", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            if col not in payment_cols:
                conn.execute(f"ALTER TABLE payments ADD COLUMN {col} {col_type}")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_deductions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id INTEGER NOT NULL REFERENCES payments(id),
                label      TEXT    NOT NULL,
                amount     INTEGER NOT NULL CHECK(amount > 0),
                note       TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_payment_deductions_payment_id
            ON payment_deductions(payment_id)
            """
        )

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

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS owner_monthly_expenses (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id INTEGER NOT NULL REFERENCES payments(id),
                label      TEXT    NOT NULL,
                amount     INTEGER NOT NULL CHECK(amount > 0),
                note       TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_owner_monthly_expenses_payment_id
            ON owner_monthly_expenses(payment_id)
            """
        )

        # One-time migration: move non-zero legacy deduction columns into payment_deductions.
        # Guard ensures idempotency — once zeroed, this block never fires again.
        legacy_count = conn.execute(
            """
            SELECT COUNT(*) FROM payments
            WHERE brokerage_fee > 0 OR repair_discount > 0 OR other_discount > 0
            """
        ).fetchone()[0]
        if legacy_count > 0:
            conn.execute(
                """
                INSERT INTO payment_deductions (payment_id, label, amount, sort_order)
                SELECT id, 'Honorarios corredora', brokerage_fee, 0
                FROM payments WHERE brokerage_fee > 0
                """
            )
            conn.execute(
                """
                INSERT INTO payment_deductions (payment_id, label, amount, sort_order)
                SELECT id, 'Descuento reparación', repair_discount, 1
                FROM payments WHERE repair_discount > 0
                """
            )
            conn.execute(
                """
                INSERT INTO payment_deductions (payment_id, label, amount, sort_order)
                SELECT id, 'Otro descuento', other_discount, 2
                FROM payments WHERE other_discount > 0
                """
            )
            conn.execute(
                "UPDATE payments SET brokerage_fee = 0, repair_discount = 0, other_discount = 0"
            )

        conn.commit()


def insert_managed_property(data: ManagedPropertyCreate) -> int:
    display_name = data.rental.property_label if data.rental else data.property.rol

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO properties
                    (user_id, display_name, rol, comuna, address, destination, status,
                     fojas, property_number, year, fiscal_appraisal)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    display_name,
                    data.property.rol,
                    data.property.comuna,
                    data.property.address,
                    data.property.destination,
                    data.property.status.value,
                    data.property.fojas,
                    data.property.property_number,
                    data.property.year,
                    data.property.fiscal_appraisal,
                ),
            )
            property_id = cursor.lastrowid

            if data.rental:
                cursor = conn.execute(
                    "INSERT INTO tenants (display_name) VALUES (?)",
                    (data.rental.tenant_name,),
                )
                tenant_id = cursor.lastrowid

                cursor = conn.execute(
                    """
                    INSERT INTO contracts
                        (property_id, start_date, payment_day, notice_days,
                         adjustment_frequency, adjustment_month, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        property_id,
                        data.rental.start_date.isoformat(),
                        data.rental.payment_day,
                        data.rental.notice_days,
                        data.rental.adjustment_frequency.value,
                        data.rental.adjustment_month,
                    ),
                )
                contract_id = cursor.lastrowid

                conn.execute(
                    """
                    INSERT INTO contract_tenants (contract_id, tenant_id, is_primary)
                    VALUES (?, ?, 1)
                    """,
                    (contract_id, tenant_id),
                )

                conn.execute(
                    """
                    INSERT INTO rent_changes (contract_id, effective_from, amount)
                    VALUES (?, ?, ?)
                    """,
                    (
                        contract_id,
                        data.rental.start_date.isoformat(),
                        data.rental.current_rent,
                    ),
                )

                generate_payment_periods(
                    conn,
                    contract_id=contract_id,
                    start_date=data.rental.start_date,
                    end_date=None,
                    payment_day=data.rental.payment_day,
                    current_rent=data.rental.current_rent,
                )

            conn.commit()
            return property_id

    except sqlite3.IntegrityError:
        raise


def update_managed_property(property_id: int, data: ManagedPropertyCreate) -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE properties
                SET rol = ?, comuna = ?, address = ?, destination = ?, status = ?,
                    fojas = ?, property_number = ?, year = ?, fiscal_appraisal = ?
                WHERE id = ?
                """,
                (
                    data.property.rol,
                    data.property.comuna,
                    data.property.address,
                    data.property.destination,
                    data.property.status.value,
                    data.property.fojas,
                    data.property.property_number,
                    data.property.year,
                    data.property.fiscal_appraisal,
                    property_id,
                ),
            )

            if cursor.rowcount == 0:
                return False

            if data.rental:
                row = conn.execute(
                    "SELECT id FROM contracts WHERE property_id = ? AND is_active = 1",
                    (property_id,),
                ).fetchone()

                if row:
                    contract_id = row[0]

                    conn.execute(
                        """
                        UPDATE contracts
                        SET payment_day = ?, notice_days = ?,
                            adjustment_frequency = ?, adjustment_month = ?
                        WHERE id = ?
                        """,
                        (
                            data.rental.payment_day,
                            data.rental.notice_days,
                            data.rental.adjustment_frequency.value,
                            data.rental.adjustment_month,
                            contract_id,
                        ),
                    )

                    tenant_row = conn.execute(
                        """
                        SELECT tenant_id FROM contract_tenants
                        WHERE contract_id = ? AND is_primary = 1
                        """,
                        (contract_id,),
                    ).fetchone()

                    if tenant_row:
                        conn.execute(
                            "UPDATE tenants SET display_name = ? WHERE id = ?",
                            (data.rental.tenant_name, tenant_row[0]),
                        )

                conn.execute(
                    "UPDATE properties SET display_name = ? WHERE id = ?",
                    (data.rental.property_label, property_id),
                )

            conn.commit()
            return True

    except sqlite3.IntegrityError:
        raise


def delete_managed_property(property_id: int) -> bool:
    with get_connection() as conn:
        contract_rows = conn.execute(
            "SELECT id FROM contracts WHERE property_id = ?", (property_id,)
        ).fetchall()
        contract_ids = [row[0] for row in contract_rows]

        for cid in contract_ids:
            conn.execute(
                "DELETE FROM payment_entries WHERE payment_id IN (SELECT id FROM payments WHERE contract_id = ?)",
                (cid,),
            )
            conn.execute("DELETE FROM payment_deductions WHERE payment_id IN (SELECT id FROM payments WHERE contract_id = ?)", (cid,))
            conn.execute("DELETE FROM owner_monthly_expenses WHERE payment_id IN (SELECT id FROM payments WHERE contract_id = ?)", (cid,))
            conn.execute("DELETE FROM payments WHERE contract_id = ?", (cid,))
            conn.execute("DELETE FROM rent_changes WHERE contract_id = ?", (cid,))
            conn.execute("DELETE FROM contract_tenants WHERE contract_id = ?", (cid,))

        conn.execute("DELETE FROM contracts WHERE property_id = ?", (property_id,))
        cursor = conn.execute("DELETE FROM properties WHERE id = ?", (property_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_managed_property(property_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT
                p.id,
                p.rol,
                p.comuna,
                p.address,
                p.destination,
                p.status,
                p.fojas,
                p.property_number,
                p.year,
                p.fiscal_appraisal,
                p.display_name        AS property_label,
                t.display_name        AS tenant_name,
                c.payment_day,
                c.notice_days,
                c.adjustment_frequency,
                c.adjustment_month,
                c.start_date,
                rc.amount             AS current_rent
            FROM properties p
            LEFT JOIN contracts c
                   ON c.property_id = p.id AND c.is_active = 1
            LEFT JOIN contract_tenants ct
                   ON ct.contract_id = c.id AND ct.is_primary = 1
            LEFT JOIN tenants t
                   ON t.id = ct.tenant_id
            LEFT JOIN rent_changes rc
                   ON rc.contract_id = c.id AND rc.id = {_LATEST_RENT}
            WHERE p.id = ?
            """,
            (property_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "rol": row[1],
        "comuna": row[2],
        "address": row[3],
        "destination": row[4],
        "status": row[5],
        "fojas": row[6],
        "property_number": row[7],
        "year": row[8],
        "fiscal_appraisal": row[9],
        "property_label": row[10],
        "tenant_name": row[11],
        "payment_day": row[12],
        "notice_days": row[13],
        "adjustment_frequency": row[14],
        "adjustment_month": row[15],
        "start_date": row[16],
        "current_rent": row[17],
    }


_LATEST_RENT = """
    (
        SELECT id FROM rent_changes
        WHERE  contract_id = c.id
        ORDER  BY effective_from DESC, id DESC
        LIMIT  1
    )
"""

_LATEST_ADJUSTMENT = """
    (
        SELECT effective_from FROM rent_changes
        WHERE  contract_id = c.id
        AND    effective_from > c.start_date
        ORDER  BY effective_from DESC, id DESC
        LIMIT  1
    )
"""


def _current_rent_sql(today: str) -> str:
    """Rent change in effect as of `today` (falls back to the earliest row
    if the contract hasn't started yet), excluding pre-registered future rows."""
    return f"""
        (
            SELECT COALESCE(
                (
                    SELECT id FROM rent_changes
                    WHERE  contract_id = c.id
                    AND    effective_from <= '{today}'
                    ORDER  BY effective_from DESC, id DESC
                    LIMIT  1
                ),
                (
                    SELECT id FROM rent_changes
                    WHERE  contract_id = c.id
                    ORDER  BY effective_from ASC, id ASC
                    LIMIT  1
                )
            )
        )
    """


def _last_adjustment_sql(today: str) -> str:
    """Most recent rent change after the contract start that has taken
    effect as of `today` — excludes pre-registered future rows."""
    return f"""
        (
            SELECT effective_from FROM rent_changes
            WHERE  contract_id = c.id
            AND    effective_from > c.start_date
            AND    effective_from <= '{today}'
            ORDER  BY effective_from DESC, id DESC
            LIMIT  1
        )
    """


def list_managed_properties() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                p.id,
                p.rol,
                p.comuna,
                p.status,
                p.display_name                                AS property_label,
                t.display_name                                AS tenant_name,
                c.payment_day,
                CASE WHEN c.id IS NOT NULL THEN 1 ELSE 0 END AS has_rental
            FROM properties p
            LEFT JOIN contracts c
                   ON c.property_id = p.id AND c.is_active = 1
            LEFT JOIN contract_tenants ct
                   ON ct.contract_id = c.id AND ct.is_primary = 1
            LEFT JOIN tenants t
                   ON t.id = ct.tenant_id
            ORDER BY p.id DESC
            """
        ).fetchall()

    return [
        {
            "id": row[0],
            "rol": row[1],
            "comuna": row[2],
            "status": row[3],
            "property_label": row[4],
            "tenant_name": row[5],
            "payment_day": row[6],
            "has_rental": bool(row[7]),
        }
        for row in rows
    ]


def list_rentals_for_adjustments(today: date | None = None) -> list[dict]:
    today_iso = (today or date.today()).isoformat()

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                p.id,
                p.rol,
                p.comuna,
                p.display_name          AS property_label,
                t.display_name          AS tenant_name,
                c.payment_day,
                rc.amount               AS current_rent,
                c.adjustment_frequency,
                c.start_date,
                {_last_adjustment_sql(today_iso)}    AS last_adjustment_date,
                c.notice_sent_at,
                c.notice_days,
                c.id                    AS contract_id
            FROM properties p
            JOIN contracts c
                ON c.property_id = p.id AND c.is_active = 1
            JOIN contract_tenants ct
                ON ct.contract_id = c.id AND ct.is_primary = 1
            JOIN tenants t
                ON t.id = ct.tenant_id
            JOIN rent_changes rc
                ON rc.contract_id = c.id AND rc.id = {_current_rent_sql(today_iso)}
            ORDER BY p.id DESC
            """
        ).fetchall()

    return [
        {
            "id": row[0],
            "rol": row[1],
            "comuna": row[2],
            "property_label": row[3],
            "tenant_name": row[4],
            "payment_day": row[5],
            "current_rent": row[6],
            "adjustment_frequency": row[7],
            "start_date": row[8],
            "last_adjustment_date": row[9],
            "notice_sent_at": row[10],
            "notice_days": row[11],
            "contract_id": row[12],
        }
        for row in rows
    ]


def list_rent_changes(contract_id: int) -> list[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM contracts WHERE id = ?", (contract_id,)
        ).fetchone()
        if row is None:
            raise LookupError("Contract not found.")

        rows = conn.execute(
            """
            SELECT id, contract_id, effective_from, amount, adjustment_pct, comment
            FROM rent_changes
            WHERE contract_id = ?
            ORDER BY effective_from DESC, id DESC
            """,
            (contract_id,),
        ).fetchall()

    return [
        {
            "id": r[0],
            "contract_id": r[1],
            "effective_from": r[2],
            "amount": r[3],
            "adjustment_pct": r[4],
            "comment": r[5],
        }
        for r in rows
    ]


def get_rent_change(rent_change_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, contract_id, effective_from, amount, adjustment_pct, comment
            FROM rent_changes WHERE id = ?
            """,
            (rent_change_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "contract_id": row[1],
        "effective_from": row[2],
        "amount": row[3],
        "adjustment_pct": row[4],
        "comment": row[5],
    }


def insert_rent_change(contract_id: int, data) -> int:
    with get_connection() as conn:
        contract_row = conn.execute(
            "SELECT id, start_date, is_active FROM contracts WHERE id = ?",
            (contract_id,),
        ).fetchone()

        if contract_row is None or not contract_row[2]:
            raise LookupError("Active contract not found.")

        start_date_str = contract_row[1]

        if data.effective_from.isoformat() < start_date_str:
            raise ValueError(
                "effective_from must be on or after the contract start_date."
            )

        latest_row = conn.execute(
            """
            SELECT effective_from FROM rent_changes
            WHERE contract_id = ?
            ORDER BY effective_from DESC, id DESC
            LIMIT 1
            """,
            (contract_id,),
        ).fetchone()

        if latest_row and data.effective_from.isoformat() <= latest_row[0]:
            raise ValueError(
                "effective_from must be strictly after the latest rent change date."
            )

        cursor = conn.execute(
            """
            INSERT INTO rent_changes
                (contract_id, effective_from, amount, adjustment_pct, comment)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                contract_id,
                data.effective_from.isoformat(),
                data.amount,
                data.adjustment_pct,
                data.comment,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def delete_rent_change(rent_change_id: int) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, contract_id FROM rent_changes WHERE id = ?",
            (rent_change_id,),
        ).fetchone()

        if row is None:
            raise LookupError("Rent change not found.")

        contract_id = row[1]

        count = conn.execute(
            "SELECT COUNT(*) FROM rent_changes WHERE contract_id = ?",
            (contract_id,),
        ).fetchone()[0]

        if count == 1:
            raise ValueError("Cannot delete the only rent change of a contract.")

        latest_row = conn.execute(
            """
            SELECT id FROM rent_changes
            WHERE contract_id = ?
            ORDER BY effective_from DESC, id DESC
            LIMIT 1
            """,
            (contract_id,),
        ).fetchone()

        if latest_row[0] != rent_change_id:
            raise RuntimeError("Can only delete the most recent rent change.")

        conn.execute("DELETE FROM rent_changes WHERE id = ?", (rent_change_id,))
        conn.commit()


def _iter_months(start_ym: str, end_ym: str):
    """Yield 'YYYY-MM' strings from start_ym to end_ym inclusive."""
    y, m = int(start_ym[:4]), int(start_ym[5:7])
    ey, em = int(end_ym[:4]), int(end_ym[5:7])
    while (y, m) <= (ey, em):
        yield f"{y}-{m:02d}"
        m += 1
        if m > 12:
            m, y = 1, y + 1


def _period_horizon(today: date) -> str:
    """Return the inclusive upper-bound month for period generation.

    Always current month + 12 months: 2026-06 → 2027-06.
    """
    m_offset = today.month - 1 + 12
    hy = today.year + m_offset // 12
    hm = m_offset % 12 + 1
    return f"{hy}-{hm:02d}"


def _first_missing_period(start_ym: str, cap_ym: str, existing: set) -> str | None:
    """Return the earliest month in [start_ym, cap_ym] not present in existing, or None."""
    for ym in _iter_months(start_ym, cap_ym):
        if ym not in existing:
            return ym
    return None


def list_dashboard_items() -> list[dict]:
    today = date.today()
    today_ym = today.strftime("%Y-%m")
    today_iso = today.isoformat()

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT
                p.id,
                p.rol,
                p.comuna,
                p.status,
                p.display_name          AS property_label,
                t.display_name          AS tenant_name,
                c.payment_day,
                rc.amount               AS current_rent,
                c.adjustment_frequency,
                c.start_date,
                c.end_date,
                {_last_adjustment_sql(today_iso)}    AS last_adjustment_date,
                cp.status               AS current_payment_status,
                cp.expected_amount      AS current_payment_amount,
                cp.paid_amount          AS current_payment_paid_amount,
                ps.total_exigibles,
                ps.saldo_pendiente,
                pp.period_amount,
                pp.latest_period,
                ap.actionable_payment_period,
                ap.actionable_payment_status,
                ap.actionable_payment_amount,
                ap.actionable_payment_paid_amount,
                ap.actionable_payment_recognized_amount,
                c.notice_sent_at,
                c.notice_days,
                c.id                    AS contract_id
            FROM properties p
            LEFT JOIN contracts c
                   ON c.property_id = p.id AND c.is_active = 1
            LEFT JOIN contract_tenants ct
                   ON ct.contract_id = c.id AND ct.is_primary = 1
            LEFT JOIN tenants t
                   ON t.id = ct.tenant_id
            LEFT JOIN rent_changes rc
                   ON rc.contract_id = c.id AND rc.id = {_current_rent_sql(today_iso)}
            LEFT JOIN (
                SELECT
                    contract_id,
                    CASE
                        WHEN COALESCE(paid_amount, 0) + COALESCE(
                                 (SELECT SUM(d.amount) FROM payment_deductions d WHERE d.payment_id = payments.id), 0
                             ) >= expected_amount THEN 'paid'
                        WHEN COALESCE(paid_amount, 0) + COALESCE(
                                 (SELECT SUM(d.amount) FROM payment_deductions d WHERE d.payment_id = payments.id), 0
                             ) > 0               THEN 'partial'
                        ELSE                         'pending'
                    END AS status,
                    expected_amount,
                    paid_amount
                FROM payments
                WHERE period = strftime('%Y-%m', 'now')
            ) cp ON c.id = cp.contract_id
            LEFT JOIN (
                SELECT
                    contract_id,
                    COUNT(*)                                      AS total_exigibles,
                    SUM(expected_amount - (
                        COALESCE(paid_amount, 0) + COALESCE(
                            (SELECT SUM(d.amount) FROM payment_deductions d WHERE d.payment_id = payments.id), 0
                        )
                    )) AS saldo_pendiente
                FROM payments
                WHERE period <= strftime('%Y-%m', 'now')
                GROUP BY contract_id
            ) ps ON c.id = ps.contract_id
            LEFT JOIN (
                SELECT p1.contract_id,
                       p1.expected_amount AS period_amount,
                       p1.period          AS latest_period
                FROM   payments p1
                INNER JOIN (
                    SELECT contract_id, MAX(period) AS max_period
                    FROM   payments
                    WHERE  period <= strftime('%Y-%m', 'now')
                    GROUP BY contract_id
                ) p2 ON p1.contract_id = p2.contract_id
                     AND p1.period      = p2.max_period
            ) pp ON c.id = pp.contract_id
            LEFT JOIN (
                SELECT
                    p1.contract_id,
                    p1.period          AS actionable_payment_period,
                    CASE
                        WHEN COALESCE(p1.paid_amount, 0) + COALESCE(
                                 (SELECT SUM(d.amount) FROM payment_deductions d WHERE d.payment_id = p1.id), 0
                             ) = 0 THEN 'pending'
                        ELSE 'partial'
                    END                AS actionable_payment_status,
                    p1.expected_amount AS actionable_payment_amount,
                    p1.paid_amount     AS actionable_payment_paid_amount,
                    COALESCE(p1.paid_amount, 0) + COALESCE(
                        (SELECT SUM(d.amount) FROM payment_deductions d WHERE d.payment_id = p1.id), 0
                    )                  AS actionable_payment_recognized_amount
                FROM payments p1
                INNER JOIN (
                    SELECT contract_id, MIN(period) AS min_period
                    FROM   payments
                    WHERE  period <= strftime('%Y-%m', 'now')
                      AND  COALESCE(paid_amount, 0) + COALESCE(
                               (SELECT SUM(d.amount) FROM payment_deductions d WHERE d.payment_id = payments.id), 0
                           ) < expected_amount
                    GROUP BY contract_id
                ) p3 ON p1.contract_id = p3.contract_id
                     AND p1.period      = p3.min_period
            ) ap ON c.id = ap.contract_id
            WHERE p.parent_property_id IS NULL
            ORDER BY p.id DESC
            """
        ).fetchall()

        # Batch query: all existing periods per active contract up to current month.
        # Runs inside the same connection to avoid a second open/close cycle.
        contract_ids = [row["contract_id"] for row in rows if row["contract_id"] is not None]
        existing_periods_by_contract: dict[int, set[str]] = {}
        if contract_ids:
            placeholders = ",".join("?" * len(contract_ids))
            period_rows = conn.execute(
                f"SELECT contract_id, period FROM payments "
                f"WHERE contract_id IN ({placeholders}) AND period <= ?",
                (*contract_ids, today_ym),
            ).fetchall()
            for pr in period_rows:
                existing_periods_by_contract.setdefault(pr[0], set()).add(pr[1])

    result = []
    for row in rows:
        total_exigibles = row["total_exigibles"]
        saldo_pendiente  = row["saldo_pendiente"]

        if total_exigibles is None:
            payment_status = "missing_period"
        elif saldo_pendiente <= 0:
            payment_status = "paid_up"
        else:
            payment_status = "outstanding_balance"

        actionable_period     = row["actionable_payment_period"]
        actionable_status     = row["actionable_payment_status"]
        actionable_amount     = row["actionable_payment_amount"]
        actionable_paid       = row["actionable_payment_paid_amount"]
        actionable_recognized = row["actionable_payment_recognized_amount"]

        contract_id     = row["contract_id"]
        start_date_str  = row["start_date"]
        end_date_str    = row["end_date"]
        current_rent    = row["current_rent"]

        if contract_id is not None and start_date_str is not None:
            start_ym = start_date_str[:7]
            cap_ym   = min(today_ym, end_date_str[:7]) if end_date_str else today_ym

            if start_ym <= cap_ym:
                existing = existing_periods_by_contract.get(contract_id, set())
                virtual_period = _first_missing_period(start_ym, cap_ym, existing)

                if virtual_period is not None and (
                    actionable_period is None or virtual_period < actionable_period
                ):
                    actionable_period     = virtual_period
                    actionable_status     = "pending"
                    actionable_amount     = current_rent
                    actionable_paid       = None
                    actionable_recognized = None

        result.append({
            "id":                     row["id"],
            "rol":                    row["rol"],
            "comuna":                 row["comuna"],
            "status":                 row["status"],
            "property_label":         row["property_label"],
            "tenant_name":            row["tenant_name"],
            "payment_day":            row["payment_day"],
            "current_rent":           current_rent,
            "adjustment_frequency":   row["adjustment_frequency"],
            "start_date":             start_date_str,
            "last_adjustment_date":   row["last_adjustment_date"],
            "current_payment_status": row["current_payment_status"],
            "current_payment_period": today_ym,
            "current_payment_amount": row["current_payment_amount"],
            "current_payment_paid_amount": row["current_payment_paid_amount"],
            "payment_status":         payment_status,
            "period_amount":              row["period_amount"],
            "latest_period":              row["latest_period"],
            "actionable_payment_period":       actionable_period,
            "actionable_payment_status":       actionable_status,
            "actionable_payment_amount":       actionable_amount,
            "actionable_payment_paid_amount":        actionable_paid,
            "actionable_payment_recognized_amount":  actionable_recognized,
            "notice_sent_at":             row["notice_sent_at"],
            "notice_days":                row["notice_days"],
            "contract_id":                contract_id,
        })
    return result


def list_contracts() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                c.id,
                c.property_id,
                p.display_name  AS property_label,
                p.rol,
                t.display_name  AS tenant_name,
                c.start_date,
                rc.amount       AS current_rent,
                c.payment_day,
                c.adjustment_frequency,
                c.notice_days,
                c.adjustment_month,
                c.comment,
                c.contract_document_url,
                c.contract_document_path,
                c.contract_document_filename,
                c.contract_document_mime_type,
                c.contract_document_size_bytes,
                c.contract_document_uploaded_at,
                c.broker_fee_enabled,
                c.usual_broker_fee,
                c.owner_pays_ggcc
            FROM contracts c
            JOIN properties p
                ON p.id = c.property_id
            JOIN contract_tenants ct
                ON ct.contract_id = c.id AND ct.is_primary = 1
            JOIN tenants t
                ON t.id = ct.tenant_id
            JOIN rent_changes rc
                ON rc.contract_id = c.id AND rc.id = {_LATEST_RENT}
            WHERE c.is_active = 1
            ORDER BY c.id DESC
            """
        ).fetchall()

    return [
        {
            "id": row[0],
            "property_id": row[1],
            "property_label": row[2],
            "rol": row[3],
            "tenant_name": row[4],
            "start_date": row[5],
            "current_rent": row[6],
            "payment_day": row[7],
            "adjustment_frequency": row[8],
            "notice_days": row[9],
            "adjustment_month": row[10],
            "comment": row[11],
            "contract_document_url": row[12],
            "contract_document_path": row[13],
            "contract_document_filename": row[14],
            "contract_document_mime_type": row[15],
            "contract_document_size_bytes": row[16],
            "contract_document_uploaded_at": row[17],
            "broker_fee_enabled": bool(row[18]),
            "usual_broker_fee": row[19],
            "owner_pays_ggcc": bool(row[20]),
        }
        for row in rows
    ]


def get_contract(contract_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT
                c.id,
                c.property_id,
                p.display_name  AS property_label,
                p.rol,
                t.display_name  AS tenant_name,
                c.start_date,
                c.end_date,
                rc.amount       AS current_rent,
                c.payment_day,
                c.adjustment_frequency,
                c.notice_days,
                c.adjustment_month,
                c.comment,
                c.is_active,
                c.contract_document_url,
                c.contract_document_path,
                c.contract_document_filename,
                c.contract_document_mime_type,
                c.contract_document_size_bytes,
                c.contract_document_uploaded_at,
                c.broker_fee_enabled,
                c.usual_broker_fee,
                c.owner_pays_ggcc
            FROM contracts c
            JOIN properties p ON p.id = c.property_id
            JOIN contract_tenants ct ON ct.contract_id = c.id AND ct.is_primary = 1
            JOIN tenants t ON t.id = ct.tenant_id
            JOIN rent_changes rc ON rc.contract_id = c.id AND rc.id = {_LATEST_RENT}
            WHERE c.id = ?
            """,
            (contract_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "property_id": row[1],
        "property_label": row[2],
        "rol": row[3],
        "tenant_name": row[4],
        "start_date": row[5],
        "end_date": row[6],
        "current_rent": row[7],
        "payment_day": row[8],
        "adjustment_frequency": row[9],
        "notice_days": row[10],
        "adjustment_month": row[11],
        "comment": row[12],
        "is_active": bool(row[13]),
        "contract_document_url": row[14],
        "contract_document_path": row[15],
        "contract_document_filename": row[16],
        "contract_document_mime_type": row[17],
        "contract_document_size_bytes": row[18],
        "contract_document_uploaded_at": row[19],
        "broker_fee_enabled": bool(row[20]),
        "usual_broker_fee": row[21],
        "owner_pays_ggcc": bool(row[22]),
    }


def create_contract(data) -> int:
    with get_connection() as conn:
        prop = conn.execute(
            "SELECT id FROM properties WHERE id = ?", (data.property_id,)
        ).fetchone()
        if prop is None:
            raise LookupError("Property not found.")

        tenant = conn.execute(
            "SELECT id FROM tenants WHERE id = ?", (data.tenant_id,)
        ).fetchone()
        if tenant is None:
            raise LookupError("Tenant not found.")

        existing = conn.execute(
            "SELECT id FROM contracts WHERE property_id = ? AND is_active = 1",
            (data.property_id,),
        ).fetchone()
        if existing:
            raise ValueError("Property already has an active contract.")

        cursor = conn.execute(
            """
            INSERT INTO contracts
                (property_id, start_date, payment_day, notice_days,
                 adjustment_frequency, adjustment_month, comment, contract_document_url, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                data.property_id,
                data.start_date.isoformat(),
                data.payment_day,
                data.notice_days,
                data.adjustment_frequency.value,
                data.adjustment_month,
                data.comment,
                data.contract_document_url,
            ),
        )
        contract_id = cursor.lastrowid

        conn.execute(
            "INSERT INTO contract_tenants (contract_id, tenant_id, is_primary) VALUES (?, ?, 1)",
            (contract_id, data.tenant_id),
        )
        conn.execute(
            "INSERT INTO rent_changes (contract_id, effective_from, amount) VALUES (?, ?, ?)",
            (contract_id, data.start_date.isoformat(), data.current_rent),
        )
        conn.execute(
            "UPDATE properties SET status = 'occupied' WHERE id = ?",
            (data.property_id,),
        )
        generate_payment_periods(
            conn,
            contract_id=contract_id,
            start_date=data.start_date,
            end_date=None,
            payment_day=data.payment_day,
            current_rent=data.current_rent,
        )
        conn.commit()
        return contract_id


def update_contract(contract_id: int, data) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM contracts WHERE id = ? AND is_active = 1",
            (contract_id,),
        ).fetchone()
        if row is None:
            return False

        updates: dict = {}
        if data.payment_day is not None:
            updates["payment_day"] = data.payment_day
        if data.notice_days is not None:
            updates["notice_days"] = data.notice_days
        if data.adjustment_frequency is not None:
            updates["adjustment_frequency"] = data.adjustment_frequency.value
        if "adjustment_month" in data.model_fields_set:
            updates["adjustment_month"] = data.adjustment_month
        if "comment" in data.model_fields_set:
            updates["comment"] = data.comment
        if "contract_document_url" in data.model_fields_set:
            updates["contract_document_url"] = data.contract_document_url
        if "broker_fee_enabled" in data.model_fields_set and data.broker_fee_enabled is not None:
            updates["broker_fee_enabled"] = int(data.broker_fee_enabled)
        if "usual_broker_fee" in data.model_fields_set:
            updates["usual_broker_fee"] = data.usual_broker_fee
        if "owner_pays_ggcc" in data.model_fields_set and data.owner_pays_ggcc is not None:
            updates["owner_pays_ggcc"] = int(data.owner_pays_ggcc)

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE contracts SET {set_clause} WHERE id = ?",
                [*updates.values(), contract_id],
            )

        if data.current_rent is not None:
            conn.execute(
                "INSERT INTO rent_changes (contract_id, effective_from, amount) VALUES (?, ?, ?)",
                (contract_id, date.today().isoformat(), data.current_rent),
            )

        conn.commit()
        return True


def update_contract_document(
    contract_id: int,
    path: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
    uploaded_at: str,
) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM contracts WHERE id = ? AND is_active = 1",
            (contract_id,),
        ).fetchone()
        if row is None:
            return False
        conn.execute(
            """
            UPDATE contracts SET
                contract_document_path = ?,
                contract_document_filename = ?,
                contract_document_mime_type = ?,
                contract_document_size_bytes = ?,
                contract_document_uploaded_at = ?
            WHERE id = ?
            """,
            (path, filename, mime_type, size_bytes, uploaded_at, contract_id),
        )
        conn.commit()
        return True


def close_contract(contract_id: int, end_date: str) -> None:
    end_ym = end_date[:7]  # YYYY-MM
    with get_connection() as conn:
        conn.execute(
            "UPDATE contracts SET is_active = 0, end_date = ? WHERE id = ?",
            (end_date, contract_id),
        )
        # Remove auto-generated pending periods that fall after the contract end month.
        # Paid and partial periods are never deleted.
        conn.execute(
            """
            DELETE FROM payments
            WHERE contract_id = ? AND period > ? AND status = 'pending'
            """,
            (contract_id, end_ym),
        )
        row = conn.execute(
            "SELECT property_id FROM contracts WHERE id = ?", (contract_id,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE properties SET status = 'vacant' WHERE id = ?",
                (row[0],),
            )
        conn.commit()


def mark_notice_sent(
    contract_id: int,
    noticed_at: date,
    comment: str | None,
    due_adjustment_date: date,
) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE contracts SET notice_sent_at = ? WHERE id = ? AND is_active = 1",
            (noticed_at.isoformat(), contract_id),
        )
        if cursor.rowcount == 0:
            conn.commit()
            return False
        conn.execute(
            """
            INSERT INTO adjustment_notice_events
                (contract_id, due_adjustment_date, event_type, event_at, comment)
            VALUES (?, ?, 'sent', ?, ?)
            """,
            (contract_id, due_adjustment_date.isoformat(), noticed_at.isoformat(), comment),
        )
        conn.commit()
    return True


def dismiss_adjustment_alert(
    contract_id: int,
    dismissed_at: date,
    comment: str | None,
    due_adjustment_date: date,
) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM contracts WHERE id = ? AND is_active = 1",
            (contract_id,),
        ).fetchone()
        if row is None:
            return False
        conn.execute(
            """
            INSERT INTO adjustment_notice_events
                (contract_id, due_adjustment_date, event_type, event_at, comment)
            VALUES (?, ?, 'dismissed', ?, ?)
            """,
            (contract_id, due_adjustment_date.isoformat(), dismissed_at.isoformat(), comment),
        )
        conn.commit()
    return True


def is_adjustment_alert_dismissed(contract_id: int, due_adjustment_date: date) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT event_type FROM adjustment_notice_events
            WHERE contract_id = ? AND due_adjustment_date = ?
            ORDER BY id DESC LIMIT 1
            """,
            (contract_id, due_adjustment_date.isoformat()),
        ).fetchone()

    return row is not None and row[0] == "dismissed"


def revert_notice_sent(
    contract_id: int,
    reverted_at: date,
    comment: str | None,
    fallback_due_date: date,
) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT notice_sent_at FROM contracts WHERE id = ? AND is_active = 1",
            (contract_id,),
        ).fetchone()
        if row is None:
            raise LookupError("Active contract not found.")
        if row[0] is None:
            raise ValueError("No active notice to revert.")

        event_row = conn.execute(
            """
            SELECT due_adjustment_date FROM adjustment_notice_events
            WHERE contract_id = ? AND event_type = 'sent'
            ORDER BY id DESC LIMIT 1
            """,
            (contract_id,),
        ).fetchone()
        due_date = event_row[0] if event_row else fallback_due_date.isoformat()

        conn.execute(
            "UPDATE contracts SET notice_sent_at = NULL WHERE id = ? AND is_active = 1",
            (contract_id,),
        )
        conn.execute(
            """
            INSERT INTO adjustment_notice_events
                (contract_id, due_adjustment_date, event_type, event_at, comment)
            VALUES (?, ?, 'reverted', ?, ?)
            """,
            (contract_id, due_date, reverted_at.isoformat(), comment),
        )
        conn.commit()


def list_notice_events(contract_id: int) -> list[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM contracts WHERE id = ?", (contract_id,)
        ).fetchone()
        if row is None:
            raise LookupError("Contract not found.")

        rows = conn.execute(
            """
            SELECT id, contract_id, due_adjustment_date, event_type, event_at, comment, created_at
            FROM adjustment_notice_events
            WHERE contract_id = ?
            ORDER BY id DESC
            """,
            (contract_id,),
        ).fetchall()

    return [
        {
            "id": r[0],
            "contract_id": r[1],
            "due_adjustment_date": r[2],
            "event_type": r[3],
            "event_at": r[4],
            "comment": r[5],
            "created_at": r[6],
        }
        for r in rows
    ]


def list_tenants() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                t.id,
                t.display_name,
                p.id            AS property_id,
                p.rol,
                p.display_name  AS property_label,
                c.payment_day,
                c.start_date,
                rc.amount       AS current_rent,
                {_LATEST_ADJUSTMENT} AS last_adjustment_date
            FROM tenants t
            LEFT JOIN contract_tenants ct
                ON ct.tenant_id = t.id AND ct.is_primary = 1
            LEFT JOIN contracts c
                ON c.id = ct.contract_id AND c.is_active = 1
            LEFT JOIN properties p
                ON p.id = c.property_id
            LEFT JOIN rent_changes rc
                ON rc.contract_id = c.id AND rc.id = {_LATEST_RENT}
            WHERE c.id IS NOT NULL OR ct.contract_id IS NULL
            ORDER BY t.id DESC
            """
        ).fetchall()

    return [
        {
            "id": row[0],
            "display_name": row[1],
            "property_id": row[2],
            "rol": row[3],
            "property_label": row[4],
            "payment_day": row[5],
            "start_date": row[6],
            "current_rent": row[7],
            "last_adjustment_date": row[8],
        }
        for row in rows
    ]


def get_tenant(tenant_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, display_name, tenant_type, tax_id, email, phone, notes
            FROM tenants WHERE id = ?
            """,
            (tenant_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "display_name": row[1],
        "tenant_type": row[2],
        "tax_id": row[3],
        "email": row[4],
        "phone": row[5],
        "notes": row[6],
    }


def insert_tenant(data) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tenants (display_name, tenant_type, tax_id, email, phone, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (data.display_name, data.tenant_type, data.tax_id,
             data.email, data.phone, data.notes),
        )
        conn.commit()
        return cursor.lastrowid


def update_tenant(tenant_id: int, data) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE tenants
            SET display_name = ?, tenant_type = ?, tax_id = ?, email = ?, phone = ?, notes = ?
            WHERE id = ?
            """,
            (data.display_name, data.tenant_type, data.tax_id,
             data.email, data.phone, data.notes, tenant_id),
        )
        conn.commit()
    return cursor.rowcount > 0


def tenant_has_any_contract(tenant_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM contract_tenants WHERE tenant_id = ? LIMIT 1",
            (tenant_id,),
        ).fetchone()
    return row is not None


def delete_tenant(tenant_id: int) -> bool:
    with get_connection() as conn:
        conn.execute("DELETE FROM contract_tenants WHERE tenant_id = ?", (tenant_id,))
        cursor = conn.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
        conn.commit()
    return cursor.rowcount > 0


def get_contract_for_payment(contract_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT c.id, c.payment_day, rc.amount AS current_rent
            FROM contracts c
            JOIN rent_changes rc
                ON rc.contract_id = c.id AND rc.id = {_LATEST_RENT}
            WHERE c.id = ? AND c.is_active = 1
            """,
            (contract_id,),
        ).fetchone()

    if row is None:
        return None

    return {"id": row[0], "payment_day": row[1], "current_rent": row[2]}


def _load_deductions(conn, payment_id: int) -> list[dict]:
    """Return deduction rows for a single payment, ordered by sort_order."""
    rows = conn.execute(
        """
        SELECT id, label, amount, note, sort_order
        FROM payment_deductions
        WHERE payment_id = ?
        ORDER BY sort_order
        """,
        (payment_id,),
    ).fetchall()
    return [{"id": r[0], "label": r[1], "amount": r[2], "note": r[3], "sort_order": r[4]} for r in rows]


def _load_deductions_batch(conn, payment_ids: list[int]) -> dict[int, list[dict]]:
    """Return a dict mapping payment_id → deduction rows for all given payment IDs."""
    if not payment_ids:
        return {}
    placeholders = ",".join("?" * len(payment_ids))
    rows = conn.execute(
        f"""
        SELECT id, payment_id, label, amount, note, sort_order
        FROM payment_deductions
        WHERE payment_id IN ({placeholders})
        ORDER BY payment_id, sort_order
        """,
        payment_ids,
    ).fetchall()
    result: dict[int, list[dict]] = {}
    for r in rows:
        result.setdefault(r[1], []).append(
            {"id": r[0], "label": r[2], "amount": r[3], "note": r[4], "sort_order": r[5]}
        )
    return result


def _insert_deductions(conn, payment_id: int, deductions: list[dict]) -> None:
    """Insert deduction rows for a payment. Caller owns the transaction."""
    for i, d in enumerate(deductions):
        conn.execute(
            """
            INSERT INTO payment_deductions (payment_id, label, amount, note, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payment_id, d["label"], d["amount"], d.get("note") or None, i),
        )


def _replace_deductions(conn, payment_id: int, deductions: list[dict]) -> None:
    """Delete and re-insert all deduction rows for a payment. Caller owns the transaction."""
    conn.execute("DELETE FROM payment_deductions WHERE payment_id = ?", (payment_id,))
    _insert_deductions(conn, payment_id, deductions)


def _load_owner_expenses(conn, payment_id: int) -> list[dict]:
    """Return owner_monthly_expenses rows for a single payment, ordered by sort_order."""
    rows = conn.execute(
        """
        SELECT id, label, amount, note, sort_order
        FROM owner_monthly_expenses
        WHERE payment_id = ?
        ORDER BY sort_order
        """,
        (payment_id,),
    ).fetchall()
    return [{"id": r[0], "label": r[1], "amount": r[2], "note": r[3], "sort_order": r[4]} for r in rows]


def _load_owner_expenses_batch(conn, payment_ids: list[int]) -> dict[int, list[dict]]:
    """Return a dict mapping payment_id → owner_monthly_expenses rows for all given payment IDs."""
    if not payment_ids:
        return {}
    placeholders = ",".join("?" * len(payment_ids))
    rows = conn.execute(
        f"""
        SELECT id, payment_id, label, amount, note, sort_order
        FROM owner_monthly_expenses
        WHERE payment_id IN ({placeholders})
        ORDER BY payment_id, sort_order
        """,
        payment_ids,
    ).fetchall()
    result: dict[int, list[dict]] = {}
    for r in rows:
        result.setdefault(r[1], []).append(
            {"id": r[0], "label": r[2], "amount": r[3], "note": r[4], "sort_order": r[5]}
        )
    return result


def _insert_owner_expenses(conn, payment_id: int, owner_expenses: list[dict]) -> None:
    """Insert owner_monthly_expenses rows for a payment. Caller owns the transaction."""
    for i, e in enumerate(owner_expenses):
        conn.execute(
            """
            INSERT INTO owner_monthly_expenses (payment_id, label, amount, note, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payment_id, e["label"], e["amount"], e.get("note") or None, i),
        )


def _replace_owner_expenses(conn, payment_id: int, owner_expenses: list[dict]) -> None:
    """Delete and re-insert all owner_monthly_expenses rows for a payment. Caller owns the transaction."""
    conn.execute("DELETE FROM owner_monthly_expenses WHERE payment_id = ?", (payment_id,))
    _insert_owner_expenses(conn, payment_id, owner_expenses)


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
    # recognized_amount = paid_amount + Σ deductions (rent-recognizing credits)
    recognized = (paid or 0) + total_deductions
    overpayment = max(0, paid - expected) if paid is not None else 0
    # net_owner_amount = paid_amount − Σ owner_expenses (NOT deductions)
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


def generate_payment_periods(
    conn,
    contract_id: int,
    start_date: date,
    end_date: date | None,
    payment_day: int,
    current_rent: int,
) -> None:
    """Insert pending payment rows for each monthly period of the contract.

    Called inside an already-open connection/transaction. Uses INSERT OR IGNORE
    so re-running is safe if rows already exist.
    """
    year, month = start_date.year, start_date.month
    end_year = end_date.year if end_date else None
    end_month = end_date.month if end_date else None
    generated = 0

    while True:
        if end_date is None and generated >= 12:
            break
        if end_date is not None and (
            year > end_year or (year == end_year and month > end_month)
        ):
            break

        period = f"{year}-{month:02d}"
        last_day = monthrange(year, month)[1]
        day = min(payment_day, last_day)
        due_date_str = f"{year}-{month:02d}-{day:02d}"

        conn.execute(
            """
            INSERT OR IGNORE INTO payments
                (contract_id, period, due_date, expected_amount, status, source)
            VALUES (?, ?, ?, ?, 'pending', 'manual')
            """,
            (contract_id, period, due_date_str, current_rent),
        )

        generated += 1
        month += 1
        if month > 12:
            month = 1
            year += 1


def bootstrap_payment_periods_for_active_contracts(
    today: date | None = None,
) -> dict:
    """Create missing payment periods for all active contracts.

    Historical months (contract start through last month): inserted as paid/manual
    with paid_amount = expected_amount and comment 'Carga histórica inicial'.

    Current and future months (this month through 12 months ahead): inserted as
    pending/manual with no paid_amount.

    Existing rows are never modified. Safe to run multiple times (idempotent).
    Inactive contracts are skipped.

    Returns a summary dict with counts of contracts processed and periods inserted.
    """
    ref = today or date.today()
    today_ym = ref.strftime("%Y-%m")

    prev_y, prev_m = ref.year, ref.month - 1
    if prev_m == 0:
        prev_m, prev_y = 12, prev_y - 1
    prev_ym = f"{prev_y}-{prev_m:02d}"

    future_m_offset = ref.month - 1 + 12
    future_y = ref.year + future_m_offset // 12
    future_m = future_m_offset % 12 + 1
    future_ym = f"{future_y}-{future_m:02d}"

    historical_inserted = 0
    operational_inserted = 0
    contracts_processed = 0

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.start_date,
                c.payment_day,
                (
                    SELECT amount FROM rent_changes
                    WHERE contract_id = c.id
                    ORDER BY effective_from DESC, id DESC
                    LIMIT 1
                ) AS current_rent
            FROM contracts c
            WHERE c.is_active = 1
            """
        ).fetchall()

        for contract_id, start_date_str, payment_day, current_rent in rows:
            contracts_processed += 1
            start_ym = start_date_str[:7]

            existing = {
                r[0]
                for r in conn.execute(
                    "SELECT period FROM payments WHERE contract_id = ?",
                    (contract_id,),
                ).fetchall()
            }

            if start_ym <= prev_ym:
                for period in _iter_months(start_ym, prev_ym):
                    if period in existing:
                        continue
                    y, m = int(period[:4]), int(period[5:7])
                    last_day = monthrange(y, m)[1]
                    due_date_str = f"{y}-{m:02d}-{min(payment_day, last_day):02d}"
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO payments
                            (contract_id, period, due_date, expected_amount,
                             paid_amount, paid_at, status, source, comment)
                        VALUES (?, ?, ?, ?, ?, ?, 'paid', 'manual', 'Carga histórica inicial')
                        """,
                        (contract_id, period, due_date_str, current_rent,
                         current_rent, due_date_str),
                    )
                    historical_inserted += 1

            op_start_ym = today_ym if start_ym <= today_ym else start_ym
            for period in _iter_months(op_start_ym, future_ym):
                if period in existing:
                    continue
                y, m = int(period[:4]), int(period[5:7])
                last_day = monthrange(y, m)[1]
                due_date_str = f"{y}-{m:02d}-{min(payment_day, last_day):02d}"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO payments
                        (contract_id, period, due_date, expected_amount,
                         status, source)
                    VALUES (?, ?, ?, ?, 'pending', 'manual')
                    """,
                    (contract_id, period, due_date_str, current_rent),
                )
                operational_inserted += 1

        conn.commit()

    return {
        "contracts_processed": contracts_processed,
        "historical_inserted": historical_inserted,
        "operational_inserted": operational_inserted,
        "periods_inserted": historical_inserted + operational_inserted,
    }


def apply_overpayment_to_next_period(payment_id: int) -> tuple[dict, dict]:
    """Move the excess amount from an overpaid period into the next monthly period.

    Returns (updated_current, updated_next) dicts.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM payments WHERE id = ?", (payment_id,)
        ).fetchone()
        if row is None:
            raise LookupError("Payment not found.")

        current = _payment_row_to_dict(row, _load_deductions(conn, row[0]), _load_owner_expenses(conn, row[0]), [])
        if current["overpayment"] <= 0:
            raise ValueError("No overpayment to apply.")

        excess = current["overpayment"]
        contract_id = current["contract_id"]

        # Reduce current period to exactly expected_amount
        conn.execute(
            "UPDATE payments SET paid_amount = ?, status = 'paid' WHERE id = ?",
            (current["expected_amount"], payment_id),
        )
        conn.execute("DELETE FROM payment_entries WHERE payment_id = ?", (payment_id,))

        # Compute next period string
        year = int(current["period"][:4])
        month = int(current["period"][5:7])
        month += 1
        if month > 12:
            month = 1
            year += 1
        next_period_str = f"{year}-{month:02d}"

        # Get or create the next period row
        next_row = conn.execute(
            "SELECT * FROM payments WHERE contract_id = ? AND period = ?",
            (contract_id, next_period_str),
        ).fetchone()

        if next_row is None:
            # Create it using the contract's current payment_day and rent
            contract_row = conn.execute(
                """
                SELECT c.payment_day, (
                    SELECT amount FROM rent_changes
                    WHERE contract_id = c.id
                    ORDER BY effective_from DESC, id DESC LIMIT 1
                ) AS current_rent
                FROM contracts c WHERE c.id = ?
                """,
                (contract_id,),
            ).fetchone()
            if contract_row is None:
                raise LookupError("Contract not found.")

            payment_day = contract_row[0]
            expected_amount = contract_row[1]
            last_day = monthrange(year, month)[1]
            day = min(payment_day, last_day)
            due_date_str = f"{year}-{month:02d}-{day:02d}"

            new_paid = excess
            new_status = "paid" if new_paid >= expected_amount else "partial"

            cursor = conn.execute(
                """
                INSERT INTO payments
                    (contract_id, period, due_date, expected_amount,
                     paid_amount, paid_at, status, source)
                VALUES (?, ?, ?, ?, ?, date('now'), ?, 'manual')
                """,
                (contract_id, next_period_str, due_date_str,
                 expected_amount, new_paid, new_status),
            )
            next_id = cursor.lastrowid
        else:
            next_dict = _payment_row_to_dict(next_row, _load_deductions(conn, next_row[0]), _load_owner_expenses(conn, next_row[0]), [])
            next_id = next_dict["id"]
            expected_amount = next_dict["expected_amount"]
            current_paid = next_dict["paid_amount"] or 0
            new_paid = current_paid + excess
            new_status = (
                "paid" if new_paid >= expected_amount
                else "partial" if new_paid > 0
                else "pending"
            )
            conn.execute(
                """
                UPDATE payments
                SET paid_amount = ?, paid_at = date('now'), status = ?
                WHERE id = ?
                """,
                (new_paid, new_status, next_id),
            )

        conn.commit()

        cur_row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        nxt_row = conn.execute("SELECT * FROM payments WHERE id = ?", (next_id,)).fetchone()
        updated_current = _payment_row_to_dict(cur_row, _load_deductions(conn, payment_id), _load_owner_expenses(conn, payment_id), _load_payment_entries(conn, payment_id))
        updated_next = _payment_row_to_dict(nxt_row, _load_deductions(conn, next_id), _load_owner_expenses(conn, next_id), _load_payment_entries(conn, next_id))

    return updated_current, updated_next


def _ensure_payment_periods(contract_id: int) -> int:
    """Fill gaps in the payment schedule without extending it.

    Inserts a pending row for any month that is missing within the range
    [min_existing_period, max_existing_period]. Existing rows are never
    modified (INSERT OR IGNORE). Does not extend the schedule beyond the
    current last period. Returns count of rows inserted.
    """
    with get_connection() as conn:
        bounds = conn.execute(
            "SELECT MIN(period), MAX(period) FROM payments WHERE contract_id = ?",
            (contract_id,),
        ).fetchone()
        if bounds is None or bounds[0] is None:
            return 0
        min_ym, max_ym = bounds

        row = conn.execute(
            """
            SELECT c.payment_day,
                   (SELECT amount FROM rent_changes
                    WHERE contract_id = c.id
                    ORDER BY effective_from DESC, id DESC LIMIT 1) AS current_rent
            FROM contracts c WHERE c.id = ? AND c.is_active = 1
            """,
            (contract_id,),
        ).fetchone()
        if row is None:
            return 0
        payment_day, current_rent = row
        if not current_rent:
            return 0

        existing = {
            r[0]
            for r in conn.execute(
                "SELECT period FROM payments WHERE contract_id = ?",
                (contract_id,),
            ).fetchall()
        }

        inserted = 0
        for period in _iter_months(min_ym, max_ym):
            if period in existing:
                continue
            y, m = int(period[:4]), int(period[5:7])
            last_day = monthrange(y, m)[1]
            due_date_str = f"{y}-{m:02d}-{min(payment_day, last_day):02d}"
            conn.execute(
                """
                INSERT OR IGNORE INTO payments
                    (contract_id, period, due_date, expected_amount, status, source)
                VALUES (?, ?, ?, ?, 'pending', 'manual')
                """,
                (contract_id, period, due_date_str, current_rent),
            )
            inserted += 1

        if inserted:
            conn.commit()

    return inserted


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


def rent_change_payment_atomic(
    contract_id: int,
    period: str,
    new_rent_amount: int,
    paid_amount: int | None,
    paid_at: str | None,
    comment: str | None,
    payment_id: int | None = None,
    deductions: list[dict] | None = None,
    owner_expenses: list[dict] | None = None,
) -> dict:
    """Create a rent change and save/update the payment in one SQLite transaction.

    If rent_change creation fails (chronology, inactive contract), no payment is
    touched. If the payment step fails, the rent_change insert is rolled back.
    """
    deductions_list = deductions or []
    owner_expenses_list = owner_expenses or []

    with get_connection() as conn:
        # --- Validate contract ---
        contract_row = conn.execute(
            "SELECT id, start_date, is_active, payment_day FROM contracts WHERE id = ?",
            (contract_id,),
        ).fetchone()
        if contract_row is None or not contract_row[2]:
            raise LookupError("Active contract not found.")

        start_date_str = contract_row[1]
        payment_day = contract_row[3]
        effective_from = period + "-01"

        # --- Chronological validation ---
        if effective_from < start_date_str:
            raise ValueError("effective_from must be on or after the contract start_date.")

        latest_rc = conn.execute(
            """
            SELECT effective_from FROM rent_changes
            WHERE contract_id = ?
            ORDER BY effective_from DESC, id DESC
            LIMIT 1
            """,
            (contract_id,),
        ).fetchone()
        if latest_rc and effective_from <= latest_rc[0]:
            raise ValueError(
                "effective_from must be strictly after the latest rent change date."
            )

        # --- Insert rent_change (no commit yet) ---
        rc_cursor = conn.execute(
            """
            INSERT INTO rent_changes (contract_id, effective_from, amount, adjustment_pct, comment)
            VALUES (?, ?, ?, NULL, NULL)
            """,
            (contract_id, effective_from, new_rent_amount),
        )
        rent_change_id = rc_cursor.lastrowid

        # --- Compute status ---
        paid = paid_amount or 0
        total_deductions = sum(d["amount"] for d in deductions_list)
        recognized = paid + total_deductions
        if recognized == 0:
            status = "pending"
        elif recognized >= new_rent_amount:
            status = "paid"
        else:
            status = "partial"

        # --- Update existing payment or create new one ---
        if payment_id is not None:
            existing = conn.execute(
                "SELECT id FROM payments WHERE id = ? AND contract_id = ?",
                (payment_id, contract_id),
            ).fetchone()
            if existing is None:
                raise LookupError("Payment not found for this contract.")
            conn.execute(
                """
                UPDATE payments
                SET paid_amount = ?, paid_at = ?, status = ?, comment = ?, expected_amount = ?
                WHERE id = ?
                """,
                (paid_amount, paid_at, status, comment, new_rent_amount, payment_id),
            )
            if deductions is not None:
                _replace_deductions(conn, payment_id, deductions_list)
            if owner_expenses is not None:
                _replace_owner_expenses(conn, payment_id, owner_expenses_list)
            final_payment_id = payment_id
        else:
            year, month = int(period[:4]), int(period[5:7])
            last_day = monthrange(year, month)[1]
            due_date = date(year, month, min(payment_day, last_day)).isoformat()
            try:
                p_cursor = conn.execute(
                    """
                    INSERT INTO payments
                        (contract_id, period, due_date, expected_amount, paid_amount, paid_at, status, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (contract_id, period, due_date, new_rent_amount,
                     paid_amount, paid_at, status, comment),
                )
            except sqlite3.IntegrityError:
                raise ValueError(
                    f"A payment for period {period} already exists on this contract."
                )
            final_payment_id = p_cursor.lastrowid
            if deductions_list:
                _insert_deductions(conn, final_payment_id, deductions_list)
            if owner_expenses_list:
                _insert_owner_expenses(conn, final_payment_id, owner_expenses_list)

        # --- Single commit covers both operations ---
        conn.commit()

        # Read results while connection is still open
        row = conn.execute(
            "SELECT * FROM payments WHERE id = ?", (final_payment_id,)
        ).fetchone()
        deductions_out = _load_deductions(conn, final_payment_id)
        owner_expenses_out = _load_owner_expenses(conn, final_payment_id)

    return {
        "rent_change_id": rent_change_id,
        "payment": _payment_row_to_dict(row, deductions_out, owner_expenses_out, []),
    }


def delete_payment(payment_id: int) -> bool:
    """Clear payment data while keeping the period row in the schedule.

    Resets paid_amount, paid_at, status, comment and removes deductions and
    owner_expenses. The payment period row itself is preserved so the monthly
    contract cycle has no gaps.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM payment_deductions WHERE payment_id = ?", (payment_id,))
        conn.execute("DELETE FROM owner_monthly_expenses WHERE payment_id = ?", (payment_id,))
        conn.execute("DELETE FROM payment_entries WHERE payment_id = ?", (payment_id,))
        cursor = conn.execute(
            """
            UPDATE payments
            SET paid_amount = NULL, paid_at = NULL, status = 'pending', comment = NULL
            WHERE id = ?
            """,
            (payment_id,),
        )
        conn.commit()
    return cursor.rowcount > 0
