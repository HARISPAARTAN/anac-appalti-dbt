"""Copertura dei test dbt dal manifest: descrizione per ogni modello, test sulla chiave dichiarata.

Staging (grana = riga del file ANAC, non univoca): descrizione e almeno un test not_null.
Intermediate e mart: `config.meta.chiave` (colonna o lista) con unique + not_null, oppure
dbt_utils.unique_combination_of_columns + not_null su ogni colonna della chiave.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from anac_appalti.config import Impostazioni
from anac_appalti.pipeline import garantisci_manifest


@dataclass
class Copertura:
    modelli: int
    conformi: int
    mancanze: list[str] = field(default_factory=list)

    @property
    def quota(self) -> float:
        return 1.0 if not self.modelli else self.conformi / self.modelli


def _nome_test(nodo: dict) -> str:
    return (nodo.get("test_metadata") or {}).get("name", "")


def _chiave(nodo: dict):
    meta = (nodo.get("config") or {}).get("meta") or nodo.get("meta") or {}
    return meta.get("chiave")


def calcola_copertura(manifest: dict, progetto: str = "anac_appalti") -> Copertura:
    nodi = manifest["nodes"]
    modelli = {
        uid: n for uid, n in nodi.items() if n["resource_type"] == "model" and n["package_name"] == progetto
    }
    test_per_modello: dict[str, list[dict]] = {}
    for nodo in nodi.values():
        if nodo["resource_type"] == "test" and nodo.get("attached_node"):
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
    return Copertura(modelli=len(modelli), conformi=conformi, mancanze=mancanze)


def verifica_copertura(imp: Impostazioni) -> Copertura:
    manifest = json.loads(garantisci_manifest(imp).read_text(encoding="utf-8"))
    return calcola_copertura(manifest)
