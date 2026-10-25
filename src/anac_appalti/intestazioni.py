"""Intestazioni reali dei CSV ANAC, lette dai primi 128 KB di ogni zip con una richiesta HTTP Range."""

from __future__ import annotations

import csv
import json
import struct
import zlib
from contextlib import closing
from datetime import date
from pathlib import Path

from anac_appalti.ckan import Fonte, crea_fonte
from anac_appalti.config import Impostazioni

FIRMA_LOCALE = 0x04034B50
N_BYTE = 131072
CAMPIONI: dict[str, tuple[str, str]] = {
    "cig": ("cig-2025", "cig_csv_2025_01.zip"),
    "aggiudicazioni": ("aggiudicazioni", "aggiudicazioni_csv.zip"),
    "aggiudicatari": ("aggiudicatari", "aggiudicatari_csv.zip"),
    "partecipanti": ("partecipanti", "partecipanti_csv.zip"),
    "varianti": ("varianti", "varianti_csv.zip"),
    "subappalti": ("subappalti", "subappalti_csv.zip"),
    "stazioni_appaltanti": ("stazioni-appaltanti", "stazioni-appaltanti_csv.zip"),
    "tipi_scelta_contraente": (
        "bandi-cig-tipo-scelta-contraente",
        "bandi-cig-tipo-scelta-contraente_csv.zip",
    ),
}
CAMPIONE_DELTA_CIG = ("cig", "20261001-cig_csv.zip")
FILE_PICCOLO = ("bandi-cig-tipo-scelta-contraente", "bandi-cig-tipo-scelta-contraente_csv.zip")


def url_download(base_url: str, pacchetto: str, file: str) -> str:
    return f"{base_url.rstrip('/')}/download/dataset/{pacchetto}/filesystem/{file}"


def intestazione_da_zip_parziale(dati: bytes) -> dict:
    """Legge nome interno, delimitatore, codifica e colonne dal primo file di uno zip troncato."""
    if len(dati) < 30:
        raise ValueError("Troppo pochi byte per un'intestazione zip")
    firma, _v, flag, metodo, _ora, _data, _crc, _cs, _us, n_nome, n_extra = struct.unpack(
        "<IHHHHHIIIHH", dati[:30]
    )
    if firma != FIRMA_LOCALE:
        raise ValueError("I byte non iniziano con un'intestazione locale zip")
    nome = dati[30 : 30 + n_nome].decode("utf-8" if flag & 0x800 else "cp437")
    corpo = dati[30 + n_nome + n_extra :]
    if metodo == 8:
        testo = zlib.decompressobj(-15).decompress(corpo)
    elif metodo == 0:
        testo = corpo
    else:
        raise ValueError(f"Metodo di compressione zip {metodo} non gestito")
    completo = testo[: testo.rfind(b"\n") + 1] if b"\n" in testo else testo
    try:
        completo.decode("utf-8")
        codifica = "utf-8"
    except UnicodeDecodeError:
        codifica = "latin-1"
    prima = testo.split(b"\n", 1)[0].rstrip(b"\r").decode(codifica).lstrip("\ufeff")
    delimitatore = ";" if prima.count(";") >= prima.count(",") else ","
    colonne = next(csv.reader([prima], delimiter=delimitatore, quotechar='"'))
    return {
        "file_interno": nome,
        "delimitatore": delimitatore,
        "virgolette": '"',
        "codifica": codifica,
        "colonne": colonne,
    }


def rileva_intestazioni(fonte: Fonte, base_url: str) -> dict:
    # Il package_show di cig-2025 è la richiesta che il WAF ha rifiutato con lo User-Agent del progetto:
    # farla per prima attiva subito l'eventuale User-Agent di riserva per tutte le richieste successive.
    fonte.package_show(CAMPIONI["cig"][0])
    tabelle: dict[str, dict] = {}
    for tabella, (pacchetto, file) in CAMPIONI.items():
        info = intestazione_da_zip_parziale(
            fonte.leggi_inizio(url_download(base_url, pacchetto, file), N_BYTE)
        )
        tabelle[tabella] = {"pacchetto": pacchetto, "file": file, **info}
    delta = intestazione_da_zip_parziale(
        fonte.leggi_inizio(url_download(base_url, *CAMPIONE_DELTA_CIG), N_BYTE)
    )
    tabelle["cig"]["delta_identico"] = delta["colonne"] == tabelle["cig"]["colonne"]
    return {
        "verificato_il": date.today().isoformat(),
        "fonte": base_url,
        "user_agent": fonte.user_agent_usato,
        "tabelle": tabelle,
    }


def scrivi_intestazioni(imp: Impostazioni) -> Path:
    """Registra le intestazioni reali e scarica per intero un file piccolo (vocabolario, 1,2 KB)."""
    with closing(crea_fonte(imp)) as fonte:
        dati = rileva_intestazioni(fonte, imp.base_url)
        fonte.scarica(url_download(imp.base_url, *FILE_PICCOLO), imp.raw / "_campioni" / FILE_PICCOLO[1])
    destinazione = imp.contratti_dir / "_intestazioni_reali.json"
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    destinazione.write_text(
        json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return destinazione
