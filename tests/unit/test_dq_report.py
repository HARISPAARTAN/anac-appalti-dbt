from anac_appalti.dq_report import QUERY, componi_report


def test_report_deterministico_e_completo():
    indicatori = {chiave: 0 for chiave in QUERY}
    indicatori.update(
        {
            "lotti_correnti": 1500,
            "versioni_lotti": 1500,
            "righe_cig": 1653,
            "duplicati_esatti": 3,
            "date_impossibili": 2,
            "importi_anomali": 2,
            "senza_aggiudicatario": 1,
            "righe_operatori": 4000,
            "file_atterrati": 9,
            "file_riconciliati": 7,
            "file_non_verificabili": 2,
        }
    )
    testo = componi_report(indicatori, "2026-10-25")
    assert testo == componi_report(indicatori, "2026-10-25")
    assert testo.startswith("# Qualità dei dati")
    assert "| Date impossibili |" in testo and "| 2 | 0,13 % |" in testo
    assert "1.653" in testo
    assert "Fonte: ANAC – Autorità Nazionale Anticorruzione" in testo


def test_report_mostra_importi_illeggibili_e_perdite_di_parsing():
    indicatori = {chiave: 0 for chiave in QUERY}
    indicatori.update(
        {
            "lotti_correnti": 1000,
            "importi_non_leggibili": 7,
            "aggiudicazioni_non_leggibili": 3,
            "aggiudicazioni_correnti": 800,
            "perdite_date": 5,
            "valori_date": 2500,
            "perdite_conteggi": 11,
            "valori_conteggi": 1600,
        }
    )
    testo = componi_report(indicatori, "2026-10-25")
    assert "| Importo non leggibile |" in testo and "| 7 | 0,70 % |" in testo
    assert "| Aggiudicazione non leggibile |" in testo and "| 3 | 0,38 % |" in testo
    assert "| Date non leggibili |" in testo and "| 5 | 0,20 % |" in testo
    assert "| Conteggi di offerte non leggibili |" in testo and "| 11 | 0,69 % |" in testo


def test_magazzino_mancante_non_viene_creato(tmp_path):
    """Report ed esportazione aprono il magazzino in sola lettura: un percorso sbagliato fallisce senza creare un file."""
    import duckdb
    import pytest

    from anac_appalti.config import carica_impostazioni
    from anac_appalti.dq_report import calcola_indicatori
    from anac_appalti.export import esporta_mart

    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    assert not imp.warehouse_file.exists()
    with pytest.raises(duckdb.Error):
        calcola_indicatori(imp)
    with pytest.raises(duckdb.Error):
        esporta_mart(imp, tmp_path / "export")
    assert not imp.warehouse_file.exists()


def test_report_della_fixture_e_marcato_come_tale():
    indicatori = {chiave: 0 for chiave in QUERY}
    fixture = componi_report(indicatori, "2026-10-25", fixtures=True, mese=2)
    righe = fixture.splitlines()
    assert righe[0] == "# Qualità dei dati (report sulla fixture sintetica)"
    assert "non dei dati ANAC reali" in righe[2]
    assert "fixture sintetica (mese 2)" in righe[4] and "2026-10-25" in righe[4]
    reale = componi_report(indicatori, "2026-10-25")
    assert reale.splitlines()[0] == "# Qualità dei dati"
    assert "fixture" not in reale.lower()
