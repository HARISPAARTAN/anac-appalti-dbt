from dagster import AssetKey, DefaultSensorStatus

from anac_appalti import definitions


def test_definizioni_caricabili():
    grafo = definitions.defs.resolve_asset_graph()
    chiavi = {chiave.to_user_string() for chiave in grafo.get_all_asset_keys()}
    for tabella in ("cig", "aggiudicazioni", "stazioni_appaltanti", "tipi_scelta_contraente"):
        assert f"raw_{tabella}" in chiavi
        assert f"landing_{tabella}" in chiavi
    assert {"stg_anac__cig", "fct_lotti", "mart_concorrenza", "riepilogo_qualita"} <= chiavi
    assert AssetKey("landing_cig") in grafo.get(AssetKey("stg_anac__cig")).parent_keys
    assert definitions.defs.resolve_job_def("pipeline_completo") is not None
    pianificazione = definitions.defs.resolve_schedule_def("mensile_25")
    assert (pianificazione.cron_schedule, pianificazione.execution_timezone) == ("0 6 25 * *", "Europe/Rome")
    assert definitions.defs.resolve_sensor_def("ckan_aggiornato") is not None


def test_sensor_e_schedule_non_partono_da_soli():
    """Il sensor contatta il portale: parte solo se acceso a mano nel daemon, mai in CI."""
    sensore = definitions.defs.resolve_sensor_def("ckan_aggiornato")
    assert sensore.default_status == DefaultSensorStatus.STOPPED


def test_nodi_asset():
    nodi = {nome: (gruppo, dipendenze) for nome, gruppo, dipendenze in definitions.nodi_asset()}
    assert nodi["landing_cig"] == ("landing", ["raw_cig"])
    assert nodi["raw_cig"][0] == "estrazione"
