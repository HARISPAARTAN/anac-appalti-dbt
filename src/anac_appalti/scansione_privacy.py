"""Scansione di privacy dei file rilasciati: codici fiscali personali e nomi di persona in ogni colonna di testo.

Due controlli, entrambi su ogni colonna di testo di ogni mart Parquet:

1. il modello del codice fiscale di 16 caratteri (`privacy.RE_CF_IN_TESTO`);
2. i nomi: per ogni codice fiscale personale presente nell'anagrafe delle stazioni appaltanti si derivano i tre
   caratteri del cognome e i tre del nome (le consonanti del cognome e del nome, regola del codice fiscale); un testo
   che contiene una parola con il codice del cognome e un'altra con il codice del nome è il nome di quella persona
   (nei dati reali la revisione finale ha trovato così sette nomi su nove). Per non segnalare le denominazioni di
   enti e società, che hanno molte parole e un marcatore di forma giuridica, si considerano solo i testi con al più
   sei parole e senza marcatori di ente.

Il controllo dei nomi non può essere esaustivo (una persona con un codice fiscale che non è nell'anagrafe non si
riconosce, e una persona con un codice segnaposto e forma giuridica non classificata nemmeno): le regole vere sono in
staging (codice, forma giuridica) e nella revisione manuale dei candidati (`int_stazioni_da_verificare`). Questa
scansione è la prova a valle che nel file rilasciato non è rimasto nulla di ciò che quelle regole riconoscono.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import duckdb

from anac_appalti.config import Impostazioni
from anac_appalti.privacy import MODELLO_CF_PERSONA, RE_CF_IN_TESTO

RE_CF_PERSONA_INTERO = re.compile(MODELLO_CF_PERSONA)
RE_PAROLA = re.compile(r"[^\W\d_]+")
# Sigle puntate ("I.C.", "S.R.L."): sono enti, non persone.
RE_SIGLA = re.compile(r"(?<![^\W\d_])[^\W\d_]\.\s?[^\W\d_]\.")
VOCALI = "AEIOU"
# Una denominazione di ente o di società non è il nome di una persona: se contiene una di queste parole non si
# confronta con i codici (evita i falsi positivi su 48 mila denominazioni).
MARCATORI_ENTE = frozenset(
    {
        "SRL",
        "SPA",
        "SAS",
        "SNC",
        "SCARL",
        "SOC",
        "SOCIETA",
        "COOP",
        "COOPERATIVA",
        "CONSORZIO",
        "ASSOCIAZIONE",
        "FONDAZIONE",
        "COMUNE",
        "COMUNI",
        "PROVINCIA",
        "REGIONE",
        "CITTA",
        "METROPOLITANA",
        "UNIONE",
        "AZIENDA",
        "ASL",
        "ASST",
        "AUSL",
        "ENTE",
        "ISTITUTO",
        "SCUOLA",
        "UNIVERSITA",
        "MINISTERO",
        "AGENZIA",
        "AUTORITA",
        "COMANDO",
        "DIREZIONE",
        "DIPARTIMENTO",
        "PARROCCHIA",
        "ORDINE",
        "COLLEGIO",
        "CAMERA",
        "COMUNITA",
        "COMPRENSORIO",
        "ISTITUZIONE",
        "SERVIZI",
        "SERVIZIO",
        "AMBITO",
        "TERRITORIALE",
        "ENTI",
        "LAVORI",
        "GRUPPO",
        "AZIONE",
        "LOCALE",
        "LICEO",
        "SCIENTIFICO",
        "STATALE",
        "TRIBUNALE",
        "DIOCESI",
        "TERRA",
        "CUC",
        "ALER",
        "COMPRENSIVO",
        "OSPEDALE",
        "POLICLINICO",
        "PREFETTURA",
        "QUESTURA",
        "MUSEO",
        "BIBLIOTECA",
        "TEATRO",
        "PARCO",
        "ITALIANA",
        "ITALIANO",
        "NAZIONALE",
        "REGIONALE",
        "PROVINCIALE",
        "COMUNALE",
    }
)
MAX_PAROLE_NOME = 6
MAX_PAROLE_GRUPPO = 4


def _lettere(parola: str) -> str:
    base = unicodedata.normalize("NFKD", parola.upper())
    return "".join(c for c in base if "A" <= c <= "Z")


def codice_cognome(parola: str) -> str:
    lettere = _lettere(parola)
    consonanti = [c for c in lettere if c not in VOCALI]
    vocali = [c for c in lettere if c in VOCALI]
    return "".join(consonanti + vocali + ["X", "X"])[:3]


def codice_nome(parola: str) -> str:
    lettere = _lettere(parola)
    consonanti = [c for c in lettere if c not in VOCALI]
    if len(consonanti) >= 4:
        return consonanti[0] + consonanti[2] + consonanti[3]
    return codice_cognome(parola)


@dataclass(frozen=True)
class Rilievo:
    file: str
    colonna: str
    tipo: str
    valore: str

    def __str__(self) -> str:
        return f"{self.file}.{self.colonna}: {self.tipo}"


def codici_personali_anagrafe(imp: Impostazioni) -> list[str]:
    """Codici fiscali personali (16 caratteri) presenti nell'anagrafe delle stazioni appaltanti, dal landing."""
    file = list((imp.landing / "stazioni_appaltanti").glob("*.parquet"))
    if not file:
        return []
    con = duckdb.connect()
    try:
        righe = con.execute(
            "select distinct upper(trim(codice_fiscale)) from read_parquet(?, union_by_name = true) "
            "where codice_fiscale is not null",
            [[f.as_posix() for f in file]],
        ).fetchall()
    finally:
        con.close()
    return sorted(c for (c,) in righe if RE_CF_PERSONA_INTERO.fullmatch(c))


def coppie_nome(codici: list[str]) -> set[tuple[str, str]]:
    """(codice del cognome, codice del nome) di ogni codice fiscale personale."""
    return {(c[0:3], c[3:6]) for c in codici}


def nome_di_persona(testo: str, coppie: set[tuple[str, str]]) -> bool:
    """Vero se il testo ha una parola con il codice del cognome e un'altra con il codice del nome di una coppia."""
    parole = RE_PAROLA.findall(testo)
    if len(parole) < 2 or len(parole) > MAX_PAROLE_NOME:
        return False
    if RE_SIGLA.search(testo) or any(_lettere(p) in MARCATORI_ENTE for p in parole):
        return False
    n = len(parole)
    # un cognome o un nome può essere fatto di più parole ("DEL GALLO", "MARIA GRAZIA"): si provano i gruppi di parole
    # vicine, senza sovrapporli
    for i in range(n):
        for lung_cognome in range(1, min(MAX_PAROLE_GRUPPO, n - i) + 1):
            cognome = codice_cognome("".join(parole[i : i + lung_cognome]))
            for j in range(n):
                for lung_nome in range(1, min(MAX_PAROLE_GRUPPO, n - j) + 1):
                    if not (j + lung_nome <= i or j >= i + lung_cognome):
                        continue
                    if (cognome, codice_nome("".join(parole[j : j + lung_nome]))) in coppie:
                        return True
    return False


def scansiona_parquet(percorso: Path, codici: list[str]) -> list[Rilievo]:
    """Rilievi in tutte le colonne di testo di un Parquet: codici fiscali personali e nomi di persona."""
    coppie = coppie_nome(codici)
    rilievi: list[Rilievo] = []
    con = duckdb.connect()
    try:
        sorgente = f"read_parquet('{percorso.as_posix()}')"
        colonne = [
            nome
            for nome, tipo, *_ in con.execute(f"describe select * from {sorgente}").fetchall()
            if tipo == "VARCHAR"
        ]
        for colonna in colonne:
            valori = con.execute(
                f'select distinct "{colonna}" from {sorgente} where "{colonna}" is not null'
            ).fetchall()
            for (valore,) in valori:
                if RE_CF_IN_TESTO.search(valore.upper()):
                    rilievi.append(Rilievo(percorso.name, colonna, "codice fiscale personale", valore))
                elif coppie and nome_di_persona(valore, coppie):
                    rilievi.append(Rilievo(percorso.name, colonna, "nome di persona", valore))
    finally:
        con.close()
    return rilievi


def scansiona_cartella(imp: Impostazioni, cartella: Path) -> tuple[list[Rilievo], dict[str, int]]:
    """Scansiona tutti i Parquet della cartella. Restituisce i rilievi e il numero di colonne di testo per file."""
    codici = codici_personali_anagrafe(imp)
    rilievi: list[Rilievo] = []
    colonne_per_file: dict[str, int] = {}
    for percorso in sorted(cartella.glob("*.parquet")):
        rilievi += scansiona_parquet(percorso, codici)
        con = duckdb.connect()
        try:
            colonne_per_file[percorso.name] = sum(
                1
                for _, tipo, *_ in con.execute(
                    f"describe select * from read_parquet('{percorso.as_posix()}')"
                ).fetchall()
                if tipo == "VARCHAR"
            )
        finally:
            con.close()
    return rilievi, colonne_per_file
