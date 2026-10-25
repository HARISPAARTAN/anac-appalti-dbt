import json
from pathlib import Path

import duckdb

from anac_appalti.config import carica_impostazioni
from anac_appalti.log_esecuzioni import hash_modelli, leggi_ultimo_log, nuovo_run_id, scrivi_log


def crea_db(percorso: Path, righe: list[tuple[int, str]]) -> None:
    con = duckdb.connect(str(percorso))
    con.execute("create schema if not exists core")
    con.execute("create or replace table core.t (n integer, s varchar)")
    con.executemany("insert into core.t values (?, ?)", righe)
    con.execute("create schema if not exists audit")
    con.execute("create or replace table audit.ignorata (n integer)")
    con.close()


def test_hash_modelli_indipendente_dall_ordine(tmp_path: Path):
    crea_db(tmp_path / "a.duckdb", [(1, "a"), (2, "b")])
    crea_db(tmp_path / "b.duckdb", [(2, "b"), (1, "a")])
    crea_db(tmp_path / "c.duckdb", [(1, "a"), (2, "c")])
    a, b, c = (hash_modelli(tmp_path / f"{n}.duckdb") for n in "abc")
    assert list(a) == ["core.t"]
    assert a == b
    assert a["core.t"]["righe"] == 2
    assert a["core.t"]["hash"] != c["core.t"]["hash"]
    assert hash_modelli(tmp_path / "assente.duckdb") == {}


def test_scrivi_e_leggi_log(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    run_id = nuovo_run_id()
    record = {
        "run_id": run_id,
        "git_sha": "abc",
        "inizio": "2026-10-25T10:00:00",
        "fine": "2026-10-25T10:01:00",
        "esito": "successo",
    }
    percorso = scrivi_log(imp, record)
    assert json.loads(percorso.read_text(encoding="utf-8"))["run_id"] == run_id
    assert leggi_ultimo_log(imp)["run_id"] == run_id
    con = duckdb.connect(str(imp.warehouse_file))
    assert con.execute("select run_id, esito from meta.log_esecuzioni").fetchall() == [(run_id, "successo")]
    con.close()
