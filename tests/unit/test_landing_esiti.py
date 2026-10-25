from pathlib import Path

import pytest
from typer.testing import CliRunner

from anac_appalti import cli
from anac_appalti.archivio import ArchivioNonIntegro, leggi_manifest, righe_attese_tabella
from anac_appalti.config import carica_impostazioni
from anac_appalti.landing import _connetti, leggi_registro
from tests.unit.landing_aiuti import CONTRATTI, atterra, leggi_parquet, registra_csv, registra_log, riga

CF_A = "RSSMRA80A01H501U"
CF_B = "BNCLRA85M41H501Z"


def agg(i: int, **valori: str) -> str:
    base = {
        "cig": f"FX{i:08d}",
        "ruolo": "MANDANTE",
        "codice_fiscale": "10000104729",
        "denominazione": "IMPRESA ESEMPIO 01 S.R.L.",
        "tipo_soggetto": "IMPRESA",
        "id_aggiudicazione": str(5_000_000 + i),
    }
    return riga(CONTRATTI["aggiudicatari"], **(base | valori))


def test_differenza_di_riconciliazione_e_un_avviso_e_un_fallimento(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    registra_log(imp, "aggiudicatari", 4)
    registra_csv(imp, "aggiudicatari", [agg(1), agg(2), agg(3)])
    riepilogo, voce = atterra(imp, "aggiudicatari")
    assert riepilogo.atterrati == 1 and riepilogo.errori == []
    assert (voce.righe, voce.righe_attese, voce.riconciliazione, voce.esito) == (
        "3",
        "4",
        "differenza",
        "atterrato",
    )
    assert "righe attese 4, atterrate 3" in voce.messaggio
    assert riepilogo.differenze == 1 and riepilogo.con_scarti == 0
    assert any("aggiudicatari_csv" in a and "3" in a and "4" in a for a in riepilogo.avvisi)
    assert not riepilogo.riuscito


def test_differenza_resta_segnalata_alla_seconda_esecuzione(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    registra_log(imp, "aggiudicatari", 4)
    registra_csv(imp, "aggiudicatari", [agg(1), agg(2), agg(3)])
    atterra(imp, "aggiudicatari")
    seconda, _ = atterra(imp, "aggiudicatari")
    assert seconda.saltati == 1 and seconda.atterrati == 0
    assert seconda.differenze == 1 and not seconda.riuscito
    assert any("diverse" in a for a in seconda.avvisi)


def test_riconciliazione_ok_e_riuscita(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    registra_log(imp, "aggiudicatari", 2)
    registra_csv(imp, "aggiudicatari", [agg(1), agg(2)])
    riepilogo, voce = atterra(imp, "aggiudicatari")
    assert voce.riconciliazione == "ok" and voce.messaggio == ""
    assert riepilogo.differenze == 0 and riepilogo.riuscito
    assert not any("non riconciliabile" in a for a in riepilogo.avvisi)


def test_file_senza_conteggio_righe_e_non_riconciliabile(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    registra_csv(imp, "aggiudicatari", [agg(1)])
    riepilogo, voce = atterra(imp, "aggiudicatari")
    assert voce.riconciliazione == "non_disponibile"
    assert any("non riconciliabile" in a and "aggiudicatari_csv" in a for a in riepilogo.avvisi)
    assert riepilogo.riuscito  # non riconciliabile è un'informazione, non un errore


def test_letto_con_scarti_e_un_avviso_e_la_privacy_vale_anche_nel_fallback(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    corta = '"FX00000002";"MANDANTE";"10000104729";"IMPRESA";"IMPRESA"'  # manca l'ultima colonna
    registra_csv(
        imp,
        "aggiudicatari",
        [agg(1, codice_fiscale=CF_A, denominazione="ROSSI MARIO"), corta, agg(3, codice_fiscale=CF_B)],
    )
    riepilogo, voce = atterra(imp, "aggiudicatari")
    assert voce.esito == "letto_con_scarti"
    assert "1 righe illeggibili scartate" in voce.messaggio
    assert voce.righe == "2"
    assert riepilogo.atterrati == 1 and riepilogo.errori == []
    assert riepilogo.con_scarti == 1 and not riepilogo.riuscito
    assert any("letto con scarti" in a for a in riepilogo.avvisi)
    righe = leggi_parquet(imp, voce)
    assert all(r["codice_fiscale"] is None and r["denominazione"] is None for r in righe)
    assert [r["_classe_cf"] for r in righe] == ["persona_fisica", "persona_fisica"]
    assert len({r["_hash_riga"] for r in righe}) == 2
    testo = "|".join(str(v) for r in righe for v in r.values() if v is not None)
    assert CF_A not in testo and CF_B not in testo and "ROSSI MARIO" not in testo
    assert atterra(imp, "aggiudicatari")[0].con_scarti == 1  # resta segnalato


def test_copia_archiviata_alterata_non_atterra(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    voce = registra_csv(imp, "aggiudicatari", [agg(1), agg(2)])
    percorso = imp.area / voce.percorso
    dati = bytearray(percorso.read_bytes())
    dati[len(dati) // 2] ^= 0x01
    percorso.write_bytes(bytes(dati))
    riepilogo, registro = atterra(imp, "aggiudicatari")
    assert riepilogo.atterrati == 0 and len(riepilogo.errori) == 1
    assert "non corrisponde al manifest" in riepilogo.errori[0]
    assert registro.esito == "errore"
    assert not list((tmp_path / "data" / "landing").rglob("*.parquet"))


def test_copia_archiviata_mancante_non_atterra(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    voce = registra_csv(imp, "aggiudicatari", [agg(1)])
    (imp.area / voce.percorso).unlink()
    riepilogo, registro = atterra(imp, "aggiudicatari")
    assert riepilogo.atterrati == 0 and "il file archiviato manca" in riepilogo.errori[0]
    assert registro.esito == "errore"


def test_log_alterato_ferma_la_lettura_dei_conteggi(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    voce = registra_log(imp, "aggiudicatari", 3)
    (imp.area / voce.percorso).write_bytes(b"identifier;numero_righe\n")
    with pytest.raises(ArchivioNonIntegro):
        righe_attese_tabella(imp, "aggiudicatari", leggi_manifest(imp.manifest_file))


def test_sha256_nel_parquet_e_quello_del_file(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    voce = registra_csv(imp, "aggiudicatari", [agg(1)])
    _, registro = atterra(imp, "aggiudicatari")
    (riga_parquet,) = leggi_parquet(imp, registro)
    assert riga_parquet["_sha256"] == voce.sha256 == registro.sha256


def test_limiti_duckdb_dalla_configurazione(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    assert (imp.duckdb.memory_limit, imp.duckdb.threads) == ("2GB", 4)
    con = _connetti(imp)
    try:
        assert con.execute("select current_setting('threads')").fetchone()[0] == 4
        assert con.execute("select current_setting('memory_limit')").fetchone()[0].startswith("1.8")
        assert Path(con.execute("select current_setting('temp_directory')").fetchone()[0]) == imp.tmp_duckdb
    finally:
        con.close()


def test_cli_landing_esce_con_1_se_la_riconciliazione_ha_differenze(tmp_path: Path, monkeypatch):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    monkeypatch.setattr(cli, "carica_impostazioni", lambda **_: imp)
    registra_log(imp, "aggiudicatari", 4)
    registra_csv(imp, "aggiudicatari", [agg(1), agg(2), agg(3)])
    risultato = CliRunner().invoke(cli.app, ["landing", "--fixtures", "--pacchetti", "aggiudicatari"])
    assert risultato.exit_code == 1
    assert "diverse" in risultato.output


def test_cli_landing_esce_con_0_se_tutto_riconcilia(tmp_path: Path, monkeypatch):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    monkeypatch.setattr(cli, "carica_impostazioni", lambda **_: imp)
    registra_log(imp, "aggiudicatari", 2)
    registra_csv(imp, "aggiudicatari", [agg(1), agg(2)])
    risultato = CliRunner().invoke(cli.app, ["landing", "--fixtures", "--pacchetti", "aggiudicatari"])
    assert risultato.exit_code == 0, risultato.output
    assert len(leggi_registro(imp.registro_file)) == 1
