"""Interfaccia a riga di comando `appalti`."""

from __future__ import annotations

import typer

from anac_appalti.config import VERSIONE, carica_impostazioni

app = typer.Typer(help="Pipeline ANAC appalti: estrazione, dbt, qualità dei dati.", no_args_is_help=True)
contratti_app = typer.Typer(help="Contratti di sorgente.", no_args_is_help=True)
fixture_app = typer.Typer(help="Fixture sintetica per test e CI.", no_args_is_help=True)
app.add_typer(contratti_app, name="contratti")
app.add_typer(fixture_app, name="fixture")


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
