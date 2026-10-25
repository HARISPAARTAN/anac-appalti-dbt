"""Contratti di sorgente: unica fonte di verità per colonne, tipi di staging, allowlist e dati personali."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from anac_appalti.config import Impostazioni

TIPI_AMMESSI = {"varchar", "date", "timestamp", "integer", "bigint", "double", "decimal(18,2)", "boolean"}
LANDING_JINJA = "{{ env_var('APPALTI_LANDING', 'data/landing') }}"
INTESTAZIONE_SOURCES = (
    "# Generato da `appalti contratti sync` a partire da contratti/anac/*.yml. Non modificare a mano.\n"
)
NOTA_PERSONALE = " Può contenere dati di persone fisiche: in staging è annullato quando il codice fiscale non è di 11 cifre."
COLONNE_META: tuple[tuple[str, str], ...] = (
    ("_risorsa", "Nome del file ANAC senza estensione da cui proviene la riga."),
    (
        "_data_snapshot",
        "Data del file: dal prefisso AAAAMMGG dei delta, altrimenti dalla data di modifica della risorsa CKAN.",
    ),
    ("_caricato_il", "Istante di atterraggio del file in Parquet."),
    ("_sha256", "SHA-256 dello zip originale nell'archivio raw."),
    (
        "_hash_riga",
        "MD5 del contenuto (già ripulito) della riga, per riconoscere i duplicati esatti nello stesso file. "
        "Se un identificativo personale è stato annullato, nell'impronta entra anche `_ordinale_riga`: "
        "quelle righe non sono mai duplicati esatti e persone diverse restano righe diverse.",
    ),
    (
        "_ordinale_riga",
        "Posizione della riga nel file di origine (parte da 1). Vale solo dentro lo stesso file.",
    ),
)
# Date e conteggi che i mart usano: un testo non vuoto che diventa NULL in staging è una perdita silenziosa.
# Il test dbt `perdita_parsing` (warn) sta nelle sources generate; int_perdite_parsing li conta per il report.
CONTROLLI_PARSING: frozenset[tuple[str, str]] = frozenset(
    {
        ("cig", "data_pubblicazione"),
        ("cig", "data_scadenza_offerta"),
        ("aggiudicazioni", "data_aggiudicazione_definitiva"),
        ("aggiudicazioni", "numero_offerte_ammesse"),
        ("aggiudicazioni", "num_imprese_offerenti"),
        ("varianti", "data_approvazione_variante"),
        ("subappalti", "data_autorizzazione"),
    }
)
TIPO_PARSING = {"date": "data", "integer": "intero", "bigint": "intero"}
DESCRIZIONE_CLASSE = (
    "Classe del codice fiscale di `{sorgente}` prima dell'annullamento: persona_giuridica (11 cifre), persona_fisica "
    "(16 caratteri), non_verificabile o assente. Non identifica nessuno: il valore originale non è nel landing."
)


class ContrattoNonValido(ValueError):
    """Contratto di sorgente incoerente."""


@dataclass(frozen=True)
class Colonna:
    nome: str
    sorgente: str
    tipo: str
    tenere: bool
    dato_personale: bool
    descrizione: str


@dataclass(frozen=True)
class Contratto:
    tabella: str
    pacchetto: str
    descrizione: str
    freschezza: bool
    colonne: tuple[Colonna, ...]

    @property
    def tenute(self) -> tuple[Colonna, ...]:
        return tuple(c for c in self.colonne if c.tenere)

    @property
    def sorgenti(self) -> list[str]:
        return [c.sorgente for c in self.colonne]


def e_codice_fiscale(colonna: Colonna) -> bool:
    """Colonna che contiene un codice fiscale (`codice_fiscale`, `cf`, `cf_*`)."""
    nome = colonna.sorgente.lower()
    return nome in ("codice_fiscale", "cf") or nome.startswith("cf_")


def colonne_classe(contratto: Contratto) -> list[tuple[Colonna, str]]:
    """Colonne-codice-fiscale personali del contratto e nome della colonna `_classe_*` che il landing aggiunge.

    `codice_fiscale` -> `_classe_cf`; le altre (per esempio `cf_subappaltante`) -> `_classe_{sorgente}`.
    """
    return [
        (c, "_classe_cf" if c.sorgente == "codice_fiscale" else f"_classe_{c.sorgente}")
        for c in contratto.colonne
        if c.dato_personale and e_codice_fiscale(c)
    ]


def _valida(contratto: Contratto, origine: str) -> None:
    nomi = [c.nome for c in contratto.colonne]
    if len(set(nomi)) != len(nomi):
        raise ContrattoNonValido(f"{origine}: nomi di colonna duplicati")
    if len(set(contratto.sorgenti)) != len(contratto.sorgenti):
        raise ContrattoNonValido(f"{origine}: colonne sorgente duplicate")
    for c in contratto.colonne:
        if c.tipo not in TIPI_AMMESSI:
            raise ContrattoNonValido(f"{origine}: tipo {c.tipo!r} non ammesso per {c.nome}")
        if c.nome != c.nome.lower() or c.nome.startswith("_") or not c.nome.replace("_", "").isalnum():
            raise ContrattoNonValido(f"{origine}: nome {c.nome!r} non è snake_case minuscolo")


def carica_contratto(percorso: Path) -> Contratto:
    dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
    contratto = Contratto(
        tabella=str(dati["tabella"]),
        pacchetto=str(dati["pacchetto"]),
        descrizione=str(dati["descrizione"]),
        freschezza=bool(dati["freschezza"]),
        colonne=tuple(
            Colonna(
                nome=str(c["nome"]),
                sorgente=str(c["sorgente"]),
                tipo=str(c["tipo"]),
                tenere=bool(c["tenere"]),
                dato_personale=bool(c["dato_personale"]),
                descrizione=str(c["descrizione"]),
            )
            for c in dati["colonne"]
        ),
    )
    _valida(contratto, percorso.name)
    return contratto


def carica_contratti(cartella: Path) -> dict[str, Contratto]:
    contratti = [carica_contratto(p) for p in sorted(cartella.glob("*.yml"))]
    return {c.tabella: c for c in contratti}


@dataclass(frozen=True)
class EsitoSchema:
    mancanti: tuple[str, ...]
    nuove: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.mancanti


def confronta_schema(contratto: Contratto, intestazione: list[str]) -> EsitoSchema:
    """Colonne del contratto assenti nel file (errore) e colonne nuove del file (avviso, non atterrate)."""
    presenti = set(intestazione)
    attese = set(contratto.sorgenti)
    return EsitoSchema(
        mancanti=tuple(s for s in contratto.sorgenti if s not in presenti),
        nuove=tuple(h for h in intestazione if h not in attese),
    )


def _colonna_sources(tabella: str, col: Colonna) -> dict:
    voce: dict = {
        "name": col.nome,
        "description": col.descrizione + (NOTA_PERSONALE if col.dato_personale else ""),
    }
    if (tabella, col.nome) in CONTROLLI_PARSING:
        voce["data_tests"] = [
            {
                "perdita_parsing": {
                    "arguments": {"tipo": TIPO_PARSING[col.tipo]},
                    "config": {"severity": "warn"},
                }
            }
        ]
    return voce


def genera_sources_yml(contratti: dict[str, Contratto], warn_giorni: int, error_giorni: int) -> str:
    tabelle = []
    for tabella in sorted(contratti):
        c = contratti[tabella]
        voce: dict = {
            "name": tabella,
            "description": c.descrizione,
            "meta": {
                "external_location": f"read_parquet('{LANDING_JINJA}/{tabella}/*.parquet', union_by_name = true)",
                "dagster": {"asset_key": [f"landing_{tabella}"]},
            },
        }
        if c.freschezza:
            voce["loaded_at_field"] = "cast(_data_snapshot as timestamp)"
            voce["freshness"] = {
                "warn_after": {"count": warn_giorni, "period": "day"},
                "error_after": {"count": error_giorni, "period": "day"},
            }
        voce["columns"] = (
            [_colonna_sources(tabella, col) for col in c.tenute]
            + [
                {"name": nome, "description": DESCRIZIONE_CLASSE.format(sorgente=col.sorgente)}
                for col, nome in colonne_classe(c)
            ]
            + [{"name": nome, "description": descrizione} for nome, descrizione in COLONNE_META]
        )
        tabelle.append(voce)
    documento = {
        "version": 2,
        "sources": [
            {
                "name": "anac",
                "description": "Dati aperti ANAC (dati.anticorruzione.it), licenza CC BY-SA 4.0, atterrati in Parquet dalla pipeline Python.",
                "tables": tabelle,
            }
        ],
    }
    return INTESTAZIONE_SOURCES + yaml.safe_dump(documento, sort_keys=False, allow_unicode=True, width=1000)


def percorso_sources(imp: Impostazioni) -> Path:
    return imp.dbt_dir / "models" / "staging" / "anac" / "_anac__sources.yml"


def sincronizza(imp: Impostazioni, *, verifica: bool = False) -> bool:
    """Rigenera il file sources di dbt. Restituisce True se il file su disco era diverso."""
    testo = genera_sources_yml(
        carica_contratti(imp.contratti_dir),
        imp.soglie.freschezza_warn_giorni,
        imp.soglie.freschezza_error_giorni,
    )
    percorso = percorso_sources(imp)
    attuale = percorso.read_text(encoding="utf-8") if percorso.exists() else ""
    diverso = attuale != testo
    if diverso and not verifica:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(testo, encoding="utf-8", newline="\n")
    return diverso
