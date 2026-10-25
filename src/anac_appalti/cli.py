"""Interfaccia a riga di comando `appalti`."""

from __future__ import annotations

import json
import shutil

import typer

from anac_appalti.config import VERSIONE, carica_impostazioni

app = typer.Typer(help="Pipeline ANAC appalti: estrazione, dbt, qualità dei dati.", no_args_is_help=True)
contratti_app = typer.Typer(help="Contratti di sorgente.", no_args_is_help=True)
fixture_app = typer.Typer(help="Fixture sintetica per test e CI.", no_args_is_help=True)
app.add_typer(contratti_app, name="contratti")
app.add_typer(fixture_app, name="fixture")

OPZIONE_FIXTURE = typer.Option(
    False, "--fixtures", help="Usa la fixture sintetica (offline) in build/fixture/."
)
OPZIONE_MESE = typer.Option(1, "--mese", help="Mese della fixture: 1 o 2 (il 2 aggiunge un delta CIG).")


@app.callback()
def principale() -> None:
    """Pipeline ANAC appalti."""


@app.command()
def versione() -> None:
    """Stampa la versione."""
    typer.echo(VERSIONE)


@app.command()
def intestazioni() -> None:
    """Legge le intestazioni reali dal portale e scrive contratti/anac/_intestazioni_reali.json."""
    from anac_appalti.intestazioni import scrivi_intestazioni

    percorso = scrivi_intestazioni(carica_impostazioni())
    typer.echo(f"Intestazioni reali scritte in {percorso}")


@contratti_app.command("sync")
def contratti_sync(
    verifica: bool = typer.Option(
        False, "--verifica", help="Non scrive: esce con 1 se il file generato è diverso."
    ),
) -> None:
    """Rigenera dbt/models/staging/anac/_anac__sources.yml dai contratti."""
    from anac_appalti.contratti import percorso_sources, sincronizza

    imp = carica_impostazioni()
    diverso = sincronizza(imp, verifica=verifica)
    if verifica and diverso:
        typer.echo(
            f"{percorso_sources(imp)} non è allineato ai contratti: esegui `appalti contratti sync`.",
            err=True,
        )
        raise typer.Exit(1)
    typer.echo("Sources dbt aggiornati." if diverso else "Sources dbt già allineati.")


@fixture_app.command("genera")
def fixture_genera() -> None:
    """Rigenera la fixture sintetica in data/fixtures/ (mese1 e mese2)."""
    from anac_appalti.fixture import genera_fixture

    imp = carica_impostazioni()
    conteggi = genera_fixture(imp.contratti_dir, imp.radice / "data" / "fixtures")
    for file, righe in conteggi.items():
        typer.echo(f"{file}: {righe} righe")


@app.command()
def landing(
    fixtures: bool = typer.Option(False, "--fixtures", help="Usa l'area della fixture (build/fixture)."),
    mese: int = typer.Option(1, "--mese", help="Mese della fixture (1 o 2)."),
    pacchetti: str = typer.Option(
        "", "--pacchetti", help="Pacchetti o tabelle separati da virgola (default: tutti)."
    ),
) -> None:
    """Atterra in Parquet i file già archiviati in data/raw (non scarica). Esce con 1 se un file è in errore,
    è stato letto con scarti o la riconciliazione delle righe ha una differenza."""
    from anac_appalti.contratti import carica_contratti
    from anac_appalti.landing import atterra_pacchetto

    imp = carica_impostazioni(fixtures=fixtures, mese=mese)
    scelti = {p.strip() for p in pacchetti.split(",") if p.strip()}
    contratti = carica_contratti(imp.contratti_dir)
    riuscito = True
    for pacchetto in imp.pacchetti:
        if scelti and pacchetto.nome not in scelti and pacchetto.tabella not in scelti:
            continue
        riepilogo = atterra_pacchetto(imp, pacchetto, contratti[pacchetto.tabella])
        typer.echo(f"{pacchetto.tabella}: atterrati {riepilogo.atterrati}, saltati {riepilogo.saltati}")
        for avviso in riepilogo.avvisi:
            typer.echo(f"  avviso: {avviso}", err=True)
        for errore in riepilogo.errori:
            typer.echo(f"  errore: {errore}", err=True)
        riuscito = riuscito and riepilogo.riuscito
    if not riuscito:
        raise typer.Exit(1)


@app.command()
def run(
    fixtures: bool = OPZIONE_FIXTURE,
    mese: int = OPZIONE_MESE,
    solo_estrazione: bool = typer.Option(False, "--solo-estrazione", help="Solo raw e landing, senza dbt."),
    pacchetti: str = typer.Option(
        "", "--pacchetti", help="Pacchetti o tabelle separati da virgola (default: tutti)."
    ),
    da_archivio: bool = typer.Option(
        False,
        "--da-archivio",
        help="Non scarica: registra i file messi a mano in data/raw/anac/ e li atterra.",
    ),
) -> None:
    """Esegue la pipeline completa (asset Dagster in processo) e scrive il log di esecuzione."""
    from anac_appalti.pipeline import esegui_pipeline

    imp = carica_impostazioni(fixtures=fixtures, mese=mese)
    scelti = [p.strip() for p in pacchetti.split(",") if p.strip()] or None
    esito = esegui_pipeline(imp, solo_estrazione=solo_estrazione, pacchetti=scelti, da_archivio=da_archivio)
    typer.echo(f"Esecuzione {esito.run_id}: {'successo' if esito.successo else 'errore'}. Log: {esito.log}")
    for errore in esito.errori:
        typer.echo(f"  - {errore}", err=True)
    if not esito.successo:
        raise typer.Exit(1)


@app.command()
def report(fixtures: bool = OPZIONE_FIXTURE, mese: int = OPZIONE_MESE) -> None:
    """Scrive docs/qualita-dati.md e docs/ultima-esecuzione.md; sui dati reali aggiorna i numeri dei README."""
    from anac_appalti.copertura import verifica_copertura
    from anac_appalti.documenti import (
        aggiorna_readme,
        blocco_numeri,
        gravita_test,
        record_per_readme,
        scrivi_ultima_esecuzione,
    )
    from anac_appalti.dq_report import calcola_indicatori, scrivi_report
    from anac_appalti.log_esecuzioni import leggi_log, leggi_ultimo_log
    from anac_appalti.pipeline import garantisci_manifest

    imp = carica_impostazioni(fixtures=fixtures, mese=mese)
    record = leggi_ultimo_log(imp)
    if record is None:
        typer.echo("Nessun log di esecuzione: esegui prima `appalti run`.", err=True)
        raise typer.Exit(1)
    indicatori = calcola_indicatori(imp)
    typer.echo(f"Scritto {scrivi_report(imp, indicatori)}")
    typer.echo(f"Scritto {scrivi_ultima_esecuzione(imp, record)}")
    if not fixtures:
        quota = verifica_copertura(imp).quota
        gravita = gravita_test(json.loads(garantisci_manifest(imp).read_text(encoding="utf-8")))
        record_readme = record_per_readme(leggi_log(imp))
        for lingua, nome in (("it", "README.md"), ("en", "README.en.md")):
            if aggiorna_readme(
                imp.radice / nome, blocco_numeri(record_readme, indicatori, quota, gravita, lingua)
            ):
                typer.echo(f"Aggiornati i numeri in {nome}")


@app.command()
def export(fixtures: bool = OPZIONE_FIXTURE, mese: int = OPZIONE_MESE) -> None:
    """Esporta i nove mart Radar in build/export/ con ATTRIBUTION.md e SHA256SUMS, dopo la scansione di privacy."""
    from anac_appalti.export import ScansionePrivacyFallita, esporta_per_release
    from anac_appalti.log_esecuzioni import leggi_ultimo_log

    imp = carica_impostazioni(fixtures=fixtures, mese=mese)
    record = leggi_ultimo_log(imp)
    try:
        file = esporta_per_release(imp, record["run_id"] if record else "non disponibile")
    except ScansionePrivacyFallita as exc:
        typer.echo(f"Esportazione annullata: {exc}", err=True)
        raise typer.Exit(1) from exc
    for percorso in file:
        typer.echo(f"Scritto {percorso}")
    typer.echo(
        "Scansione di privacy superata (codici fiscali personali e nomi): ATTRIBUTION.md e SHA256SUMS scritti."
    )


@app.command("copertura-test")
def copertura_test(fixtures: bool = OPZIONE_FIXTURE) -> None:
    """Esce con 1 se un modello dbt non ha descrizione o test sulla chiave."""
    from anac_appalti.copertura import verifica_copertura

    esito = verifica_copertura(carica_impostazioni(fixtures=fixtures))
    typer.echo(f"Modelli conformi: {esito.conformi}/{esito.modelli} ({esito.quota:.0%})")
    for mancanza in esito.mancanze:
        typer.echo(f"  - {mancanza}", err=True)
    if esito.mancanze:
        raise typer.Exit(1)


@app.command()
def docs(fixtures: bool = OPZIONE_FIXTURE, mese: int = OPZIONE_MESE) -> None:
    """Genera il sito per GitHub Pages in build/sito/ (documentazione dbt statica e grafo Dagster)."""
    from anac_appalti.definitions import nodi_asset
    from anac_appalti.documenti import componi_indice_sito, componi_pagina_dagster
    from anac_appalti.pipeline import cartella_target, esegui_dbt

    imp = carica_impostazioni(fixtures=fixtures, mese=mese)
    if esegui_dbt(imp, ["docs", "generate", "--static"]) != 0:
        typer.echo("dbt docs generate non riuscito.", err=True)
        raise typer.Exit(1)
    sito = imp.radice / "build" / "sito"
    (sito / "dbt").mkdir(parents=True, exist_ok=True)
    (sito / "dagster").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cartella_target(imp) / "static_index.html", sito / "dbt" / "index.html")
    (sito / "dagster" / "index.html").write_text(componi_pagina_dagster(nodi_asset()), encoding="utf-8")
    (sito / "index.html").write_text(componi_indice_sito(VERSIONE), encoding="utf-8")
    typer.echo(f"Sito scritto in {sito}")
