import sqlite3
from models import ManagedPropertyCreate


# Nombre del archivo SQLite que guardará los datos localmente.
DB_NAME = "rental_manager.db"


# Devuelve una conexión a la base SQLite.
def get_connection():
    return sqlite3.connect(DB_NAME)


# Crea la tabla si todavía no existe.
def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS managed_properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comuna TEXT NOT NULL,
                rol TEXT NOT NULL UNIQUE,
                address TEXT NOT NULL,
                destination TEXT NOT NULL,
                status TEXT NOT NULL,
                fojas TEXT,
                property_number TEXT,
                year INTEGER,
                fiscal_appraisal INTEGER,
                property_label TEXT,
                current_rent INTEGER,
                adjustment_frequency TEXT,
                start_date TEXT,
                notice_days INTEGER,
                adjustment_month TEXT
            )
            """
        )
        conn.commit()


# Inserta una propiedad gestionada y devuelve el id generado.
def insert_managed_property(data: ManagedPropertyCreate) -> int:
    # Si hay rental, toma sus valores; si no, guarda None.
    property_label = data.rental.property_label if data.rental else None
    current_rent = data.rental.current_rent if data.rental else None
    adjustment_frequency = data.rental.adjustment_frequency if data.rental else None
    start_date = data.rental.start_date.isoformat() if data.rental else None
    notice_days = data.rental.notice_days if data.rental else None
    adjustment_month = data.rental.adjustment_month if data.rental else None

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO managed_properties (
                    comuna,
                    rol,
                    address,
                    destination,
                    status,
                    fojas,
                    property_number,
                    year,
                    fiscal_appraisal,
                    property_label,
                    current_rent,
                    adjustment_frequency,
                    start_date,
                    notice_days,
                    adjustment_month
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.property.comuna,
                    data.property.rol,
                    data.property.address,
                    data.property.destination,
                    data.property.status.value,
                    data.property.fojas,
                    data.property.property_number,
                    data.property.year,
                    data.property.fiscal_appraisal,
                    property_label,
                    current_rent,
                    adjustment_frequency.value if adjustment_frequency else None,
                    start_date,
                    notice_days,
                    adjustment_month,
                ),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise

# Devuelve todas las propiedades guardadas en la base.
def list_managed_properties() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, rol, comuna, status, property_label
            FROM managed_properties
            ORDER BY id DESC
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
                "has_rental": row[4] is not None,
                "property_label": row[4],
            }
        )

    return results

# Actualiza una propiedad gestionada por id. Devuelve True si actualizó una fila.
def update_managed_property(property_id: int, data: ManagedPropertyCreate) -> bool:
    # Si hay rental, toma sus valores; si no, guarda None.
    property_label = data.rental.property_label if data.rental else None
    current_rent = data.rental.current_rent if data.rental else None
    adjustment_frequency = data.rental.adjustment_frequency if data.rental else None
    start_date = data.rental.start_date.isoformat() if data.rental else None
    notice_days = data.rental.notice_days if data.rental else None
    adjustment_month = data.rental.adjustment_month if data.rental else None

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE managed_properties
                SET
                    comuna = ?,
                    rol = ?,
                    address = ?,
                    destination = ?,
                    status = ?,
                    fojas = ?,
                    property_number = ?,
                    year = ?,
                    fiscal_appraisal = ?,
                    property_label = ?,
                    current_rent = ?,
                    adjustment_frequency = ?,
                    start_date = ?,
                    notice_days = ?,
                    adjustment_month = ?
                WHERE id = ?
                """,
                (
                    data.property.comuna,
                    data.property.rol,
                    data.property.address,
                    data.property.destination,
                    data.property.status.value,
                    data.property.fojas,
                    data.property.property_number,
                    data.property.year,
                    data.property.fiscal_appraisal,
                    property_label,
                    current_rent,
                    adjustment_frequency.value if adjustment_frequency else None,
                    start_date,
                    notice_days,
                    adjustment_month,
                    property_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        raise

# Elimina una propiedad gestionada por id. Devuelve True si borró una fila.
def delete_managed_property(property_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM managed_properties WHERE id = ?",
            (property_id,),
        )
        conn.commit()
        return cursor.rowcount > 0