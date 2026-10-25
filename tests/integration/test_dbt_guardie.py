"""Le guardie sono testate: gli avvisi attesi di dbt, la privacy con persone fisiche vere nei dati e i test che
devono fallire quando un controllo viene svuotato (SQL del controllo reso inerte)."""

from __future__ import annotations

import io
import json
import random
import zipfile

import duckdb
import pytest

from anac_appalti.config import Impostazioni, Pacchetto, carica_impostazioni
from anac_appalti.fixture import (
    COMPETITIVE,
    aggiudicato,
    cig,
    componi,
    crea_lotti,
    csv_anac,
    riga_aggiudicazione,
    riga_cig,
)
from anac_appalti.landing import atterra_pacchetto
from anac_appalti.pipeline import ESITI_NEGATIVI, esegui_dbt, leggi_run_results
from tests.integration.aiuti import esiti_test, estrai_e_atterra, interroga, percorso_esiti, uno
from tests.unit.landing_aiuti import CONTRATTI, LM, registra

pytestmark = pytest.mark.integrazione

# Gli unici avvisi (severità warn con righe) della fixture: i cinque difetti iniettati.
AVVISI_MESE1 = {
    "dq_ribassi_fuori_range": 1,  # CIG 71, ribasso 120 %
    "dq_duplicati_esatti": 3,  # CIG 11, 21, 31
    "dq_importi_anomali": 3,  # CIG 51 (zero), 52 (nove miliardi), 91 (oltre l'importo della gara)
    "dq_date_impossibili": 3,  # CIG 41, 42 (scadenza prima della pubblicazione), 81 (aggiudicazione anticipata)
    "dq_senza_aggiudicatario": 1,  # CIG 61
}
AVVISI_MESE2 = AVVISI_MESE1 | {
    "dq_senza_aggiudicatario": 2
}  # più il CIG 4, aggiudicato dal delta senza aggiudicatario
CONTROLLI_PRIVACY = ("assert_nessun_cf_personale_nei_mart", "assert_nessuna_colonna_personale")


def verifica_esiti(esiti: dict[str, tuple[str, int | None]], avvisi_attesi: dict[str, int]) -> None:
    avvisi = {nome: righe for nome, (stato, righe) in esiti.items() if stato == "warn"}
    assert avvisi == avvisi_attesi
    assert not [nome for nome, (stato, _) in esiti.items() if stato in ESITI_NEGATIVI | {"skipped"}]
    # i controlli che devono essere presenti e superati (nessuna riga), non solo "non falliti"
    for nome in (
        "dq_duplicati_conflittuali",
        "dq_aggiudicazioni_orfane",
        "dq_stazioni_orfane",
        *CONTROLLI_PRIVACY,
    ):
        assert esiti[nome] == ("pass", 0), nome
    assert esiti["assert_riconciliazione"][0] == "pass"
    perdite = {nome: esito for nome, esito in esiti.items() if nome.startswith("source_perdita_parsing_")}
    assert len(perdite) == 7
    assert all(esito == ("pass", 0) for esito in perdite.values()), perdite


def test_avvisi_attesi_mese1(magazzino_mese1):
    esiti = esiti_test(json.loads(percorso_esiti(magazzino_mese1, 1).read_text(encoding="utf-8")))
    verifica_esiti(esiti, AVVISI_MESE1)


def test_avvisi_attesi_mese2(magazzino_mese2):
    esiti = esiti_test(json.loads(percorso_esiti(magazzino_mese2, 2).read_text(encoding="utf-8")))
    verifica_esiti(esiti, AVVISI_MESE2)


# --- persone fisiche attraverso landing e dbt ------------------------------------------------------------------

PERSONE = {
    "RSSMRA80A01H501U": "ROSSI MARIO",
    "BNCLRA85M41H501Z": "BIANCHI LAURA",
    "VRDLCU70T10L219Q": "VERDI LUCA",
    "NRIGPP60D15F205K": "NERI GIUSEPPE",
}
CF_ROSSI, CF_BIANCHI, CF_VERDI, CF_NERI = PERSONE
LOTTO = 3  # aggiudicato, procedura competitiva, nel perimetro del Radar


def aggiungi_file(imp: Impostazioni, tabella: str, righe: list[list[str]]) -> None:
    """Un secondo file della tabella, con nome proprio, registrato nel manifest e atterrato."""
    contratto = CONTRATTI[tabella]
    csv = csv_anac(list(contratto.sorgenti), righe)
    nome = f"zz_extra_{tabella}.zip"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"zz_extra_{tabella}.csv", csv)
    registra(imp, tabella, nome, buffer.getvalue(), LM)
    riepilogo = atterra_pacchetto(imp, Pacchetto(tabella, tabella), contratto)
    assert riepilogo.errori == [], riepilogo.errori


@pytest.fixture(scope="module")
def area_persone(tmp_path_factory) -> Impostazioni:
    """Fixture del mese 1 più persone fisiche in aggiudicatari, partecipanti e subappalti e due valori illeggibili."""
    imp = carica_impostazioni(fixtures=True, mese=1, area=tmp_path_factory.mktemp("persone"))
    estrai_e_atterra(imp)
    lotto = {x.i: x for x in crea_lotti(random.Random(2026))}[LOTTO]
    riga = riga_cig(CONTRATTI["cig"], lotto)
    assert lotto.procedura in COMPETITIVE
    numero = [c.nome for c in CONTRATTI["cig"].colonne]
    riga[numero.index("data_scadenza_offerta")] = "non è una data"
    aggiungi_file(imp, "cig", [riga])
    aggiudicazione = riga_aggiudicazione(CONTRATTI["aggiudicazioni"], lotto)
    nomi_agg = [c.nome for c in CONTRATTI["aggiudicazioni"].colonne]
    aggiudicazione[nomi_agg.index("numero_offerte_ammesse")] = "tre"
    aggiungi_file(imp, "aggiudicazioni", [aggiudicazione])
    cig_lotto = cig(LOTTO)
    assert aggiudicato(LOTTO)
    id_agg = str(5_000_000 + LOTTO)
    aggiungi_file(
        imp,
        "aggiudicatari",
        [
            componi(
                CONTRATTI["aggiudicatari"],
                {
                    "cig": cig_lotto,
                    "ruolo": "MANDANTE",
                    "codice_fiscale": cf,
                    "denominazione": PERSONE[cf],
                    "tipo_soggetto": "IMPRESA INDIVIDUALE",
                    "id_aggiudicazione": id_agg,
                },
            )
            for cf in (CF_ROSSI, CF_BIANCHI)
        ],
    )
    aggiungi_file(
        imp,
        "partecipanti",
        [
            componi(
                CONTRATTI["partecipanti"],
                {
                    "cig": cig_lotto,
                    "ruolo": "MANDANTE",
                    "codice_fiscale": cf,
                    "denominazione": PERSONE[cf],
                    "tipo_soggetto": "IMPRESA INDIVIDUALE",
                },
            )
            for cf in (CF_ROSSI, CF_VERDI)
        ],
    )
    aggiungi_file(
        imp,
        "subappalti",
        [
            componi(
                CONTRATTI["subappalti"],
                {
                    "cig": cig_lotto,
                    "id_subappalto": "ZZ|persona",
                    "cf_subappaltante": CF_NERI,
                    "data_autorizzazione": "2025-03-01",
                    "oggetto": "OPERE ACCESSORIE",
                    "cod_categoria": "OG 1",
                    "classe_importo": "A",
                    "codice_fiscale": CF_VERDI,
                    "denominazione": PERSONE[CF_VERDI],
                    "ruolo": "SUBAPPALTATORE",
                    "tipo_soggetto": "IMPRESA INDIVIDUALE",
                },
            )
        ],
    )
    assert esegui_dbt(imp, ["build"]) == 0, "dbt build non riuscito con persone fisiche nei dati"
    return imp


def valori_identificativi() -> list[str]:
    return [valore.lower() for coppia in PERSONE.items() for valore in coppia]


def contiene_identita(testo: str) -> list[str]:
    testo = testo.lower()
    return [valore for valore in valori_identificativi() if valore in testo]


def test_persone_fisiche_attraversano_gli_strati_senza_identita(area_persone):
    imp = area_persone
    # le persone sono davvero arrivate nei fatti, solo come membro anonimo (una riga per lotto e ruolo, con i conteggi)
    assert interroga(
        imp,
        "select cig, ruolo, n_righe_aggiudicatari, n_righe_partecipanti, flag_aggiudicatario, flag_partecipante "
        "from core.fct_partecipazioni where operatore_key = 'PERSONA_FISICA'",
    ) == [(cig(LOTTO), "MANDANTE", 2, 2, True, True)]
    assert uno(imp, "select count(*) from core.fct_subappalti where operatore_key = 'PERSONA_FISICA'") == 1
    assert (
        uno(imp, "select count(*) from core.fct_subappalti where subappaltante_key = 'PERSONA_FISICA'") == 1
    )
    assert (
        uno(
            imp,
            "select count(*) from staging.stg_anac__aggiudicatari where tipo_soggetto_privacy = 'persona_fisica'",
        )
        == 2
    )
    # nessuna tabella o vista di nessuno schema, e nessun parquet del landing, contiene un codice o un nome
    trovati = []
    con = duckdb.connect(str(imp.warehouse_file), read_only=True)
    try:
        colonne = con.execute(
            "select table_schema, table_name, column_name from information_schema.columns "
            "where data_type = 'VARCHAR' and table_schema in "
            "('staging', 'intermediate', 'core', 'radar', 'seeds', 'audit')"
        ).fetchall()
        assert len({(s, t) for s, t, _ in colonne}) > 40
        for schema, tabella, colonna in colonne:
            condizione = " or ".join(f"lower(\"{colonna}\") like '%{v}%'" for v in valori_identificativi())
            conteggio = con.execute(
                f'select count(*) from "{schema}"."{tabella}" where {condizione}'
            ).fetchone()[0]
            if conteggio:
                trovati.append(f"{schema}.{tabella}.{colonna}")
        for parquet in sorted((imp.landing).rglob("*.parquet")):
            righe = con.execute(f"select * from read_parquet('{parquet.as_posix()}')").fetchall()
            if contiene_identita(repr(righe)):
                trovati.append(parquet.name)
    finally:
        con.close()
    assert trovati == []


def test_perdita_parsing_segnala_i_valori_illeggibili(area_persone):
    esiti = esiti_test(imp=area_persone)
    avvisi = {
        nome: righe for nome, (stato, righe) in esiti.items() if stato == "warn" and "perdita_parsing" in nome
    }
    assert avvisi == {
        "source_perdita_parsing_anac_cig_data_scadenza_offerta__data": 1,
        "source_perdita_parsing_anac_aggiudicazioni_numero_offerte_ammesse__intero": 1,
    }
    assert uno(area_persone, "select sum(n_perdite) from intermediate.int_perdite_parsing") == 2
    assert not [nome for nome, (stato, _) in esiti.items() if stato in ESITI_NEGATIVI | {"skipped"}]
    assert all(esiti[nome] == ("pass", 0) for nome in CONTROLLI_PRIVACY)


# I test seguenti modificano il magazzino di prova (un valore messo apposta in una foglia): vanno per ultimi.


def esegui_test(imp: Impostazioni, selezione: str) -> tuple[int, dict]:
    codice = esegui_dbt(imp, ["test", "--select", selezione])
    return codice, esiti_test(leggi_run_results(imp))


def scrivi(imp: Impostazioni, sql: str) -> None:
    con = duckdb.connect(str(imp.warehouse_file))
    try:
        con.execute(sql)
    finally:
        con.close()


def test_il_controllo_privacy_sui_dati_scatta_su_un_codice_messo_apposta(area_persone):
    imp = area_persone
    scrivi(
        imp,
        f"update core.dim_operatori set denominazione = '{CF_ROSSI}' where operatore_key = 'PERSONA_FISICA'",
    )
    codice, esiti = esegui_test(imp, "assert_nessun_cf_personale_nei_mart")
    assert codice != 0
    assert esiti["assert_nessun_cf_personale_nei_mart"][0] in ESITI_NEGATIVI
    assert esiti["assert_nessun_cf_personale_nei_mart"][1] == 1
    # lo stesso codice dentro una frase e in una chiave
    scrivi(
        imp,
        f"update core.dim_operatori set denominazione = 'Ditta {CF_BIANCHI.lower()}, titolare' where operatore_key = 'PERSONA_FISICA'",
    )
    assert esegui_test(imp, "assert_nessun_cf_personale_nei_mart")[0] != 0
    scrivi(
        imp,
        "update core.dim_operatori set denominazione = 'Persona fisica' where operatore_key = 'PERSONA_FISICA'",
    )
    scrivi(imp, f"update core.fct_subappalti set subappaltante_key = '{CF_VERDI}'")
    assert esegui_test(imp, "assert_nessun_cf_personale_nei_mart")[0] != 0


def test_il_controllo_sui_nomi_di_colonna_scatta_su_una_colonna_personale(area_persone):
    imp = area_persone
    for nome in ("responsabile_procedimento", "nome", "cognome", "rup"):
        scrivi(imp, f"alter table radar.mart_ribassi add column {nome} varchar")
        codice, esiti = esegui_test(imp, "assert_nessuna_colonna_personale")
        assert codice != 0, nome
        assert esiti["assert_nessuna_colonna_personale"][1] == 1, nome
        scrivi(imp, f"alter table radar.mart_ribassi drop column {nome}")
    assert esegui_test(imp, "assert_nessuna_colonna_personale")[0] == 0
