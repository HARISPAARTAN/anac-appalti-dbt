"""Client CKAN per dati.anticorruzione.it: rilevamento del WAF, User-Agent di riserva, ritentativi.

Il WAF del portale risponde HTTP 200 con una pagina HTML "Request Rejected": il rifiuto si riconosce dal
corpo, non dallo stato. `SpecchioLocale` legge invece uno specchio su disco (fixture, CI senza rete).
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import httpx

from anac_appalti.config import UA_BROWSER, Impostazioni

log = logging.getLogger(__name__)

RE_SUPPORT_ID = re.compile(rb"support ID is[:\s]*([0-9A-Za-z-]+)", re.IGNORECASE)
STATI_RIPROVABILI = {429, 500, 502, 503, 504}


class WafRifiuto(RuntimeError):
    """Il WAF del portale ANAC ha rifiutato la richiesta anche con lo User-Agent di riserva."""

    def __init__(self, url: str, support_id: str) -> None:
        super().__init__(f"Il portale ANAC ha rifiutato la richiesta {url} (support ID {support_id}).")
        self.url = url
        self.support_id = support_id


class ErroreCkan(RuntimeError):
    """Risposta CKAN inattesa o tentativi esauriti."""


def rileva_waf(corpo: bytes) -> str | None:
    """Restituisce il support ID se il corpo è la pagina di rifiuto del WAF, altrimenti None."""
    inizio = corpo[:4096].lstrip().lower()
    if not (
        inizio.startswith(b"<html") or inizio.startswith(b"<!doctype html") or b"request rejected" in inizio
    ):
        return None
    trovato = RE_SUPPORT_ID.search(corpo)
    return trovato.group(1).decode("ascii", "replace") if trovato else "sconosciuto"


@dataclass(frozen=True)
class Risorsa:
    pacchetto: str
    nome: str
    url: str
    formato: str
    dimensione: int
    last_modified: datetime

    @property
    def file(self) -> str:
        return urlparse(self.url).path.rsplit("/", 1)[-1]


def _data_ckan(valore: str | None) -> datetime:
    return datetime.fromisoformat(valore) if valore else datetime(1970, 1, 1)


def risorse_da_package(dati: dict) -> list[Risorsa]:
    """Risorse CSV di un pacchetto CKAN (`size` CKAN = dimensione del CSV non compresso)."""
    risorse = [
        Risorsa(
            pacchetto=dati["name"],
            nome=r.get("name") or "",
            url=r["url"],
            formato="CSV",
            dimensione=int(r.get("size") or 0),
            last_modified=_data_ckan(r.get("last_modified") or r.get("created")),
        )
        for r in dati.get("resources", [])
        if (r.get("format") or "").upper() == "CSV"
    ]
    return sorted(risorse, key=lambda r: r.file)


class Fonte(Protocol):
    user_agent_usato: str

    def package_show(self, nome: str) -> dict | None: ...

    def scarica(self, url: str, destinazione: Path) -> int: ...

    def leggi_inizio(self, url: str, n_byte: int) -> bytes: ...

    def metadata_modificati(self) -> dict[str, str]: ...


def _json(risposta: httpx.Response, cosa: str) -> dict:
    try:
        return risposta.json()
    except ValueError as exc:
        raise ErroreCkan(f"Risposta non JSON per {cosa}") from exc


class ClientCkan:
    """Client HTTP del portale CKAN di ANAC."""

    def __init__(
        self,
        base_url: str,
        user_agent: str,
        *,
        timeout_s: float = 60.0,
        tentativi: int = 4,
        ua_riserva: str = UA_BROWSER,
        transport: httpx.BaseTransport | None = None,
        attesa: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent_usato = user_agent
        self._ua_riserva = ua_riserva
        self._riserva_usata = user_agent == ua_riserva
        self._tentativi = max(1, tentativi)
        self._attesa = attesa
        self._http = httpx.Client(timeout=timeout_s, transport=transport, follow_redirects=True)

    def _passa_a_riserva(self, support_id: str) -> bool:
        if self._riserva_usata:
            return False
        log.warning(
            "Il WAF ANAC ha rifiutato lo User-Agent %r (support ID %s): uso lo User-Agent di riserva.",
            self.user_agent_usato,
            support_id,
        )
        self.user_agent_usato = self._ua_riserva
        self._riserva_usata = True
        return True

    def _get(self, url: str, intestazioni: dict[str, str] | None = None) -> httpx.Response:
        ultimo: Exception | None = None
        for tentativo in range(self._tentativi):
            try:
                risposta = self._http.get(
                    url, headers={"User-Agent": self.user_agent_usato, **(intestazioni or {})}
                )
            except httpx.TransportError as exc:
                ultimo = exc
            else:
                if risposta.status_code not in STATI_RIPROVABILI:
                    support_id = rileva_waf(risposta.content)
                    if support_id is None:
                        return risposta
                    if self._passa_a_riserva(support_id):
                        continue
                    raise WafRifiuto(url, support_id)
                ultimo = ErroreCkan(f"HTTP {risposta.status_code} su {url}")
            if tentativo < self._tentativi - 1:
                self._attesa(2**tentativo)
        raise ErroreCkan(f"Richiesta non riuscita dopo {self._tentativi} tentativi: {url} ({ultimo})")

    def package_show(self, nome: str) -> dict | None:
        dati = _json(self._get(f"{self.base_url}/api/3/action/package_show?id={nome}"), nome)
        if dati.get("success"):
            return dati["result"]
        if (dati.get("error") or {}).get("__type") == "Not Found Error":
            return None
        raise ErroreCkan(f"package_show {nome}: {dati.get('error')}")

    def metadata_modificati(self) -> dict[str, str]:
        url = f"{self.base_url}/api/3/action/package_search?rows=1000&fl=name,metadata_modified"
        dati = _json(self._get(url), "package_search")
        return {r["name"]: r.get("metadata_modified", "") for r in dati["result"]["results"]}

    def leggi_inizio(self, url: str, n_byte: int) -> bytes:
        risposta = self._get(url, {"Range": f"bytes=0-{n_byte - 1}"})
        risposta.raise_for_status()
        return risposta.content[:n_byte]

    def scarica(self, url: str, destinazione: Path) -> int:
        """Download in streaming su un file `.part`, rinominato solo a download completo."""
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        parziale = destinazione.with_name(destinazione.name + ".part")
        ultimo: Exception | None = None
        for tentativo in range(self._tentativi):
            parziale.unlink(missing_ok=True)
            try:
                with self._http.stream("GET", url, headers={"User-Agent": self.user_agent_usato}) as risposta:
                    if risposta.status_code in STATI_RIPROVABILI:
                        raise ErroreCkan(f"HTTP {risposta.status_code} su {url}")
                    if "html" in risposta.headers.get("content-type", "").lower():
                        support_id = rileva_waf(risposta.read()) or "sconosciuto"
                        if self._passa_a_riserva(support_id):
                            continue
                        raise WafRifiuto(url, support_id)
                    risposta.raise_for_status()
                    scritti = 0
                    with parziale.open("wb") as f:
                        for blocco in risposta.iter_bytes(1 << 20):
                            f.write(blocco)
                            scritti += len(blocco)
                parziale.replace(destinazione)
                return scritti
            except (httpx.TransportError, ErroreCkan) as exc:
                ultimo = exc
                if tentativo < self._tentativi - 1:
                    self._attesa(2**tentativo)
        parziale.unlink(missing_ok=True)
        raise ErroreCkan(f"Download non riuscito dopo {self._tentativi} tentativi: {url} ({ultimo})")


class SpecchioLocale:
    """Specchio CKAN su disco: `ckan/{pacchetto}.json` e `files/{pacchetto}/{file}`."""

    def __init__(self, cartella: Path) -> None:
        self.cartella = cartella
        self.user_agent_usato = "specchio-locale"

    def _file(self, url: str) -> Path:
        parti = urlparse(url).path.split("/")
        pacchetto = parti[parti.index("dataset") + 1]
        return self.cartella / "files" / pacchetto / parti[-1]

    def package_show(self, nome: str) -> dict | None:
        percorso = self.cartella / "ckan" / f"{nome}.json"
        if not percorso.exists():
            return None
        return json.loads(percorso.read_text(encoding="utf-8"))["result"]

    def metadata_modificati(self) -> dict[str, str]:
        return {
            p.stem: json.loads(p.read_text(encoding="utf-8"))["result"]["metadata_modified"]
            for p in sorted((self.cartella / "ckan").glob("*.json"))
        }

    def leggi_inizio(self, url: str, n_byte: int) -> bytes:
        return self._file(url).read_bytes()[:n_byte]

    def scarica(self, url: str, destinazione: Path) -> int:
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._file(url), destinazione)
        return destinazione.stat().st_size


def crea_fonte(imp: Impostazioni) -> Fonte:
    if imp.fixtures and imp.specchio is not None:
        return SpecchioLocale(imp.specchio)
    return ClientCkan(imp.base_url, imp.user_agent, timeout_s=imp.timeout_s, tentativi=imp.tentativi)
