import json
from pathlib import Path

from anac_appalti.config import carica_impostazioni
from anac_appalti.pipeline import (
    ambiente_dbt,
    argomenti_comuni,
    conteggi_esiti,
    errori_dbt,
    leggi_run_results,
    salva_run_results,
    target_dbt,
    variabili_dbt,
)

RUN_RESULTS = {
    "results": [
        {"unique_id": "model.anac_appalti.stg_anac__cig", "status": "success", "message": "OK"},
        {"unique_id": "test.anac_appalti.dq_date_impossibili", "status": "warn", "message": "Got 2 results"},
        {
            "unique_id": "test.anac_appalti.assert_riconciliazione",
            "status": "fail",
            "message": "Got 1 result",
        },
        {"unique_id": "model.anac_appalti.fct_lotti", "status": "error", "message": "Binder Error"},
    ]
}


def test_variabili_e_target(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    assert target_dbt(imp) == "ci"
    assert target_dbt(carica_impostazioni()) == "locale"
    assert variabili_dbt(imp) == {
        "anno_minimo": 2025,
        "data_riferimento": "2026-10-25",
        "importo_max_plausibile": 5e9,
        "mad_fattore": 3.0,
        "giorni_scadenza_tasso": 180,
    }
    ambiente = ambiente_dbt(imp)
    assert ambiente["APPALTI_LANDING"] == (tmp_path / "data" / "landing").as_posix()
    assert ambiente["APPALTI_DUCKDB"] == (tmp_path / "data" / "warehouse" / "appalti.duckdb").as_posix()
    assert ambiente["DBT_TARGET_PATH"] == (tmp_path / "dbt_target").as_posix()
    assert argomenti_comuni(imp)[-2:] == ["--target", "ci"]


def test_run_results(tmp_path: Path):
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    assert leggi_run_results(imp) is None
    sorgente = tmp_path / "altrove" / "run_results.json"
    sorgente.parent.mkdir()
    sorgente.write_text(json.dumps(RUN_RESULTS), encoding="utf-8")
    salva_run_results(imp, sorgente)
    letti = leggi_run_results(imp)
    assert conteggi_esiti(letti) == {"success": 1, "warn": 1, "fail": 1, "error": 1}
    assert errori_dbt(letti) == [
        "test.anac_appalti.assert_riconciliazione: Got 1 result",
        "model.anac_appalti.fct_lotti: Binder Error",
    ]
