"""Le macro di tipizzazione (dbt/macros/parsing.sql) valutate in DuckDB sui formati che le intestazioni reali fanno prevedere."""

from datetime import date
from decimal import Decimal

import duckdb
import jinja2
import pytest

from anac_appalti.config import carica_impostazioni

MACRO = (carica_impostazioni().dbt_dir / "macros" / "parsing.sql").read_text(encoding="utf-8")


def valuta(macro: str, valori: list[str | None]):
    espressione = jinja2.Environment().from_string(MACRO + "{{ " + macro + "('v') }}").render()
    con = duckdb.connect()
    con.execute("create table t (n integer, v varchar)")
    con.executemany("insert into t values (?, ?)", list(enumerate(valori)))
    risultati = dict(con.execute(f"select n, {espressione} from t").fetchall())
    con.close()
    return [risultati[n] for n in range(len(valori))]


IMPORTI = [
    ("1234.56", Decimal("1234.56")),
    ("1234,56", Decimal("1234.56")),
    ("1.234,56", Decimal("1234.56")),
    ("1,234.56", Decimal("1234.56")),
    ("2.500.000,50", Decimal("2500000.50")),
    ("1.234.567", Decimal("1234567.00")),
    ("1,234,567", Decimal("1234567.00")),
    ("-1.000,00", Decimal("-1000.00")),
    (" 12 ", Decimal("12.00")),
    ("0", Decimal("0.00")),
    ("1234.567", Decimal("1234.57")),
    ("5000000000.00", Decimal("5000000000.00")),
    ("9999999999999999.99", Decimal("9999999999999999.99")),
    # un solo punto è il separatore decimale del formato ANAC, anche con tre decimali
    ("1.234", Decimal("1.23")),
    ("12.345", Decimal("12.35")),
    ("0.125", Decimal("0.13")),
    ("-1.234", Decimal("-1.23")),
    # ambiguo: una sola virgola e tre cifre dopo (migliaia o decimali?), nessuna scelta silenziosa
    ("1,234", None),
    ("-1,234", None),
    # fuori formato o oltre decimal(18,2): NULL (il testo resta in _raw e la qualità lo segnala)
    ("10000000000000000", None),
    ("12345678901234567.00", None),
    ("abc", None),
    ("12%", None),
    ("€ 100", None),
    ("nan", None),
    ("", None),
    (None, None),
]


@pytest.mark.parametrize(("testo", "atteso"), IMPORTI)
def test_parse_importo(testo, atteso):
    assert valuta("parse_importo", [testo]) == [atteso]


def test_parse_ribasso():
    valori = ["12,5", "12.5", "-0.5", "120", "1.234,5", "12%", "", None]
    assert valuta("parse_ribasso", valori) == [12.5, 12.5, -0.5, 120.0, 1234.5, None, None, None]


def test_parse_ribasso_un_solo_separatore_e_decimale():
    """Un ribasso non ha migliaia: con un solo separatore è sempre decimale, anche con tre cifre dopo."""
    valori = ["12.345", "12,345", "0.125", "0,125", "-1.234", "99.999", "1.234.567", "abc"]
    assert valuta("parse_ribasso", valori) == [12.345, 12.345, 0.125, 0.125, -1.234, 99.999, 1234567.0, None]


def test_parse_intero():
    valori = ["27", "27.0", " 27 ", "-1", "27.5", "1e3", "x", "", None]
    assert valuta("parse_intero", valori) == [27, 27, 27, -1, None, 1000, None, None, None]


def test_parse_data_it():
    valori = [
        "2025-12-03",
        "2025-12-03T10:00:00",
        "2025-12-03 10:00:00.123",
        "03/12/2025",
        "3/12/2025",
        "3/12/2025 10:30:00",
        "31/02/2025",
        "12-03-2025",
        "",
        None,
    ]
    dicembre = date(2025, 12, 3)
    assert valuta("parse_data_it", valori) == [dicembre] * 6 + [None] * 4


def test_codici_e_flag():
    assert valuta("codice_numerico", ["27.0", "27.00", "27", " 11.0 ", "27.5", "a.0", "", None]) == [
        "27",
        "27",
        "27",
        "11",
        "27.5",
        "A",
        None,
        None,
    ]
    assert valuta("codice", [" abc ", "", None]) == ["ABC", None, None]
    assert valuta("testo", [" abc ", "", None]) == ["abc", None, None]
    assert valuta("parse_flag", ["1", "1.0", "true", "SI", "0", "no", "boh", "", None]) == [
        True,
        True,
        True,
        True,
        False,
        False,
        None,
        None,
        None,
    ]
