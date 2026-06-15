"""Parser for Banco de Chile XLS bank statements ("cartolas").

Only credit movements (Abonos) are extracted. Cargos (debits) and the
SALDO INICIAL / SALDO FINAL summary rows are ignored.
"""

import hashlib
import re
from datetime import date

import xlrd

BANK_NAME = "banco_de_chile"

_SALDO_LABELS = {"SALDO INICIAL", "SALDO FINAL"}

_DATE_DDMMYYYY_RE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")
_DATE_DDMM_RE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})\s*$")


class StatementParseError(Exception):
    """Raised when a statement file cannot be parsed."""


def parse_xls(content: bytes, bank: str = BANK_NAME) -> list[dict]:
    """Parse the bytes of a Banco de Chile XLS statement into movement dicts."""
    try:
        book = xlrd.open_workbook(file_contents=content)
        sheet = book.sheet_by_index(0)
    except Exception as exc:
        raise StatementParseError(f"Could not read XLS file: {exc}") from exc

    rows = [
        [sheet.cell_value(r, c) for c in range(sheet.ncols)]
        for r in range(sheet.nrows)
    ]
    return parse_rows(rows, bank=bank)


def parse_rows(rows: list[list], bank: str = BANK_NAME) -> list[dict]:
    """Parse a list of spreadsheet rows (lists of cell values) into movement dicts.

    Each returned dict has: movement_date (ISO), description, amount,
    balance_after, dedup_key.
    """
    header_row_idx = _find_header_row(rows)
    if header_row_idx is None:
        raise StatementParseError("Could not locate movements header row ('Fecha').")

    emission_date = _find_emission_date(rows)
    if emission_date is None:
        raise StatementParseError("Could not locate statement emission date.")

    headers = [str(v).strip() for v in rows[header_row_idx]]
    try:
        fecha_col = headers.index("Fecha")
        desc_col = headers.index("Descripción")
        abonos_col = headers.index("Abonos (PESOS)")
    except ValueError as exc:
        raise StatementParseError(f"Missing expected column: {exc}") from exc

    saldo_col = headers.index("Saldo (PESOS)") if "Saldo (PESOS)" in headers else None

    period_label = emission_date.isoformat()
    movements = []

    for row in rows[header_row_idx + 1:]:
        if len(row) <= max(fecha_col, desc_col, abonos_col):
            continue

        description = _normalize_description(row[desc_col])
        if not description or description.upper() in _SALDO_LABELS:
            continue

        amount = _read_amount(row[abonos_col])
        if not amount:
            continue

        movement_date = _normalize_date(row[fecha_col], emission_date)
        if movement_date is None:
            continue

        balance_after = None
        if saldo_col is not None and saldo_col < len(row):
            balance_after = _read_amount(row[saldo_col])

        dedup_key = _build_dedup_key(
            bank=bank,
            period_label=period_label,
            movement_date=movement_date,
            description=description,
            amount=amount,
            balance_after=balance_after,
        )

        movements.append(
            {
                "movement_date": movement_date.isoformat(),
                "description": description,
                "amount": amount,
                "balance_after": balance_after,
                "dedup_key": dedup_key,
            }
        )

    return movements


def _find_header_row(rows: list[list]) -> int | None:
    for i, row in enumerate(rows):
        for cell in row:
            if isinstance(cell, str) and cell.strip().lower() == "fecha":
                return i
    return None


def _find_emission_date(rows: list[list]) -> date | None:
    for row in rows:
        if not any(isinstance(c, str) and "emisi" in c.lower() for c in row):
            continue
        for cell in row:
            if not isinstance(cell, str):
                continue
            m = _DATE_DDMMYYYY_RE.match(cell)
            if m:
                day, month, year = (int(g) for g in m.groups())
                try:
                    return date(year, month, day)
                except ValueError:
                    continue
    return None


def _normalize_date(value, emission_date: date) -> date | None:
    if not isinstance(value, str):
        return None

    m = _DATE_DDMMYYYY_RE.match(value)
    if m:
        day, month, year = (int(g) for g in m.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None

    m = _DATE_DDMM_RE.match(value)
    if not m:
        return None

    day, month = int(m.group(1)), int(m.group(2))
    year = emission_date.year
    try:
        candidate = date(year, month, day)
    except ValueError:
        return None

    if candidate > emission_date:
        try:
            candidate = date(year - 1, month, day)
        except ValueError:
            return None

    return candidate


def _normalize_description(value) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _read_amount(value) -> int | None:
    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        amount = int(round(value))
        return amount or None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        text = text.replace(".", "").replace(",", ".")
        try:
            amount = int(round(float(text)))
        except ValueError:
            return None
        return amount or None

    return None


def _build_dedup_key(
    *,
    bank: str,
    period_label: str,
    movement_date: date,
    description: str,
    amount: int,
    balance_after: int | None,
) -> str:
    raw = "|".join(
        [
            bank,
            period_label,
            movement_date.isoformat(),
            description.upper(),
            str(amount),
            "" if balance_after is None else str(balance_after),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
