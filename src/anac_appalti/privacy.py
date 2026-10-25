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
