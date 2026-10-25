from dagster import (
    AssetKey,
    DagsterInstance,
    DefaultScheduleStatus,
    DefaultSensorStatus,
    RunRequest,
    SkipReason,
    build_sensor_context,
    materialize,
)

from anac_appalti import definitions
from anac_appalti.ckan import WafRifiuto
from anac_appalti.config import carica_impostazioni
from anac_appalti.landing import RiepilogoLanding


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


def test_schedule_e_sensor_partono_spenti():
    """Contattano il portale: si accendono a mano nel daemon, mai da soli e mai in CI."""
    pianificazione = definitions.defs.resolve_schedule_def("mensile_25")
    assert pianificazione.default_status == DefaultScheduleStatus.STOPPED
    assert (
        definitions.defs.resolve_sensor_def("ckan_aggiornato").default_status == DefaultSensorStatus.STOPPED
    )


def test_riepilogo_qualita_dipende_da_tutti_i_modelli_dbt():
    grafo = definitions.defs.resolve_asset_graph()
    genitori = grafo.get(AssetKey("riepilogo_qualita")).parent_keys
    assert set(definitions.modelli_dbt.keys) <= genitori
    assert {AssetKey("fct_lotti"), AssetKey("mart_concorrenza")} <= genitori
    assert AssetKey("raw_cig") in grafo.get(AssetKey("landing_cig")).parent_keys


def test_il_job_usa_l_esecutore_in_processo():
    """Con più processi gli otto raw_* contattano il portale insieme e i landing_* si perdono righe nel registro."""
    assert definitions.defs.resolve_job_def("pipeline_completo").executor_def.name == "in_process"


def test_landing_con_errori_fa_fallire_l_asset(tmp_path, monkeypatch):
    """Un errore di landing non può lasciare l'esecuzione Dagster in RUN_SUCCESS."""

    def guasto(imp, pacchetto, contratto):
        return RiepilogoLanding(tabella=pacchetto.tabella, errori=["varianti_csv.zip: SHA-256 diverso"])

    monkeypatch.setattr(definitions, "atterra_pacchetto", guasto)
    imp = carica_impostazioni(fixtures=True, area=tmp_path)
    landing_varianti = next(a for a in definitions.ASSETS if AssetKey("landing_varianti") in a.keys)
    risultato = materialize(
        [landing_varianti],
        resources=definitions.risorse_per(imp),
        raise_on_error=False,
        instance=DagsterInstance.ephemeral(),
    )
    assert not risultato.success
    messaggi = [e.event_specific_data.error.cause.message for e in risultato.get_step_failure_events()]
    assert any("SHA-256 diverso" in m for m in messaggi), messaggi


def _fonte_con(modificati=None, errore=None):
    class Fonte:
        def metadata_modificati(self):
            if errore:
                raise errore
            return modificati

    return lambda imp: Fonte()


def test_sensor_richiede_una_volta_per_stato_e_salta_se_il_portale_non_risponde(monkeypatch):
    stato = {"cig": "2026-10-01T10:00:00", "aggiudicazioni": "2026-10-02T10:00:00", "altro": "x"}
    monkeypatch.setattr(definitions, "crea_fonte", _fonte_con(stato))
    primo = build_sensor_context()
    richiesta = definitions.ckan_aggiornato(primo)
    assert isinstance(richiesta, RunRequest) and richiesta.run_key
    assert "altro" not in primo.cursor  # solo i pacchetti in ambito entrano nello stato

    invariato = definitions.ckan_aggiornato(build_sensor_context(cursor=primo.cursor))
    assert isinstance(invariato, SkipReason)

    stato["cig"] = "2026-11-01T10:00:00"
    cambiato = definitions.ckan_aggiornato(build_sensor_context(cursor=primo.cursor))
    assert isinstance(cambiato, RunRequest) and cambiato.run_key != richiesta.run_key

    monkeypatch.setattr(
        definitions, "crea_fonte", _fonte_con(errore=WafRifiuto("https://x/api", "123", "Mozilla/5.0"))
    )
    rifiutato = definitions.ckan_aggiornato(build_sensor_context())
    assert isinstance(rifiutato, SkipReason) and "non raggiungibile" in str(rifiutato.skip_message)
