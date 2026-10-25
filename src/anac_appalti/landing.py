"""Landing: ogni zip ANAC diventa un Parquet (una sola volta per sha256), con l'allowlist del contratto.

Colonne mancanti rispetto al contratto: errore, il pacchetto si ferma. Colonne nuove: avviso, non atterrate
finché non entrano nel contratto (privacy per impostazione predefinita).

Privacy al landing (decisione del Task 3): l'archivio raw conserva i file scaricati intatti, ma nessun Parquet
contiene identificativi di persone fisiche. Prima della scrittura, le colonne `dato_personale` del contratto
passano dal classificatore (stesso modello di `anac_appalti.privacy`): il codice fiscale resta solo se è una
partita IVA di 11 cifre (`persona_giuridica`), la denominazione solo se il codice fiscale della stessa riga lo è;
in ogni altro caso (`persona_fisica`, `non_verificabile`, assente) il valore è NULL. Anche `_hash_riga` è calcolato
sui valori già ripuliti. Lo staging dbt annulla gli stessi valori una seconda volta (seconda linea di difesa).
"""

from __future__ import annotations

import csv
import logging
import shutil
import zipfile
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import date, datetime
from pathlib import Path

import duckdb

from anac_appalti.archivio import (
    VoceManifest,
    controlla_spazio,
    data_snapshot,
    leggi_manifest,
    righe_attese_tabella,
)
from anac_appalti.config import Impostazioni, Pacchetto
from anac_appalti.contratti import Colonna, Contratto, confronta_schema
from anac_appalti.privacy import MODELLO_PIVA

log = logging.getLogger(__name__)
ESITI_VALIDI = {"atterrato", "letto_con_scarti"}
OPZIONI_CSV = (
    "delim = ';', quote = '\"', escape = '\"', header = true, all_varchar = true, strict_mode = false"
)


class SchemaNonConforme(RuntimeError):
    """Il file non contiene tutte le colonne del contratto."""


@dataclass(frozen=True)
class VoceRegistro:
    sha256: str
    tabella: str
    pacchetto: str
    risorsa: str
    parquet: str
    righe: str
    righe_attese: str
    riconciliazione: str
    colonne_nuove: str
    data_snapshot: str
    caricato_il: str
    esito: str
    messaggio: str


CAMPI_REGISTRO = [f.name for f in fields(VoceRegistro)]


def leggi_registro(percorso: Path) -> list[VoceRegistro]:
    if not percorso.exists():
        return []
    with percorso.open(encoding="utf-8", newline="") as f:
        return [VoceRegistro(**riga) for riga in csv.DictReader(f)]


def scrivi_registro(percorso: Path, voci: list[VoceRegistro]) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with percorso.open("w", encoding="utf-8", newline="") as f:
        scrittore = csv.DictWriter(f, fieldnames=CAMPI_REGISTRO, lineterminator="\n")
        scrittore.writeheader()
        scrittore.writerows(asdict(v) for v in voci)


def leggi_intestazione_csv(percorso: Path) -> list[str]:
    with percorso.open(encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f, delimiter=";", quotechar='"'))


def _quota(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _letterale(testo: str) -> str:
    return "'" + testo.replace("'", "''") + "'"


def _e_codice_fiscale(colonna: Colonna) -> bool:
    return colonna.sorgente.lower() in ("codice_fiscale", "cf") or colonna.sorgente.lower().startswith("cf_")


def espressione_privacy(contratto: Contratto, colonna: Colonna) -> str:
    """Espressione SQL con cui una colonna entra nel landing: i dati personali passano dal classificatore.

    Un codice fiscale (o una partita IVA) resta solo se, ripulito, è di 11 cifre (`persona_giuridica`); altrimenti è
    NULL. Le altre colonne personali (la denominazione) restano solo se il codice fiscale della stessa riga è di
    11 cifre; se il contratto non ha un `codice_fiscale` da cui dipendere sono sempre NULL.
    """
    riferimento = f"b.{_quota(colonna.sorgente)}"
    if not colonna.dato_personale:
        return riferimento
    if _e_codice_fiscale(colonna):
        return f"CASE WHEN {_e_persona_giuridica(riferimento)} THEN {riferimento} END"
    garante = next(
        (c for c in contratto.colonne if c.sorgente == "codice_fiscale" and c is not colonna), None
    )
    if garante is None:
        return "NULL"
    return f"CASE WHEN {_e_persona_giuridica(f'b.{_quota(garante.sorgente)}')} THEN {riferimento} END"


def _e_persona_giuridica(riferimento: str) -> str:
    return f"regexp_full_match(upper(trim({riferimento})), {_letterale(MODELLO_PIVA)})"


def sql_landing(
    csv_path: Path,
    parquet: Path,
    contratto: Contratto,
    risorsa: str,
    snapshot: date,
    sha: str,
    caricato_il: datetime,
    ignora_errori: bool,
) -> str:
    """SQL del landing. I dati personali sono resi NULL prima di scrivere il Parquet, e anche prima dell'impronta di
    riga: l'MD5 di un codice fiscale di persona fisica sarebbe comunque un identificativo."""
    puliti = ",\n      ".join(
        f"{espressione_privacy(contratto, c)} AS {_quota(c.sorgente)}" for c in contratto.colonne
    )
    selezione = ",\n    ".join(f"{_quota(c.sorgente)} AS {_quota(c.nome)}" for c in contratto.tenute)
    impronta = (
        "md5(concat_ws(chr(31), "
        + ", ".join(f"coalesce({_quota(c.sorgente)}, chr(30))" for c in contratto.colonne)
        + "))"
    )
    opzioni = OPZIONI_CSV + (", ignore_errors = true" if ignora_errori else "")
    return f"""
COPY (
  WITH pulito AS (
    SELECT
      {puliti}
    FROM read_csv({_letterale(csv_path.as_posix())}, {opzioni}) AS b
  )
  SELECT
    {selezione},
    {_letterale(risorsa)} AS _risorsa,
    DATE {_letterale(snapshot.isoformat())} AS _data_snapshot,
    TIMESTAMP {_letterale(caricato_il.isoformat(sep=" ", timespec="seconds"))} AS _caricato_il,
    {_letterale(sha)} AS _sha256,
    {impronta} AS _hash_riga
  FROM pulito
) TO {_letterale(parquet.as_posix())} (FORMAT parquet, COMPRESSION zstd)
"""


def atterra_file(
    imp: Impostazioni, voce: VoceManifest, contratto: Contratto, righe_attese: dict[str, int]
) -> VoceRegistro:
    controlla_spazio(imp.tmp, imp.soglie.spazio_libero_min_gb)
    cartella_tmp = imp.tmp / "landing"
    cartella_tmp.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(imp.area / voce.percorso) as archivio:
        interni = [n for n in archivio.namelist() if n.lower().endswith(".csv")]
        if len(interni) != 1:
            raise RuntimeError(f"{voce.risorsa}: atteso un solo CSV nello zip, trovati {len(interni)}")
        csv_path = cartella_tmp / Path(interni[0]).name
        with archivio.open(interni[0]) as sorgente, csv_path.open("wb") as destinazione:
            shutil.copyfileobj(sorgente, destinazione, 1 << 20)
    try:
        esito_schema = confronta_schema(contratto, leggi_intestazione_csv(csv_path))
        if not esito_schema.ok:
            raise SchemaNonConforme(
                f"{voce.risorsa}: colonne del contratto assenti nel file: {', '.join(esito_schema.mancanti)}"
            )
        stem = Path(voce.risorsa).stem
        snapshot = data_snapshot(voce.risorsa, voce.last_modified)
        parquet = imp.landing / contratto.tabella / f"{stem}__{voce.sha256[:8]}.parquet"
        parquet.parent.mkdir(parents=True, exist_ok=True)
        caricato_il = datetime.now().replace(microsecond=0)
        esito = "atterrato"
        con = duckdb.connect()
        try:
            try:
                con.execute(
                    sql_landing(csv_path, parquet, contratto, stem, snapshot, voce.sha256, caricato_il, False)
                )
            except duckdb.Error as exc:
                log.warning(
                    "%s: lettura rigorosa fallita (%s), riprovo scartando le righe illeggibili.", stem, exc
                )
                con.execute(
                    sql_landing(csv_path, parquet, contratto, stem, snapshot, voce.sha256, caricato_il, True)
                )
                esito = "letto_con_scarti"
            righe = con.execute(
                f"SELECT count(*) FROM read_parquet({_letterale(parquet.as_posix())})"
            ).fetchone()[0]
        finally:
            con.close()
    finally:
        csv_path.unlink(missing_ok=True)
    attese = righe_attese.get(f"{stem}.csv")
    riconciliazione = "non_disponibile" if attese is None else ("ok" if attese == righe else "differenza")
    return VoceRegistro(
        sha256=voce.sha256,
        tabella=contratto.tabella,
        pacchetto=voce.pacchetto,
        risorsa=stem,
        parquet=parquet.relative_to(imp.area).as_posix(),
        righe=str(righe),
        righe_attese="" if attese is None else str(attese),
        riconciliazione=riconciliazione,
        colonne_nuove="|".join(esito_schema.nuove),
        data_snapshot=snapshot.isoformat(),
        caricato_il=caricato_il.isoformat(sep=" "),
        esito=esito,
        messaggio="",
    )


@dataclass
class RiepilogoLanding:
    tabella: str
    atterrati: int = 0
    saltati: int = 0
    righe: dict[str, int] = field(default_factory=dict)
    avvisi: list[str] = field(default_factory=list)
    errori: list[str] = field(default_factory=list)


def _voce_errore(voce: VoceManifest, contratto: Contratto, messaggio: str) -> VoceRegistro:
    return VoceRegistro(
        sha256=voce.sha256,
        tabella=contratto.tabella,
        pacchetto=voce.pacchetto,
        risorsa=Path(voce.risorsa).stem,
        parquet="",
        righe="0",
        righe_attese="",
        riconciliazione="non_disponibile",
        colonne_nuove="",
        data_snapshot="",
        caricato_il=datetime.now().isoformat(sep=" ", timespec="seconds"),
        esito="errore",
        messaggio=messaggio,
    )


def atterra_pacchetto(imp: Impostazioni, pacchetto: Pacchetto, contratto: Contratto) -> RiepilogoLanding:
    riepilogo = RiepilogoLanding(tabella=pacchetto.tabella)
    manifest = leggi_manifest(imp.manifest_file)
    registro = leggi_registro(imp.registro_file)
    righe_attese = righe_attese_tabella(imp, pacchetto.tabella, manifest)
    ultime: dict[str, VoceManifest] = {}
    for voce in manifest:
        if voce.tabella == pacchetto.tabella and voce.risorsa.endswith(".zip"):
            ultime[voce.risorsa] = voce
    for risorsa in sorted(ultime):
        voce = ultime[risorsa]
        if any(r.sha256 == voce.sha256 and r.esito in ESITI_VALIDI for r in registro):
            riepilogo.saltati += 1
            continue
        try:
            nuova = atterra_file(imp, voce, contratto, righe_attese)
        except SchemaNonConforme as exc:
            registro.append(_voce_errore(voce, contratto, str(exc)))
            riepilogo.errori.append(str(exc))
            break
        except Exception as exc:  # un file illeggibile non deve fermare gli altri file
            registro.append(_voce_errore(voce, contratto, str(exc)))
            riepilogo.errori.append(f"{risorsa}: {exc}")
            continue
        for indice, precedente in enumerate(registro):
            if (
                precedente.tabella == nuova.tabella
                and precedente.risorsa == nuova.risorsa
                and precedente.esito in ESITI_VALIDI
            ):
                (imp.area / precedente.parquet).unlink(missing_ok=True)
                registro[indice] = replace(precedente, esito="sostituito")
        registro.append(nuova)
        riepilogo.atterrati += 1
        riepilogo.righe[nuova.risorsa] = int(nuova.righe)
        if nuova.colonne_nuove:
            riepilogo.avvisi.append(f"{nuova.risorsa}: colonne nuove non atterrate: {nuova.colonne_nuove}")
        scrivi_registro(imp.registro_file, registro)
    scrivi_registro(imp.registro_file, registro)
    return riepilogo
