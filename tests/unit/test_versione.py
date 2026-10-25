"""La versione è scritta in quattro posti: devono coincidere (e coincidere con l'ultima sezione del CHANGELOG)."""

import re
import tomllib

import yaml

import anac_appalti
from anac_appalti.config import RADICE_PROGETTO, VERSIONE


def test_versione_coincide_nei_quattro_posti():
    pyproject = tomllib.loads((RADICE_PROGETTO / "pyproject.toml").read_text(encoding="utf-8"))
    progetto_dbt = yaml.safe_load((RADICE_PROGETTO / "dbt" / "dbt_project.yml").read_text(encoding="utf-8"))
    assert {
        "pyproject.toml": pyproject["project"]["version"],
        "anac_appalti.__version__": anac_appalti.__version__,
        "config.VERSIONE": VERSIONE,
        "dbt_project.yml": str(progetto_dbt["version"]),
    } == dict.fromkeys(
        ("pyproject.toml", "anac_appalti.__version__", "config.VERSIONE", "dbt_project.yml"), VERSIONE
    )


def test_il_changelog_ha_la_sezione_della_versione_corrente():
    testo = (RADICE_PROGETTO / "CHANGELOG.md").read_text(encoding="utf-8")
    sezioni = re.findall(r"^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$", testo, flags=re.MULTILINE)
    assert sezioni and sezioni[0] == VERSIONE
