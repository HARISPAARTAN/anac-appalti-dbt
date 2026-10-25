"""Client CKAN per dati.anticorruzione.it: rilevamento del WAF, User-Agent di riserva, ritentativi.

Il WAF del portale risponde HTTP 200 con una pagina HTML "Request Rejected": il rifiuto si riconosce dai
marcatori nel corpo (support ID), non dallo stato e non da un HTML qualunque. `SpecchioLocale` legge invece
uno specchio su disco (fixture, CI senza rete).
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import httpx

from anac_appalti.config import UA_BROWSER, Impostazioni

log = logging.getLogger(__name__)

RE_SUPPORT_ID = re.compile(rb"support ID is[:\s]*([0-9A-Za-z-]+)", re.IGNORECASE)
MARCATORE_WAF = b"<title>request rejected</title>"
STATI_RIPROVABILI = {429, 500, 502, 503, 504}
N_TESTA = 4096


class ErroreCkan(RuntimeError):
    """Risposta CKAN inattesa o tentativi esauriti."""


class ErroreHttp(ErroreCkan):
    """Risposta HTTP di errore non riprovabile (4xx) che non è un rifiuto del WAF."""

    def __init__(self, stato: int, url: str) -> None:
        super().__init__(f"HTTP {stato} su {url}")
        self.stato = stato
        self.url = url


class NonTrovato(ErroreHttp):
    """HTTP 404: la risorsa o il pacchetto non esiste."""


class WafRifiuto(RuntimeError):
    """Il WAF del portale ANAC ha rifiutato la richiesta anche con lo User-Agent di riserva."""

    def __init__(self, url: str, support_id: str, user_agent: str | None = None) -> None:
        dettaglio = f"support ID {support_id}" + (f", User-Agent {user_agent!r}" if user_agent else "")
        super().__init__(f"Il portale ANAC ha rifiutato la richiesta {url} ({dettaglio}).")
        self.url = url
        self.support_id = support_id
        self.user_agent = user_agent


def rileva_waf(corpo: bytes) -> str | None:
    """Support ID se il corpo è la pagina di rifiuto del WAF, altrimenti None.

    Il verdetto richiede i marcatori del WAF ("Your support ID is ..." o il titolo "Request Rejected"):
    una pagina HTML qualunque (per esempio un 404) non è un rifiuto del WAF.
    """
    inizio = corpo[:N_TESTA]
    trovato = RE_SUPPORT_ID.search(inizio)
    if trovato:
        return trovato.group(1).decode("ascii", "replace")
    if MARCATORE_WAF in inizio.lower():
        return "sconosciuto"
    return None


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

    def close(self) -> None: ...


@dataclass(frozen=True)
class _Risposta:
    stato: int
    corpo: bytes


def _errore_http(stato: int, url: str) -> ErroreHttp:
    return (NonTrovato if stato == 404 else ErroreHttp)(stato, url)


def _json(risposta: _Risposta, cosa: str, url: str) -> dict:
    """Corpo JSON di una risposta; un errore HTTP senza JSON (per esempio una pagina HTML 404) è un errore HTTP."""
    try:
        dati = json.loads(risposta.corpo)
    except ValueError as exc:
        if risposta.stato >= 400:
            raise _errore_http(risposta.stato, url) from exc
        raise ErroreCkan(f"Risposta non JSON per {cosa}") from exc
    if not isinstance(dati, dict):
        raise ErroreCkan(f"Risposta JSON inattesa per {cosa}")
    return dati


def _leggi_testa(blocchi: Iterator[bytes], n_byte: int) -> bytes:
    """Legge dal flusso almeno `n_byte` (o fino alla fine) senza chiuderlo: il resto si legge dopo."""
    testa = b""
    for blocco in blocchi:
        testa += blocco
        if len(testa) >= n_byte:
            break
    return testa


class ClientCkan:
    """Client HTTP del portale CKAN di ANAC (da usare come context manager, oppure chiamare `close`)."""

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

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> ClientCkan:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

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

    def _richiedi[T](
        self,
        url: str,
        consuma: Callable[[httpx.Response, bytes, Iterator[bytes]], T],
        intestazioni: dict[str, str] | None = None,
        *,
        testa_206: int = N_TESTA,
    ) -> T:
        """GET in streaming con ritentativi e User-Agent di riserva.

        Per ogni risposta non riprovabile legge la testa del corpo, la confronta con i marcatori del WAF e poi
        passa risposta, testa e resto del flusso a `consuma`. Il cambio di User-Agent dopo un rifiuto del WAF
        ripete lo stesso tentativo: non ne consuma uno.
        """
        ultimo: Exception | None = None
        numero = 0
        while numero < self._tentativi:
            try:
                with self._http.stream(
                    "GET", url, headers={"User-Agent": self.user_agent_usato, **(intestazioni or {})}
                ) as risposta:
                    if risposta.status_code in STATI_RIPROVABILI:
                        ultimo = ErroreCkan(f"HTTP {risposta.status_code} su {url}")
                    else:
                        blocchi = risposta.iter_bytes()
                        n_testa = min(N_TESTA, testa_206) if risposta.status_code == 206 else N_TESTA
                        testa = _leggi_testa(blocchi, n_testa)
                        support_id = rileva_waf(testa)
                        if support_id is None:
                            return consuma(risposta, testa, blocchi)
                        if self._passa_a_riserva(support_id):
                            continue
                        raise WafRifiuto(url, support_id, self.user_agent_usato)
            except httpx.TransportError as exc:
                ultimo = exc
            numero += 1
            if numero < self._tentativi:
                self._attesa(2 ** (numero - 1))
        raise ErroreCkan(
            f"Richiesta non riuscita dopo {self._tentativi} tentativi: {url} "
            f"({ultimo}; ultimo User-Agent {self.user_agent_usato!r})"
        )

    def _get(self, url: str) -> _Risposta:
        def consuma(risposta: httpx.Response, testa: bytes, blocchi: Iterator[bytes]) -> _Risposta:
            return _Risposta(risposta.status_code, testa + b"".join(blocchi))

        return self._richiedi(url, consuma)

    def package_show(self, nome: str) -> dict | None:
        url = f"{self.base_url}/api/3/action/package_show?id={nome}"
        dati = _json(self._get(url), nome, url)
        if dati.get("success"):
            return dati["result"]
        if (dati.get("error") or {}).get("__type") == "Not Found Error":
            return None
        raise ErroreCkan(f"package_show {nome}: {dati.get('error')}")

    def metadata_modificati(self) -> dict[str, str]:
        url = f"{self.base_url}/api/3/action/package_search?rows=1000&fl=name,metadata_modified"
        dati = _json(self._get(url), "package_search", url)
        return {r["name"]: r.get("metadata_modified", "") for r in dati["result"]["results"]}

    def leggi_inizio(self, url: str, n_byte: int) -> bytes:
        """Primi `n_byte` byte con una richiesta Range: serve un 206 e non si leggono mai più byte del dovuto."""

        def consuma(risposta: httpx.Response, testa: bytes, blocchi: Iterator[bytes]) -> bytes:
            if risposta.status_code >= 400:
                raise _errore_http(risposta.status_code, url)
            if risposta.status_code != 206:
                raise ErroreCkan(
                    f"Il portale ha ignorato la richiesta Range (HTTP {risposta.status_code}, atteso 206): {url}"
                )
            dati = testa
            while len(dati) < n_byte:
                blocco = next(blocchi, None)
                if blocco is None:
                    break
                dati += blocco
            return dati[:n_byte]

        return self._richiedi(url, consuma, {"Range": f"bytes=0-{n_byte - 1}"}, testa_206=n_byte)

    def scarica(self, url: str, destinazione: Path) -> int:
        """Download in streaming su un file `.part`, rinominato solo a download completo."""
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        parziale = destinazione.with_name(destinazione.name + ".part")

        def consuma(risposta: httpx.Response, testa: bytes, blocchi: Iterator[bytes]) -> int:
            if risposta.status_code >= 400:
                raise _errore_http(risposta.status_code, url)
            if "html" in risposta.headers.get("content-type", "").lower():
                raise ErroreCkan(f"Risposta HTML inattesa (non è un rifiuto del WAF): {url}")
            if destinazione.suffix.lower() == ".zip" and not testa.startswith(b"PK"):
                raise ErroreCkan(f"Il contenuto scaricato non è uno zip: {url}")
            scritti = len(testa)
            with parziale.open("wb") as f:
                f.write(testa)
                for blocco in blocchi:
                    f.write(blocco)
                    scritti += len(blocco)
            parziale.replace(destinazione)
            return scritti

        try:
            return self._richiedi(url, consuma)
        finally:
            parziale.unlink(missing_ok=True)


class SpecchioLocale:
    """Specchio CKAN su disco: `ckan/{pacchetto}.json` e `files/{pacchetto}/{file}`."""

    def __init__(self, cartella: Path) -> None:
        self.cartella = cartella
        self.user_agent_usato = "specchio-locale"

    def close(self) -> None:
        """Niente da chiudere: stessa interfaccia di `ClientCkan`."""

    def __enter__(self) -> SpecchioLocale:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

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
