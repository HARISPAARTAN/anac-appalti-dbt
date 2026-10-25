import pytest

from anac_appalti.fixture import AGGIORNATI, CANCELLATO, aggiudicato, cig, n_offerte
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


def test_flag_qualita_mese1(magazzino_mese1):
    riga = interroga(
        magazzino_mese1,
        """
        select
            count(*) filter (where flag_duplicato_esatto),
            count(*) filter (where flag_data_impossibile),
            count(*) filter (where flag_importo_anomalo),
            count(*) filter (where flag_senza_aggiudicatario),
            count(*) filter (where flag_stazione_orfana),
            count(*) filter (where flag_ribasso_fuori_range),
            count(*) filter (where flag_duplicato_conflittuale)
        from intermediate.int_lotti__qualita
        """,
    )[0]
    assert riga == (3, 2, 2, 1, 0, 0, 0)
    anomali = {
        r[0]
        for r in interroga(
            magazzino_mese1, "select cig from intermediate.int_lotti__qualita where flag_importo_anomalo"
        )
    }
    assert anomali == {cig(51), cig(52)}


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
