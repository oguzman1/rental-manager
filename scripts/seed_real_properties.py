import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import db
from models import ManagedPropertyCreate

DB_PATH = ROOT / os.getenv("DB_NAME", "rental_manager.db")
SEED_PATH = ROOT / "data" / "real_properties_seed.json"


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"DB eliminada: {DB_PATH}")

    db.init_db()
    print(f"DB inicializada: {DB_PATH}\n")

    with open(SEED_PATH) as f:
        entries = json.load(f)

    inserted = 0
    for entry in entries:
        data = ManagedPropertyCreate.model_validate(entry)
        try:
            property_id = db.insert_managed_property(data)

            # Properties without rental can still carry a property_label in the
            # JSON. ManagedPropertyCreate ignores it, so we patch it via SQL.
            if data.rental is None and (pl := entry.get("property_label")):
                with db.get_connection() as conn:
                    conn.execute(
                        "UPDATE managed_properties SET property_label = ? WHERE id = ?",
                        (pl, property_id),
                    )
                    conn.commit()

            label = f"  [{data.property.status.value}] {data.property.rol} — {data.property.comuna}"
            print(f"✓ (id={property_id}){label}")
            inserted += 1
        except Exception as e:
            print(f"✗ {data.property.rol} — {e}")

    print(f"\n{inserted} de {len(entries)} propiedades insertadas.")


if __name__ == "__main__":
    main()
