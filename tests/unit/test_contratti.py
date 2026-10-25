import json
import re
from pathlib import Path

import pytest
import yaml

from anac_appalti.config import carica_impostazioni
from anac_appalti.contratti import (
    ContrattoNonValido,
    carica_contratti,
    carica_contratto,
    confronta_schema,
    genera_sources_yml,
)

IMP = carica_impostazioni()
CONTRATTI = carica_contratti(IMP.contratti_dir)
VIETATI = re.compile(r"(^|_)(rup|nome|cognome|responsabile)(_|$)")


def test_un_contratto_per_pacchetto_configurato():
    assert set(CONTRATTI) == {p.tabella for p in IMP.pacchetti}
    for p in IMP.pacchetti:
        assert CONTRATTI[p.tabella].pacchetto == p.nome


def test_contratti_uguali_alle_intestazioni_reali():
    reali = json.loads((IMP.contratti_dir / "_intestazioni_reali.json").read_text(encoding="utf-8"))
    for tabella, contratto in CONTRATTI.items():
        colonne = reali["tabelle"][tabella]["colonne"]
        assert confronta_schema(contratto, colonne).ok, tabella
        assert contratto.sorgenti == colonne, f"{tabella}: ordine o nomi diversi dal file reale"
        assert reali["tabelle"][tabella]["delimitatore"] == ";"


def test_dati_personali_marcati():
    personali = {(t, c.nome) for t, k in CONTRATTI.items() for c in k.colonne if c.dato_personale}
    assert personali == {
        ("aggiudicatari", "codice_fiscale"),
        ("aggiudicatari", "denominazione"),
        ("partecipanti", "codice_fiscale"),
        ("partecipanti", "denominazione"),
        ("subappalti", "cf_subappaltante"),
        ("subappalti", "codice_fiscale"),
        ("subappalti", "denominazione"),
    }


def test_nessuna_colonna_tenuta_con_nome_vietato():
    for contratto in CONTRATTI.values():
        for c in contratto.tenute:
            assert not VIETATI.search(c.nome), f"{contratto.tabella}.{c.nome}"


def test_confronta_schema_mancanti_e_nuove():
    esito = confronta_schema(
        CONTRATTI["aggiudicatari"],
        ["cig", "ruolo", "codice_fiscale", "denominazione", "id_aggiudicazione", "colonna_nuova"],
    )
    assert esito.mancanti == ("tipo_soggetto",)
    assert esito.nuove == ("colonna_nuova",)
    assert not esito.ok


def test_genera_sources():
    testo = genera_sources_yml(CONTRATTI, 40, 75)
    assert testo.startswith("# Generato da `appalti contratti sync`")
    documento = yaml.safe_load(testo)
    tabelle = {t["name"]: t for t in documento["sources"][0]["tables"]}
    assert len(tabelle) == 8
    assert tabelle["cig"]["freshness"]["warn_after"] == {"count": 40, "period": "day"}
    assert "freshness" not in tabelle["stazioni_appaltanti"]
    assert "env_var('APPALTI_LANDING'" in tabelle["cig"]["meta"]["external_location"]
    assert tabelle["cig"]["meta"]["dagster"]["asset_key"] == ["landing_cig"]
    colonne_cig = [c["name"] for c in tabelle["cig"]["columns"]]
    assert "_hash_riga" in colonne_cig and "cui_programma" not in colonne_cig
    assert genera_sources_yml(CONTRATTI, 40, 75) == testo
    # Colonne aggiunte dal landing: ordinale ovunque, classe del codice fiscale solo dove c'è un codice personale.
    for tabella in tabelle.values():
        assert "_ordinale_riga" in [c["name"] for c in tabella["columns"]]
    assert "_classe_cf" in [c["name"] for c in tabelle["aggiudicatari"]["columns"]]
    colonne_sub = [c["name"] for c in tabelle["subappalti"]["columns"]]
    assert "_classe_cf" in colonne_sub and "_classe_cf_subappaltante" in colonne_sub
    assert "_classe_cf" not in colonne_cig


def test_contratto_con_nomi_duplicati(tmp_path: Path):
    p = tmp_path / "x.yml"
    p.write_text(
        yaml.safe_dump(
            {
                "tabella": "x",
                "pacchetto": "x",
                "descrizione": "d",
                "freschezza": False,
                "colonne": [
                    {
                        "nome": "a",
                        "sorgente": "a",
                        "tipo": "varchar",
                        "tenere": True,
                        "dato_personale": False,
                        "descrizione": "d",
                    },
                    {
                        "nome": "a",
                        "sorgente": "b",
                        "tipo": "varchar",
                        "tenere": True,
                        "dato_personale": False,
                        "descrizione": "d",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ContrattoNonValido):
        carica_contratto(p)
