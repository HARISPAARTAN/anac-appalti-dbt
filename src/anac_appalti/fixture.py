"""Fixture sintetica e deterministica nel formato dei file ANAC.

Stessi nomi e ordine di colonna dei file reali (presi dai contratti), stesso layout di zip e logCsv, stesso
specchio CKAN. Nessun dato reale e nessuna persona fisica: tutti i codici fiscali hanno 11 cifre.

Difetti iniettati nel mese 1 (conteggi attesi nei test): 3 duplicati esatti (CIG 11, 21, 31), 2 date
impossibili (41, 42: scadenza prima della pubblicazione), 2 importi anomali (51 = 0 euro, 52 = 9 miliardi),
1 lotto aggiudicato senza aggiudicatario (61), 1 ribasso fuori intervallo (71 = 120 %), 1 aggiudicazione
precedente alla pubblicazione (81), 1 lotto oltre l'importo della gara (91). Il mese 2 aggiunge il delta
`20260401-cig_csv.zip` con 50 aggiornamenti di importo e 1 cancellazione (CIG 201) e il delta
`20260401-aggiudicazioni_csv.zip` con 20 aggiornamenti di importo e 1 aggiudicazione nuova (CIG 4).
"""

from __future__ import annotations

import json
import random
import shutil
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from anac_appalti.contratti import Contratto, carica_contratti

BASE_URL = "https://dati.anticorruzione.it/opendata"
DATA_ZIP = (2026, 1, 15, 0, 0, 0)
N_LOTTI = 1500
DUPLICATI = (11, 21, 31)
DATE_IMPOSSIBILI = (41, 42)
IMPORTO_ZERO = 51
IMPORTO_ENORME = 52
SENZA_AGGIUDICATARIO = 61
RIBASSO_FUORI_INTERVALLO = 71
AGGIUDICAZIONE_ANTICIPATA = 81
OLTRE_GARA = 91
AGGIORNATI = tuple(i for i in range(101, 200) if i % 10 != 0)[:50]
CANCELLATO = 201
AGGIUDICAZIONI_AGGIORNATE = tuple(i for i in range(301, 400) if i % 5 != 4)[:20]
AGGIUDICAZIONE_NUOVA = 4
PROVINCE = (
    ("072", "BA", "BARI"),
    ("073", "TA", "TARANTO"),
    ("075", "LE", "LECCE"),
    ("071", "FG", "FOGGIA"),
    ("074", "BR", "BRINDISI"),
    ("110", "BT", "BARLETTA-ANDRIA-TRANI"),
)
OGGETTI = ("LAVORI", "SERVIZI", "FORNITURE")
CPV = {
    "LAVORI": (("45233140-2", "LAVORI STRADALI"),),
    "SERVIZI": (
        ("90910000-9", "SERVIZI DI PULIZIA"),
        ("72267000-4", "SERVIZI DI MANUTENZIONE E RIPARAZIONE DI SOFTWARE"),
    ),
    "FORNITURE": (("33600000-6", "PRODOTTI FARMACEUTICI"), ("30192000-1", "FORNITURE PER UFFICIO")),
}
CPV_SECONDARIO = ("71000000-8", "SERVIZI ARCHITETTONICI, DI COSTRUZIONE, INGEGNERIA E ISPEZIONE")
PROCEDURE = {
    "1": "PROCEDURA APERTA",
    "2": "PROCEDURA RISTRETTA",
    "3": "PROCEDURA NEGOZIATA PREVIA PUBBLICAZIONE",
    "4": "PROCEDURA NEGOZIATA SENZA PREVIA PUBBLICAZIONE",
    "24": "AFFIDAMENTO DIRETTO",
    "27": "AFFIDAMENTO DIRETTO IN ADESIONE AD ACCORDO QUADRO/CONVENZIONE",
}
COMPETITIVE = frozenset({"1", "2", "3"})
LM = {
    "cig-2025": "2026-01-16T00:00:00",
    "aggiudicazioni": "2026-01-15T00:00:00",
    "aggiudicatari": "2026-01-23T00:00:00",
    "partecipanti": "2026-01-23T00:00:00",
    "varianti": "2026-01-21T00:00:00",
    "subappalti": "2026-01-15T00:00:00",
    "stazioni-appaltanti": "2026-10-13T00:00:00",
    "bandi-cig-tipo-scelta-contraente": "2026-10-13T00:00:00",
}
LM_DELTA = "2026-04-02T00:00:00"
LM_LOG_CIG = "2025-09-02T00:00:00"
RIGA_LOG_CIG_VECCHIA = "cig;cig;20250901-cig_csv.csv;215989;csv;12-02-2024;2025-09-02T10:02:24.531"


def cig(i: int) -> str:
    return f"FX{i:08d}"


def ausa(s: int) -> str:
    return f"{900000 + s:010d}"


def cf_stazione(s: int) -> str:
    return f"{80000000000 + s * 7919:011d}"


def nome_stazione(s: int) -> str:
    return f"COMUNE DI ESEMPIO {s:02d}"


def cf_operatore(k: int) -> str:
    return f"{10000000000 + k * 104729:011d}"


def nome_operatore(k: int) -> str:
    return f"IMPRESA ESEMPIO {k:02d} S.R.L."


def codice_procedura(i: int) -> str:
    return ("1", "1", "2", "3", "4", "24", "24", "24", "24", "24")[i % 10]


def aggiudicato(i: int) -> bool:
    return i % 5 != 4


def n_offerte(i: int) -> int:
    return 1 + (i % 6) if codice_procedura(i) in COMPETITIVE else 1


@dataclass(frozen=True)
class Lotto:
    i: int
    mese: int
    pubblicazione: date
    scadenza: date
    aggiudicazione: date
    oggetto: str
    cpv: str
    descrizione_cpv: str
    importo: float
    procedura: str
    stazione: int
    luogo: str
    provincia: str


def crea_lotti(rng: random.Random) -> list[Lotto]:
    lotti = []
    for i in range(1, N_LOTTI + 1):
        mese = 1 if i <= N_LOTTI // 2 else 2
        pubblicazione = date(2025, mese, 1 + i % 27)
        if i in DATE_IMPOSSIBILI:
            scadenza = pubblicazione - timedelta(days=5)
            aggiudicazione = pubblicazione + timedelta(days=10 + i % 50)
        else:
            scadenza = pubblicazione + timedelta(days=20 + i % 21)
            aggiudicazione = scadenza + timedelta(days=10 + i % 50)
        if i == AGGIUDICAZIONE_ANTICIPATA:
            aggiudicazione = pubblicazione - timedelta(days=10)
        oggetto = OGGETTI[i % 3]
        cpv, descrizione = CPV[oggetto][i % len(CPV[oggetto])]
        importo = round(10 ** rng.uniform(4.0, 5.0), 2)
        if i == IMPORTO_ZERO:
            importo = 0.0
        if i == IMPORTO_ENORME:
            importo = 9_000_000_000.0
        provincia = PROVINCE[i % len(PROVINCE)]
        lotti.append(
            Lotto(
                i,
                mese,
                pubblicazione,
                scadenza,
                aggiudicazione,
                oggetto,
                cpv,
                descrizione,
                importo,
                codice_procedura(i),
                i % 12,
                f"{provincia[0]}{(i % 50) + 1:03d}",
                provincia[2],
            )
        )
    return lotti


def componi(contratto: Contratto, valori: dict[str, str]) -> list[str]:
    sconosciute = set(valori) - {c.nome for c in contratto.colonne}
    if sconosciute:
        raise KeyError(f"{contratto.tabella}: colonne non nel contratto: {sorted(sconosciute)}")
    return [valori.get(c.nome, "") for c in contratto.colonne]


def riga_cig(
    contratto: Contratto,
    lotto: Lotto,
    *,
    cpv: tuple[str, str] | None = None,
    prevalente: str = "1",
    importo: float | None = None,
    cancellazione: date | None = None,
) -> list[str]:
    valore = lotto.importo if importo is None else importo
    complessivo = round(valore * 0.5, 2) if lotto.i == OLTRE_GARA else valore
    accordo = lotto.i % 25 == 0
    codice_cpv, descrizione_cpv = cpv or (lotto.cpv, lotto.descrizione_cpv)
    valori = {
        "cig": cig(lotto.i),
        "cig_accordo_quadro": "FX99999999" if accordo else "",
        "numero_gara": str(9_000_000 + lotto.i),
        "oggetto_gara": f"GARA DI ESEMPIO {lotto.i:04d}",
        "importo_complessivo_gara": f"{complessivo:.2f}",
        "n_lotti_componenti": "1",
        "oggetto_lotto": f"LOTTO DI ESEMPIO {lotto.i:04d}",
        "importo_lotto": f"{valore:.2f}",
        "oggetto_principale_contratto": lotto.oggetto,
        "stato": "ATTIVO",
        "settore": "SETTORI SPECIALI" if lotto.i % 7 == 0 else "SETTORI ORDINARI",
        "luogo_istat": lotto.luogo,
        "provincia": lotto.provincia,
        "data_pubblicazione": lotto.pubblicazione.isoformat(),
        "data_scadenza_offerta": lotto.scadenza.isoformat(),
        "cod_tipo_scelta_contraente": lotto.procedura,
        "tipo_scelta_contraente": PROCEDURE[lotto.procedura],
        "cod_modalita_realizzazione": "11" if accordo else "1",
        "modalita_realizzazione": (
            "CONTRATTO D'APPALTO DISCENDENTE DA ACCORDO QUADRO/CONVENZIONE SENZA SUCCESSIVO CONFRONTO COMPETITIVO"
            if accordo
            else "CONTRATTO D'APPALTO"
        ),
        "codice_ausa": ausa(lotto.stazione),
        "cf_amministrazione_appaltante": cf_stazione(lotto.stazione),
        "denominazione_amministrazione_appaltante": nome_stazione(lotto.stazione),
        "sezione_regionale": "SEZIONE REGIONALE PUGLIA",
        "anno_pubblicazione": str(lotto.pubblicazione.year),
        "mese_pubblicazione": str(lotto.pubblicazione.month),
        "cod_cpv": codice_cpv,
        "descrizione_cpv": descrizione_cpv,
        "flag_prevalente": prevalente,
        "data_ultimo_perfezionamento": lotto.pubblicazione.isoformat(),
        "durata_prevista": "365.0",
        "flag_urgenza": "0",
        "importo_sicurezza": "0.0",
        "flag_pnrr_pnc": "1" if lotto.i % 9 == 0 else "0",
    }
    if aggiudicato(lotto.i):
        valori |= {
            "cod_esito": "1.0",
            "esito": "AGGIUDICATA",
            "data_comunicazione_esito": lotto.aggiudicazione.isoformat(),
        }
    if cancellazione is not None:
        valori |= {
            "stato": "CANCELLATO",
            "cod_motivo_cancellazione": "1",
            "motivo_cancellazione": "CANCELLAZIONE SU RICHIESTA DELLA STAZIONE APPALTANTE",
            "data_cancellazione": cancellazione.isoformat(),
        }
    return componi(contratto, valori)


def righe_cig_mensili(contratto: Contratto, lotti: list[Lotto]) -> list[list[str]]:
    righe = []
    for lotto in lotti:
        riga = riga_cig(contratto, lotto)
        righe.append(riga)
        if lotto.i % 10 == 0:
            righe.append(riga_cig(contratto, lotto, cpv=CPV_SECONDARIO, prevalente="0"))
        if lotto.i in DUPLICATI:
            righe.append(list(riga))
    return righe


def righe_delta_cig(contratto: Contratto, lotti: list[Lotto]) -> list[list[str]]:
    per_indice = {lotto.i: lotto for lotto in lotti}
    righe = [
        riga_cig(contratto, per_indice[i], importo=round(per_indice[i].importo * 1.1, 2)) for i in AGGIORNATI
    ]
    righe.append(riga_cig(contratto, per_indice[CANCELLATO], cancellazione=date(2026, 3, 15)))
    return righe


def _ribasso(lotto: Lotto) -> float:
    if lotto.i == RIBASSO_FUORI_INTERVALLO:
        return 120.0
    return round((lotto.i % 30) + 0.5, 2) if lotto.procedura in COMPETITIVE else 0.0


def riga_aggiudicazione(contratto: Contratto, lotto: Lotto, *, fattore_importo: float = 1.0) -> list[str]:
    ribasso = _ribasso(lotto)
    offerte = str(n_offerte(lotto.i))
    importo = lotto.importo * (1 - min(ribasso, 100.0) / 100) * fattore_importo
    return componi(
        contratto,
        {
            "cig": cig(lotto.i),
            "data_aggiudicazione_definitiva": lotto.aggiudicazione.isoformat(),
            "esito": "AGGIUDICATA",
            "criterio_aggiudicazione": "OFFERTA ECONOMICAMENTE PIU' VANTAGGIOSA"
            if lotto.procedura in COMPETITIVE
            else "PREZZO PIU' BASSO",
            "data_comunicazione_esito": lotto.aggiudicazione.isoformat(),
            "numero_offerte_ammesse": offerte,
            "numero_offerte_escluse": "0",
            "importo_aggiudicazione": f"{importo:.2f}",
            "ribasso_aggiudicazione": f"{ribasso}",
            "num_imprese_offerenti": offerte,
            "flag_subappalto": "true" if lotto.i % 40 == 0 else "false",
            "id_aggiudicazione": str(5_000_000 + lotto.i),
            "cod_esito": "1",
            "asta_elettronica": "0",
            "flag_scomputo": "0",
            "flag_proc_accelerata": "0",
        },
    )


def righe_aggiudicazioni(contratto: Contratto, lotti: list[Lotto]) -> list[list[str]]:
    return [riga_aggiudicazione(contratto, lotto) for lotto in lotti if aggiudicato(lotto.i)]


def righe_delta_aggiudicazioni(contratto: Contratto, lotti: list[Lotto]) -> list[list[str]]:
    """Delta del mese 2: 20 aggiudicazioni con importo ridotto del 3 % e una aggiudicazione nuova."""
    per_indice = {lotto.i: lotto for lotto in lotti}
    righe = [
        riga_aggiudicazione(contratto, per_indice[i], fattore_importo=0.97) for i in AGGIUDICAZIONI_AGGIORNATE
    ]
    righe.append(riga_aggiudicazione(contratto, per_indice[AGGIUDICAZIONE_NUOVA]))
    return righe


def righe_aggiudicatari(contratto: Contratto, lotti: list[Lotto]) -> list[list[str]]:
    return [
        componi(
            contratto,
            {
                "cig": cig(lotto.i),
                "ruolo": "OPERATORE ECONOMICO MONOSOGGETTIVO",
                "codice_fiscale": cf_operatore(lotto.i % 40),
                "denominazione": nome_operatore(lotto.i % 40),
                "tipo_soggetto": "IMPRESA",
                "id_aggiudicazione": str(5_000_000 + lotto.i),
            },
        )
        for lotto in lotti
        if aggiudicato(lotto.i) and lotto.i != SENZA_AGGIUDICATARIO
    ]


def righe_partecipanti(contratto: Contratto, lotti: list[Lotto]) -> list[list[str]]:
    righe = []
    for lotto in lotti:
        if not aggiudicato(lotto.i):
            continue
        for j in range(n_offerte(lotto.i)):
            k = (lotto.i + j) % 40
            righe.append(
                componi(
                    contratto,
                    {
                        "cig": cig(lotto.i),
                        "ruolo": "OPERATORE ECONOMICO MONOSOGGETTIVO",
                        "codice_fiscale": cf_operatore(k),
                        "denominazione": nome_operatore(k),
                        "tipo_soggetto": "IMPRESA",
                    },
                )
            )
    return righe


def righe_varianti(contratto: Contratto, lotti: list[Lotto]) -> list[list[str]]:
    return [
        componi(
            contratto,
            {
                "id_variante": str(700_000 + lotto.i),
                "cod_motivo_variante": "1",
                "motivo_variante": "REVISIONE DEI PREZZI",
                "data_approvazione_variante": (lotto.aggiudicazione + timedelta(days=90)).isoformat(),
                "cig": cig(lotto.i),
                "id_aggiudicazione": str(5_000_000 + lotto.i),
                "data_atto_aggiuntivo": (lotto.aggiudicazione + timedelta(days=95)).isoformat(),
            },
        )
        for lotto in lotti
        if lotto.i % 50 == 0
    ]


def righe_subappalti(contratto: Contratto, lotti: list[Lotto]) -> list[list[str]]:
    return [
        componi(
            contratto,
            {
                "cig": cig(lotto.i),
                "id_subappalto": f"{cig(lotto.i)}|{lotto.i}",
                "cf_subappaltante": cf_operatore(lotto.i % 40),
                "data_autorizzazione": (lotto.aggiudicazione + timedelta(days=30)).isoformat(),
                "oggetto": "OPERE ACCESSORIE",
                "cod_categoria": "OG 1",
                "descrizione_categoria": "OG 1 - EDIFICI CIVILI E INDUSTRIALI",
                "descrizione_tipo_categoria": "PREVALENTE",
                "cod_cpv": lotto.cpv,
                "descrizione_cpv": lotto.descrizione_cpv,
                "codice_fiscale": cf_operatore((lotto.i + 7) % 40),
                "denominazione": nome_operatore((lotto.i + 7) % 40),
                "tipo_soggetto": "IMPRESA",
            },
        )
        for lotto in lotti
        if lotto.i % 40 == 0
    ]


def righe_stazioni(contratto: Contratto, lotti: list[Lotto]) -> list[list[str]]:
    righe = []
    for s in range(12):
        provincia = PROVINCE[s % len(PROVINCE)]
        righe.append(
            componi(
                contratto,
                {
                    "codice_fiscale": cf_stazione(s),
                    "partita_iva": cf_stazione(s),
                    "denominazione": nome_stazione(s),
                    "codice_ausa": ausa(s),
                    "natura_giuridica_codice": "1",
                    "natura_giuridica_descrizione": "AMMINISTRAZIONI COMUNALI",
                    "soggetto_estero": "false",
                    "provincia_codice": f"IT-{provincia[1]}",
                    "provincia": provincia[2],
                    "codice_comune": f"{provincia[0]}{s + 1:03d}",
                    "comune": f"COMUNE DI ESEMPIO {s:02d}",
                    "flag_inhouse": "false",
                    "flag_partecipata": "false",
                    "stato": "ATTIVO",
                    "data_inizio": "2013-07-09 19:19:04.143",
                    "data_fine": "2099-12-31 01:00:00.0",
                },
            )
        )
    return righe


def righe_procedure(contratto: Contratto, lotti: list[Lotto]) -> list[list[str]]:
    return [
        componi(contratto, {"cod_tipo_scelta_contraente": codice, "tipo_scelta_contraente": descrizione})
        for codice, descrizione in PROCEDURE.items()
    ]


def csv_anac(intestazione: list[str], righe: list[list[str]]) -> bytes:
    def campo(valore: str) -> str:
        return "" if valore == "" else '"' + valore.replace('"', '""') + '"'

    linee = [";".join(campo(h) for h in intestazione)] + [";".join(campo(v) for v in riga) for riga in righe]
    return ("\n".join(linee) + "\n").encode("utf-8")


def scrivi_zip(percorso: Path, nome_interno: str, contenuto: bytes) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    info = zipfile.ZipInfo(nome_interno, date_time=DATA_ZIP)
    info.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(percorso, "w") as archivio:
        archivio.writestr(info, contenuto)


def _url(pacchetto: str, file: str) -> str:
    return f"{BASE_URL}/download/dataset/{pacchetto}/filesystem/{file}"


class Specchio:
    """Scrive uno specchio CKAN: files/{pacchetto}/{file} e ckan/{pacchetto}.json con il logCsv."""

    def __init__(self, cartella: Path) -> None:
        self.cartella = cartella
        self.risorse: dict[str, list[dict]] = {}
        self.log_extra: dict[str, list[str]] = {}
        self.lm_log: dict[str, str] = {}

    def zip(
        self, pacchetto: str, file: str, contratto: Contratto, righe: list[list[str]], last_modified: str
    ) -> None:
        contenuto = csv_anac(contratto.sorgenti, righe)
        scrivi_zip(self.cartella / "files" / pacchetto / file, file.removesuffix(".zip") + ".csv", contenuto)
        self.risorse.setdefault(pacchetto, []).append(
            {"file": file, "size": len(contenuto), "last_modified": last_modified, "righe": len(righe)}
        )

    def log(self, pacchetto: str, righe_log: list[str], last_modified: str) -> None:
        self.risorse.setdefault(pacchetto, [])
        self.log_extra.setdefault(pacchetto, []).extend(righe_log)
        self.lm_log[pacchetto] = last_modified

    def chiudi(self) -> None:
        for pacchetto, risorse in sorted(self.risorse.items()):
            annuale = pacchetto.startswith("cig-")
            righe_log = list(self.log_extra.get(pacchetto, []))
            for r in risorse:
                stem = r["file"].removesuffix(".zip")
                if annuale:
                    righe_log.append(
                        f"{pacchetto};{pacchetto};{stem.replace('_csv_', '_ttl_')}.ttl;{r['righe'] * 60};ttl;15-01-2026;{r['last_modified']}.000"
                    )
                else:
                    righe_log.append(
                        f"{pacchetto};{pacchetto};{stem}.csv;{r['righe']};csv;15-01-2026;{r['last_modified']}.000"
                    )
            testo_log = (
                "identifier;nome_dataset;nome_risorsa;numero_righe;formato;data;ultimaModifica\n\n"
                + "\n".join(righe_log)
                + "\n"
            ).encode("utf-8")
            nome_log = f"{pacchetto}_csv_logCsv.csv"
            percorso_log = self.cartella / "files" / pacchetto / nome_log
            percorso_log.parent.mkdir(parents=True, exist_ok=True)
            percorso_log.write_bytes(testo_log)
            date_lm = [r["last_modified"] for r in risorse] + (
                [self.lm_log[pacchetto]] if pacchetto in self.lm_log else []
            )
            lm_log = max(date_lm)
            resources = [
                {
                    "name": r["file"].removesuffix(".zip"),
                    "format": "CSV",
                    "size": r["size"],
                    "last_modified": r["last_modified"],
                    "url": _url(pacchetto, r["file"]),
                }
                for r in risorse
            ]
            resources.append(
                {
                    "name": nome_log.removesuffix(".csv"),
                    "format": "CSV",
                    "size": len(testo_log),
                    "last_modified": lm_log,
                    "url": _url(pacchetto, nome_log),
                }
            )
            resources.append(
                {
                    "name": f"{pacchetto}_json",
                    "format": "JSON",
                    "size": 1,
                    "last_modified": lm_log,
                    "url": _url(pacchetto, f"{pacchetto}_json.zip"),
                }
            )
            documento = {
                "help": "fixture sintetica anac-appalti-dbt",
                "success": True,
                "result": {
                    "name": pacchetto,
                    "license_id": "CC-BY-SA-4.0",
                    "metadata_modified": lm_log + ".000000",
                    "resources": resources,
                },
            }
            percorso_json = self.cartella / "ckan" / f"{pacchetto}.json"
            percorso_json.parent.mkdir(parents=True, exist_ok=True)
            percorso_json.write_text(
                json.dumps(documento, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
            )


GENERATORI = (
    ("aggiudicazioni", righe_aggiudicazioni),
    ("aggiudicatari", righe_aggiudicatari),
    ("partecipanti", righe_partecipanti),
    ("varianti", righe_varianti),
    ("subappalti", righe_subappalti),
    ("stazioni-appaltanti", righe_stazioni),
    ("bandi-cig-tipo-scelta-contraente", righe_procedure),
)


def genera_fixture(contratti_dir: Path, destinazione: Path) -> dict[str, int]:
    contratti = carica_contratti(contratti_dir)
    per_pacchetto = {c.pacchetto: c for c in contratti.values()}
    lotti = crea_lotti(random.Random(2026))
    contratto_cig = per_pacchetto["cig"]
    conteggi: dict[str, int] = {}
    for mese in (1, 2):
        cartella = destinazione / f"mese{mese}"
        if cartella.exists():
            shutil.rmtree(cartella)
        specchio = Specchio(cartella)
        for mese_file, file in ((1, "cig_csv_2025_01.zip"), (2, "cig_csv_2025_02.zip")):
            righe = righe_cig_mensili(contratto_cig, [lotto for lotto in lotti if lotto.mese == mese_file])
            specchio.zip("cig-2025", file, contratto_cig, righe, LM["cig-2025"])
            conteggi[file] = len(righe)
        specchio.log("cig", [RIGA_LOG_CIG_VECCHIA], LM_LOG_CIG)
        if mese == 2:
            delta = righe_delta_cig(contratto_cig, lotti)
            specchio.zip("cig", "20260401-cig_csv.zip", contratto_cig, delta, LM_DELTA)
            conteggi["20260401-cig_csv.zip"] = len(delta)
            delta_agg = righe_delta_aggiudicazioni(per_pacchetto["aggiudicazioni"], lotti)
            specchio.zip(
                "aggiudicazioni",
                "20260401-aggiudicazioni_csv.zip",
                per_pacchetto["aggiudicazioni"],
                delta_agg,
                LM_DELTA,
            )
            conteggi["20260401-aggiudicazioni_csv.zip"] = len(delta_agg)
        for pacchetto, generatore in GENERATORI:
            contratto = per_pacchetto[pacchetto]
            righe = generatore(contratto, lotti)
            file = f"{pacchetto}_csv.zip"
            specchio.zip(pacchetto, file, contratto, righe, LM[pacchetto])
            conteggi[file] = len(righe)
        specchio.chiudi()
    return conteggi
