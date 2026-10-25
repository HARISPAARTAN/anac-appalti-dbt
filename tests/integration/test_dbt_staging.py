import duckdb
import pytest

from anac_appalti.fixture import (
    AGGIORNATI,
    AGGIUDICAZIONE_ANTICIPATA,
    AGGIUDICAZIONE_NUOVA,
    AGGIUDICAZIONI_AGGIORNATE,
    CANCELLATO,
    DATE_IMPOSSIBILI,
    DUPLICATI,
    IMPORTO_ENORME,
    IMPORTO_ZERO,
    OLTRE_GARA,
    RIBASSO_FUORI_INTERVALLO,
    SENZA_AGGIUDICATARIO,
    aggiudicato,
    cig,
    n_offerte,
)
from anac_appalti.pipeline import esegui_dbt
from tests.integration.aiuti import interroga, uno

pytestmark = pytest.mark.integrazione


def test_conteggi_mese1(magazzino_mese1):
    imp = magazzino_mese1
    assert uno(imp, "select count(*) from staging.stg_anac__cig") == 1653
    assert uno(imp, "select count(*) from intermediate.int_cig__versioni") == 1500
    assert uno(imp, "select count(*) from intermediate.int_cig__corrente") == 1500
    assert uno(imp, "select sum(n_duplicati_esatti) from intermediate.int_cig__versioni") == 3
    assert uno(imp, "select count(*) from intermediate.int_aggiudicazioni__corrente") == 1200
    assert uno(imp, "select count(*) from intermediate.int_aggiudicatari__corrente") == 1199
    attesi = sum(n_offerte(i) for i in range(1, 1501) if aggiudicato(i))
    assert uno(imp, "select count(*) from intermediate.int_partecipanti__corrente") == attesi
    assert uno(imp, "select count(*) from intermediate.int_varianti__corrente") == 30
    assert uno(imp, "select count(*) from intermediate.int_subappalti__corrente") == 37
    operatori = {i % 40 for i in range(1, 1501) if aggiudicato(i) and i != 61}
    operatori |= {(i + j) % 40 for i in range(1, 1501) if aggiudicato(i) for j in range(n_offerte(i))}
    operatori |= {(i + 7) % 40 for i in range(1, 1501) if i % 40 == 0} | {0}
    assert uno(imp, "select count(*) from intermediate.int_operatori") == len(operatori) == 36
    assert uno(imp, "select count(*) from staging.stg_anac__tipi_scelta_contraente") == 6
    assert uno(imp, "select count(*) from seeds.famiglie_procedura") == 47


FLAG_ATTESI_MESE1 = {
    "flag_duplicato_esatto": set(DUPLICATI),
    "flag_duplicato_conflittuale": set(),
    "flag_data_impossibile": {*DATE_IMPOSSIBILI, AGGIUDICAZIONE_ANTICIPATA},
    "flag_importo_non_positivo": {IMPORTO_ZERO},
    "flag_importo_oltre_gara": {OLTRE_GARA},
    "flag_importo_implausibile": {IMPORTO_ENORME},
    "flag_importo_non_leggibile": set(),
    "flag_importo_mad": {IMPORTO_ENORME},
    "flag_importo_anomalo": {IMPORTO_ZERO, IMPORTO_ENORME, OLTRE_GARA},
    "flag_senza_aggiudicatario": {SENZA_AGGIUDICATARIO},
    "flag_stazione_orfana": set(),
    "flag_ribasso_fuori_range": {RIBASSO_FUORI_INTERVALLO},
    "flag_aggiudicazione_non_leggibile": set(),
}


def lotti_con_flag(imp, flag: str) -> set[str]:
    righe = interroga(imp, f"select cig from intermediate.int_lotti__qualita where {flag}")
    return {r[0] for r in righe}


@pytest.mark.parametrize("flag", sorted(FLAG_ATTESI_MESE1))
def test_flag_qualita_mese1(magazzino_mese1, flag):
    assert lotti_con_flag(magazzino_mese1, flag) == {cig(i) for i in FLAG_ATTESI_MESE1[flag]}


def test_tutti_i_flag_sono_asseriti(magazzino_mese1):
    colonne = interroga(
        magazzino_mese1,
        "select column_name from information_schema.columns "
        "where table_schema = 'intermediate' and table_name = 'int_lotti__qualita' "
        "and starts_with(column_name, 'flag_')",
    )
    assert {c[0] for c in colonne} == set(FLAG_ATTESI_MESE1)


def test_riconciliazione_e_privacy(magazzino_mese1):
    stati = dict(
        interroga(
            magazzino_mese1,
            "select riconciliazione, count(*) from intermediate.int_riconciliazione group by 1",
        )
    )
    assert stati == {"ok": 7, "non_disponibile": 2}
    tipi = interroga(
        magazzino_mese1, "select distinct tipo_soggetto_privacy from staging.stg_anac__partecipanti"
    )
    assert tipi == [("persona_giuridica",)]


def test_delta_mese2(magazzino_mese2):
    imp = magazzino_mese2
    assert uno(imp, "select count(*) from intermediate.int_cig__versioni") == 1551
    assert uno(imp, "select count(*) from intermediate.int_cig__corrente") == 1500
    assert uno(imp, "select count(*) from intermediate.int_cig__corrente where n_versioni = 2") == 51
    assert (
        uno(imp, f"select stato from intermediate.int_cig__corrente where cig = '{cig(CANCELLATO)}'")
        == "CANCELLATO"
    )
    versioni = interroga(
        imp,
        f"select importo_lotto, _data_snapshot from intermediate.int_cig__versioni "
        f"where cig = '{cig(AGGIORNATI[0])}' order by ordine_versione desc",
    )
    (vecchio, _), (nuovo, snapshot) = versioni
    assert abs(float(nuovo) - round(float(vecchio) * 1.1, 2)) < 0.011
    assert str(snapshot) == "2026-04-01"
    assert (
        uno(
            imp,
            f"select importo_lotto from intermediate.int_cig__corrente where cig = '{cig(AGGIORNATI[0])}'",
        )
        == nuovo
    )


def test_delta_aggiudicazioni_mese2(magazzino_mese2):
    imp = magazzino_mese2
    delta = "_risorsa = '20260401-aggiudicazioni_csv'"
    assert uno(imp, "select count(*) from intermediate.int_aggiudicazioni__corrente") == 1201
    assert uno(imp, f"select count(*) from intermediate.int_aggiudicazioni__corrente where {delta}") == 21
    assert (
        uno(imp, "select count(*) from intermediate.int_aggiudicazioni__corrente where n_versioni = 2") == 20
    )
    for i in (AGGIUDICAZIONI_AGGIORNATE[0], AGGIUDICAZIONI_AGGIORNATE[-1]):
        id_aggiudicazione = 5_000_000 + i
        nuovo, vecchio = (
            float(
                uno(
                    imp,
                    f"select importo_aggiudicazione from {tabella} where id_aggiudicazione = {id_aggiudicazione} and {filtro}",
                )
            )
            for tabella, filtro in (
                ("intermediate.int_aggiudicazioni__corrente", "true"),
                ("staging.stg_anac__aggiudicazioni", "_risorsa = 'aggiudicazioni_csv'"),
            )
        )
        assert abs(nuovo - vecchio * 0.97) < 0.02
    nuova = interroga(
        imp,
        f"select _risorsa, n_versioni from intermediate.int_aggiudicazioni__corrente where cig = '{cig(AGGIUDICAZIONE_NUOVA)}'",
    )
    assert nuova == [("20260401-aggiudicazioni_csv", 1)]
    # l'aggiudicazione nuova è senza aggiudicatario: il flag la vede solo dal mese 2
    assert lotti_con_flag(imp, "flag_senza_aggiudicatario") == {
        cig(SENZA_AGGIUDICATARIO),
        cig(AGGIUDICAZIONE_NUOVA),
    }


def test_incrementale_uguale_al_full_refresh(magazzino_mese2):
    """Mese 1 e poi mese 2 con righe cambiate (cig e aggiudicazioni): il risultato incrementale è quello di un full refresh."""
    imp = magazzino_mese2
    modelli = ("int_cig__corrente", "int_aggiudicazioni__corrente")
    con = duckdb.connect(str(imp.warehouse_file))
    try:
        con.execute("create schema if not exists verifica")
        for m in modelli:
            con.execute(f"create or replace table verifica.{m} as select * from intermediate.{m}")
    finally:
        con.close()
    assert esegui_dbt(imp, ["run", "--full-refresh", "--select", *modelli]) == 0
    for m in modelli:
        righe = uno(imp, f"select count(*) from intermediate.{m}")
        assert righe > 0
        assert uno(imp, f"select count(*) from verifica.{m}") == righe
        assert (
            uno(
                imp,
                f"select count(*) from (select * from verifica.{m} except select * from intermediate.{m})",
            )
            == 0
        )
        assert (
            uno(
                imp,
                f"select count(*) from (select * from intermediate.{m} except select * from verifica.{m})",
            )
            == 0
        )
    con = duckdb.connect(str(imp.warehouse_file))
    try:
        con.execute("drop schema verifica cascade")
    finally:
        con.close()
