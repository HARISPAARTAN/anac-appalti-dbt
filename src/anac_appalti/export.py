"""Esportazione dei nove mart Radar in Parquet con l'attribuzione CC BY-SA nei metadati del file."""

from __future__ import annotations

from pathlib import Path

import duckdb

from anac_appalti.config import VERSIONE, Impostazioni

MART_RADAR: tuple[str, ...] = (
    "mart_appalti_regione_mese",
    "mart_appalti_settore_cpv",
    "mart_procedure",
    "mart_tasso_aggiudicazione",
    "mart_tempi_aggiudicazione",
    "mart_concorrenza",
    "mart_ribassi",
    "mart_varianti_subappalti",
    "mart_stazioni_appaltanti",
)
ATTRIBUZIONE = "Fonte: ANAC – Autorità Nazionale Anticorruzione, dati.anticorruzione.it, licenza CC BY-SA 4.0; dati elaborati"


def esporta_mart(imp: Impostazioni, destinazione: Path | None = None) -> list[Path]:
    cartella = destinazione or imp.export
    cartella.mkdir(parents=True, exist_ok=True)
    metadati = (
        "{licenza: 'CC BY-SA 4.0', "
        f"attribuzione: '{ATTRIBUZIONE}', "
        "fonte: 'https://dati.anticorruzione.it/opendata', "
        "progetto: 'https://github.com/HARISPAARTAN/anac-appalti-dbt', "
        f"versione: '{VERSIONE}', data_riferimento: '{imp.data_riferimento}'}}"
    )
    scritti = []
    con = duckdb.connect(str(imp.warehouse_file))
    try:
        for mart in MART_RADAR:
            percorso = cartella / f"{mart}.parquet"
            con.execute(
                f"COPY (SELECT * FROM radar.{mart} ORDER BY ALL) TO '{percorso.as_posix()}' "
                f"(FORMAT parquet, COMPRESSION zstd, KV_METADATA {metadati})"
            )
            scritti.append(percorso)
    finally:
        con.close()
    return scritti
