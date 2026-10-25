from pathlib import Path

import pytest

from anac_appalti.config import RADICE_PROGETTO, UA_PROGETTO, VERSIONE, carica_impostazioni


def test_impostazioni_reali(monkeypatch):
    monkeypatch.delenv("APPALTI_HOME", raising=False)
    monkeypatch.delenv("APPALTI_USER_AGENT", raising=False)
    imp = carica_impostazioni()
    assert VERSIONE == "0.1.0"
    assert imp.anni == (2024, 2025, 2026)
    assert len(imp.pacchetti) == 8
    assert imp.pacchetto("cig").annuale is True
    assert imp.pacchetto("stazioni-appaltanti").tabella == "stazioni_appaltanti"
    assert imp.pacchetto("tipi_scelta_contraente").nome == "bandi-cig-tipo-scelta-contraente"
    assert imp.user_agent == UA_PROGETTO
    assert imp.area == RADICE_PROGETTO
    assert imp.warehouse_file == RADICE_PROGETTO / "data" / "warehouse" / "appalti.duckdb"
    assert imp.docs == RADICE_PROGETTO / "docs"
    assert imp.specchio is None
    assert imp.soglie.importo_max_plausibile == 5e9
    assert imp.base_url == "https://dati.anticorruzione.it/opendata"


def test_impostazioni_fixture():
    imp = carica_impostazioni(fixtures=True, mese=2)
    assert imp.anni == (2025,)
    assert imp.data_riferimento == "2026-10-25"
    assert imp.area == RADICE_PROGETTO / "build" / "fixture"
    assert imp.docs == imp.area / "docs"
    assert imp.specchio == RADICE_PROGETTO / "data" / "fixtures" / "mese2"
    assert imp.manifest_file == imp.area / "data" / "raw" / "_manifest.csv"
    assert imp.registro_file == imp.area / "data" / "landing" / "_registro.csv"
    assert imp.soglie.spazio_libero_min_gb == 1.0


def test_variabili_ambiente(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APPALTI_HOME", str(tmp_path))
    monkeypatch.setenv("APPALTI_USER_AGENT", "prova/1.0")
    imp = carica_impostazioni()
    assert imp.area == tmp_path
    assert imp.user_agent == "prova/1.0"


def test_area_esplicita_vince(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    assert imp.area == tmp_path
    assert imp.landing == tmp_path / "data" / "landing"


def test_mese_non_valido():
    with pytest.raises(ValueError):
        carica_impostazioni(fixtures=True, mese=3)


def test_pacchetto_sconosciuto():
    with pytest.raises(KeyError):
        carica_impostazioni().pacchetto("ocds")
