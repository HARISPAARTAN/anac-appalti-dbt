import hashlib
import zipfile
from pathlib import Path

from anac_appalti.config import carica_impostazioni
from anac_appalti.fixture import aggiudicato, genera_fixture, n_offerte
from anac_appalti.privacy import cerca_cf_personali

IMP = carica_impostazioni()
COMMESSA = IMP.radice / "data" / "fixtures"


def impronte(cartella: Path) -> dict[str, str]:
    return {
        p.relative_to(cartella).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(cartella.rglob("*"))
        if p.is_file()
    }


def test_fixture_committata_uguale_al_generatore(tmp_path: Path):
    conteggi = genera_fixture(IMP.contratti_dir, tmp_path)
    assert impronte(tmp_path) == impronte(COMMESSA)
    partecipanti = sum(n_offerte(i) for i in range(1, 1501) if aggiudicato(i))
    assert conteggi == {
        "cig_csv_2025_01.zip": 828,
        "cig_csv_2025_02.zip": 825,
        "20260401-cig_csv.zip": 51,
        "aggiudicazioni_csv.zip": 1200,
        "aggiudicatari_csv.zip": 1199,
        "partecipanti_csv.zip": partecipanti,
        "varianti_csv.zip": 30,
        "subappalti_csv.zip": 37,
        "stazioni-appaltanti_csv.zip": 12,
        "bandi-cig-tipo-scelta-contraente_csv.zip": 6,
    }


def test_fixture_senza_persone_fisiche_e_piccola():
    totale = 0
    for percorso in COMMESSA.rglob("*.zip"):
        totale += percorso.stat().st_size
        with zipfile.ZipFile(percorso) as z:
            for nome in z.namelist():
                assert cerca_cf_personali(z.read(nome).decode("utf-8")) == [], percorso
    assert totale < 5_000_000
