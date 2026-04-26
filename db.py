import os
import sqlite3

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

        # Default user required by the legacy write mapping (user_id = 1).
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
                created_at           TEXT    NOT NULL DEFAULT (date('now'))
            )
            """
        )

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

        conn.commit()


# ---------------------------------------------------------------------------
# Legacy write mapping
#
# The public API still accepts ManagedPropertyCreate (flat property + rental).
# Internally this maps to the normalized schema:
#
#   property  → properties row
#              (display_name = rental.property_label if rental else property.rol)
#   rental    → contracts row       (non-rent fields)
#             → contract_tenants row (is_primary = 1)
#             → tenants row          (display_name = rental.tenant_name)
#             → rent_changes row     (amount = rental.current_rent,
#                                     effective_from = rental.start_date)
#
# update_managed_property applies changes surgically:
#   a) property fields  → UPDATE properties directly
#   b) contract fields  → UPDATE the existing active contract (no new contract)
#   c) tenant name      → UPDATE tenants.display_name in place
#
# Rent history is intentionally NOT updated by the legacy endpoint.
# New rent_changes rows must come from the seed (with a real effective_from)
# or from an explicit future action with a known effective date.
# Using date.today() as effective_from would introduce fabricated history.
#
# Creating a new contract via the legacy endpoint is intentionally unsupported.
# ---------------------------------------------------------------------------


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
                    (contract_id, data.rental.start_date.isoformat(), data.rental.current_rent),
                )

            conn.commit()
            return property_id

    except sqlite3.IntegrityError:
        raise


def update_managed_property(property_id: int, data: ManagedPropertyCreate) -> bool:
    try:
        with get_connection() as conn:
            # a) Update property fields directly.
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

                    # b) Update active contract fields — no new contract is created.
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

                    # Update primary tenant name in place.
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

                # Sync display_name with property_label if it changed.
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
            conn.execute("DELETE FROM rent_changes WHERE contract_id = ?", (cid,))
            conn.execute("DELETE FROM contract_tenants WHERE contract_id = ?", (cid,))

        conn.execute("DELETE FROM contracts WHERE property_id = ?", (property_id,))

        cursor = conn.execute("DELETE FROM properties WHERE id = ?", (property_id,))
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Read queries
#
# All functions return the same dict shapes as before so main.py and the
# response models require no changes.
#
# The subquery below selects the single latest rent_change per contract,
# breaking ties by effective_from DESC then id DESC.
# ---------------------------------------------------------------------------

_LATEST_RENT = """
    (
        SELECT id FROM rent_changes
        WHERE  contract_id = c.id
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

    results = []
    for row in rows:
        results.append(
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
        )
    return results


def list_rentals_for_adjustments() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                p.id,
                p.rol,
                p.comuna,
                p.display_name     AS property_label,
                t.display_name     AS tenant_name,
                c.payment_day,
                rc.amount          AS current_rent,
                c.adjustment_frequency,
                c.start_date
            FROM properties p
            JOIN contracts c
                ON c.property_id = p.id AND c.is_active = 1
            JOIN contract_tenants ct
                ON ct.contract_id = c.id AND ct.is_primary = 1
            JOIN tenants t
                ON t.id = ct.tenant_id
            JOIN rent_changes rc
                ON rc.contract_id = c.id AND rc.id = {_LATEST_RENT}
            ORDER BY p.id DESC
            """
        ).fetchall()

    results = []
    for row in rows:
        results.append(
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
            }
        )
    return results


def list_dashboard_items() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                p.id,
                p.rol,
                p.comuna,
                p.status,
                p.display_name     AS property_label,
                t.display_name     AS tenant_name,
                c.payment_day,
                rc.amount          AS current_rent,
                c.adjustment_frequency,
                c.start_date
            FROM properties p
            LEFT JOIN contracts c
                   ON c.property_id = p.id AND c.is_active = 1
            LEFT JOIN contract_tenants ct
                   ON ct.contract_id = c.id AND ct.is_primary = 1
            LEFT JOIN tenants t
                   ON t.id = ct.tenant_id
            LEFT JOIN rent_changes rc
                   ON rc.contract_id = c.id AND rc.id = {_LATEST_RENT}
            ORDER BY p.id DESC
            """
        ).fetchall()

    results = []
    for row in rows:
        results.append(
            {
                "id": row[0],
                "rol": row[1],
                "comuna": row[2],
                "status": row[3],
                "property_label": row[4],
                "tenant_name": row[5],
                "payment_day": row[6],
                "current_rent": row[7],
                "adjustment_frequency": row[8],
                "start_date": row[9],
            }
        )
    return results


# ---------------------------------------------------------------------------
# Payment queries
# ---------------------------------------------------------------------------

def get_contract_for_payment(contract_id: int) -> dict | None:
    """Returns the active contract + its current rent, or None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT c.id, c.property_id, rc.amount AS current_rent
            FROM contracts c
            JOIN rent_changes rc
                ON rc.contract_id = c.id AND rc.id = {_LATEST_RENT}
            WHERE c.id = ? AND c.is_active = 1
            """,
            (contract_id,),
        ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "property_id": row[1], "current_rent": row[2]}


def insert_payment(
    contract_id: int,
    period: str,
    due_date: str,
    expected_amount: int,
    comment: str | None,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO payments (contract_id, period, due_date, expected_amount, comment)
            VALUES (?, ?, ?, ?, ?)
            """,
            (contract_id, period, due_date, expected_amount, comment),
        )
        conn.commit()
        return cursor.lastrowid


def list_payments_for_contract(contract_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, contract_id, period, due_date, expected_amount,
                   paid_amount, paid_at, status, source, comment, created_at
            FROM payments
            WHERE contract_id = ?
            ORDER BY period DESC
            """,
            (contract_id,),
        ).fetchall()
    return [
        {
            "id": r[0], "contract_id": r[1], "period": r[2], "due_date": r[3],
            "expected_amount": r[4], "paid_amount": r[5], "paid_at": r[6],
            "status": r[7], "source": r[8], "comment": r[9], "created_at": r[10],
        }
        for r in rows
    ]


def get_payment(payment_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, contract_id, period, due_date, expected_amount,
                   paid_amount, paid_at, status, source, comment, created_at
            FROM payments
            WHERE id = ?
            """,
            (payment_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0], "contract_id": row[1], "period": row[2], "due_date": row[3],
        "expected_amount": row[4], "paid_amount": row[5], "paid_at": row[6],
        "status": row[7], "source": row[8], "comment": row[9], "created_at": row[10],
    }


def update_payment(
    payment_id: int,
    paid_amount: int | None,
    paid_at: str | None,
    status: str,
    comment: str | None,
) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE payments
            SET paid_amount = ?, paid_at = ?, status = ?, comment = ?
            WHERE id = ?
            """,
            (paid_amount, paid_at, status, comment, payment_id),
        )
        conn.commit()
        return cursor.rowcount > 0
