import re
import shutil
from pathlib import Path

import pytest

from anac_appalti.documenti import MARCATORE_FINE, MARCATORE_INIZIO, aggiorna_readme
from anac_appalti.export import ATTRIBUZIONE
from anac_appalti.privacy import cerca_cf_personali

RADICE = Path(__file__).resolve().parents[2]
SEZIONI_IT = [
    "In breve",
    "Architettura",
    "Fonti e licenze",
    "Modello dati",
    "Qualità dei dati",
    "Avvio rapido",
    "Esecuzione completa",
    "Test e CI",
    "Decisioni",
    "Limiti",
    "Roadmap",
]
SEZIONI_EN = [
    "In short",
    "Architecture",
    "Sources and licences",
    "Data model",
    "Data quality",
    "Quick start",
    "Full run",
    "Tests and CI",
    "Decisions",
    "Limitations",
    "Roadmap",
]
GENERATI = {"docs/qualita-dati.md", "docs/ultima-esecuzione.md"}


def leggi(nome: str) -> str:
    return (RADICE / nome).read_text(encoding="utf-8")


def documenti_markdown() -> list[Path]:
    return [
        RADICE / "README.md",
        RADICE / "README.en.md",
        RADICE / "CHANGELOG.md",
        RADICE / "data" / "LICENSE-DATA.md",
        *sorted((RADICE / "docs").rglob("*.md")),
    ]


@pytest.mark.parametrize(("nome", "sezioni"), [("README.md", SEZIONI_IT), ("README.en.md", SEZIONI_EN)])
def test_sezioni_readme(nome, sezioni):
    assert re.findall(r"^## (.+)$", leggi(nome), re.MULTILINE) == sezioni


@pytest.mark.parametrize("nome", ["README.md", "README.en.md", "data/LICENSE-DATA.md"])
def test_attribuzione_testuale(nome):
    assert ATTRIBUZIONE in leggi(nome)


@pytest.mark.parametrize("nome", ["README.md", "README.en.md"])
def test_blocco_numeri_aggiornabile(nome, tmp_path):
    contenuto = leggi(nome)
    assert contenuto.count(MARCATORE_INIZIO) == 1
    assert contenuto.count(MARCATORE_FINE) == 1
    copia = tmp_path / nome
    shutil.copyfile(RADICE / nome, copia)
    assert aggiorna_readme(copia, "| Misura | Valore |\n|---|---:|\n| prova | 1 |") is True
    assert "| prova | 1 |" in copia.read_text(encoding="utf-8")


def blocco_numeri_readme(nome: str) -> str:
    testo = leggi(nome)
    return testo[testo.index(MARCATORE_INIZIO) : testo.index(MARCATORE_FINE)]


def test_blocchi_numeri_dei_due_readme_coincidono():
    """Le cifre (senza separatori di migliaia e decimali) sono le stesse riga per riga in italiano e inglese."""
    righe_it = blocco_numeri_readme("README.md").splitlines()
    righe_en = blocco_numeri_readme("README.en.md").splitlines()
    assert len(righe_it) == len(righe_en)
    cifre_it = [re.findall(r"\d+", riga) for riga in righe_it]
    cifre_en = [re.findall(r"\d+", riga) for riga in righe_en]
    assert cifre_it == cifre_en
    assert any(cifre_it)


@pytest.mark.parametrize("nome", ["README.md", "README.en.md"])
def test_blocco_numeri_nomina_una_sola_esecuzione(nome):
    blocco = blocco_numeri_readme(nome)
    assert len(set(re.findall(r"\d{8}T\d{6}-[0-9a-f]{6}", blocco))) == 1


@pytest.mark.parametrize("nome", ["README.md", "README.en.md", "docs/glossario.md"])
def test_link_relativi_esistono(nome):
    for destinazione in re.findall(r"\]\(([^)\s]+)\)", leggi(nome)):
        if destinazione.startswith(("http://", "https://", "#")):
            continue
        percorso = destinazione.split("#")[0]
        relativo = (Path(nome).parent / percorso).as_posix().removeprefix("./")
        if relativo in GENERATI:
            continue
        assert (RADICE / relativo).exists(), f"{nome}: link rotto {destinazione}"


def test_adr():
    adr = sorted((RADICE / "docs" / "decisioni").glob("ADR-*.md"))
    assert [p.name[:7] for p in adr] == ["ADR-001", "ADR-002", "ADR-003", "ADR-004", "ADR-005"]
    for percorso in adr:
        contenuto = percorso.read_text(encoding="utf-8")
        assert "Stato: accettata" in contenuto, percorso.name
        for sezione in ("## Contesto", "## Decisione", "## Alternative scartate", "## Conseguenze"):
            assert sezione in contenuto, f"{percorso.name}: manca {sezione}"


def test_glossario_trilingue():
    righe = [r for r in leggi("docs/glossario.md").splitlines() if r.startswith("|")]
    assert righe[0] == "| Italiano | English | Deutsch | Nota |"
    voci = righe[2:]
    assert len(voci) >= 30
    for riga in voci:
        celle = [c.strip() for c in riga.strip("|").split("|")]
        assert len(celle) == 4 and all(celle[:3]), riga


def test_changelog():
    assert re.search(r"^## \[(Non rilasciato|\d+\.\d+\.\d+)\]", leggi("CHANGELOG.md"), re.MULTILINE)


def test_nessun_codice_fiscale_personale_nei_documenti():
    for percorso in documenti_markdown():
        assert cerca_cf_personali(percorso.read_text(encoding="utf-8")) == [], percorso.name


@pytest.mark.parametrize("nome", ["README.md", "README.en.md"])
def test_readme_dichiara_che_i_numeri_vengono_dalla_fixture(nome):
    testo = leggi(nome)
    assert "fixture" in testo.lower()
    for indirizzo in (
        "https://harispaartan.github.io/anac-appalti-dbt/dbt/",
        "https://harispaartan.github.io/anac-appalti-dbt/dagster/",
    ):
        assert indirizzo in testo
    assert "cod_esito" in testo and "42" in testo
