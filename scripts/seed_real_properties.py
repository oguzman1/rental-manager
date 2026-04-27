import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import db

DB_PATH = ROOT / os.getenv("DB_NAME", "rental_manager.db")
SEED_PATH = ROOT / "data" / "real_properties_seed.local.json"


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"DB eliminada: {DB_PATH}")

    db.init_db()
    print(f"DB inicializada: {DB_PATH}\n")

    with open(SEED_PATH) as f:
        entries = json.load(f)

    rol_to_id = {}
    inserted = 0

    # Paso 1: insertar todas las propiedades y construir mapa rol → id
    for entry in entries:
        prop = entry["property"]
        contracts = entry.get("contracts", [])

        try:
            with db.get_connection() as conn:
                # 1. Insert property
                cursor = conn.execute(
                    """
                    INSERT INTO properties
                        (user_id, display_name, rol, comuna, address, destination, status,
                         fojas, property_number, year, fiscal_appraisal)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prop["display_name"],
                        prop["rol"],
                        prop["comuna"],
                        prop["address"],
                        prop["destination"],
                        prop["status"],
                        prop.get("fojas"),
                        prop.get("property_number"),
                        prop.get("year"),
                        prop.get("fiscal_appraisal"),
                    ),
                )
                property_id = cursor.lastrowid
                rol_to_id[prop["rol"]] = property_id

                for contract_entry in contracts:
                    c = contract_entry["contract"]

                    # 2. Insert contract
                    cursor = conn.execute(
                        """
                        INSERT INTO contracts
                            (property_id, start_date, end_date, payment_day, notice_days,
                             adjustment_frequency, adjustment_month, is_active, comment,
                             contract_file_name, contract_file_path, contract_signed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            property_id,
                            c["start_date"],
                            c.get("end_date"),
                            c["payment_day"],
                            c["notice_days"],
                            c["adjustment_frequency"],
                            c.get("adjustment_month"),
                            1 if c["is_active"] else 0,
                            c.get("comment"),
                            c.get("contract_file_name"),
                            c.get("contract_file_path"),
                            c.get("contract_signed_at"),
                        ),
                    )
                    contract_id = cursor.lastrowid

                    # 3. Insert tenants and contract_tenants
                    for tenant in contract_entry["tenants"]:
                        cursor = conn.execute(
                            "INSERT INTO tenants (display_name) VALUES (?)",
                            (tenant["display_name"],),
                        )
                        tenant_id = cursor.lastrowid

                        conn.execute(
                            """
                            INSERT INTO contract_tenants (contract_id, tenant_id, is_primary)
                            VALUES (?, ?, ?)
                            """,
                            (contract_id, tenant_id, 1 if tenant["is_primary"] else 0),
                        )

                    # 4. Insert rent_changes (effective_from must be explicit in seed)
                    for rc in contract_entry["rent_changes"]:
                        conn.execute(
                            """
                            INSERT INTO rent_changes
                                (contract_id, effective_from, amount, adjustment_pct, comment)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                contract_id,
                                rc["effective_from"],
                                rc["amount"],
                                rc.get("adjustment_pct"),
                                rc.get("comment"),
                            ),
                        )

                conn.commit()

            n = len(contracts)
            label = f"[{prop['status']}] {prop['rol']} — {prop['comuna']} ({n} contrato{'s' if n != 1 else ''})"
            print(f"✓ {label}")
            inserted += 1

        except Exception as e:
            print(f"✗ {prop['rol']} — {e}")

    # Paso 2: resolver parent_property_id para unidades accesorias
    parents_to_set = [
        (entry["property"]["rol"], entry["property"]["parent_rol"])
        for entry in entries
        if "parent_rol" in entry["property"]
    ]

    if parents_to_set:
        print()
        with db.get_connection() as conn:
            for rol, parent_rol in parents_to_set:
                if parent_rol not in rol_to_id:
                    raise ValueError(
                        f"parent_rol '{parent_rol}' not found for property '{rol}'"
                    )
                conn.execute(
                    "UPDATE properties SET parent_property_id = ? WHERE id = ?",
                    (rol_to_id[parent_rol], rol_to_id[rol]),
                )
                print(f"  parent: {rol} → {parent_rol}")
            conn.commit()

    print(f"\n{inserted} de {len(entries)} propiedades insertadas.")


if __name__ == "__main__":
    main()
