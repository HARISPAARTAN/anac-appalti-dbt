"""Definizioni Dagster: raw e landing per pacchetto, modelli dbt, riepilogo qualità, job, schedule, sensor.

`uv run dagster dev -m anac_appalti.definitions` mostra il grafo; `appalti run` esegue gli stessi asset in processo.
Niente `from __future__ import annotations`: Dagster valida le annotazioni di `context` a runtime.
"""

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from dagster import (
    AssetCheckResult,
    AssetCheckSpec,
    AssetExecutionContext,
    AssetKey,
    AssetsDefinition,
    AssetSelection,
    ConfigurableResource,
    DefaultScheduleStatus,
    DefaultSensorStatus,
    Definitions,
    MaterializeResult,
    MetadataValue,
    RetryPolicy,
    RunRequest,
    ScheduleDefinition,
    SensorEvaluationContext,
    SkipReason,
    asset,
    define_asset_job,
    in_process_executor,
    sensor,
)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets

from anac_appalti.archivio import estrai_pacchetto, nomi_ckan
from anac_appalti.ckan import ErroreCkan, WafRifiuto, crea_fonte
from anac_appalti.config import Impostazioni, Pacchetto, carica_impostazioni
from anac_appalti.contratti import carica_contratti
from anac_appalti.landing import atterra_pacchetto
from anac_appalti.pipeline import (
    ErroreDbt,
    conteggi_esiti,
    errori_dbt,
    eseguibile_dbt,
    garantisci_manifest,
    leggi_run_results,
    prepara_ambiente_dbt,
    salva_run_results,
    target_dbt,
    variabili_dbt,
)


class ErroreLanding(RuntimeError):
    """Almeno un file non è stato atterrato: l'asset fallisce, così lo stato dell'esecuzione Dagster è FAILURE."""


class RisorsaAppalti(ConfigurableResource):
    """Impostazioni della pipeline (dati reali o fixture) per gli asset."""

    fixtures: bool = False
    mese: int = 1
    area: str = ""

    def impostazioni(self) -> Impostazioni:
        return carica_impostazioni(
            fixtures=self.fixtures, mese=self.mese, area=Path(self.area) if self.area else None
        )


IMPOSTAZIONI_BASE = carica_impostazioni()
MANIFEST = garantisci_manifest(IMPOSTAZIONI_BASE)


def risorse_per(imp: Impostazioni) -> dict:
    return {
        "appalti": RisorsaAppalti(fixtures=imp.fixtures, mese=imp.mese, area=str(imp.area)),
        "dbt": DbtCliResource(
            project_dir=str(imp.dbt_dir),
            profiles_dir=str(imp.dbt_dir),
            target=target_dbt(imp),
            dbt_executable=eseguibile_dbt(),
        ),
    }


def _asset_raw(pacchetto: Pacchetto) -> AssetsDefinition:
    @asset(
        name=f"raw_{pacchetto.tabella}",
        group_name="estrazione",
        retry_policy=RetryPolicy(max_retries=3, delay=60),
        description=f"Archivio raw append-only del pacchetto ANAC {pacchetto.nome} con manifest.",
    )
    def _raw(context: AssetExecutionContext, appalti: RisorsaAppalti) -> MaterializeResult:
        imp = appalti.impostazioni()
        inizio = time.perf_counter()
        riepilogo = estrai_pacchetto(imp, crea_fonte(imp), pacchetto)
        dati = asdict(riepilogo) | {"durata_s": round(time.perf_counter() - inizio, 3)}
        context.log.info(
            f"{pacchetto.nome}: {riepilogo.scaricati} scaricati, {riepilogo.saltati} invariati, "
            f"User-Agent: {riepilogo.user_agent}"
        )
        return MaterializeResult(
            metadata={
                "riepilogo": MetadataValue.json(dati),
                "scaricati": riepilogo.scaricati,
                "byte": riepilogo.byte,
            }
        )

    return _raw


def _asset_landing(pacchetto: Pacchetto) -> AssetsDefinition:
    @asset(
        name=f"landing_{pacchetto.tabella}",
        group_name="landing",
        deps=[AssetKey(f"raw_{pacchetto.tabella}")],
        description=f"Parquet di landing della tabella {pacchetto.tabella} (allowlist del contratto).",
    )
    def _landing(context: AssetExecutionContext, appalti: RisorsaAppalti) -> MaterializeResult:
        imp = appalti.impostazioni()
        inizio = time.perf_counter()
        contratto = carica_contratti(imp.contratti_dir)[pacchetto.tabella]
        riepilogo = atterra_pacchetto(imp, pacchetto, contratto)
        for avviso in riepilogo.avvisi:
            context.log.warning(avviso)
        for errore in riepilogo.errori:
            context.log.error(errore)
        if riepilogo.errori:
            raise ErroreLanding(" | ".join(riepilogo.errori))
        dati = asdict(riepilogo) | {"durata_s": round(time.perf_counter() - inizio, 3)}
        return MaterializeResult(
            metadata={
                "riepilogo": MetadataValue.json(dati),
                "atterrati": riepilogo.atterrati,
                "righe": sum(riepilogo.righe.values()),
            }
        )

    return _landing


class TraduttoreAppalti(DagsterDbtTranslator):
    """Chiavi brevi (nome del modello) e sorgenti anac.{tabella} collegate agli asset landing_{tabella}."""

    def get_asset_key(self, dbt_resource_props) -> AssetKey:
        if dbt_resource_props["resource_type"] == "source":
            if dbt_resource_props["source_name"] == "anac":
                return AssetKey(f"landing_{dbt_resource_props['name']}")
            return AssetKey(f"{dbt_resource_props['source_name']}_{dbt_resource_props['name']}")
        return AssetKey(dbt_resource_props["name"])

    def get_group_name(self, dbt_resource_props) -> str:
        if dbt_resource_props["resource_type"] == "seed":
            return "seeds"
        fqn = dbt_resource_props["fqn"]
        return fqn[1] if len(fqn) > 2 else "dbt"


@dbt_assets(manifest=MANIFEST, dagster_dbt_translator=TraduttoreAppalti())
def modelli_dbt(context: AssetExecutionContext, dbt: DbtCliResource, appalti: RisorsaAppalti):
    imp = appalti.impostazioni()
    prepara_ambiente_dbt(imp)
    invocazione = dbt.cli(
        ["build", "--vars", json.dumps(variabili_dbt(imp))], context=context, raise_on_error=False
    )
    yield from invocazione.stream()
    risultati = invocazione.target_path / "run_results.json"
    if risultati.exists():
        salva_run_results(imp, risultati)
    if not invocazione.is_successful():
        # dbt build con errori (test di gravità errore, modello fallito, warehouse non apribile):
        # l'esecuzione Dagster deve risultare FAILURE, non solo l'uscita di `appalti run`
        raise ErroreDbt(f"dbt build terminato con codice {invocazione.process.returncode}")


@asset(
    group_name="qualita",
    deps=[modelli_dbt],
    check_specs=[AssetCheckSpec(name="qualita_dati", asset="riepilogo_qualita")],
    description="Esiti di dbt build; il controllo qualita_dati fallisce se un test di gravità errore fallisce.",
)
def riepilogo_qualita(context: AssetExecutionContext, appalti: RisorsaAppalti) -> MaterializeResult:
    imp = appalti.impostazioni()
    run_results = leggi_run_results(imp)
    errori = errori_dbt(run_results)
    for errore in errori:
        context.log.error(errore)
    return MaterializeResult(
        metadata={"esiti_dbt": MetadataValue.json(conteggi_esiti(run_results)), "errori": len(errori)},
        check_results=[
            AssetCheckResult(
                check_name="qualita_dati",
                passed=not errori,
                metadata={"errori": MetadataValue.json(errori[:50])},
            )
        ],
    )


ASSETS: list[AssetsDefinition] = [
    *[_asset_raw(p) for p in IMPOSTAZIONI_BASE.pacchetti],
    *[_asset_landing(p) for p in IMPOSTAZIONI_BASE.pacchetti],
    modelli_dbt,
    riepilogo_qualita,
]

# Esecutore in processo: gli otto raw_* non colpiscono il portale in parallelo e i landing_* non si
# contendono la riscrittura integrale di _registro.csv (aggiornamento perso con l'esecutore multiprocesso).
pipeline_completo = define_asset_job(
    "pipeline_completo", selection=AssetSelection.all(), executor_def=in_process_executor
)

# Schedule e sensor partono SPENTI: contattano il portale ANAC e vanno accesi a mano nel daemon (mai in CI).
mensile_25 = ScheduleDefinition(
    name="mensile_25",
    job=pipeline_completo,
    cron_schedule="0 6 25 * *",
    execution_timezone="Europe/Rome",
    default_status=DefaultScheduleStatus.STOPPED,
    description="Riserva: il 25 di ogni mese alle 06:00 (ANAC pubblica i delta entro il 22 circa).",
)


@sensor(
    job=pipeline_completo,
    minimum_interval_seconds=24 * 3600,
    default_status=DefaultSensorStatus.STOPPED,
    description="Una richiesta package_search al giorno.",
)
def ckan_aggiornato(context: SensorEvaluationContext):
    imp = carica_impostazioni()
    try:
        modificati = crea_fonte(imp).metadata_modificati()
    except (WafRifiuto, ErroreCkan) as exc:
        return SkipReason(f"Portale ANAC non raggiungibile: {exc}")
    in_ambito = {nome for p in imp.pacchetti for nome in nomi_ckan(p, imp.anni)}
    stato = {nome: data for nome, data in sorted(modificati.items()) if nome in in_ambito}
    testo = json.dumps(stato, sort_keys=True)
    if context.cursor == testo:
        return SkipReason("Nessun pacchetto ANAC in ambito è cambiato.")
    context.update_cursor(testo)
    return RunRequest(run_key=hashlib.sha256(testo.encode("utf-8")).hexdigest()[:16])


defs = Definitions(
    assets=ASSETS,
    jobs=[pipeline_completo],
    schedules=[mensile_25],
    sensors=[ckan_aggiornato],
    resources=risorse_per(IMPOSTAZIONI_BASE),
)


def nodi_asset() -> list[tuple[str, str, list[str]]]:
    """(chiave, gruppo, dipendenze) per ogni asset, per la pagina del grafo su GitHub Pages."""
    nodi = []
    for definizione in ASSETS:
        for spec in definizione.specs:
            nodi.append(
                (
                    spec.key.to_user_string(),
                    spec.group_name or "default",
                    sorted(d.asset_key.to_user_string() for d in spec.deps),
                )
            )
    return sorted(nodi)
