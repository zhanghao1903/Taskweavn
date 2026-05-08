"""Typer CLI entry point."""

from __future__ import annotations

import sys
import threading
import uuid
from pathlib import Path
from typing import Annotated, Any

import typer

from code_agent import __version__
from code_agent.audit import AuditAgent, AuditConfig
from code_agent.core.loop import AgentLoop
from code_agent.interaction import (
    AUTONOMY_PRESETS,
    AgentMessage,
    AutonomyGate,
    BaselineOnlyAssessor,
    InProcessMessageBus,
    SqliteMessageStream,
    WaitCoordinator,
)
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
    autonomy: Annotated[
        str | None,
        typer.Option(
            "--autonomy",
            help=(
                "Autonomy preset name. One of: full_auto, risk_gated, careful, "
                "collaborative, manual. Unset → no gate, the loop runs every "
                "tool call without consulting the user."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str | None,
        typer.Option(
            "--session-id",
            help=(
                "Identifier used for cross-stream joins (events ⊕ messages) "
                "and as the namespace for bus subscriptions. Defaults to a "
                "fresh uuid hex."
            ),
        ),
    ] = None,
    messages_db: Annotated[
        Path | None,
        typer.Option(
            "--messages-db",
            help=(
                "Path to the SQLite file backing the MessageStream when "
                "--autonomy is set. Defaults to <log-dir>/messages.sqlite."
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

    # Autonomy wiring (Phase 3.6c). Off by default; opt in with --autonomy.
    # When set, we own a SqliteMessageStream + InProcessMessageBus +
    # AutonomyGate + WaitCoordinator, plus a daemon thread that prints
    # actionables to stderr and reads replies from stdin. Everything is
    # tied to ``resolved_session_id`` so the operator can replay later
    # via the message stream alone.
    resolved_session_id = session_id or uuid.uuid4().hex
    bus: InProcessMessageBus | None = None
    stream: SqliteMessageStream | None = None
    gate: AutonomyGate | None = None
    coord: WaitCoordinator | None = None
    responder_thread: threading.Thread | None = None
    if autonomy is not None:
        if autonomy not in AUTONOMY_PRESETS:
            valid = ", ".join(sorted(AUTONOMY_PRESETS))
            raise typer.BadParameter(
                f"unknown autonomy preset {autonomy!r}; valid: {valid}",
                param_hint="--autonomy",
            )
        behavior = AUTONOMY_PRESETS[autonomy]
        msgs_path = messages_db or (log_dir / "messages.sqlite")
        msgs_path.parent.mkdir(parents=True, exist_ok=True)
        stream = SqliteMessageStream(msgs_path)
        bus = InProcessMessageBus(stream)
        gate = AutonomyGate(behavior, BaselineOnlyAssessor())
        coord = WaitCoordinator(bus, behavior)
        responder_thread = _start_stdin_responder(bus, resolved_session_id)

    loop = AgentLoop(
        llm=llm,
        runtime=runtime,
        tools=tools,
        max_steps=max_steps,
        auditor=auditor,
        thought_store=thought_store,
        session_id=resolved_session_id,
        workspace_root=ws.root if gate is not None else None,
        bus=bus,
        gate=gate,
        wait_coordinator=coord,
    )
    try:
        result = loop.run(task)
    finally:
        # Closing the bus signals the responder thread (and any Subscription)
        # to unwind. Stream is closed last so the bus's close path can still
        # commit any final notify_all reads.
        if bus is not None:
            bus.close()
        if stream is not None:
            stream.close()
        if responder_thread is not None:
            responder_thread.join(timeout=2.0)

    typer.echo(f"\n[stop_reason] {result.stop_reason} (steps={result.steps})")
    typer.echo(f"[final_answer] {result.final_answer}")
    if not result.finished:
        raise typer.Exit(code=1)


def _start_stdin_responder(
    bus: InProcessMessageBus,
    session_id: str,
) -> threading.Thread:
    """Spawn a daemon thread that prints actionables to stderr and reads
    yes/no/free-form replies from stdin, publishing each as a ``response``
    on the bus. Informational messages (incl. timeout self-decisions) are
    also surfaced so the operator sees what the agent decided on its own.

    The thread is daemon=True: the process can exit cleanly even if a stale
    stdin read is still parked. ``bus.close()`` raises ``StopIteration`` on
    the subscription's iterator, ending the loop normally for the common
    shutdown path.
    """

    def _run() -> None:
        try:
            with bus.subscribe(
                session_id, types=["actionable", "informational"]
            ) as sub:
                for msg in sub:
                    if msg.message_type == "informational":
                        typer.secho(
                            f"[fyi] {msg.content}", fg=typer.colors.BLUE, err=True
                        )
                        continue
                    # actionable
                    options = (
                        f" [{', '.join(msg.action_options)}]"
                        if msg.action_options
                        else ""
                    )
                    typer.secho(
                        f"\n[ask] {msg.content}{options}",
                        fg=typer.colors.YELLOW,
                        err=True,
                    )
                    typer.secho("> ", fg=typer.colors.YELLOW, err=True, nl=False)
                    line = sys.stdin.readline()
                    if not line:
                        # EOF — operator detached. Treat as "skip".
                        line = "no"
                    reply = line.strip()
                    bus.publish(
                        AgentMessage(
                            session_id=session_id,
                            message_type="response",
                            content=reply,
                            parent_message_id=msg.message_id,
                            response_source="user",
                            response_value=reply or None,
                        )
                    )
        except Exception as exc:  # pragma: no cover — surface in CLI mode only
            typer.secho(
                f"[responder] crashed: {exc!r}", fg=typer.colors.RED, err=True
            )

    t = threading.Thread(target=_run, name="cli-responder", daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    app()
