"""Classificazione dei codici fiscali. L'identità resta solo per le persone giuridiche (11 cifre).

Gemello Python della macro dbt `classifica_cf` (dbt/macros/privacy.sql): i due modelli devono restare
identici, lo verifica tests/unit/test_privacy_sql.py.
"""

from __future__ import annotations

import re

MODELLO_PIVA = r"[0-9]{11}"
MODELLO_CF_PERSONA = r"[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]"
RE_PIVA = re.compile(MODELLO_PIVA)
RE_CF_PERSONA = re.compile(MODELLO_CF_PERSONA)
RE_CF_IN_TESTO = re.compile(r"(?<![A-Z0-9])" + MODELLO_CF_PERSONA + r"(?![A-Z0-9])")


# Forme giuridiche che indicano una persona fisica: codice e descrizione dell'anagrafe delle stazioni appaltanti, e
# descrizione anche per il tipo_soggetto degli operatori. Gemelle delle macro dbt `stazione_persona_fisica` e
# `tipo_soggetto_individuale`; il test tests/unit/test_privacy_sql.py le confronta.
NATURE_GIURIDICHE_INDIVIDUALI_CODICI = ("56", "58", "59", "60", "61", "A070")
NATURE_GIURIDICHE_INDIVIDUALI_DESCRIZIONI = (
    "ALTRI LAVORATORI AUTONOMI",
    "DITTA INDIVIDUALE",
    "DITTE INDIVIDUALI",
    "IMPRESE INDIVIDUALI ARTIGIANE",
    "IMPRESE INDIVIDUALI COMMERCIALI",
    "LAVORATORI AUTONOMI - PROFESSIONISTI",
    "LIBERO PROFESSIONISTA",
)
# Denominazione che sostituisce il nome di una persona fisica (stessa dicitura del membro anonimo degli operatori).
DENOMINAZIONE_PERSONA_FISICA = "Persona fisica (identità non pubblicata)"
CHIAVE_PERSONA_FISICA = "PERSONA_FISICA"


# Maschera dei codici fiscali personali nel testo libero (oggetto della gara, del lotto, del subappalto, motivi):
# il landing sostituisce ogni codice trovato con questo token. Gemello SQL: landing.maschera_cf_sql.
TOKEN_CF_MASCHERATO = "[CF]"
RE_CF_DA_MASCHERARE = re.compile(r"(?<![A-Za-z0-9])" + MODELLO_CF_PERSONA + r"(?![A-Za-z0-9])", re.IGNORECASE)


def maschera_cf_in_testo(testo: str) -> tuple[str, int]:
    """Il testo con ogni codice fiscale di persona fisica sostituito da `[CF]` e il numero di sostituzioni."""
    return RE_CF_DA_MASCHERARE.subn(TOKEN_CF_MASCHERATO, testo)


def classifica_codice_fiscale(cf: str | None) -> str:
    valore = (cf or "").strip().upper()
    if not valore:
        return "assente"
    if RE_PIVA.fullmatch(valore):
        return "persona_giuridica"
    if RE_CF_PERSONA.fullmatch(valore):
        return "persona_fisica"
    return "non_verificabile"


def cerca_cf_personali(testo: str) -> list[str]:
    return RE_CF_IN_TESTO.findall(testo.upper())


def e_stazione_persona_fisica(
    codice_fiscale: str | None, natura_codice: str | None, natura_descrizione: str | None
) -> bool:
    """Una stazione appaltante è una persona fisica se il codice fiscale è personale (16 caratteri) o se la forma
    giuridica dell'anagrafe dice che è un individuo (ditta individuale, libero professionista, lavoratore autonomo).
    Gemello della macro dbt `stazione_persona_fisica`."""
    if classifica_codice_fiscale(codice_fiscale) == "persona_fisica":
        return True
    codice = (natura_codice or "").strip().upper()
    descrizione = (natura_descrizione or "").strip().upper()
    return (
        codice in NATURE_GIURIDICHE_INDIVIDUALI_CODICI
        or descrizione in NATURE_GIURIDICHE_INDIVIDUALI_DESCRIZIONI
    )


def e_tipo_soggetto_individuale(tipo_soggetto: str | None) -> bool:
    """Vero se il tipo_soggetto di un operatore è una forma giuridica individuale (nome e partita IVA sono dati
    personali). Gemello della macro dbt `tipo_soggetto_individuale`."""
    return (tipo_soggetto or "").strip().upper() in NATURE_GIURIDICHE_INDIVIDUALI_DESCRIZIONI
