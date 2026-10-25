"""Zona raw: selezione delle risorse, rilevamento delle modifiche, archivio append-only e manifest.

Nulla nella zona raw viene sovrascritto o cancellato dalla pipeline: ANAC rimuove i delta superati quando
pubblica un nuovo file annuale, quindi l'archivio locale è l'unica copia della storia.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
import shutil
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime
from pathlib import Path

from anac_appalti.ckan import Fonte, Risorsa, risorse_da_package
from anac_appalti.config import Impostazioni, Pacchetto

log = logging.getLogger(__name__)
RE_DELTA = re.compile(r"^(\d{8})-")
RE_CIG_ANNUALE = re.compile(r"^cig_csv_\d{4}_\d{2}\.zip$")


class SpazioInsufficiente(RuntimeError):
    """Spazio libero sotto la soglia configurata."""


class ArchivioNonIntegro(RuntimeError):
    """Un file archiviato manca o non ha più lo SHA-256 registrato nel manifest."""


@dataclass(frozen=True)
class VoceManifest:
    pacchetto: str
    tabella: str
    risorsa: str
    url: str
    dimensione: int
    last_modified: str
    sha256: str
    percorso: str
    scaricato_il: str
    righe_attese: str


CAMPI_MANIFEST = [f.name for f in fields(VoceManifest)]


def leggi_manifest(percorso: Path) -> list[VoceManifest]:
    if not percorso.exists():
        return []
    with percorso.open(encoding="utf-8", newline="") as f:
        return [VoceManifest(**{**riga, "dimensione": int(riga["dimensione"])}) for riga in csv.DictReader(f)]


def aggiungi_manifest(percorso: Path, voce: VoceManifest) -> None:
    nuovo = not percorso.exists()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with percorso.open("a", encoding="utf-8", newline="") as f:
        scrittore = csv.DictWriter(f, fieldnames=CAMPI_MANIFEST, lineterminator="\n")
        if nuovo:
            scrittore.writeheader()
        scrittore.writerow(asdict(voce))


def data_snapshot(file: str, last_modified: datetime | str) -> date:
    """Prefisso AAAAMMGG dei delta, altrimenti la data di modifica CKAN della risorsa."""
    trovato = RE_DELTA.match(file)
    if trovato:
        return datetime.strptime(trovato.group(1), "%Y%m%d").date()
    if isinstance(last_modified, str):
        last_modified = datetime.fromisoformat(last_modified)
    return last_modified.date()


def e_log(file: str) -> bool:
    return file.endswith("_csv_logCsv.csv")


def nomi_ckan(pacchetto: Pacchetto, anni: tuple[int, ...]) -> list[str]:
    if pacchetto.annuale:
        return [f"{pacchetto.nome}-{anno}" for anno in anni] + [pacchetto.nome]
    return [pacchetto.nome]


def seleziona_risorse(pacchetto: Pacchetto, cataloghi: dict[str, list[Risorsa]]) -> list[Risorsa]:
    """Log sempre; file completi; delta più recenti dell'ultimo file completo. Log per primi."""
    scelte: list[Risorsa] = []
    if pacchetto.annuale:
        annuali = [r for nome, risorse in cataloghi.items() if nome != pacchetto.nome for r in risorse]
        piene = [r for r in annuali if RE_CIG_ANNUALE.match(r.file)]
        scelte += [r for r in annuali if e_log(r.file)] + piene
        delta_e_log = cataloghi.get(pacchetto.nome, [])
    else:
        risorse = cataloghi.get(pacchetto.nome, [])
        piene = [r for r in risorse if r.file == f"{pacchetto.nome}_csv.zip"]
        scelte += piene
        delta_e_log = risorse
    soglia = max((r.last_modified.date() for r in piene), default=date.min)
    re_delta = re.compile(rf"^\d{{8}}-{re.escape(pacchetto.nome)}_csv\.zip$")
    scelte += [r for r in delta_e_log if e_log(r.file)]
    scelte += [
        r for r in delta_e_log if re_delta.match(r.file) and data_snapshot(r.file, r.last_modified) > soglia
    ]
    return sorted(scelte, key=lambda r: (not e_log(r.file), r.pacchetto, r.file))


def da_scaricare(risorsa: Risorsa, manifest: list[VoceManifest]) -> bool:
    lm = risorsa.last_modified.isoformat()
    return not any(
        v.url == risorsa.url and v.dimensione == risorsa.dimensione and v.last_modified == lm
        for v in manifest
    )


def sha256_file(percorso: Path) -> str:
    h = hashlib.sha256()
    with percorso.open("rb") as f:
        for blocco in iter(lambda: f.read(1 << 20), b""):
            h.update(blocco)
    return h.hexdigest()


def verifica_voce(imp: Impostazioni, voce: VoceManifest) -> str:
    """Ricalcola lo SHA-256 del file archiviato e lo confronta con il manifest; restituisce quello ricalcolato."""
    percorso = imp.area / voce.percorso
    if not percorso.is_file():
        raise ArchivioNonIntegro(f"{voce.risorsa}: il file archiviato manca ({voce.percorso})")
    calcolato = sha256_file(percorso)
    if calcolato != voce.sha256:
        raise ArchivioNonIntegro(
            f"{voce.risorsa}: lo SHA-256 di {voce.percorso} non corrisponde al manifest "
            f"(manifest {voce.sha256[:12]}, file {calcolato[:12]})"
        )
    return calcolato


def controlla_spazio(cartella: Path, soglia_gb: float) -> None:
    cartella.mkdir(parents=True, exist_ok=True)
    libero = shutil.disk_usage(cartella).free / 1e9
    if libero < soglia_gb:
        raise SpazioInsufficiente(
            f"Spazio libero {libero:.1f} GB sotto la soglia di {soglia_gb:g} GB in {cartella}"
        )


def righe_attese_da_log(testo: str) -> dict[str, int]:
    """Righe dichiarate da ANAC per ogni CSV (ultima versione per `ultimaModifica`, intestazione esclusa)."""
    ultimi: dict[str, tuple[str, int]] = {}
    for riga in csv.DictReader(io.StringIO(testo), delimiter=";"):
        if (riga.get("formato") or "").lower() != "csv" or not riga.get("nome_risorsa"):
            continue
        try:
            numero = int(riga["numero_righe"])
        except (TypeError, ValueError):
            continue
        quando = riga.get("ultimaModifica") or ""
        if riga["nome_risorsa"] not in ultimi or quando >= ultimi[riga["nome_risorsa"]][0]:
            ultimi[riga["nome_risorsa"]] = (quando, numero)
    return {nome: valore[1] for nome, valore in ultimi.items()}


def righe_attese_tabella(imp: Impostazioni, tabella: str, manifest: list[VoceManifest]) -> dict[str, int]:
    """Unisce l'ultima versione archiviata di ogni logCsv della tabella."""
    ultimi: dict[str, VoceManifest] = {}
    for voce in manifest:
        if voce.tabella == tabella and e_log(voce.risorsa):
            ultimi[voce.risorsa] = voce
    conteggi: dict[str, int] = {}
    for voce in ultimi.values():
        verifica_voce(imp, voce)
        conteggi.update(
            righe_attese_da_log((imp.area / voce.percorso).read_text(encoding="utf-8", errors="replace"))
        )
    return conteggi


def nome_archivio(risorsa: Risorsa, sha: str) -> str:
    p = Path(risorsa.file)
    return f"{p.stem}__{risorsa.last_modified:%Y%m%dT%H%M}__{sha[:8]}{p.suffix}"


def _controlla_copia(imp: Impostazioni, copia: Path, sha: str, temporaneo: Path, risorsa: Risorsa) -> None:
    """Se la copia archiviata manca o differisce dal download, tiene il download in quarantena e solleva."""
    if copia.is_file() and sha256_file(copia) == sha:
        return
    motivo = "manca" if not copia.is_file() else "ha un contenuto diverso dal download"
    quarantena = imp.tmp / "quarantena" / f"{Path(risorsa.file).stem}__{sha[:8]}{Path(risorsa.file).suffix}"
    quarantena.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(temporaneo, quarantena)
    raise ArchivioNonIntegro(
        f"{risorsa.file}: la copia archiviata {motivo} ({copia}); il download è conservato in {quarantena}"
    )


def archivia(
    fonte: Fonte,
    risorsa: Risorsa,
    imp: Impostazioni,
    pacchetto: Pacchetto,
    manifest: list[VoceManifest],
    righe_attese: dict[str, int],
) -> tuple[VoceManifest, int]:
    controlla_spazio(imp.raw, imp.soglie.spazio_libero_min_gb)
    temporaneo = imp.tmp / "download" / risorsa.file
    byte = fonte.scarica(risorsa.url, temporaneo)
    sha = sha256_file(temporaneo)
    gia_presenti = [v for v in manifest if v.url == risorsa.url and v.sha256 == sha]
    if gia_presenti:
        # Il download fresco si cancella solo se la copia archiviata esiste ed è davvero identica.
        precedente = gia_presenti[-1]
        _controlla_copia(imp, imp.area / precedente.percorso, sha, temporaneo, risorsa)
        percorso = precedente.percorso
        temporaneo.unlink()
    else:
        destinazione = imp.raw / "anac" / risorsa.pacchetto / nome_archivio(risorsa, sha)
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        if destinazione.exists():
            _controlla_copia(imp, destinazione, sha, temporaneo, risorsa)
            temporaneo.unlink()
        else:
            shutil.move(temporaneo, destinazione)
        percorso = destinazione.relative_to(imp.area).as_posix()
    attese = righe_attese.get(Path(risorsa.file).stem + ".csv")
    voce = VoceManifest(
        pacchetto=risorsa.pacchetto,
        tabella=pacchetto.tabella,
        risorsa=risorsa.file,
        url=risorsa.url,
        dimensione=risorsa.dimensione,
        last_modified=risorsa.last_modified.isoformat(),
        sha256=sha,
        percorso=percorso,
        scaricato_il=datetime.now().isoformat(timespec="seconds"),
        righe_attese="" if attese is None else str(attese),
    )
    aggiungi_manifest(imp.manifest_file, voce)
    manifest.append(voce)
    return voce, byte


@dataclass
class RiepilogoEstrazione:
    pacchetto: str
    scaricati: int = 0
    saltati: int = 0
    byte: int = 0
    pacchetti_assenti: list[str] = field(default_factory=list)
    user_agent: str = ""


def estrai_pacchetto(imp: Impostazioni, fonte: Fonte, pacchetto: Pacchetto) -> RiepilogoEstrazione:
    riepilogo = RiepilogoEstrazione(pacchetto=pacchetto.nome)
    cataloghi: dict[str, list[Risorsa]] = {}
    for nome in nomi_ckan(pacchetto, imp.anni):
        dati = fonte.package_show(nome)
        if dati is None:
            log.info("Pacchetto CKAN %s non presente: saltato.", nome)
            riepilogo.pacchetti_assenti.append(nome)
            continue
        cataloghi[nome] = risorse_da_package(dati)
    manifest = leggi_manifest(imp.manifest_file)
    righe_attese = righe_attese_tabella(imp, pacchetto.tabella, manifest)
    for risorsa in seleziona_risorse(pacchetto, cataloghi):
        if not da_scaricare(risorsa, manifest):
            riepilogo.saltati += 1
            continue
        _voce, byte = archivia(fonte, risorsa, imp, pacchetto, manifest, righe_attese)
        riepilogo.scaricati += 1
        riepilogo.byte += byte
        if e_log(risorsa.file):
            righe_attese = righe_attese_tabella(imp, pacchetto.tabella, manifest)
    riepilogo.user_agent = fonte.user_agent_usato
    return riepilogo
