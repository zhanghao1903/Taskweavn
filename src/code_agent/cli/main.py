"""Typer CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from code_agent import __version__
from code_agent.core.loop import AgentLoop
from code_agent.llm.client import LLMClient
from code_agent.observability import configure_logging
from code_agent.runtime.local import LocalRuntime
from code_agent.tools.base import Tool
from code_agent.tools.fs import ListDirTool, ReadFileTool, WriteFileTool
from code_agent.tools.shell import RunCommandTool
from code_agent.tools.workspace import Workspace

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
def run(
    task: Annotated[str, typer.Option("--task", "-t", help="The task to execute.")],
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
            "-w",
            help="Workspace root directory. Created if it does not exist.",
        ),
    ] = Path("./workspace"),
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="LLM model identifier (provider/model). Defaults to LLM_MODEL env.",
        ),
    ] = None,
    max_steps: Annotated[
        int,
        typer.Option("--max-steps", help="Maximum ReAct iterations before stopping."),
    ] = 20,
    log_dir: Annotated[
        Path,
        typer.Option(
            "--log-dir",
            help="Directory for tool/action/observation/llm logs.",
        ),
    ] = Path("./logs"),
) -> None:
    """Run the agent on a task inside a workspace."""
    configure_logging(log_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    ws = Workspace(workspace)

    llm = (
        LLMClient.from_env() if model is None else LLMClient(model=model)
    )

    runtime = LocalRuntime()
    tools: list[Tool[Any, Any]] = [
        ReadFileTool(ws),
        WriteFileTool(ws),
        ListDirTool(ws),
        RunCommandTool(ws),
    ]
    for tool in tools:
        tool.register(runtime)

    loop = AgentLoop(llm=llm, runtime=runtime, tools=tools, max_steps=max_steps)
    result = loop.run(task)

    typer.echo(f"\n[stop_reason] {result.stop_reason} (steps={result.steps})")
    typer.echo(f"[final_answer] {result.final_answer}")
    if not result.finished:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
