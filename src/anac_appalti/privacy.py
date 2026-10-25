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


# Forme giuridiche dell'anagrafe delle stazioni appaltanti che indicano una persona fisica (codice e descrizione).
# Gemello della macro dbt `stazione_persona_fisica`; il test tests/unit/test_privacy_sql.py li confronta.
NATURE_GIURIDICHE_INDIVIDUALI_CODICI = ("56", "58", "59", "60", "61", "A070")
NATURE_GIURIDICHE_INDIVIDUALI_DESCRIZIONI = (
    "ALTRI LAVORATORI AUTONOMI",
    "DITTE INDIVIDUALI",
    "IMPRESE INDIVIDUALI ARTIGIANE",
    "IMPRESE INDIVIDUALI COMMERCIALI",
    "LAVORATORI AUTONOMI - PROFESSIONISTI",
    "LIBERO PROFESSIONISTA",
)
# Denominazione che sostituisce il nome di una persona fisica (stessa dicitura del membro anonimo degli operatori).
DENOMINAZIONE_PERSONA_FISICA = "Persona fisica (identità non pubblicata)"
CHIAVE_PERSONA_FISICA = "PERSONA_FISICA"


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
