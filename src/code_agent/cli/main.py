"""Typer CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from code_agent import __version__
from code_agent.audit import AuditAgent, AuditConfig
from code_agent.core.loop import AgentLoop
from code_agent.llm.client import LLMClient
from code_agent.memory import ThoughtConfig, build_store
from code_agent.observability import configure_logging
from code_agent.runtime.local import LocalRuntime
from code_agent.tools.base import Tool
from code_agent.tools.code_action_tool import CodeActionTool
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
    audit: Annotated[
        bool,
        typer.Option(
            "--audit/--no-audit",
            help=(
                "Run the AuditAgent on every CodeAction. "
                "Off by default. Falls back to AUDIT_ENABLED env if unset."
            ),
        ),
    ] = False,
    audit_model: Annotated[
        str | None,
        typer.Option(
            "--audit-model",
            help=(
                "LLM model identifier for the auditor. Defaults to AUDIT_MODEL "
                "env, or the main loop's model when neither is set."
            ),
        ),
    ] = None,
    thoughts: Annotated[
        bool,
        typer.Option(
            "--thoughts/--no-thoughts",
            help=(
                "Persist the LLM's reasoning to a SQLite ThoughtStore. "
                "Off by default. Falls back to THOUGHTS_ENABLED env if unset."
            ),
        ),
    ] = False,
    thoughts_db: Annotated[
        Path | None,
        typer.Option(
            "--thoughts-db",
            help=(
                "Path to the SQLite database file used when --thoughts is on. "
                "Defaults to THOUGHTS_DB_PATH env, or <log-dir>/thoughts.sqlite."
            ),
        ),
    ] = None,
    thoughts_phases: Annotated[
        str | None,
        typer.Option(
            "--thoughts-phases",
            help=(
                "Comma-separated list of phase names to persist (e.g. 'plan,reason'). "
                "If unset, persists every phase. Falls back to THOUGHTS_PHASES env."
            ),
        ),
    ] = None,
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
        CodeActionTool(ws),
    ]
    for tool in tools:
        tool.register(runtime)

    # AuditConfig precedence: explicit CLI flag → AUDIT_* env. Model override
    # likewise prefers the CLI flag over env.
    env_cfg = AuditConfig.from_env()
    audit_cfg = AuditConfig(
        enabled=audit or env_cfg.enabled,
        model=audit_model or env_cfg.model,
        api_key=env_cfg.api_key,
    )
    auditor = AuditAgent.from_config(audit_cfg, fallback_llm=llm)

    # ThoughtConfig precedence: explicit CLI flag > THOUGHTS_* env, with a
    # sane default db_path under log-dir so users don't have to pick one
    # just to flip the feature on.
    env_thoughts = ThoughtConfig.from_env()
    enabled = thoughts or env_thoughts.enabled
    if thoughts_phases is not None:
        phases: tuple[str, ...] | None = tuple(
            p.strip() for p in thoughts_phases.split(",") if p.strip()
        ) or None
    else:
        phases = env_thoughts.phases
    db_path = thoughts_db or env_thoughts.db_path
    if enabled and db_path is None:
        db_path = log_dir / "thoughts.sqlite"
    thought_cfg = ThoughtConfig(
        enabled=enabled,
        backend="sqlite" if enabled else "null",
        db_path=db_path,
        phases=phases,
    )
    thought_store = build_store(thought_cfg)

    loop = AgentLoop(
        llm=llm,
        runtime=runtime,
        tools=tools,
        max_steps=max_steps,
        auditor=auditor,
        thought_store=thought_store,
    )
    result = loop.run(task)

    typer.echo(f"\n[stop_reason] {result.stop_reason} (steps={result.steps})")
    typer.echo(f"[final_answer] {result.final_answer}")
    if not result.finished:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
