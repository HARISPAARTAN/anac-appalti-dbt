"""Aiuti condivisi dai test del landing: archivio finto con nomi di produzione, CSV e zip sintetici."""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import datetime

import duckdb

from anac_appalti.archivio import VoceManifest, aggiungi_manifest
from anac_appalti.config import Impostazioni, Pacchetto, carica_impostazioni
from anac_appalti.contratti import Contratto, carica_contratti
from anac_appalti.landing import RiepilogoLanding, VoceRegistro, atterra_pacchetto, leggi_registro

CONTRATTI = carica_contratti(carica_impostazioni().contratti_dir)
LM = "2026-01-23T00:00:00"


def intestazione(contratto: Contratto) -> str:
    return ";".join(f'"{s}"' for s in contratto.sorgenti)


def riga(contratto: Contratto, **valori: str) -> str:
    """Riga CSV nel formato ANAC: valori fra virgolette, vuoti non quotati."""
    sconosciute = set(valori) - set(contratto.sorgenti)
    assert not sconosciute, sconosciute
    return ";".join(f'"{valori[s]}"' if valori.get(s) else "" for s in contratto.sorgenti)


def zip_di(nome_csv: str, righe: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(nome_csv, "\n".join(righe) + "\n")
    return buffer.getvalue()


def registra(imp: Impostazioni, tabella: str, nome: str, contenuto: bytes, lm: str = LM) -> VoceManifest:
    """Archivia `contenuto` come farebbe `archivia` (nome `stem__ts__sha8`) e aggiunge la riga di manifest."""
    sha = hashlib.sha256(contenuto).hexdigest()
    stem, suffisso = nome.rsplit(".", 1)
    percorso = (
        imp.raw / "anac" / tabella / f"{stem}__{datetime.fromisoformat(lm):%Y%m%dT%H%M}__{sha[:8]}.{suffisso}"
    )
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_bytes(contenuto)
    voce = VoceManifest(
        pacchetto=tabella,
        tabella=tabella,
        risorsa=nome,
        url=f"https://x/{tabella}/{nome}",
        dimensione=len(contenuto),
        last_modified=lm,
        sha256=sha,
        percorso=percorso.relative_to(imp.area).as_posix(),
        scaricato_il=datetime.now().isoformat(),
        righe_attese="",
    )
    aggiungi_manifest(imp.manifest_file, voce)
    return voce


def registra_csv(imp: Impostazioni, tabella: str, righe: list[str], lm: str = LM) -> VoceManifest:
    contratto = CONTRATTI[tabella]
    return registra(
        imp,
        tabella,
        f"{tabella}_csv.zip",
        zip_di(f"{tabella}_csv.csv", [intestazione(contratto), *righe]),
        lm,
    )


def registra_log(imp: Impostazioni, tabella: str, n: int, lm: str = LM) -> VoceManifest:
    testo = (
        "identifier;nome_dataset;nome_risorsa;numero_righe;formato;data;ultimaModifica\n\n"
        f"{tabella};{tabella};{tabella}_csv.csv;{n};csv;28-10-2022;2026-01-23T13:01:01.912\n"
    )
    return registra(imp, tabella, f"{tabella}_csv_logCsv.csv", testo.encode(), lm)


def atterra(imp: Impostazioni, tabella: str) -> tuple[RiepilogoLanding, VoceRegistro]:
    riepilogo = atterra_pacchetto(imp, Pacchetto(tabella, tabella), CONTRATTI[tabella])
    return riepilogo, leggi_registro(imp.registro_file)[-1]


def leggi_parquet(imp: Impostazioni, voce: VoceRegistro) -> list[dict]:
    percorso = (imp.area / voce.parquet).as_posix()
    con = duckdb.connect()
    try:
        cursore = con.execute(f"select * from read_parquet('{percorso}')")
        nomi = [d[0] for d in cursore.description]
        return [dict(zip(nomi, r, strict=True)) for r in cursore.fetchall()]
    finally:
        con.close()
