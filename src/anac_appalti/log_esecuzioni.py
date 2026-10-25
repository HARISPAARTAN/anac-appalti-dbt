"""Log di esecuzione: JSON in logs/esecuzioni/ e tabella meta.log_esecuzioni, impronte dei modelli."""

from __future__ import annotations

import json
import platform
import subprocess
import uuid
from datetime import datetime
from importlib import metadata
from pathlib import Path

import duckdb

from anac_appalti.config import Impostazioni

SCHEMI_MODELLI = ("staging", "intermediate", "core", "radar", "seeds")


def nuovo_run_id() -> str:
    return f"{datetime.now():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"


def git_sha(radice: Path) -> str:
    try:
        esito = subprocess.run(
            ["git", "-C", str(radice), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return esito.stdout.strip() if esito.returncode == 0 else ""


def git_modificato(radice: Path) -> bool | None:
    """Vero se l'albero di lavoro ha modifiche non committate (anche file nuovi non ignorati), None se git non
    risponde. Il numero di un'esecuzione con l'albero modificato non è riproducibile dal solo commit."""
    try:
        esito = subprocess.run(
            ["git", "-C", str(radice), "status", "--porcelain"], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return bool(esito.stdout.strip()) if esito.returncode == 0 else None


STRUMENTI = ("dbt-core", "dbt-duckdb", "duckdb", "dagster", "dagster-dbt")


def versioni_strumenti() -> dict[str, str]:
    """Versione di Python e dei pacchetti che producono i numeri (dbt, DuckDB, Dagster)."""
    versioni = {"python": platform.python_version()}
    for nome in STRUMENTI:
        try:
            versioni[nome] = metadata.version(nome)
        except metadata.PackageNotFoundError:
            versioni[nome] = "non installato"
    return versioni


def hash_modelli(percorso_db: Path) -> dict[str, dict[str, object]]:
    """Righe e impronta indipendente dall'ordine (somma degli hash di riga) per ogni tabella o vista dbt."""
    if not percorso_db.exists():
        return {}
    con = duckdb.connect(str(percorso_db))
    try:
        elenco = ", ".join(f"'{s}'" for s in SCHEMI_MODELLI)
        tabelle = con.execute(
            "select table_schema, table_name from information_schema.tables "
            f"where table_catalog = current_database() and table_schema in ({elenco}) order by 1, 2"
        ).fetchall()
        esito: dict[str, dict[str, object]] = {}
        for schema, nome in tabelle:
            righe, impronta = con.execute(
                f'select count(*), coalesce(sum(hash(t)::hugeint), 0) from "{schema}"."{nome}" as t'
            ).fetchone()
            esito[f"{schema}.{nome}"] = {"righe": int(righe), "hash": str(impronta)}
        return esito
    finally:
        con.close()


def _dimensione(percorso: Path) -> int:
    if percorso.is_file():
        return percorso.stat().st_size
    if not percorso.exists():
        return 0
    return sum(p.stat().st_size for p in percorso.rglob("*") if p.is_file())


def uso_disco(imp: Impostazioni) -> dict[str, int]:
    return {
        "raw": _dimensione(imp.raw),
        "landing": _dimensione(imp.landing),
        "warehouse": _dimensione(imp.warehouse_file),
    }


def scrivi_log(imp: Impostazioni, record: dict) -> Path:
    cartella = imp.logs / "esecuzioni"
    cartella.mkdir(parents=True, exist_ok=True)
    percorso = cartella / f"{record['run_id']}.json"
    testo = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    percorso.write_text(testo + "\n", encoding="utf-8", newline="\n")
    imp.warehouse_file.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(imp.warehouse_file))
    try:
        con.execute("create schema if not exists meta")
        con.execute(
            "create table if not exists meta.log_esecuzioni ("
            "run_id varchar primary key, git_sha varchar, inizio timestamp, fine timestamp, esito varchar, dati varchar)"
        )
        con.execute(
            "insert or replace into meta.log_esecuzioni values (?, ?, ?, ?, ?, ?)",
            [
                record["run_id"],
                record.get("git_sha", ""),
                record["inizio"],
                record["fine"],
                record["esito"],
                testo,
            ],
        )
    finally:
        con.close()
    return percorso


def leggi_log(imp: Impostazioni) -> list[dict]:
    return [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted((imp.logs / "esecuzioni").glob("*.json"))
    ]


def leggi_ultimo_log(imp: Impostazioni) -> dict | None:
    file = sorted((imp.logs / "esecuzioni").glob("*.json"))
    if not file:
        return None
    return json.loads(file[-1].read_text(encoding="utf-8"))
