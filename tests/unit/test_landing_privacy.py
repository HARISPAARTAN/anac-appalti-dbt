import hashlib
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

from anac_appalti.config import carica_impostazioni
from anac_appalti.contratti import Colonna, Contratto
from anac_appalti.landing import espressione_classe, sql_landing
from anac_appalti.privacy import classifica_codice_fiscale
from tests.unit.landing_aiuti import CONTRATTI, atterra, intestazione, leggi_parquet, registra_csv, riga

CF_A = "RSSMRA80A01H501U"
CF_B = "BNCLRA85M41H501Z"
ESTERO_A = "DE123456789"
ESTERO_B = "FR987654321"
PIVA_1 = "10000104729"
PIVA_2 = "10000209458"


def agg(**valori: str) -> str:
    base = {
        "cig": "FX00000001",
        "ruolo": "MANDANTE",
        "tipo_soggetto": "IMPRESA INDIVIDUALE",
        "id_aggiudicazione": "5000001",
    }
    return riga(CONTRATTI["aggiudicatari"], **(base | valori))


def test_quattro_righe_di_persone_diverse_hanno_quattro_impronte(tmp_path: Path):
    """Riproduzione della review: due persone fisiche e due codici esteri sullo stesso CIG, ruolo e aggiudicazione."""
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    registra_csv(
        imp,
        "aggiudicatari",
        [
            agg(codice_fiscale=CF_A, denominazione="ROSSI MARIO"),
            agg(codice_fiscale=CF_B, denominazione="BIANCHI LAURA"),
            agg(codice_fiscale=ESTERO_A, denominazione="FIRMA ESTERA UNO GMBH"),
            agg(codice_fiscale=ESTERO_B, denominazione="FIRMA ESTERA DUE SA"),
        ],
    )
    riepilogo, voce = atterra(imp, "aggiudicatari")
    assert riepilogo.errori == []
    righe = leggi_parquet(imp, voce)
    assert len(righe) == 4
    assert len({r["_hash_riga"] for r in righe}) == 4
    assert [r["_classe_cf"] for r in righe] == ["persona_fisica"] * 2 + ["non_verificabile"] * 2
    assert [r["_ordinale_riga"] for r in righe] == [1, 2, 3, 4]
    assert all(r["codice_fiscale"] is None and r["denominazione"] is None for r in righe)


def test_righe_con_identita_visibile_restano_duplicati_esatti(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    impresa = agg(codice_fiscale=PIVA_1, denominazione="IMPRESA ESEMPIO 01 S.R.L.", tipo_soggetto="IMPRESA")
    registra_csv(
        imp,
        "aggiudicatari",
        [impresa, impresa, agg(codice_fiscale=CF_A, denominazione="ROSSI MARIO"), agg(codice_fiscale=CF_B)],
    )
    _, voce = atterra(imp, "aggiudicatari")
    righe = leggi_parquet(imp, voce)
    assert righe[0]["_hash_riga"] == righe[1]["_hash_riga"]
    assert len({r["_hash_riga"] for r in righe}) == 3
    assert [r["_classe_cf"] for r in righe] == ["persona_giuridica"] * 2 + ["persona_fisica"] * 2


def test_nessun_valore_annullato_ne_il_suo_hash_nel_parquet(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    personali = [
        (CF_A, "ROSSI MARIO"),
        (CF_B.lower(), "BIANCHI LAURA"),
        (ESTERO_A, "FIRMA ESTERA UNO GMBH"),
        (f" {CF_B} ", "VERDI GIUSEPPE"),
    ]
    registra_csv(
        imp,
        "aggiudicatari",
        [agg(codice_fiscale=cf, denominazione=nome) for cf, nome in personali]
        + [agg(codice_fiscale=PIVA_1, denominazione="IMPRESA ESEMPIO 01 S.R.L.", tipo_soggetto="IMPRESA")],
    )
    _, voce = atterra(imp, "aggiudicatari")
    righe = leggi_parquet(imp, voce)
    celle = [str(v).lower() for r in righe for v in r.values() if v is not None]

    def varianti(valore: str) -> set[str]:
        grezzo = valore.encode()
        chiavi = {valore, valore.strip(), valore.upper(), valore.lower(), valore.strip().upper()}
        impronte = set()
        for k in chiavi:
            for algoritmo in (hashlib.md5, hashlib.sha1, hashlib.sha256):
                impronte.add(algoritmo(k.encode()).hexdigest())
        return {x.lower() for x in chiavi | impronte} | {hashlib.md5(grezzo).hexdigest()}

    for cf, nome in personali:
        for cercato in varianti(cf) | varianti(nome):
            assert not any(cercato in cella for cella in celle), cercato
    # L'impronta di riga calcolata sui valori grezzi (come prima della correzione) non compare.
    for cf, nome in personali:
        grezza = chr(31).join(["FX00000001", "MANDANTE", cf, nome, "IMPRESA INDIVIDUALE", "5000001"])
        assert hashlib.md5(grezza.encode()).hexdigest() not in celle
    # Controllo positivo: la scansione vede i dati che devono restare.
    assert any(PIVA_1 in cella for cella in celle)


def test_ordinale_di_riga_segue_l_ordine_del_file(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    n = 6000
    registra_csv(
        imp,
        "aggiudicatari",
        [
            agg(codice_fiscale=PIVA_1, denominazione="IMPRESA", id_aggiudicazione=str(i))
            for i in range(1, n + 1)
        ],
    )
    _, voce = atterra(imp, "aggiudicatari")
    righe = leggi_parquet(imp, voce)
    assert [r["_ordinale_riga"] for r in righe] == list(range(1, n + 1))
    assert [int(r["id_aggiudicazione"]) for r in righe] == list(range(1, n + 1))


VALORI_LIMITE = [
    (f" {PIVA_1} ", "persona_giuridica", True),
    (f"\t{PIVA_1}", "persona_giuridica", True),
    ("rssmra80a01h501u", "persona_fisica", False),
    (f" {CF_A.lower()} ", "persona_fisica", False),
    ("12345678901234", "non_verificabile", False),
    ("1000010472", "non_verificabile", False),
    ("X12345678901", "non_verificabile", False),
    ("12345678901X", "non_verificabile", False),
    ("   ", "assente", False),
]


@pytest.mark.parametrize(("valore", "classe", "resta"), VALORI_LIMITE)
def test_valori_limite_del_codice_fiscale(tmp_path: Path, valore: str, classe: str, resta: bool):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    registra_csv(imp, "aggiudicatari", [agg(codice_fiscale=valore, denominazione="NOME ESEMPIO")])
    _, voce = atterra(imp, "aggiudicatari")
    (r,) = leggi_parquet(imp, voce)
    assert classifica_codice_fiscale(valore) == classe
    assert r["_classe_cf"] == classe
    assert (r["codice_fiscale"] is not None) is resta
    assert (r["denominazione"] is not None) is resta


def test_classe_sql_e_python_danno_lo_stesso_risultato():
    corpo = [v for v, _, _ in VALORI_LIMITE] + ["", PIVA_1, CF_A, ESTERO_A, "10000104729\n", "ÀÈ0000104729"]
    con = duckdb.connect()
    try:
        for valore in corpo:
            sql = f"select {espressione_classe('v')} from (select ? as v)"
            assert con.execute(sql, [valore]).fetchone()[0] == classifica_codice_fiscale(valore), repr(valore)
    finally:
        con.close()


def test_subappalti_cf_subappaltante_personale_con_subappaltatore_azienda(tmp_path: Path):
    """Caso di fuga della review: `codice_fiscale` di impresa, `cf_subappaltante` di persona fisica."""
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    contratto = CONTRATTI["subappalti"]

    def sub(i: int, cf_sub: str) -> str:
        return riga(
            contratto,
            cig="FX00000040",
            id_subappalto=f"FX00000040|{i}",
            cf_subappaltante=cf_sub,
            codice_fiscale=PIVA_2,
            denominazione="IMPRESA ESEMPIO 02 S.R.L.",
        )

    registra_csv(imp, "subappalti", [sub(1, CF_A), sub(2, CF_B), sub(3, PIVA_1), sub(4, ESTERO_A)])
    riepilogo, voce = atterra(imp, "subappalti")
    assert riepilogo.errori == []
    r1, r2, r3, r4 = leggi_parquet(imp, voce)
    for r in (r1, r2, r4):
        assert r["cf_subappaltante"] is None
        assert r["codice_fiscale"] == PIVA_2 and r["denominazione"] == "IMPRESA ESEMPIO 02 S.R.L."
    assert r3["cf_subappaltante"] == PIVA_1
    assert [r["_classe_cf_subappaltante"] for r in (r1, r2, r3, r4)] == [
        "persona_fisica",
        "persona_fisica",
        "persona_giuridica",
        "non_verificabile",
    ]
    assert {r["_classe_cf"] for r in (r1, r2, r3, r4)} == {"persona_giuridica"}
    # Il subappaltante è stato annullato in tre righe: persone diverse restano righe diverse, senza surrogato.
    assert len({r["_hash_riga"] for r in (r1, r2, r3, r4)}) == 4
    testo = "|".join(str(v) for r in (r1, r2, r3, r4) for v in r.values() if v is not None)
    assert CF_A not in testo and CF_B not in testo and ESTERO_A not in testo


def test_partecipanti_annulla_persone_fisiche(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    contratto = CONTRATTI["partecipanti"]
    base = {"cig": "FX00000007", "ruolo": "OPERATORE ECONOMICO MONOSOGGETTIVO", "tipo_soggetto": "IMPRESA"}
    registra_csv(
        imp,
        "partecipanti",
        [
            riga(contratto, **base, codice_fiscale=CF_A, denominazione="ROSSI MARIO"),
            riga(contratto, **base, codice_fiscale=CF_B, denominazione="BIANCHI LAURA"),
            riga(contratto, **base, codice_fiscale=PIVA_1, denominazione="IMPRESA ESEMPIO 01 S.R.L."),
            riga(contratto, **base, codice_fiscale=PIVA_2, denominazione="IMPRESA ESEMPIO 02 S.R.L."),
            riga(contratto, **base, codice_fiscale=ESTERO_A, denominazione="FIRMA ESTERA GMBH"),
        ],
    )
    riepilogo, voce = atterra(imp, "partecipanti")
    assert riepilogo.errori == []
    righe = leggi_parquet(imp, voce)
    assert [(r["codice_fiscale"], r["denominazione"]) for r in righe] == [
        (None, None),
        (None, None),
        (PIVA_1, "IMPRESA ESEMPIO 01 S.R.L."),
        (PIVA_2, "IMPRESA ESEMPIO 02 S.R.L."),
        (None, None),
    ]
    assert [r["_classe_cf"] for r in righe] == [
        "persona_fisica",
        "persona_fisica",
        "persona_giuridica",
        "persona_giuridica",
        "non_verificabile",
    ]
    # Il numero di partecipanti distinti non dipende dall'identità: cinque righe, cinque impronte.
    assert len({r["_hash_riga"] for r in righe}) == 5
    testo = "|".join(str(v) for r in righe for v in r.values() if v is not None)
    assert CF_A not in testo and "ROSSI MARIO" not in testo and "BIANCHI LAURA" not in testo


def test_contratto_senza_codice_fiscale_annulla_la_denominazione(tmp_path: Path):
    contratto = Contratto(
        tabella="prova",
        pacchetto="prova",
        descrizione="",
        freschezza=False,
        colonne=(
            Colonna("id", "id", "varchar", True, False, ""),
            Colonna("denominazione", "denominazione", "varchar", True, True, ""),
        ),
    )
    sorgente = tmp_path / "prova.csv"
    sorgente.write_text(
        f'{intestazione(contratto)}\n"1";"ROSSI MARIO"\n"2";"IMPRESA SRL"\n', encoding="utf-8"
    )
    destinazione = tmp_path / "prova.parquet"
    sql = sql_landing(
        sorgente, destinazione, contratto, "prova", date(2026, 1, 1), "abc", datetime(2026, 1, 1), False
    )
    con = duckdb.connect()
    try:
        con.execute(sql)
        righe = con.execute(
            f"select id, denominazione, _ordinale_riga from read_parquet('{destinazione.as_posix()}') order by id"
        ).fetchall()
        impronte = con.execute(
            f"select count(distinct _hash_riga) from read_parquet('{destinazione.as_posix()}')"
        )
        distinte = impronte.fetchone()[0]
    finally:
        con.close()
    assert righe == [("1", None, 1), ("2", None, 2)]
    assert distinte == 2


def test_denominazione_che_e_un_codice_fiscale_personale_viene_annullata(tmp_path: Path):
    """Dati reali: una ditta individuale con partita IVA riporta come denominazione il codice fiscale del titolare."""
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    registra_csv(
        imp,
        "aggiudicatari",
        [
            agg(codice_fiscale=PIVA_1, denominazione=CF_A, tipo_soggetto="IMPRESA INDIVIDUALE"),
            agg(codice_fiscale=PIVA_2, denominazione=f"DITTA {CF_B.lower()} DI ESEMPIO"),
            agg(
                codice_fiscale=PIVA_1, denominazione="IMPRESA ESEMPIO 01 S.R.L.", id_aggiudicazione="5000002"
            ),
        ],
    )
    _, voce = atterra(imp, "aggiudicatari")
    righe = leggi_parquet(imp, voce)
    assert [r["codice_fiscale"] for r in righe] == [PIVA_1, PIVA_2, PIVA_1]
    assert [r["denominazione"] for r in righe] == [None, None, "IMPRESA ESEMPIO 01 S.R.L."]
    assert len({r["_hash_riga"] for r in righe}) == 3
    assert not any(CF_A.lower() in str(v).lower() for r in righe for v in r.values() if v is not None)


def test_virgolette_con_backslash_non_assorbono_le_righe_seguenti(tmp_path: Path):
    """Dati reali: ANAC scrive `\\"` dentro un valore. Con escape = '"' la riga assorbiva quelle successive."""
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    righe_csv = [
        agg(
            codice_fiscale=PIVA_1,
            denominazione='FONDAZIONE \\"CIRCOLO ESEMPIO\\" ETS',
            id_aggiudicazione="5000001",
        ),
        agg(codice_fiscale=PIVA_2, denominazione='ASSOCIAZIONE \\"FRANCESCO', id_aggiudicazione="5000002"),
        agg(codice_fiscale=PIVA_1, denominazione="IMPRESA ESEMPIO 01 S.R.L.", id_aggiudicazione="5000003"),
        agg(codice_fiscale=PIVA_2, denominazione="IMPRESA ESEMPIO 02 S.R.L.", id_aggiudicazione="5000004"),
    ]
    registra_csv(imp, "aggiudicatari", righe_csv)
    riepilogo, voce = atterra(imp, "aggiudicatari")
    assert riepilogo.errori == []
    assert voce.righe == "4"
    righe = leggi_parquet(imp, voce)
    assert [r["id_aggiudicazione"] for r in righe] == ["5000001", "5000002", "5000003", "5000004"]
    assert righe[0]["denominazione"] == 'FONDAZIONE "CIRCOLO ESEMPIO" ETS'
