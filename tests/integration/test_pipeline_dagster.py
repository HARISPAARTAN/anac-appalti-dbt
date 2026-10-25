import json

import duckdb
import pytest

from anac_appalti.config import carica_impostazioni
from anac_appalti.pipeline import esegui_pipeline

pytestmark = pytest.mark.integrazione

CHIAVI_LOG = {
    "run_id",
    "versione",
    "git_sha",
    "inizio",
    "fine",
    "durata_s",
    "fixtures",
    "mese",
    "anni",
    "data_riferimento",
    "esito",
    "errori",
    "estrazione",
    "landing",
    "dbt",
    "freschezza",
    "modelli",
    "disco",
}


def test_pipeline_idempotente_e_delta(tmp_path):
    imp1 = carica_impostazioni(fixtures=True, mese=1, area=tmp_path)
    primo = esegui_pipeline(imp1)
    assert primo.successo, primo.errori
    assert sum(v["scaricati"] for v in primo.record["estrazione"].values()) == 18
    assert primo.record["dbt"]["esiti"]["warn"] == 5
    record = primo.record
    assert set(record) == CHIAVI_LOG
    assert (record["esito"], record["errori"], record["fixtures"], record["mese"]) == (
        "successo",
        [],
        True,
        1,
    )
    assert len(record["git_sha"]) == 40 and record["versione"]
    assert set(record["dbt"]) == {"esiti", "errori", "n_modelli", "n_test", "durata_s"}
    assert record["dbt"]["errori"] == [] and record["dbt"]["n_modelli"] == 40
    assert all(record["disco"][k] > 0 for k in ("raw", "landing", "warehouse"))
    assert set(record["estrazione"]) == set(record["landing"]) and len(record["estrazione"]) == len(
        imp1.pacchetti
    )
    assert json.loads(primo.log.read_text(encoding="utf-8")) == json.loads(json.dumps(record, default=str))
    assert primo.record["modelli"]["intermediate.int_cig__corrente"]["righe"] == 1500

    secondo = esegui_pipeline(imp1)
    assert secondo.successo, secondo.errori
    assert sum(v["scaricati"] for v in secondo.record["estrazione"].values()) == 0
    assert sum(v["atterrati"] for v in secondo.record["landing"].values()) == 0
    assert secondo.record["modelli"] == primo.record["modelli"]

    imp2 = carica_impostazioni(fixtures=True, mese=2, area=tmp_path)
    terzo = esegui_pipeline(imp2)
    assert terzo.successo, terzo.errori
    assert terzo.record["estrazione"]["cig"]["scaricati"] == 2
    assert terzo.record["modelli"]["intermediate.int_cig__versioni"]["righe"] == 1551
    assert terzo.record["modelli"]["intermediate.int_cig__corrente"]["righe"] == 1500
    assert terzo.record["modelli"] != secondo.record["modelli"]

    con = duckdb.connect(str(imp1.warehouse_file))
    assert con.execute("select count(*) from meta.log_esecuzioni").fetchone()[0] == 3
    con.close()


def test_solo_estrazione_e_pacchetti(tmp_path):
    imp = carica_impostazioni(fixtures=True, mese=1, area=tmp_path)
    esito = esegui_pipeline(imp, solo_estrazione=True, pacchetti=["varianti"])
    assert esito.successo, esito.errori
    assert set(esito.record["estrazione"]) == {"varianti"}
    assert esito.record["modelli"] == {}
    with pytest.raises(ValueError):
        esegui_pipeline(imp, pacchetti=["ocds"])
