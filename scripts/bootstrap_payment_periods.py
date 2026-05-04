"""Bootstrap missing payment periods for all active contracts.

Run from the project root:
    python scripts/bootstrap_payment_periods.py

Creates historical missing months as paid baseline and current/future months as
pending. Existing payment rows are never modified. Safe to run multiple times.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db

db.init_db()
result = db.bootstrap_payment_periods_for_active_contracts()

print(f"Contracts processed : {result['contracts_processed']}")
print(f"Historical inserted : {result['historical_inserted']}")
print(f"Operational inserted: {result['operational_inserted']}")
print(f"Total inserted      : {result['periods_inserted']}")
