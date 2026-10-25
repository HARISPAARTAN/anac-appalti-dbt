"""Aiuti per i test di integrazione: estrazione e landing dalla fixture, dbt build, query."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb

from anac_appalti.archivio import estrai_pacchetto
from anac_appalti.ckan import crea_fonte
from anac_appalti.config import Impostazioni, carica_impostazioni
from anac_appalti.contratti import carica_contratti
from anac_appalti.landing import atterra_pacchetto
from anac_appalti.pipeline import cartella_target, esegui_dbt, leggi_run_results


def estrai_e_atterra(imp: Impostazioni) -> None:
    fonte = crea_fonte(imp)
    contratti = carica_contratti(imp.contratti_dir)
    for pacchetto in imp.pacchetti:
        estrai_pacchetto(imp, fonte, pacchetto)
        riepilogo = atterra_pacchetto(imp, pacchetto, contratti[pacchetto.tabella])
        assert riepilogo.errori == [], riepilogo.errori


def esegui_mese(area: Path, mese: int) -> Impostazioni:
    imp = carica_impostazioni(fixtures=True, mese=mese, area=area)
    estrai_e_atterra(imp)
    assert esegui_dbt(imp, ["build"]) == 0, "dbt build non riuscito: vedi l'output sopra"
    # run_results.json viene sovrascritto da ogni comando dbt: una copia per mese resta a disposizione dei test
    shutil.copyfile(cartella_target(imp) / "run_results.json", percorso_esiti(imp, mese))
    return imp


def percorso_esiti(imp: Impostazioni, mese: int) -> Path:
    return cartella_target(imp) / f"run_results_mese{mese}.json"


def esiti_test(
    run_results: dict | None = None, *, imp: Impostazioni | None = None
) -> dict[str, tuple[str, int | None]]:
    """Esito di ogni test dati (non unit test) di un run_results: nome -> (status, righe che falliscono)."""
    if run_results is None:
        run_results = leggi_run_results(imp)
    assert run_results is not None, "run_results.json mancante"
    esiti = {}
    for r in run_results["results"]:
        parti = r["unique_id"].split(".")
        if parti[0] == "test":
            esiti[parti[2]] = (r["status"], r.get("failures"))
    return esiti


def interroga(imp: Impostazioni, sql: str) -> list[tuple]:
    con = duckdb.connect(str(imp.warehouse_file))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def uno(imp: Impostazioni, sql: str):
    return interroga(imp, sql)[0][0]
