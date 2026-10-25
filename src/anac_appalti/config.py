"""Configurazione: appalti.toml più variabili d'ambiente (APPALTI_HOME, APPALTI_USER_AGENT)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

VERSIONE = "0.1.0"
UA_PROGETTO = "anac-appalti-dbt/0.1 (+https://github.com/HARISPAARTAN/anac-appalti-dbt)"
UA_BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
RADICE_PROGETTO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Pacchetto:
    nome: str
    tabella: str
    annuale: bool = False


@dataclass(frozen=True)
class Soglie:
    spazio_libero_min_gb: float
    importo_max_plausibile: float
    mad_fattore: float
    giorni_scadenza_tasso: int
    freschezza_warn_giorni: int
    freschezza_error_giorni: int


@dataclass(frozen=True)
class Impostazioni:
    radice: Path
    area: Path
    anni: tuple[int, ...]
    pacchetti: tuple[Pacchetto, ...]
    base_url: str
    timeout_s: float
    tentativi: int
    user_agent: str
    soglie: Soglie
    fixtures: bool
    mese: int
    data_riferimento: str

    @property
    def raw(self) -> Path:
        return self.area / "data" / "raw"

    @property
    def landing(self) -> Path:
        return self.area / "data" / "landing"

    @property
    def tmp(self) -> Path:
        return self.area / "data" / "tmp"

    @property
    def warehouse_file(self) -> Path:
        return self.area / "data" / "warehouse" / "appalti.duckdb"

    @property
    def export(self) -> Path:
        return self.area / "build" / "export"

    @property
    def logs(self) -> Path:
        return self.area / "logs"

    @property
    def docs(self) -> Path:
        return self.area / "docs" if self.fixtures else self.radice / "docs"

    @property
    def contratti_dir(self) -> Path:
        return self.radice / "contratti" / "anac"

    @property
    def dbt_dir(self) -> Path:
        return self.radice / "dbt"

    @property
    def specchio(self) -> Path | None:
        if not self.fixtures:
            return None
        return self.radice / "data" / "fixtures" / f"mese{self.mese}"

    @property
    def manifest_file(self) -> Path:
        return self.raw / "_manifest.csv"

    @property
    def registro_file(self) -> Path:
        return self.landing / "_registro.csv"

    def pacchetto(self, nome_o_tabella: str) -> Pacchetto:
        for p in self.pacchetti:
            if nome_o_tabella in (p.nome, p.tabella):
                return p
        raise KeyError(f"Pacchetto non configurato: {nome_o_tabella}")


def carica_impostazioni(
    radice: Path | None = None,
    *,
    fixtures: bool = False,
    mese: int = 1,
    area: Path | None = None,
) -> Impostazioni:
    radice = (radice or RADICE_PROGETTO).resolve()
    dati = tomllib.loads((radice / "appalti.toml").read_text(encoding="utf-8"))
    if fixtures and mese not in (1, 2):
        raise ValueError(f"La fixture ha i mesi 1 e 2, non {mese}")
    if area is None:
        ambiente = os.environ.get("APPALTI_HOME", "").strip()
        if fixtures:
            area = radice / "build" / "fixture"
        elif ambiente:
            area = Path(ambiente)
        else:
            area = radice
    if fixtures:
        anni = tuple(int(a) for a in dati["fixture"]["anni"])
        data_riferimento = str(dati["fixture"]["data_riferimento"])
    else:
        anni = tuple(int(a) for a in dati["ambito"]["anni"])
        data_riferimento = date.today().isoformat()
    s = dati["soglie"]
    return Impostazioni(
        radice=radice,
        area=Path(area).resolve(),
        anni=anni,
        pacchetti=tuple(
            Pacchetto(nome=p["nome"], tabella=p["tabella"], annuale=bool(p.get("annuale", False)))
            for p in dati["pacchetti"]
        ),
        base_url=str(dati["ckan"]["base_url"]).rstrip("/"),
        timeout_s=float(dati["ckan"]["timeout_s"]),
        tentativi=int(dati["ckan"]["tentativi"]),
        user_agent=os.environ.get("APPALTI_USER_AGENT", "").strip() or UA_PROGETTO,
        soglie=Soglie(
            spazio_libero_min_gb=float(
                dati["fixture"]["spazio_libero_min_gb"] if fixtures else s["spazio_libero_min_gb"]
            ),
            importo_max_plausibile=float(s["importo_max_plausibile"]),
            mad_fattore=float(s["mad_fattore"]),
            giorni_scadenza_tasso=int(s["giorni_scadenza_tasso"]),
            freschezza_warn_giorni=int(s["freschezza_warn_giorni"]),
            freschezza_error_giorni=int(s["freschezza_error_giorni"]),
        ),
        fixtures=fixtures,
        mese=mese,
        data_riferimento=data_riferimento,
    )
