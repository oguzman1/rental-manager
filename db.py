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


def list_rentals_for_adjustments() -> list[dict]:
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
                {_LATEST_ADJUSTMENT}    AS last_adjustment_date,
                c.id                    AS contract_id
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
            "contract_id": row[10],
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


def list_dashboard_items() -> list[dict]:
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
                {_LATEST_ADJUSTMENT}    AS last_adjustment_date,
                cp.status               AS current_payment_status,
                ps.total_exigibles,
                ps.saldo_pendiente,
                pp.period_amount,
                pp.latest_period,
                ap.actionable_payment_period,
                ap.actionable_payment_status,
                ap.actionable_payment_amount,
                c.id                    AS contract_id
            FROM properties p
            LEFT JOIN contracts c
                   ON c.property_id = p.id AND c.is_active = 1
            LEFT JOIN contract_tenants ct
                   ON ct.contract_id = c.id AND ct.is_primary = 1
            LEFT JOIN tenants t
                   ON t.id = ct.tenant_id
            LEFT JOIN rent_changes rc
                   ON rc.contract_id = c.id AND rc.id = {_LATEST_RENT}
            LEFT JOIN (
                SELECT
                    contract_id,
                    CASE
                        WHEN COALESCE(paid_amount, 0) >= expected_amount THEN 'paid'
                        WHEN COALESCE(paid_amount, 0) > 0               THEN 'partial'
                        ELSE                                                  'pending'
                    END AS status
                FROM payments
                WHERE period = strftime('%Y-%m', 'now')
            ) cp ON c.id = cp.contract_id
            LEFT JOIN (
                SELECT
                    contract_id,
                    COUNT(*)                                         AS total_exigibles,
                    SUM(expected_amount - COALESCE(paid_amount, 0)) AS saldo_pendiente
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
                        WHEN COALESCE(p1.paid_amount, 0) = 0 THEN 'pending'
                        ELSE                                      'partial'
                    END                AS actionable_payment_status,
                    p1.expected_amount AS actionable_payment_amount
                FROM payments p1
                INNER JOIN (
                    SELECT contract_id, MIN(period) AS min_period
                    FROM   payments
                    WHERE  period <= strftime('%Y-%m', 'now')
                      AND  COALESCE(paid_amount, 0) < expected_amount
                    GROUP BY contract_id
                ) p3 ON p1.contract_id = p3.contract_id
                     AND p1.period      = p3.min_period
            ) ap ON c.id = ap.contract_id
            WHERE p.parent_property_id IS NULL
            ORDER BY p.id DESC
            """
        ).fetchall()

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

        result.append({
            "id":                     row["id"],
            "rol":                    row["rol"],
            "comuna":                 row["comuna"],
            "status":                 row["status"],
            "property_label":         row["property_label"],
            "tenant_name":            row["tenant_name"],
            "payment_day":            row["payment_day"],
            "current_rent":           row["current_rent"],
            "adjustment_frequency":   row["adjustment_frequency"],
            "start_date":             row["start_date"],
            "last_adjustment_date":   row["last_adjustment_date"],
            "current_payment_status": row["current_payment_status"],
            "payment_status":         payment_status,
            "period_amount":              row["period_amount"],
            "latest_period":              row["latest_period"],
            "actionable_payment_period":  row["actionable_payment_period"],
            "actionable_payment_status":  row["actionable_payment_status"],
            "actionable_payment_amount":  row["actionable_payment_amount"],
            "contract_id":                row["contract_id"],
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
                c.comment
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
                c.is_active
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
                 adjustment_frequency, adjustment_month, comment, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                data.property_id,
                data.start_date.isoformat(),
                data.payment_day,
                data.notice_days,
                data.adjustment_frequency.value,
                data.adjustment_month,
                data.comment,
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


def insert_payment(
    contract_id: int,
    period: str,
    due_date: str,
    expected_amount: int,
    comment: str | None,
    paid_amount: int | None = None,
    paid_at: str | None = None,
    status: str = "pending",
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO payments
                (contract_id, period, due_date, expected_amount, paid_amount, paid_at, status, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (contract_id, period, due_date, expected_amount, paid_amount, paid_at, status, comment),
        )
        conn.commit()
        return cursor.lastrowid


def _payment_row_to_dict(row) -> dict:
    paid = row[5]
    expected = row[4]
    overpayment = max(0, paid - expected) if paid is not None else 0
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
        "overpayment": overpayment,
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

        current = _payment_row_to_dict(row)
        if current["overpayment"] <= 0:
            raise ValueError("No overpayment to apply.")

        excess = current["overpayment"]
        contract_id = current["contract_id"]

        # Reduce current period to exactly expected_amount
        conn.execute(
            "UPDATE payments SET paid_amount = ?, status = 'paid' WHERE id = ?",
            (current["expected_amount"], payment_id),
        )

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
            next_dict = _payment_row_to_dict(next_row)
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

        updated_current = _payment_row_to_dict(
            conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        )
        updated_next = _payment_row_to_dict(
            conn.execute("SELECT * FROM payments WHERE id = ?", (next_id,)).fetchone()
        )

    return updated_current, updated_next


def list_payments_for_contract(contract_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM payments WHERE contract_id = ? ORDER BY period DESC",
            (contract_id,),
        ).fetchall()

    return [_payment_row_to_dict(row) for row in rows]


def get_payment(payment_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM payments WHERE id = ?",
            (payment_id,),
        ).fetchone()

    return _payment_row_to_dict(row) if row else None


def update_payment(
    payment_id: int,
    paid_amount: int | None,
    paid_at: str | None,
    status: str,
    comment: str | None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE payments
            SET paid_amount = ?, paid_at = ?, status = ?, comment = ?
            WHERE id = ?
            """,
            (paid_amount, paid_at, status, comment, payment_id),
        )
        conn.commit()


def delete_payment(payment_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
        conn.commit()
    return cursor.rowcount > 0