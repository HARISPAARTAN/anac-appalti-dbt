"""Aiuti per i test di integrazione: estrazione e landing dalla fixture, dbt build, query."""

from __future__ import annotations

from pathlib import Path

import duckdb

from anac_appalti.archivio import estrai_pacchetto
from anac_appalti.ckan import crea_fonte
from anac_appalti.config import Impostazioni, carica_impostazioni
from anac_appalti.contratti import carica_contratti
from anac_appalti.landing import atterra_pacchetto
from anac_appalti.pipeline import esegui_dbt


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
    return imp


def interroga(imp: Impostazioni, sql: str) -> list[tuple]:
    con = duckdb.connect(str(imp.warehouse_file))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def uno(imp: Impostazioni, sql: str):
    return interroga(imp, sql)[0][0]
