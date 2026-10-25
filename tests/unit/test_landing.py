import hashlib
import io
import zipfile
from datetime import datetime
from pathlib import Path

import duckdb

from anac_appalti.archivio import VoceManifest, aggiungi_manifest
from anac_appalti.config import Pacchetto, carica_impostazioni
from anac_appalti.contratti import carica_contratti
from anac_appalti.landing import atterra_pacchetto, leggi_registro, sql_landing
from anac_appalti.privacy import cerca_cf_personali

CONTRATTI = carica_contratti(carica_impostazioni().contratti_dir)
P = Pacchetto("aggiudicatari", "aggiudicatari")
INTESTAZIONE = '"cig";"ruolo";"codice_fiscale";"denominazione";"tipo_soggetto";"id_aggiudicazione"'
RIGHE = [
    '"FX00000001";"OPERATORE ECONOMICO MONOSOGGETTIVO";"10000104729";"IMPRESA ESEMPIO 01 S.R.L.";"IMPRESA";"5000001"',
    '"FX00000002";"MANDANTE";"10000209458";"IMPRESA ESEMPIO 02 S.R.L.";"IMPRESA";"5000002"',
    '"FX00000002";"MANDANTE";"10000209458";"IMPRESA ESEMPIO 02 S.R.L.";"IMPRESA";"5000002"',
]


def registra(imp, nome: str, contenuto: bytes, lm: str) -> None:
    percorso = imp.raw / "anac" / "aggiudicatari" / f"{nome}__{lm[:10]}"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_bytes(contenuto)
    aggiungi_manifest(
        imp.manifest_file,
        VoceManifest(
            pacchetto="aggiudicatari",
            tabella="aggiudicatari",
            risorsa=nome,
            url=f"https://x/{nome}",
            dimensione=len(contenuto),
            last_modified=lm,
            sha256=hashlib.sha256(contenuto).hexdigest(),
            percorso=percorso.relative_to(imp.area).as_posix(),
            scaricato_il=datetime.now().isoformat(),
            righe_attese="",
        ),
    )


def zip_csv(intestazione: str, righe: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("aggiudicatari_csv.csv", "\n".join([intestazione, *righe]) + "\n")
    return buffer.getvalue()


def log_csv(n: int) -> bytes:
    return (
        "identifier;nome_dataset;nome_risorsa;numero_righe;formato;data;ultimaModifica\n\n"
        f"aggiudicatari;aggiudicatari;aggiudicatari_csv.csv;{n};csv;28-10-2022;2026-01-23T13:01:01.912\n"
    ).encode()


def test_atterraggio_riconciliazione_e_idempotenza(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    registra(imp, "aggiudicatari_csv_logCsv.csv", log_csv(3), "2026-01-23T00:00:00")
    registra(imp, "aggiudicatari_csv.zip", zip_csv(INTESTAZIONE, RIGHE), "2026-01-23T00:00:00")
    riepilogo = atterra_pacchetto(imp, P, CONTRATTI["aggiudicatari"])
    assert riepilogo.atterrati == 1 and riepilogo.errori == []
    voce = leggi_registro(imp.registro_file)[0]
    assert (voce.righe, voce.righe_attese, voce.riconciliazione, voce.esito) == ("3", "3", "ok", "atterrato")
    assert voce.data_snapshot == "2026-01-23"
    con = duckdb.connect()
    colonne = [
        r[0]
        for r in con.execute(
            f"describe select * from read_parquet('{(tmp_path / voce.parquet).as_posix()}')"
        ).fetchall()
    ]
    hash_righe = con.execute(
        f"select count(distinct _hash_riga) from read_parquet('{(tmp_path / voce.parquet).as_posix()}')"
    ).fetchone()[0]
    con.close()
    assert colonne == [
        "cig",
        "ruolo",
        "codice_fiscale",
        "denominazione",
        "tipo_soggetto",
        "id_aggiudicazione",
        "_risorsa",
        "_data_snapshot",
        "_caricato_il",
        "_sha256",
        "_hash_riga",
    ]
    assert hash_righe == 2
    assert atterra_pacchetto(imp, P, CONTRATTI["aggiudicatari"]).saltati == 1


def test_colonna_nuova_avvisa_e_non_atterra(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    righe = [riga + ';"extra"' for riga in RIGHE]
    registra(
        imp, "aggiudicatari_csv.zip", zip_csv(INTESTAZIONE + ';"colonna_nuova"', righe), "2026-01-23T00:00:00"
    )
    riepilogo = atterra_pacchetto(imp, P, CONTRATTI["aggiudicatari"])
    assert riepilogo.atterrati == 1
    assert "colonna_nuova" in riepilogo.avvisi[0]
    voce = leggi_registro(imp.registro_file)[0]
    assert voce.riconciliazione == "non_disponibile"
    con = duckdb.connect()
    colonne = [
        r[0]
        for r in con.execute(
            f"describe select * from read_parquet('{(tmp_path / voce.parquet).as_posix()}')"
        ).fetchall()
    ]
    con.close()
    assert "colonna_nuova" not in colonne


def test_colonna_mancante_ferma_il_pacchetto(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    intestazione = '"cig";"ruolo";"codice_fiscale";"denominazione";"id_aggiudicazione"'
    righe = ['"FX00000001";"MANDANTE";"10000104729";"IMPRESA";"5"']
    registra(imp, "aggiudicatari_csv.zip", zip_csv(intestazione, righe), "2026-01-23T00:00:00")
    riepilogo = atterra_pacchetto(imp, P, CONTRATTI["aggiudicatari"])
    assert riepilogo.atterrati == 0
    assert "tipo_soggetto" in riepilogo.errori[0]
    assert leggi_registro(imp.registro_file)[0].esito == "errore"
    assert not list((tmp_path / "data" / "landing").rglob("*.parquet"))


def test_nuova_versione_sostituisce_la_precedente(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    registra(imp, "aggiudicatari_csv.zip", zip_csv(INTESTAZIONE, RIGHE[:1]), "2026-01-23T00:00:00")
    atterra_pacchetto(imp, P, CONTRATTI["aggiudicatari"])
    registra(imp, "aggiudicatari_csv.zip", zip_csv(INTESTAZIONE, RIGHE), "2026-02-23T00:00:00")
    atterra_pacchetto(imp, P, CONTRATTI["aggiudicatari"])
    registro = leggi_registro(imp.registro_file)
    assert [v.esito for v in registro] == ["sostituito", "atterrato"]
    assert len(list((tmp_path / "data" / "landing" / "aggiudicatari").glob("*.parquet"))) == 1


def test_sql_landing_quota_le_colonne(tmp_path: Path):
    sql = sql_landing(
        tmp_path / "a.csv",
        tmp_path / "a.parquet",
        CONTRATTI["tipi_scelta_contraente"],
        "x",
        datetime(2026, 1, 1).date(),
        "abc",
        datetime(2026, 1, 1, 10, 0, 0),
        ignora_errori=True,
    )
    assert '"tipo-scelta-contraente_codice" AS "cod_tipo_scelta_contraente"' in sql
    assert "strict_mode = false" in sql and "ignore_errors = true" in sql


CF_PERSONALE = "RSSMRA80A01H501U"
RIGHE_PERSONALI = [
    f'"FX00000001";"OPERATORE ECONOMICO MONOSOGGETTIVO";"{CF_PERSONALE}";"ROSSI MARIO";"IMPRESA INDIVIDUALE";"5000001"',
    '"FX00000002";"MANDANTE";"DE123456789";"FIRMA ESTERA GMBH";"IMPRESA";"5000002"',
    '"FX00000003";"MANDANTE";"10000104729";"IMPRESA ESEMPIO 01 S.R.L.";"IMPRESA";"5000003"',
    '"FX00000004";"MANDANTE";;"SENZA CODICE SRL";"IMPRESA";"5000004"',
]


def valori_parquet(imp, voce) -> list[str]:
    percorso = (imp.area / voce.parquet).as_posix()
    con = duckdb.connect()
    try:
        colonne = [r[0] for r in con.execute(f"describe select * from read_parquet('{percorso}')").fetchall()]
        righe = con.execute(f"select * from read_parquet('{percorso}')").fetchall()
    finally:
        con.close()
    assert colonne
    return [str(v) for riga in righe for v in riga if v is not None]


def test_landing_non_contiene_persone_fisiche(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    registra(imp, "aggiudicatari_csv.zip", zip_csv(INTESTAZIONE, RIGHE_PERSONALI), "2026-01-23T00:00:00")
    assert atterra_pacchetto(imp, P, CONTRATTI["aggiudicatari"]).errori == []
    voce = leggi_registro(imp.registro_file)[0]
    assert voce.righe == "4"
    testo = "\n".join(valori_parquet(imp, voce))
    assert CF_PERSONALE not in testo and "ROSSI MARIO" not in testo
    assert cerca_cf_personali(testo) == []
    # La partita IVA di 11 cifre e il suo nome restano; il codice estero non verificabile e il suo nome no.
    assert "10000104729" in testo and "IMPRESA ESEMPIO 01 S.R.L." in testo
    assert "DE123456789" not in testo and "FIRMA ESTERA GMBH" not in testo
    # Senza codice fiscale non c'è identità da conservare: anche la denominazione è NULL.
    assert "SENZA CODICE SRL" not in testo
    con = duckdb.connect()
    percorso = (tmp_path / voce.parquet).as_posix()
    righe = con.execute(
        f"select cig, codice_fiscale is null, denominazione is null from read_parquet('{percorso}') order by cig"
    ).fetchall()
    con.close()
    assert righe == [
        ("FX00000001", True, True),
        ("FX00000002", True, True),
        ("FX00000003", False, False),
        ("FX00000004", True, True),
    ]


def test_landing_conserva_intatto_il_raw(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    contenuto = zip_csv(INTESTAZIONE, RIGHE_PERSONALI)
    registra(imp, "aggiudicatari_csv.zip", contenuto, "2026-01-23T00:00:00")
    atterra_pacchetto(imp, P, CONTRATTI["aggiudicatari"])
    archiviato = next((imp.raw / "anac" / "aggiudicatari").glob("aggiudicatari_csv.zip*"))
    assert archiviato.read_bytes() == contenuto


def test_landing_subappalti_annulla_codici_personali(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    contratto = CONTRATTI["subappalti"]
    riga = {s: "" for s in contratto.sorgenti} | {
        "cig": "FX00000040",
        "id_subappalto": "FX00000040|40",
        "cf_subappaltante": CF_PERSONALE,
        "codice_fiscale": "RSSMRA80A01H501U",
        "denominazione": "ROSSI MARIO",
    }
    seconda = riga | {
        "id_subappalto": "FX00000040|41",
        "cf_subappaltante": "10000104729",
        "codice_fiscale": "10000209458",
        "denominazione": "IMPRESA ESEMPIO 02 S.R.L.",
    }
    intestazione = ";".join(f'"{s}"' for s in contratto.sorgenti)
    righe = [";".join(f'"{r[s]}"' if r[s] else "" for s in contratto.sorgenti) for r in (riga, seconda)]
    p = Pacchetto("subappalti", "subappalti")
    nome = "subappalti_csv"
    percorso = imp.raw / "anac" / "subappalti" / f"{nome}.zip__2026-01-15"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{nome}.csv", "\n".join([intestazione, *righe]) + "\n")
    percorso.write_bytes(buffer.getvalue())
    aggiungi_manifest(
        imp.manifest_file,
        VoceManifest(
            pacchetto="subappalti",
            tabella="subappalti",
            risorsa=f"{nome}.zip",
            url="https://x/s",
            dimensione=len(buffer.getvalue()),
            last_modified="2026-01-15T00:00:00",
            sha256=hashlib.sha256(buffer.getvalue()).hexdigest(),
            percorso=percorso.relative_to(imp.area).as_posix(),
            scaricato_il=datetime.now().isoformat(),
            righe_attese="",
        ),
    )
    assert atterra_pacchetto(imp, p, contratto).errori == []
    voce = leggi_registro(imp.registro_file)[0]
    testo = "\n".join(valori_parquet(imp, voce))
    assert CF_PERSONALE not in testo and "ROSSI MARIO" not in testo
    assert "10000104729" in testo and "10000209458" in testo and "IMPRESA ESEMPIO 02 S.R.L." in testo


def test_hash_riga_non_deriva_dai_dati_personali(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    registra(imp, "aggiudicatari_csv.zip", zip_csv(INTESTAZIONE, RIGHE_PERSONALI[:1]), "2026-01-23T00:00:00")
    atterra_pacchetto(imp, P, CONTRATTI["aggiudicatari"])
    voce = leggi_registro(imp.registro_file)[0]
    percorso = (tmp_path / voce.parquet).as_posix()
    con = duckdb.connect()
    impronta = con.execute(f"select _hash_riga from read_parquet('{percorso}')").fetchone()[0]
    con.close()
    pulita = chr(31).join(
        [
            "FX00000001",
            "OPERATORE ECONOMICO MONOSOGGETTIVO",
            chr(30),
            chr(30),
            "IMPRESA INDIVIDUALE",
            "5000001",
        ]
    )
    assert impronta == hashlib.md5(pulita.encode()).hexdigest()
