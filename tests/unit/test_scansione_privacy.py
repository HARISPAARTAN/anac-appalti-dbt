"""La scansione di privacy dei file esportati: codici del cognome e del nome, falsi positivi, colonne di testo."""

import duckdb
import pytest

from anac_appalti.scansione_privacy import (
    codice_cognome,
    codice_nome,
    coppie_nome,
    nome_di_persona,
    scansiona_parquet,
)

CF_CONTI = "CNTLRA82C45F839P"  # fittizio: CONTI LAURA
CF_COMPOSTO = "DLGMHL70A01H501X"  # fittizio: DEL GALLO MICHELE


@pytest.mark.parametrize(
    ("parola", "cognome", "nome"),
    [
        ("CONTI", "CNT", "CNT"),
        ("LAURA", "LRA", "LRA"),
        ("ROSSI", "RSS", "RSS"),
        ("MARIO", "MRA", "MRA"),
        ("GIANNI", "GNN", "GNN"),
        ("GIOVANNI", "GVN", "GNN"),  # il nome prende la 1a, 3a e 4a consonante
        ("DE", "DEX", "DEX"),
        ("Ö", "OXX", "OXX"),  # le lettere accentate perdono l'accento,
    ],
)
def test_codici_del_cognome_e_del_nome(parola, cognome, nome):
    assert codice_cognome(parola) == cognome
    assert codice_nome(parola) == nome


def test_il_nome_si_riconosce_in_entrambi_gli_ordini():
    coppie = coppie_nome([CF_CONTI])
    assert nome_di_persona("CONTI LAURA", coppie)
    assert nome_di_persona("Laura Conti", coppie)
    assert nome_di_persona("CONTI LAURA ANNA", coppie)
    assert not nome_di_persona("CONTI", coppie)  # una parola sola non basta
    assert not nome_di_persona("CONTI LAURENTI", coppie)


def test_cognome_di_piu_parole():
    coppie = coppie_nome([CF_COMPOSTO])
    assert nome_di_persona("DEL GALLO MICHELE", coppie)


def test_denominazioni_di_enti_non_sono_nomi():
    coppie = coppie_nome([CF_CONTI])
    # stesse lettere, ma forma giuridica o sigla di ente
    assert not nome_di_persona("COMUNE DI CONTI LAURA", coppie)
    assert not nome_di_persona("CONTI LAURA S.R.L.", coppie)
    assert not nome_di_persona("I.C. CONTI LAURA", coppie)
    assert not nome_di_persona("CONTI LAURA E ALTRI SEI SOCI FONDATORI", coppie)  # troppo lunga


def test_scansione_di_un_parquet(tmp_path):
    percorso = tmp_path / "mart_finto.parquet"
    con = duckdb.connect()
    con.execute(
        "copy (select * from (values ('CONTI LAURA', 'Puglia', 1), ('Comune di Esempio', 'Rssmra80a01h501u x', 2),"
        " ('Comune di Esempio', 'Puglia', 3)) as t(denominazione, regione, n)) "
        f"to '{percorso.as_posix()}' (format parquet)"
    )
    con.close()
    rilievi = scansiona_parquet(percorso, [CF_CONTI])
    assert sorted((r.colonna, r.tipo) for r in rilievi) == [
        ("denominazione", "nome di persona"),
        ("regione", "codice fiscale personale"),
    ]
    # senza codici dell'anagrafe resta solo il controllo sul formato del codice fiscale
    assert [r.tipo for r in scansiona_parquet(percorso, [])] == ["codice fiscale personale"]


def test_elenco_degli_enti_uguale_nella_macro_dbt():
    """La macro dbt `parole_ente` e `MARCATORI_ENTE` sono lo stesso elenco."""
    import re

    from anac_appalti.config import RADICE_PROGETTO
    from anac_appalti.scansione_privacy import MARCATORI_ENTE

    macro = (RADICE_PROGETTO / "dbt" / "macros" / "privacy.sql").read_text(encoding="utf-8")
    elenco = macro.split("macro parole_ente()")[1].split("endmacro")[0]
    assert set(re.findall(r"'([A-Z]+)'", elenco)) == set(MARCATORI_ENTE)
