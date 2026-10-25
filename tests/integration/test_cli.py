"""Comandi `appalti run`, `report`, `export`, `copertura-test` e `docs` sulla fixture, in un'area temporanea."""

import shutil

import duckdb
import pytest
from typer.testing import CliRunner

from anac_appalti import cli
from anac_appalti.config import carica_impostazioni
from anac_appalti.log_esecuzioni import leggi_log

pytestmark = pytest.mark.integrazione

RUNNER = CliRunner()


def _punta_all_area(monkeypatch, area):
    """I comandi con --fixtures usano build/fixture del repository: qui li spostiamo in una cartella di prova."""
    monkeypatch.setattr(cli, "carica_impostazioni", lambda **kw: carica_impostazioni(area=area, **kw))


@pytest.fixture(scope="module")
def area(tmp_path_factory):
    cartella = tmp_path_factory.mktemp("cli")
    with pytest.MonkeyPatch.context() as mp:
        _punta_all_area(mp, cartella)
        esito = RUNNER.invoke(cli.app, ["run", "--fixtures"])
        assert esito.exit_code == 0, esito.output
        yield cartella, esito


def test_run_scrive_il_log_di_successo(area):
    cartella, esito = area
    assert "successo" in esito.output
    (log,) = leggi_log(carica_impostazioni(fixtures=True, area=cartella))
    assert log["esito"] == "successo" and log["errori"] == []
    assert log["dbt"]["n_modelli"] == 41 and log["dbt"]["esiti"]["warn"] == 5


def test_report_marca_il_report_della_fixture(area):
    cartella, _ = area
    esito = RUNNER.invoke(cli.app, ["report", "--fixtures"])
    assert esito.exit_code == 0, esito.output
    qualita = (cartella / "docs" / "qualita-dati.md").read_text(encoding="utf-8")
    assert qualita.splitlines()[0] == "# Qualità dei dati (report sulla fixture sintetica)"
    assert "non dei dati ANAC reali" in qualita
    assert (cartella / "docs" / "ultima-esecuzione.md").exists()


def test_export_scrive_i_nove_mart(area):
    cartella, _ = area
    esito = RUNNER.invoke(cli.app, ["export", "--fixtures"])
    assert esito.exit_code == 0, esito.output
    file = sorted((cartella / "build" / "export").glob("*.parquet"))
    assert len(file) == 9 and all(p.name.startswith("mart_") for p in file)


def test_copertura_test_conforme(area):
    esito = RUNNER.invoke(cli.app, ["copertura-test", "--fixtures"])
    assert esito.exit_code == 0, esito.output
    assert "Modelli conformi: 41/41" in esito.output


def test_docs_scrive_il_sito(area):
    esito = RUNNER.invoke(cli.app, ["docs", "--fixtures"])
    assert esito.exit_code == 0, esito.output
    sito = carica_impostazioni(fixtures=True).radice / "build" / "sito"
    assert (sito / "index.html").exists()
    assert (sito / "dbt" / "index.html").stat().st_size > 100_000
    assert "raw_cig" in (sito / "dagster" / "index.html").read_text(encoding="utf-8")


def test_run_con_zip_corrotto_esce_con_1_e_registra_l_errore(tmp_path, monkeypatch):
    _punta_all_area(monkeypatch, tmp_path)
    base = ["run", "--fixtures", "--solo-estrazione", "--pacchetti", "varianti"]
    assert RUNNER.invoke(cli.app, base).exit_code == 0
    (zip_raw,) = (tmp_path / "data" / "raw" / "anac" / "varianti").glob("varianti_csv__*.zip")
    with zip_raw.open("ab") as f:
        f.write(b"corrotto")
    shutil.rmtree(tmp_path / "data" / "landing")

    esito = RUNNER.invoke(cli.app, [*base, "--da-archivio"])
    assert esito.exit_code == 1, esito.output
    assert "errore" in esito.output
    # i run_id hanno la risoluzione del secondo: due esecuzioni ravvicinate non hanno un ordine garantito
    log_tutti = leggi_log(carica_impostazioni(fixtures=True, area=tmp_path))
    assert sorted(log["esito"] for log in log_tutti) == ["errore", "successo"]
    (log,) = (log for log in log_tutti if log["esito"] == "errore")
    assert any("landing_varianti" in e for e in log["errori"]), log["errori"]
    con = duckdb.connect(str(tmp_path / "data" / "warehouse" / "appalti.duckdb"), read_only=True)
    try:
        registrato = con.execute("select esito from meta.log_esecuzioni order by esito").fetchall()
    finally:
        con.close()
    assert registrato == [("errore",), ("successo",)]
