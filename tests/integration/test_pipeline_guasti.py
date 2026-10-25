"""Percorsi di fallimento: un errore di dbt deve far fallire l'esecuzione Dagster, il log e l'uscita di `appalti run`."""

import duckdb
import pytest
from dagster import DagsterInstance, materialize

from anac_appalti.config import carica_impostazioni
from anac_appalti.definitions import modelli_dbt, risorse_per
from anac_appalti.log_esecuzioni import leggi_log
from anac_appalti.pipeline import esegui_pipeline

pytestmark = pytest.mark.integrazione


@pytest.fixture
def warehouse_occupato(tmp_path):
    """Un altro processo (qui: questo) tiene aperto il file DuckDB: dbt non può aprirlo e fallisce."""
    imp = carica_impostazioni(fixtures=True, mese=1, area=tmp_path)
    imp.warehouse_file.parent.mkdir(parents=True, exist_ok=True)
    connessione = duckdb.connect(str(imp.warehouse_file))
    try:
        yield imp
    finally:
        connessione.close()


def test_dbt_in_errore_fa_fallire_l_esecuzione_dagster(warehouse_occupato):
    risultato = materialize(
        [modelli_dbt],
        resources=risorse_per(warehouse_occupato),
        raise_on_error=False,
        instance=DagsterInstance.ephemeral(),
    )
    assert not risultato.success
    passi = [e.step_key for e in risultato.get_step_failure_events()]
    assert any("modelli_dbt" in passo or "stg_" in passo for passo in passi), passi


def test_dbt_in_errore_porta_esito_errore_nel_log(warehouse_occupato):
    imp = warehouse_occupato
    esito = esegui_pipeline(imp)
    assert not esito.successo
    assert esito.errori, "un'esecuzione fallita deve elencare gli errori"
    assert any("dbt" in e for e in esito.errori), esito.errori
    assert esito.record["esito"] == "errore"
    assert esito.record["errori"] == esito.errori
    (log,) = leggi_log(imp)
    assert log["esito"] == "errore" and log["errori"] == esito.errori
    # le fasi precedenti sono riuscite e restano nel log
    assert sum(v["scaricati"] for v in log["estrazione"].values()) == 18
