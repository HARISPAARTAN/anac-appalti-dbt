from datetime import date, datetime
from pathlib import Path

import pytest

from anac_appalti.archivio import (
    SpazioInsufficiente,
    archivia,
    controlla_spazio,
    da_scaricare,
    data_snapshot,
    leggi_manifest,
    nomi_ckan,
    righe_attese_da_log,
    seleziona_risorse,
)
from anac_appalti.ckan import Risorsa
from anac_appalti.config import Pacchetto, carica_impostazioni

BASE = "https://dati.anticorruzione.it/opendata/download/dataset"


def r(pacchetto: str, file: str, lm: str, dimensione: int = 10) -> Risorsa:
    return Risorsa(
        pacchetto,
        file,
        f"{BASE}/{pacchetto}/filesystem/{file}",
        "CSV",
        dimensione,
        datetime.fromisoformat(lm),
    )


class FonteFinta:
    user_agent_usato = "finta"

    def __init__(self, contenuto: bytes) -> None:
        self.contenuto = contenuto

    def scarica(self, url: str, destinazione: Path) -> int:
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        destinazione.write_bytes(self.contenuto)
        return len(self.contenuto)


def test_data_snapshot():
    assert data_snapshot("20260401-cig_csv.zip", "2026-04-02T00:00:00") == date(2026, 4, 1)
    assert data_snapshot("cig_csv_2025_01.zip", datetime(2026, 1, 16)) == date(2026, 1, 16)
    assert data_snapshot("aggiudicazioni_csv.zip", "2026-01-15T00:00:00") == date(2026, 1, 15)


def test_nomi_ckan():
    assert nomi_ckan(Pacchetto("cig", "cig", True), (2024, 2025)) == ["cig-2024", "cig-2025", "cig"]
    assert nomi_ckan(Pacchetto("varianti", "varianti"), (2024,)) == ["varianti"]


def test_seleziona_cig_annuale_e_delta_successivi():
    cataloghi = {
        "cig-2025": [
            r("cig-2025", "cig-2025_csv_logCsv.csv", "2026-01-21T00:00:00"),
            r("cig-2025", "cig_csv_2025_01.zip", "2026-01-16T00:00:00"),
            r("cig-2025", "cig_csv_2025_02.zip", "2026-01-16T00:00:00"),
        ],
        "cig": [
            r("cig", "cig_csv_logCsv.csv", "2026-10-05T00:00:00"),
            r("cig", "20251201-cig_csv.zip", "2025-12-03T00:00:00"),
            r("cig", "20260401-cig_csv.zip", "2026-04-02T00:00:00"),
        ],
    }
    scelte = [x.file for x in seleziona_risorse(Pacchetto("cig", "cig", True), cataloghi)]
    assert scelte == [
        "cig_csv_logCsv.csv",
        "cig-2025_csv_logCsv.csv",
        "20260401-cig_csv.zip",
        "cig_csv_2025_01.zip",
        "cig_csv_2025_02.zip",
    ]


def test_seleziona_pacchetto_completo_piu_delta():
    cataloghi = {
        "aggiudicazioni": [
            r("aggiudicazioni", "20260101-aggiudicazioni_csv.zip", "2026-01-05T00:00:00"),
            r("aggiudicazioni", "20260401-aggiudicazioni_csv.zip", "2026-04-02T00:00:00"),
            r("aggiudicazioni", "aggiudicazioni_csv.zip", "2026-01-15T00:00:00"),
            r("aggiudicazioni", "aggiudicazioni_csv_logCsv.csv", "2026-10-05T00:00:00"),
        ]
    }
    scelte = [x.file for x in seleziona_risorse(Pacchetto("aggiudicazioni", "aggiudicazioni"), cataloghi)]
    assert scelte == [
        "aggiudicazioni_csv_logCsv.csv",
        "20260401-aggiudicazioni_csv.zip",
        "aggiudicazioni_csv.zip",
    ]


def test_righe_attese_da_log_ultima_versione():
    testo = (
        "identifier;nome_dataset;nome_risorsa;numero_righe;formato;data;ultimaModifica\n\n"
        "cig;cig;20240201-cig_csv.csv;73349;csv;12-02-2024;2024-02-12T11:43:43.999\n"
        "cig;cig;20240201-cig_csv.csv;73350;csv;12-02-2024;2024-02-27T15:48:44.677\n"
        "cig;cig;20240201-cig_ttl.ttl;4750127;ttl;12-02-2024;2024-02-12T11:45:24.787\n"
    )
    assert righe_attese_da_log(testo) == {"20240201-cig_csv.csv": 73350}


def test_archivio_append_only_e_manifest(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    p = Pacchetto("varianti", "varianti")
    manifest: list = []
    risorsa = r("varianti", "varianti_csv.zip", "2026-01-21T00:00:00")
    assert da_scaricare(risorsa, manifest)
    voce, byte = archivia(FonteFinta(b"versione-1"), risorsa, imp, p, manifest, {"varianti_csv.csv": 5})
    assert byte == 10
    assert voce.percorso.startswith("data/raw/anac/varianti/varianti_csv__20260121T0000__")
    assert voce.righe_attese == "5"
    assert not da_scaricare(risorsa, manifest)

    ripubblicata = r("varianti", "varianti_csv.zip", "2026-02-01T00:00:00")
    assert da_scaricare(ripubblicata, manifest)
    stessa, _ = archivia(FonteFinta(b"versione-1"), ripubblicata, imp, p, manifest, {})
    assert stessa.percorso == voce.percorso

    cambiata = r("varianti", "varianti_csv.zip", "2026-03-01T00:00:00")
    nuova, _ = archivia(FonteFinta(b"versione-2"), cambiata, imp, p, manifest, {})
    assert nuova.percorso != voce.percorso
    assert (tmp_path / voce.percorso).read_bytes() == b"versione-1"
    assert (tmp_path / nuova.percorso).read_bytes() == b"versione-2"
    assert len(leggi_manifest(imp.manifest_file)) == 3


def test_spazio_insufficiente(tmp_path: Path):
    with pytest.raises(SpazioInsufficiente):
        controlla_spazio(tmp_path, 10**9)
