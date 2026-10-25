"""Copertura dei test dbt dal manifest: descrizione per ogni modello, test sulla chiave dichiarata.

Staging (grana = riga del file ANAC, non univoca): descrizione e almeno un test not_null.
Intermediate e mart: `config.meta.chiave` (colonna o lista) con unique + not_null, oppure
dbt_utils.unique_combination_of_columns + not_null su ogni colonna della chiave.

Un test conta solo se è un controllo vero: severità errore, nessun filtro `where` o `limit`, abilitato.
Un manifest senza modelli del progetto è un errore, mai una copertura piena.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from anac_appalti.config import Impostazioni
from anac_appalti.pipeline import garantisci_manifest


class ErroreCopertura(ValueError):
    """Il manifest non contiene modelli del progetto: la copertura non è calcolabile."""


@dataclass
class Copertura:
    modelli: int
    conformi: int
    mancanze: list[str] = field(default_factory=list)
    nomi: list[str] = field(default_factory=list)

    @property
    def quota(self) -> float:
        return self.conformi / self.modelli if self.modelli else 0.0


def _nome_test(nodo: dict) -> str:
    return (nodo.get("test_metadata") or {}).get("name", "")


def _test_valido(nodo: dict) -> bool:
    """Severità errore, abilitato, senza filtri che svuotano il controllo."""
    config = nodo.get("config") or {}
    if str(config.get("severity", "error")).lower() != "error":
        return False
    if config.get("enabled", True) is False:
        return False
    return not config.get("where") and config.get("limit") in (None, "")


def _chiave(nodo: dict):
    meta = (nodo.get("config") or {}).get("meta") or nodo.get("meta") or {}
    return meta.get("chiave")


def calcola_copertura(manifest: dict, progetto: str = "anac_appalti") -> Copertura:
    nodi = manifest.get("nodes") or {}
    modelli = {
        uid: n for uid, n in nodi.items() if n["resource_type"] == "model" and n["package_name"] == progetto
    }
    if not modelli:
        raise ErroreCopertura(f"nessun modello del progetto {progetto!r} nel manifest ({len(nodi)} nodi)")
    test_per_modello: dict[str, list[dict]] = {}
    for nodo in nodi.values():
        if nodo["resource_type"] == "test" and nodo.get("attached_node") and _test_valido(nodo):
            test_per_modello.setdefault(nodo["attached_node"], []).append(nodo)
    mancanze: list[str] = []
    conformi = 0
    for uid, nodo in sorted(modelli.items(), key=lambda voce: voce[1]["name"]):
        nome = nodo["name"]
        problemi = []
        test = test_per_modello.get(uid, [])
        if not (nodo.get("description") or "").strip():
            problemi.append(f"{nome}: descrizione mancante")
        livello = nodo["fqn"][1] if len(nodo["fqn"]) > 2 else ""
        chiave = _chiave(nodo)
        nulli = {t.get("column_name") for t in test if _nome_test(t) == "not_null"}
        if livello == "staging":
            if not nulli:
                problemi.append(f"{nome}: nessun test not_null")
        elif not chiave:
            problemi.append(f"{nome}: chiave non dichiarata in config.meta.chiave")
        else:
            colonne = [chiave] if isinstance(chiave, str) else list(chiave)
            if len(colonne) == 1:
                unici = {t.get("column_name") for t in test if _nome_test(t) == "unique"}
                if colonne[0] not in unici:
                    problemi.append(f"{nome}: manca il test unique sulla chiave {colonne[0]}")
            else:
                combinazioni = [
                    set((t.get("test_metadata") or {}).get("kwargs", {}).get("combination_of_columns", []))
                    for t in test
                    if _nome_test(t) == "unique_combination_of_columns"
                ]
                if set(colonne) not in combinazioni:
                    problemi.append(f"{nome}: manca unique_combination_of_columns su {', '.join(colonne)}")
            for colonna in colonne:
                if colonna not in nulli:
                    problemi.append(f"{nome}: manca il test not_null su {colonna}")
        if problemi:
            mancanze.extend(problemi)
        else:
            conformi += 1
    nomi = sorted(n["name"] for n in modelli.values())
    return Copertura(modelli=len(modelli), conformi=conformi, mancanze=mancanze, nomi=nomi)


def verifica_copertura(imp: Impostazioni) -> Copertura:
    manifest = json.loads(garantisci_manifest(imp).read_text(encoding="utf-8"))
    return calcola_copertura(manifest)
