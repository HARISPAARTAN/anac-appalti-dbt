"""Indicatori di qualità dei dati dal warehouse e docs/qualita-dati.md (testo deterministico)."""

from __future__ import annotations

from pathlib import Path

import duckdb

from anac_appalti.config import Impostazioni
from anac_appalti.export import ATTRIBUZIONE

_PF = "tipo_soggetto_privacy = 'persona_fisica'"
_AGG_NON_LEGGIBILE = (
    "(importo_aggiudicazione is null and importo_aggiudicazione_raw is not null)"
    " or (ribasso_aggiudicazione is null and ribasso_aggiudicazione_raw is not null)"
)
QUERY: dict[str, str] = {
    "righe_cig": "select count(*) from staging.stg_anac__cig",
    "versioni_lotti": "select count(*) from intermediate.int_cig__versioni",
    "lotti_correnti": "select count(*) from intermediate.int_cig__corrente",
    "lotti_radar": "select count(*) from intermediate.int_radar__lotti",
    "aggiudicazioni_correnti": "select count(*) from intermediate.int_aggiudicazioni__corrente",
    "duplicati_esatti": "select coalesce(sum(n_duplicati_esatti), 0) from intermediate.int_cig__versioni",
    "duplicati_conflittuali": "select count(*) from intermediate.int_lotti__qualita where flag_duplicato_conflittuale",
    "date_impossibili": "select count(*) from intermediate.int_lotti__qualita where flag_data_impossibile",
    "importi_anomali": "select count(*) from intermediate.int_lotti__qualita where flag_importo_anomalo",
    "importi_non_positivi": "select count(*) from intermediate.int_lotti__qualita where flag_importo_non_positivo",
    "importi_oltre_gara": "select count(*) from intermediate.int_lotti__qualita where flag_importo_oltre_gara",
    "importi_implausibili": "select count(*) from intermediate.int_lotti__qualita where flag_importo_implausibile",
    "importi_mad": "select count(*) from intermediate.int_lotti__qualita where flag_importo_mad",
    "importi_non_leggibili": "select count(*) from intermediate.int_lotti__qualita where flag_importo_non_leggibile",
    "aggiudicazioni_non_leggibili": (
        f"select count(*) from intermediate.int_aggiudicazioni__corrente where {_AGG_NON_LEGGIBILE}"
    ),
    "senza_aggiudicatario": "select count(*) from intermediate.int_lotti__qualita where flag_senza_aggiudicatario",
    "stazioni_orfane": "select count(*) from intermediate.int_lotti__qualita where flag_stazione_orfana",
    "ribassi_fuori_range": (
        "select count(*) from intermediate.int_aggiudicazioni__corrente "
        "where ribasso_aggiudicazione < 0 or ribasso_aggiudicazione > 100"
    ),
    "aggiudicazioni_orfane": (
        "select count(*) from intermediate.int_aggiudicazioni__corrente as a where not exists "
        "(select 1 from intermediate.int_cig__versioni as v where v.cig = a.cig)"
    ),
    "perdite_date": (
        "select coalesce(sum(n_perdite), 0) from intermediate.int_perdite_parsing where tipo = 'data'"
    ),
    "valori_date": (
        "select coalesce(sum(n_valorizzate), 0) from intermediate.int_perdite_parsing where tipo = 'data'"
    ),
    "perdite_conteggi": (
        "select coalesce(sum(n_perdite), 0) from intermediate.int_perdite_parsing where tipo = 'intero'"
    ),
    "valori_conteggi": (
        "select coalesce(sum(n_valorizzate), 0) from intermediate.int_perdite_parsing where tipo = 'intero'"
    ),
    "lotti_derivati_accordo_quadro": "select count(*) from core.fct_lotti where flag_derivato_da_accordo_quadro",
    "lotti_annullati": "select count(*) from core.fct_lotti where flag_annullato",
    "file_atterrati": "select count(*) from intermediate.int_riconciliazione",
    "file_riconciliati": "select count(*) from intermediate.int_riconciliazione where riconciliazione = 'ok'",
    "file_con_differenza": "select count(*) from intermediate.int_riconciliazione where riconciliazione = 'differenza'",
    "file_non_verificabili": (
        "select count(*) from intermediate.int_riconciliazione where riconciliazione = 'non_disponibile'"
    ),
    "righe_operatori": (
        "select (select count(*) from staging.stg_anac__aggiudicatari)"
        " + (select count(*) from staging.stg_anac__partecipanti)"
        " + (select count(*) from staging.stg_anac__subappalti)"
    ),
    "righe_persone_fisiche": (
        f"select (select count(*) from staging.stg_anac__aggiudicatari where {_PF})"
        f" + (select count(*) from staging.stg_anac__partecipanti where {_PF})"
        f" + (select count(*) from staging.stg_anac__subappalti where {_PF})"
    ),
}

# (indicatore, controllo, regola, gravità, base della quota)
RIGHE_REPORT = (
    (
        "file_con_differenza",
        "Riconciliazione",
        "Righe atterrate per file = numero_righe del logCsv ANAC",
        "errore",
        "file_atterrati",
    ),
    (
        "duplicati_esatti",
        "Duplicati esatti",
        "Righe identiche nello stesso file (contate, una versione tenuta)",
        "avviso",
        "righe_cig",
    ),
    (
        "duplicati_conflittuali",
        "Duplicati in conflitto",
        "Stesso CIG, righe prevalenti diverse nello stesso file",
        "avviso",
        "lotti_correnti",
    ),
    (
        "date_impossibili",
        "Date impossibili",
        "Scadenza o aggiudicazione prima della pubblicazione; date prima del 2007 o oltre due anni",
        "avviso",
        "lotti_correnti",
    ),
    (
        "importi_anomali",
        "Importi anomali",
        "≤ 0, oltre il totale di gara, oltre 5 miliardi, non leggibili o oltre 3 MAD (log10) nel gruppo CPV × oggetto; "
        "esclusi dalle somme",
        "avviso",
        "lotti_correnti",
    ),
    (
        "importi_non_leggibili",
        "Importo non leggibile",
        "Testo dell'importo che non si legge (formato sconosciuto, oltre decimal(18,2)): resta in *_raw, il lotto è "
        "escluso dalle somme",
        "avviso",
        "lotti_correnti",
    ),
    (
        "aggiudicazioni_non_leggibili",
        "Aggiudicazione non leggibile",
        "Importo o ribasso di aggiudicazione che non si legge (testo originale in *_raw)",
        "avviso",
        "aggiudicazioni_correnti",
    ),
    (
        "perdite_date",
        "Date non leggibili",
        "Data di pubblicazione, scadenza, aggiudicazione, variante o subappalto con testo non vuoto e valore NULL: "
        "il lotto manca dai mart a base temporale",
        "avviso",
        "valori_date",
    ),
    (
        "perdite_conteggi",
        "Conteggi di offerte non leggibili",
        "Offerte ammesse o imprese offerenti con testo non vuoto e valore NULL: il lotto esce dalla logica "
        "dell'offerta unica",
        "avviso",
        "valori_conteggi",
    ),
    (
        "senza_aggiudicatario",
        "Aggiudicatario mancante",
        "Lotto aggiudicato senza righe in aggiudicatari",
        "avviso",
        "lotti_correnti",
    ),
    ("stazioni_orfane", "Stazione orfana", "codice_ausa assente dall'anagrafe", "avviso", "lotti_correnti"),
    (
        "aggiudicazioni_orfane",
        "Aggiudicazione orfana",
        "CIG dell'aggiudicazione assente dai dati CIG in ambito (atteso per lotti pubblicati prima dell'anno minimo)",
        "avviso",
        None,
    ),
    ("ribassi_fuori_range", "Ribasso fuori intervallo", "Ribasso fuori da 0–100 %", "avviso", None),
    (
        "righe_persone_fisiche",
        "Persone fisiche",
        "Codice fiscale di 16 caratteri: identità annullata al landing (e di nuovo in staging), conteggio conservato",
        "privacy",
        "righe_operatori",
    ),
)


def _numero(valore: int) -> str:
    return f"{valore:,}".replace(",", ".")


def _quota(parte: int, totale: int) -> str:
    if not totale:
        return "–"
    return f"{parte / totale * 100:.2f} %".replace(".", ",")


def calcola_indicatori(imp: Impostazioni) -> dict[str, int]:
    con = duckdb.connect(str(imp.warehouse_file), read_only=True)
    try:
        return {chiave: int(con.execute(sql).fetchone()[0]) for chiave, sql in QUERY.items()}
    finally:
        con.close()


def componi_report(
    indicatori: dict[str, int], data_riferimento: str, *, fixtures: bool = False, mese: int = 1
) -> str:
    i = indicatori
    if fixtures:
        intestazione = [
            "# Qualità dei dati (report sulla fixture sintetica)",
            "",
            "**Questo è il report della fixture sintetica, non dei dati ANAC reali.** Ogni numero qui sotto "
            "viene da dati generati dal progetto per test e CI. Dopo l'esecuzione completa su dati reali "
            "(`uv run appalti run`, poi `uv run appalti report`) questo file viene sostituito dal report reale.",
            "",
            f"Generato da `appalti report --fixtures` sulla fixture sintetica (mese {mese}), "
            f"data di riferimento {data_riferimento}.",
            "",
        ]
    else:
        intestazione = [
            "# Qualità dei dati",
            "",
            f"Generato da `appalti report` sui dati reali ANAC con data di riferimento {data_riferimento}.",
            "",
        ]
    righe = [
        *intestazione,
        "Politica: si segnala, non si cancella. Ogni controllo è un test dbt (avviso o errore) "
        "e un flag in `int_lotti__qualita`.",
        "",
        "## Volumi",
        "",
        "| Misura | Valore |",
        "|---|---:|",
        f"| Righe CIG atterrate | {_numero(i['righe_cig'])} |",
        f"| Versioni di lotto (CIG × file) | {_numero(i['versioni_lotti'])} |",
        f"| Lotti correnti (un CIG per riga) | {_numero(i['lotti_correnti'])} |",
        f"| Lotti nei mart Radar | {_numero(i['lotti_radar'])} |",
        f"| Lotti derivati da accordo quadro (esclusi dalle somme) | {_numero(i['lotti_derivati_accordo_quadro'])} |",
        f"| Lotti cancellati (esclusi dal Radar) | {_numero(i['lotti_annullati'])} |",
        f"| File atterrati / riconciliati / non verificabili | {_numero(i['file_atterrati'])} / "
        f"{_numero(i['file_riconciliati'])} / {_numero(i['file_non_verificabili'])} |",
        "",
        "## Controlli",
        "",
        "| Controllo | Regola | Gravità | Valore | Quota |",
        "|---|---|---|---:|---:|",
    ]
    for chiave, controllo, regola, gravita, base in RIGHE_REPORT:
        quota = _quota(i[chiave], i[base]) if base else "–"
        righe.append(f"| {controllo} | {regola} | {gravita} | {_numero(i[chiave])} | {quota} |")
    righe += [
        "",
        "Dettaglio importi anomali: "
        f"non positivi {_numero(i['importi_non_positivi'])}, oltre il totale di gara {_numero(i['importi_oltre_gara'])}, "
        f"oltre 5 miliardi {_numero(i['importi_implausibili'])}, anomali per MAD {_numero(i['importi_mad'])}, "
        f"non leggibili {_numero(i['importi_non_leggibili'])} "
        "(un lotto può avere più flag).",
        "",
        *(
            []
            if fixtures
            else [
                'Date impossibili sui dati reali: la regola "scadenza prima della pubblicazione" scatta soprattutto '
                "sugli affidamenti diretti, dove la data di scadenza dell'offerta può precedere la pubblicazione "
                "senza che ci sia un errore; il controllo è informativo e non esclude lotti dai mart.",
                "",
            ]
        ),
        "Regole sulle somme: gli importi si sommano solo sui lotti non derivati da accordo quadro, non anomali e "
        "non cancellati, così un accordo quadro e i suoi contratti attuativi non sono contati due volte. "
        "I lotti esclusi restano nei conteggi.",
        "",
        "Le perdite di lettura (date e conteggi) sono contate su tutte le righe atterrate, anche sulle versioni "
        "superate; il dettaglio per colonna è in `intermediate.int_perdite_parsing` e ogni colonna ha un test "
        "dbt `perdita_parsing` di livello avviso sulla source.",
        "",
        "I file annuali `cig-AAAA` non hanno un conteggio CSV nel logCsv ANAC (solo TTL): la loro riconciliazione "
        "è `non_disponibile`.",
        "",
        ATTRIBUZIONE,
        "",
    ]
    return "\n".join(righe)


def scrivi_report(imp: Impostazioni, indicatori: dict[str, int]) -> Path:
    percorso = imp.docs / "qualita-dati.md"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(
        componi_report(indicatori, imp.data_riferimento, fixtures=imp.fixtures, mese=imp.mese),
        encoding="utf-8",
        newline="\n",
    )
    return percorso
