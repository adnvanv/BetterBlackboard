"""CLI entrypoint for the scraper. Run via `python -m scraper run`."""
from __future__ import annotations

import asyncio
import logging
import sys

import typer

from scraper.pipeline import run_once

app = typer.Typer(no_args_is_help=True)


@app.command()
def run() -> None:
    """Run a single scrape pass and exit."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        n = asyncio.run(run_once())
        typer.echo(f"Scraped {n} courses.")
    except Exception as e:
        typer.secho(f"Scrape failed: {e}", fg=typer.colors.RED, err=True)
        sys.exit(1)


@app.command()
def login() -> None:
    """One-time interactive login. Opens a real browser; you complete SSO + MFA by hand."""
    from scraper.interactive_login import run_interactive_login

    asyncio.run(run_interactive_login())


@app.command()
def initdb() -> None:
    """Create the SQLite schema."""
    from app.db import init_db

    init_db()
    typer.echo("DB initialized.")


if __name__ == "__main__":
    app()
