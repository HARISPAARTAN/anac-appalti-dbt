import random
from datetime import date
from decimal import Decimal

import duckdb
import pytest

from anac_appalti.copertura import verifica_copertura
from anac_appalti.dq_report import calcola_indicatori, scrivi_report
from anac_appalti.export import ATTRIBUZIONE, MART_RADAR, esporta_mart
from anac_appalti.fixture import (
    COMPETITIVE,
    IMPORTO_ENORME,
    IMPORTO_ZERO,
    OLTRE_GARA,
    RIAGGIUDICAZIONE,
    RIBASSO_FUORI_INTERVALLO,
    aggiudicato,
    cig,
    codice_procedura,
    crea_lotti,
    n_offerte,
)
from tests.integration.aiuti import interroga, uno

pytestmark = pytest.mark.integrazione
LOTTI = range(1, 1501)
# Lotti fuori dalle somme: derivati da accordo quadro (i % 25 == 0) e importi anomali (zero, enorme, oltre la gara).
ESCLUSI_DALLE_SOMME = (IMPORTO_ZERO, IMPORTO_ENORME, OLTRE_GARA)
MODELLI_ATTESI = frozenset(
    {
        *(
            "dim_cpv",
            "dim_data",
            "dim_operatori",
            "dim_procedure",
            "dim_stazioni_appaltanti",
            "dim_territorio",
        ),
        *("fct_aggiudicazioni", "fct_lotti", "fct_partecipazioni", "fct_subappalti", "fct_varianti"),
        *("int_aggiudicatari__corrente", "int_aggiudicazioni__corrente", "int_cig__corrente"),
        *("int_cig__versioni", "int_lotti__qualita", "int_operatori", "int_partecipanti__corrente"),
        *("int_perdite_parsing", "int_radar__lotti", "int_riconciliazione", "int_subappalti__corrente"),
        "int_varianti__corrente",
        *MART_RADAR,
        *("stg_anac__aggiudicatari", "stg_anac__aggiudicazioni", "stg_anac__cig", "stg_anac__partecipanti"),
        *("stg_anac__stazioni_appaltanti", "stg_anac__subappalti", "stg_anac__tipi_scelta_contraente"),
        "stg_anac__varianti",
    }
)


def test_dimensioni_e_fatti(magazzino_mese1):
    imp = magazzino_mese1
    assert uno(imp, "select count(*) from core.dim_data") == (date(2031, 1, 1) - date(2007, 1, 1)).days
    assert uno(imp, "select count(*) from core.dim_territorio") == 112
    assert uno(imp, "select count(*) from core.dim_procedure") == 7
    assert uno(imp, "select count(*) from core.dim_cpv") == 6
    assert uno(imp, "select count(*) from core.dim_stazioni_appaltanti") == 13
    assert uno(imp, "select count(*) from core.dim_operatori") == 38
    assert uno(imp, "select count(*) from core.fct_lotti") == 1500
    assert uno(imp, "select count(*) from core.fct_lotti where flag_derivato_da_accordo_quadro") == 60
    assert uno(imp, "select count(*) from core.fct_aggiudicazioni") == 1200
    partecipazioni = sum(n_offerte(i) for i in LOTTI if aggiudicato(i))
    assert uno(imp, "select count(*) from core.fct_partecipazioni") == partecipazioni
    assert uno(imp, "select count(*) from core.fct_partecipazioni where flag_aggiudicatario") == 1199
    assert uno(imp, "select count(*) from core.fct_varianti") == 30
    assert uno(imp, "select count(*) from core.fct_subappalti") == 37
    assert uno(imp, "select count(*) from intermediate.int_radar__lotti") == 1500


def test_mart_radar(magazzino_mese1):
    imp = magazzino_mese1
    for mart in MART_RADAR:
        assert uno(imp, f"select count(*) from radar.{mart}") > 0, mart
    lotti = crea_lotti(random.Random(2026))
    attesa = sum(
        Decimal(f"{lotto.importo:.2f}")
        for lotto in lotti
        if lotto.i % 25 != 0 and lotto.i not in ESCLUSI_DALLE_SOMME
    )
    totale = uno(imp, "select sum(importo_totale) from radar.mart_appalti_regione_mese")
    assert abs(totale - attesa) < Decimal("0.01")
    assert uno(imp, "select sum(n_lotti) from radar.mart_appalti_regione_mese") == 1500
    assert interroga(
        imp, "select sum(n_aggiudicati), sum(n_lotti_scaduti) from radar.mart_tasso_aggiudicazione"
    )[0] == (1200, 1500)
    competitive = [i for i in LOTTI if codice_procedura(i) in COMPETITIVE and aggiudicato(i)]
    unica = sum(1 for i in competitive if n_offerte(i) == 1)
    righe = interroga(
        imp, "select n_lotti_competitivi_aggiudicati, quota_offerta_unica from radar.mart_concorrenza"
    )
    assert sum(n for n, _ in righe) == len(competitive)
    assert round(sum(n * q for n, q in righe)) == unica
    righe = interroga(
        imp,
        "select n_lotti_aggiudicati, quota_lotti_con_variante, quota_subappalto from radar.mart_varianti_subappalti",
    )
    assert round(sum(n * v for n, v, _ in righe)) == 30
    assert round(sum(n * s for n, _, s in righe)) == 37
    tipo = uno(
        imp,
        "select data_type from information_schema.columns "
        "where table_name = 'mart_appalti_regione_mese' and column_name = 'importo_totale'",
    )
    assert tipo == "DECIMAL(18,2)"


def test_ribassi_senza_valori_fuori_range(magazzino_mese1):
    # il ribasso del 120 % (CIG 71) è segnalato, annullato in int_radar__lotti e non entra in mart_ribassi:
    # 1200 lotti aggiudicati, uno escluso. Senza l'esclusione la somma sarebbe 1200 e il p90 del gruppo salirebbe.
    imp = magazzino_mese1
    lotto = interroga(
        imp,
        f"select flag_aggiudicato, ribasso_aggiudicazione from intermediate.int_radar__lotti "
        f"where cig = '{cig(RIBASSO_FUORI_INTERVALLO)}'",
    )
    assert lotto == [(True, None)]
    assert (
        uno(imp, "select count(*) from intermediate.int_radar__lotti where ribasso_aggiudicazione > 100") == 0
    )
    assert uno(imp, "select sum(n_lotti) from radar.mart_ribassi") == 1199
    assert uno(imp, "select max(ribasso_p90) from radar.mart_ribassi") <= 100


def test_qualita_export_copertura(magazzino_mese1, tmp_path):
    imp = magazzino_mese1
    indicatori = calcola_indicatori(imp)
    assert indicatori["duplicati_esatti"] == 3
    # 41 e 42 (scadenza prima della pubblicazione) e 81 (aggiudicazione prima della pubblicazione)
    assert indicatori["date_impossibili"] == 3
    # 51 (zero euro), 52 (nove miliardi), 91 (oltre l'importo della gara)
    assert indicatori["importi_anomali"] == 3
    assert indicatori["senza_aggiudicatario"] == 1
    assert indicatori["ribassi_fuori_range"] == 1
    assert indicatori["righe_persone_fisiche"] == 0
    assert indicatori["file_con_differenza"] == 0
    assert indicatori["importi_non_leggibili"] == 0
    assert indicatori["aggiudicazioni_non_leggibili"] == 0
    assert indicatori["perdite_date"] == 0 and indicatori["valori_date"] > 0
    assert indicatori["perdite_conteggi"] == 0 and indicatori["valori_conteggi"] > 0
    report = scrivi_report(imp, indicatori)
    testo = report.read_text(encoding="utf-8")
    assert "| Date impossibili |" in testo
    assert "| Importo non leggibile |" in testo and "| Date non leggibili |" in testo
    assert testo.endswith(ATTRIBUZIONE + "\n")
    file = esporta_mart(imp, tmp_path / "export")
    assert [p.stem for p in file] == list(MART_RADAR)
    con = duckdb.connect()
    metadati = dict(
        con.execute(f"select key, value from parquet_kv_metadata('{file[0].as_posix()}')").fetchall()
    )
    con.close()
    assert metadati[b"attribuzione"].decode("utf-8") == ATTRIBUZIONE
    copertura = verifica_copertura(imp)
    assert copertura.mancanze == []
    # un manifest vuoto o sbagliato non deve poter passare: il numero e i nomi dei modelli sono fissati
    assert copertura.modelli == copertura.conformi == 40
    assert copertura.quota == 1.0
    assert set(copertura.nomi) == MODELLI_ATTESI
    sql_sul_disco = {p.stem for p in (imp.dbt_dir / "models").rglob("*.sql")}
    assert sql_sul_disco == MODELLI_ATTESI


def test_nessuna_identita_personale_nei_fatti(magazzino_mese1):
    # la fixture non contiene persone fisiche: i membri anonimi esistono ma nessuna partecipazione li usa
    imp = magazzino_mese1
    chiavi = interroga(
        imp, "select operatore_key from core.dim_operatori where tipo_soggetto_privacy <> 'persona_giuridica'"
    )
    assert sorted(c[0] for c in chiavi) == ["NON_VERIFICABILE", "PERSONA_FISICA"]
    assert (
        uno(
            imp,
            "select count(*) from core.fct_partecipazioni where operatore_key in ('PERSONA_FISICA', 'NON_VERIFICABILE')",
        )
        == 0
    )


def test_mese2_cancellazione_e_riaggiudicazione(magazzino_mese2):
    imp = magazzino_mese2
    assert uno(imp, "select count(*) from core.fct_lotti where flag_annullato") == 1
    assert uno(imp, "select count(*) from intermediate.int_radar__lotti") == 1499
    # 1200 di mese 1 + CIG 4 (aggiudicazione nuova) + la riaggiudicazione del CIG 5 (secondo id)
    assert uno(imp, "select count(*) from core.fct_aggiudicazioni") == 1202
    assert (
        uno(imp, f"select count(*) from core.fct_aggiudicazioni where cig = '{cig(RIAGGIUDICAZIONE)}'") == 2
    )
    # lotti aggiudicati: 1200 + CIG 4, meno il CIG 201 cancellato (era aggiudicato ed esce dal Radar)
    assert uno(imp, "select count(*) from intermediate.int_radar__lotti where flag_aggiudicato") == 1200
