import pytest

import bank_statement_parser as parser


def _statement_rows(*data_rows):
    """Build a synthetic set of rows mimicking the Banco de Chile XLS layout.

    Layout (1-indexed columns in the real file, kept here for fidelity):
      col 0: unused
      col 1: Fecha
      col 2: Descripción
      col 3: Canal o Sucursal
      col 4: Cargos (PESOS)
      col 5: Abonos (PESOS)
      col 6: Saldo (PESOS)
    """
    rows = [[] for _ in range(5)]
    rows.append(["", "", "", "Fecha de Emisión", " 28/02/2026", "", ""])
    rows.append([])
    rows.append(["", "Fecha", "Descripción", "Canal o Sucursal", "Cargos (PESOS)", "Abonos (PESOS)", "Saldo (PESOS)"])
    rows.extend(data_rows)
    return rows


def test_parser_extracts_abono_rows():
    rows = _statement_rows(
        ["", "31/01", "SALDO INICIAL", "", "", "", 1000000],
        ["", "05/02", "TRANSFERENCIA DE JUAN PEREZ", "INTERNET", "", 500000, ""],
        ["", "28/02", "SALDO FINAL", "", "", "", 1500000],
    )

    movements = parser.parse_rows(rows)

    assert len(movements) == 1
    assert movements[0]["amount"] == 500000
    assert movements[0]["description"] == "TRANSFERENCIA DE JUAN PEREZ"
    assert movements[0]["movement_date"] == "2026-02-05"


def test_parser_ignores_cargos_and_debits():
    rows = _statement_rows(
        ["", "31/01", "SALDO INICIAL", "", "", "", 1000000],
        ["", "05/02", "PAGO TARJETA", "INTERNET", 200000, "", ""],
        ["", "06/02", "ABONO RECIBIDO", "INTERNET", "", 300000, ""],
        ["", "28/02", "SALDO FINAL", "", "", "", 1100000],
    )

    movements = parser.parse_rows(rows)

    assert len(movements) == 1
    assert movements[0]["description"] == "ABONO RECIBIDO"
    assert movements[0]["amount"] == 300000


def test_parser_ignores_saldo_inicial_and_final():
    rows = _statement_rows(
        ["", "31/01", "SALDO INICIAL", "", "", "", 1000000],
        ["", "10/02", "ABONO", "INTERNET", "", 100000, ""],
        ["", "28/02", "SALDO FINAL", "", "", "", 1100000],
    )

    movements = parser.parse_rows(rows)

    descriptions = [m["description"] for m in movements]
    assert "SALDO INICIAL" not in descriptions
    assert "SALDO FINAL" not in descriptions
    assert len(movements) == 1


@pytest.mark.parametrize(
    "raw, expected",
    [
        (1234567.0, 1234567),
        ("1.234.567", 1234567),
        ("1.234.567,50", 1234568),
        (500000, 500000),
    ],
)
def test_amount_normalization(raw, expected):
    rows = _statement_rows(
        ["", "31/01", "SALDO INICIAL", "", "", "", 1000000],
        ["", "10/02", "ABONO", "INTERNET", "", raw, ""],
        ["", "28/02", "SALDO FINAL", "", "", "", 1100000],
    )

    movements = parser.parse_rows(rows)

    assert len(movements) == 1
    assert movements[0]["amount"] == expected


def test_date_year_normalization_wraps_to_previous_year():
    # Emission date is 30/01/2026; a row dated in December belongs to the
    # previous year (2025), while a row dated in January belongs to 2026.
    rows = [[] for _ in range(5)]
    rows.append(["", "", "", "Fecha de Emisión", " 30/01/2026", "", ""])
    rows.append([])
    rows.append(["", "Fecha", "Descripción", "Canal o Sucursal", "Cargos (PESOS)", "Abonos (PESOS)", "Saldo (PESOS)"])
    rows.append(["", "30/12", "SALDO INICIAL", "", "", "", 1000000])
    rows.append(["", "26/12", "ABONO DE DICIEMBRE", "INTERNET", "", 100000, ""])
    rows.append(["", "02/01", "ABONO DE ENERO", "INTERNET", "", 200000, ""])
    rows.append(["", "30/01", "SALDO FINAL", "", "", "", 1300000])

    movements = parser.parse_rows(rows)

    by_desc = {m["description"]: m for m in movements}
    assert by_desc["ABONO DE DICIEMBRE"]["movement_date"] == "2025-12-26"
    assert by_desc["ABONO DE ENERO"]["movement_date"] == "2026-01-02"


def test_dedup_key_is_stable_and_distinguishes_movements():
    rows = _statement_rows(
        ["", "31/01", "SALDO INICIAL", "", "", "", 1000000],
        ["", "05/02", "TRANSFERENCIA DE JUAN PEREZ", "INTERNET", "", 500000, 1500000],
        ["", "06/02", "TRANSFERENCIA DE JUAN PEREZ", "INTERNET", "", 500000, 2000000],
        ["", "28/02", "SALDO FINAL", "", "", "", 2000000],
    )

    movements_a = parser.parse_rows(rows)
    movements_b = parser.parse_rows(rows)

    # Same input -> same dedup keys (deterministic).
    assert [m["dedup_key"] for m in movements_a] == [m["dedup_key"] for m in movements_b]

    # Different dates/balances -> different dedup keys, even with identical
    # description and amount.
    assert movements_a[0]["dedup_key"] != movements_a[1]["dedup_key"]


def test_parser_raises_on_missing_header_row():
    rows = [["nothing", "here"], ["just", "noise"]]

    with pytest.raises(parser.StatementParseError):
        parser.parse_rows(rows)


def test_parser_raises_on_missing_emission_date():
    rows = [
        [],
        ["", "Fecha", "Descripción", "Canal o Sucursal", "Cargos (PESOS)", "Abonos (PESOS)", "Saldo (PESOS)"],
        ["", "05/02", "ABONO", "INTERNET", "", 500000, ""],
    ]

    with pytest.raises(parser.StatementParseError):
        parser.parse_rows(rows)
