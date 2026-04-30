"""Typer CLI entry point. Real subcommands land in Phase 1.5."""

from __future__ import annotations

import typer

from code_agent import __version__

app = typer.Typer(
    name="code-agent",
    help="A code agent with strongly-typed Action/Observation and pluggable Runtime.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the installed code-agent version."""
    typer.echo(f"code-agent {__version__}")


@app.command()
def run() -> None:
    """Run the agent on a task. (Implemented in Phase 1.5.)"""
    typer.echo("Not yet implemented — landing in Phase 1.5.")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
