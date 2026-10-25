"""Interfaccia a riga di comando `appalti`."""

from __future__ import annotations

import typer

from anac_appalti.config import VERSIONE

app = typer.Typer(help="Pipeline ANAC appalti: estrazione, dbt, qualità dei dati.", no_args_is_help=True)


@app.callback()
def principale() -> None:
    """Pipeline ANAC appalti."""


@app.command()
def versione() -> None:
    """Stampa la versione."""
    typer.echo(VERSIONE)
