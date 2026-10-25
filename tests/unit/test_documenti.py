from pathlib import Path

import pytest

from anac_appalti.documenti import (
    MARCATORE_FINE,
    MARCATORE_INIZIO,
    aggiorna_readme,
    blocco_numeri,
    componi_indice_sito,
    componi_pagina_dagster,
    componi_ultima_esecuzione,
    gravita_test,
    record_per_readme,
)

RECORD = {
    "run_id": "20261025T221500-abc123",
    "versione": "0.1.0",
    "git_sha": "0123456789abcdef",
    "git_modificato": False,
    "strumenti": {"python": "3.13.11", "dbt-core": "1.12.6", "duckdb": "1.5.6"},
    "inizio": "2026-10-25T22:15:00",
    "fine": "2026-10-26T00:45:30",
    "durata_s": 9030.0,
    "fixtures": False,
    "anni": [2024, 2025, 2026],
    "data_riferimento": "2026-10-25",
    "esito": "successo",
    "errori": [],
    "estrazione": {
        "cig": {
            "scaricati": 33,
            "saltati": 0,
            "byte": 1_130_000_000,
            "user_agent": "browser",
            "durata_s": 2400.0,
        }
    },
    "landing": {
        "cig": {
            "atterrati": 31,
            "saltati": 0,
            "righe": {"cig_csv_2024_01": 1000, "cig_csv_2024_02": 2000},
            "avvisi": [],
            "errori": [],
            "durata_s": 1800.0,
        }
    },
    "dbt": {
        "esiti": {"success": 50, "pass": 120, "warn": 6},
        "errori": [],
        "n_modelli": 41,
        "n_test": 132,
        "durata_s": 2700.0,
    },
    "freschezza": {"anac.cig": "pass"},
    "modelli": {
        "intermediate.int_cig__corrente": {"righe": 1234567, "hash": "1"},
        "radar.mart_concorrenza": {"righe": 12345, "hash": "2"},
    },
    "disco": {"raw": 2_000_000_000, "landing": 1_500_000_000, "warehouse": 3_000_000_000},
}
INDICATORI = {
    "righe_cig": 2000000,
    "duplicati_esatti": 1234,
    "lotti_correnti": 1234567,
    "date_impossibili": 12345,
    "importi_anomali": 2345,
    "righe_persone_fisiche": 34567,
}


def test_ultima_esecuzione():
    testo = componi_ultima_esecuzione(RECORD)
    assert testo == componi_ultima_esecuzione(RECORD)
    assert testo.startswith("# Ultima esecuzione")
    assert "2 h 30 min" in testo
    assert "(commit `0123456789ab`, albero di lavoro pulito)" in testo
    assert "| Strumenti | python 3.13.11, dbt-core 1.12.6, duckdb 1.5.6 |" in testo
    sporco = componi_ultima_esecuzione(RECORD | {"git_modificato": True})
    assert "albero di lavoro modificato, non riproducibile dal solo commit" in sporco
    vecchio = componi_ultima_esecuzione(
        {k: v for k, v in RECORD.items() if k not in ("git_modificato", "strumenti")}
    )
    assert (
        "stato dell'albero di lavoro non registrato" in vecchio
        and "| Strumenti | non registrati |" in vecchio
    )
    assert "| cig | 33 | 0 | 1.130,0 |" in testo
    assert "0 EUR" in testo


def test_blocco_numeri_it_en():
    gravita = {"error": 120, "warn": 8, "unit": 4}
    italiano = blocco_numeri(RECORD, INDICATORI, 1.0, gravita, "it")
    inglese = blocco_numeri(RECORD, INDICATORI, 1.0, gravita, "en")
    assert "| Lotti (CIG) correnti | 1.234.567 |" in italiano
    assert "| Current lots (CIG) | 1,234,567 |" in inglese
    assert "| Modelli con test sulla chiave | 100 % |" in italiano
    assert "| Models with key tests | 100% |" in inglese
    assert "| Test dbt: gravità error / warn / unit test | 120 / 8 / 4 |" in italiano
    assert "| Duplicati esatti rimossi | 1.234 (0,06 %) |" in italiano
    assert "| Freschezza delle sorgenti | pass 1 |" in italiano
    assert "| `mart_concorrenza` | 12.345 |" in italiano
    assert "| Disco: raw · landing · warehouse | 2,00 GB · 1,50 GB · 3,00 GB |" in italiano


def test_gravita_test():
    manifest = {
        "nodes": {
            "test.anac_appalti.a": {
                "resource_type": "test",
                "package_name": "anac_appalti",
                "config": {"severity": "ERROR"},
            },
            "test.anac_appalti.b": {
                "resource_type": "test",
                "package_name": "anac_appalti",
                "config": {"severity": "warn"},
            },
            "test.altro.c": {
                "resource_type": "test",
                "package_name": "altro",
                "config": {"severity": "warn"},
            },
            "model.anac_appalti.m": {"resource_type": "model", "package_name": "anac_appalti", "config": {}},
        },
        "unit_tests": {"unit_test.anac_appalti.m.u": {"package_name": "anac_appalti"}},
    }
    assert gravita_test(manifest) == {"error": 1, "warn": 1, "unit": 1}


def test_record_per_readme_usa_una_sola_esecuzione():
    registri = [
        {
            "run_id": "a",
            "esito": "successo",
            "modelli": {"x": 1},
            "estrazione": {"cig": {"scaricati": 3}},
            "landing": {"cig": {"atterrati": 3}},
            "durata_s": 100.0,
        },
        {
            "run_id": "b",
            "esito": "successo",
            "modelli": {"x": 2},
            "estrazione": {},
            "landing": {"cig": {"atterrati": 5}},
            "durata_s": 10.0,
        },
        {"run_id": "c", "esito": "errore", "modelli": {}, "estrazione": {}, "landing": {}, "durata_s": 1.0},
    ]
    record = record_per_readme(registri)
    assert record["run_id"] == "b"
    assert record["modelli"] == {"x": 2}
    assert record["estrazione"] == {}
    assert record["landing"] == {"cig": {"atterrati": 5}}
    assert record["durata_s"] == 10.0
    assert "esecuzione_download" not in record
    with pytest.raises(ValueError):
        record_per_readme([])


def test_blocco_numeri_fase_assente_non_prende_in_prestito():
    record = {**RECORD, "estrazione": {}}
    gravita = {"error": 120, "warn": 8, "unit": 4}
    italiano = blocco_numeri(record, INDICATORI, 1.0, gravita, "it")
    inglese = blocco_numeri(record, INDICATORI, 1.0, gravita, "en")
    assert "| File ANAC scaricati | non disponibile in questa esecuzione |" in italiano
    assert "| ANAC files downloaded | not available in this run |" in inglese
    assert (
        "| Durata: estrazione · landing · dbt · totale | non disponibile in questa esecuzione · 30 min 0 s · 45 min 0 s · 2 h 30 min |"
        in italiano
    )
    assert "| Rows landed | 3,000 |" in inglese
    assert "esecuzione `20261025T221500-abc123`" in italiano
    assert "run `20261025T221500-abc123`" in inglese


def test_durata_del_blocco_coerente_con_una_sola_esecuzione():
    italiano = blocco_numeri(RECORD, INDICATORI, 1.0, {"error": 1, "warn": 1, "unit": 1}, "it")
    assert (
        "| Durata: estrazione · landing · dbt · totale | 40 min 0 s · 30 min 0 s · 45 min 0 s · 2 h 30 min |"
        in italiano
    )


def test_aggiorna_readme(tmp_path: Path):
    readme = tmp_path / "README.md"
    readme.write_text(f"prima\n{MARCATORE_INIZIO}\nvecchio\n{MARCATORE_FINE}\ndopo\n", encoding="utf-8")
    assert aggiorna_readme(readme, "nuovo") is True
    assert readme.read_text(encoding="utf-8") == f"prima\n{MARCATORE_INIZIO}\nnuovo\n{MARCATORE_FINE}\ndopo\n"
    assert aggiorna_readme(readme, "nuovo") is False
    (tmp_path / "vuoto.md").write_text("niente", encoding="utf-8")
    with pytest.raises(ValueError):
        aggiorna_readme(tmp_path / "vuoto.md", "x")


def test_pagina_dagster():
    pagina = componi_pagina_dagster([("landing_cig", "landing", ["raw_cig"]), ("raw_cig", "estrazione", [])])
    assert "flowchart LR" in pagina
    assert "raw_cig --&gt; landing_cig" in pagina
    assert "mermaid@11.4.1" in pagina
    assert "non da un'esecuzione sui dati reali" in pagina


def test_indice_sito_licenza_e_link():
    pagina = componi_indice_sito("0.1.0")
    assert "CC BY-SA 4.0" in pagina
    assert (
        "Fonte: ANAC – Autorità Nazionale Anticorruzione, dati.anticorruzione.it, licenza CC BY-SA 4.0"
        in pagina
    )
    assert 'href="dbt/index.html"' in pagina
    assert 'href="dagster/index.html"' in pagina
    assert 'lang="it"' in pagina
