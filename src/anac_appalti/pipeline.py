"""Ponte verso dbt: ambiente, variabili, esecuzione in sottoprocesso e run_results.json.

dbt gira sempre in un sottoprocesso: dbt-duckdb tiene aperto il file DuckDB per tutta la vita del processo.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from anac_appalti.config import Impostazioni

ESITI_NEGATIVI = {"error", "fail", "runtime error"}
SORGENTI_DBT = ("models", "macros", "seeds", "tests", "dbt_project.yml", "packages.yml")


class ErroreDbt(RuntimeError):
    """Un comando dbt è terminato con errore."""


def eseguibile_dbt() -> str:
    cartella = Path(sys.executable).parent
    for nome in ("dbt.exe", "dbt"):
        if (cartella / nome).exists():
            return str(cartella / nome)
    trovato = shutil.which("dbt")
    if trovato:
        return trovato
    raise ErroreDbt(f"Eseguibile dbt non trovato accanto a {sys.executable}: esegui `uv sync`.")


def target_dbt(imp: Impostazioni) -> str:
    return "ci" if imp.fixtures else "locale"


def cartella_target(imp: Impostazioni) -> Path:
    return imp.area / "dbt_target"


def percorso_manifest(imp: Impostazioni) -> Path:
    """Manifest per Dagster: uguale per fixture e dati reali, quindi sta nel progetto dbt."""
    return imp.dbt_dir / "target" / "manifest.json"


def variabili_dbt(imp: Impostazioni) -> dict:
    return {
        "anno_minimo": min(imp.anni),
        "data_riferimento": imp.data_riferimento,
        "importo_max_plausibile": imp.soglie.importo_max_plausibile,
        "mad_fattore": imp.soglie.mad_fattore,
        "giorni_scadenza_tasso": imp.soglie.giorni_scadenza_tasso,
    }


def ambiente_dbt(imp: Impostazioni) -> dict[str, str]:
    return {
        "APPALTI_LANDING": imp.landing.as_posix(),
        "APPALTI_DUCKDB": imp.warehouse_file.as_posix(),
        "DBT_PROFILES_DIR": imp.dbt_dir.as_posix(),
        "DBT_TARGET_PATH": cartella_target(imp).as_posix(),
        "DBT_LOG_PATH": (imp.logs / "dbt").as_posix(),
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
    }


def prepara_ambiente_dbt(imp: Impostazioni) -> dict[str, str]:
    imp.warehouse_file.parent.mkdir(parents=True, exist_ok=True)
    imp.landing.mkdir(parents=True, exist_ok=True)
    cartella_target(imp).mkdir(parents=True, exist_ok=True)
    valori = ambiente_dbt(imp)
    os.environ.update(valori)
    return valori


def argomenti_comuni(imp: Impostazioni) -> list[str]:
    return [
        "--project-dir",
        str(imp.dbt_dir),
        "--profiles-dir",
        str(imp.dbt_dir),
        "--target",
        target_dbt(imp),
    ]


def _esegui(argomenti: list[str], cartella: Path) -> int:
    return subprocess.run(
        [eseguibile_dbt(), *argomenti], cwd=cartella, env=os.environ.copy(), check=False
    ).returncode


def installa_pacchetti_dbt(imp: Impostazioni) -> None:
    if (imp.dbt_dir / "dbt_packages" / "dbt_utils").exists():
        return
    codice = _esegui(
        ["deps", "--project-dir", str(imp.dbt_dir), "--profiles-dir", str(imp.dbt_dir)], imp.dbt_dir
    )
    if codice != 0:
        raise ErroreDbt("dbt deps non riuscito")


def esegui_dbt(imp: Impostazioni, comando: list[str], *, variabili: bool = True) -> int:
    prepara_ambiente_dbt(imp)
    installa_pacchetti_dbt(imp)
    argomenti = [*comando, *argomenti_comuni(imp)]
    if variabili:
        argomenti += ["--vars", json.dumps(variabili_dbt(imp))]
    return _esegui(argomenti, imp.dbt_dir)


def _ultima_modifica_sorgenti(dbt_dir: Path) -> float:
    ultima = 0.0
    for nome in SORGENTI_DBT:
        percorso = dbt_dir / nome
        file = [percorso] if percorso.is_file() else [p for p in percorso.rglob("*") if p.is_file()]
        for f in file:
            ultima = max(ultima, f.stat().st_mtime)
    return ultima


def garantisci_manifest(imp: Impostazioni) -> Path:
    """`dbt parse` solo se il manifest manca o è più vecchio dei sorgenti dbt."""
    manifest = percorso_manifest(imp)
    if manifest.exists() and manifest.stat().st_mtime >= _ultima_modifica_sorgenti(imp.dbt_dir):
        return manifest
    prepara_ambiente_dbt(imp)
    installa_pacchetti_dbt(imp)
    argomenti = ["parse", *argomenti_comuni(imp), "--target-path", str(manifest.parent)]
    argomenti += ["--vars", json.dumps(variabili_dbt(imp))]
    if _esegui(argomenti, imp.dbt_dir) != 0 or not manifest.exists():
        raise ErroreDbt("dbt parse non riuscito")
    return manifest


def leggi_run_results(imp: Impostazioni) -> dict | None:
    percorso = cartella_target(imp) / "run_results.json"
    if not percorso.exists():
        return None
    return json.loads(percorso.read_text(encoding="utf-8"))


def salva_run_results(imp: Impostazioni, sorgente: Path) -> Path:
    destinazione = cartella_target(imp) / "run_results.json"
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    if sorgente.resolve() != destinazione.resolve():
        shutil.copyfile(sorgente, destinazione)
    return destinazione


def conteggi_esiti(run_results: dict | None) -> dict[str, int]:
    if not run_results:
        return {}
    return dict(Counter(r["status"] for r in run_results.get("results", [])))


def errori_dbt(run_results: dict | None) -> list[str]:
    if not run_results:
        return []
    return [
        f"{r['unique_id']}: {r.get('message') or ''}".strip()
        for r in run_results.get("results", [])
        if r["status"] in ESITI_NEGATIVI
    ]


def freschezza(imp: Impostazioni) -> dict[str, str]:
    """Stato di freschezza per sorgente (saltato sulla fixture, statica per costruzione)."""
    if imp.fixtures:
        return {}
    codice = esegui_dbt(imp, ["source", "freshness"], variabili=False)
    percorso = cartella_target(imp) / "sources.json"
    if not percorso.exists():
        return {"errore": f"dbt source freshness terminato con codice {codice}"}
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    return {r["unique_id"].removeprefix("source.anac_appalti."): r["status"] for r in dati.get("results", [])}
