from pathlib import Path

from anac_appalti.archivio import leggi_manifest, registra_manuali
from anac_appalti.config import carica_impostazioni


def test_registra_file_messi_a_mano(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    cartella = imp.raw / "anac" / "varianti"
    cartella.mkdir(parents=True)
    (cartella / "varianti_csv.zip").write_bytes(b"zip finto")
    (cartella / "varianti_csv_logCsv.csv").write_text("identifier;nome_dataset\n", encoding="utf-8")
    (cartella / "note.txt").write_text("ignorato", encoding="utf-8")
    assert registra_manuali(imp) == 2
    voci = {v.risorsa: v for v in leggi_manifest(imp.manifest_file)}
    assert set(voci) == {"varianti_csv.zip", "varianti_csv_logCsv.csv"}
    assert voci["varianti_csv.zip"].tabella == "varianti"
    assert voci["varianti_csv.zip"].url.endswith("/download/dataset/varianti/filesystem/varianti_csv.zip")
    assert voci["varianti_csv.zip"].percorso == "data/raw/anac/varianti/varianti_csv.zip"
    assert registra_manuali(imp) == 0
