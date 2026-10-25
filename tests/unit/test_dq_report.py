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
