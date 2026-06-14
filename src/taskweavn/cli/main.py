"""Typer CLI entry point."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from taskweavn import __version__
from taskweavn.audit import AuditAgent, AuditConfig
from taskweavn.core.loop import AgentLoop
from taskweavn.diagnostics import (
    DiagnosticBundleError,
    DiagnosticBundleExporter,
    DiagnosticExportOptions,
)
from taskweavn.interaction import (
    AUTONOMY_PRESETS,
    AgentMessage,
    AutonomyGate,
    AutonomyPresetName,
    BaselineOnlyAssessor,
    CompositeAssessor,
    InProcessMessageBus,
    LLMRiskAssessor,
    RiskAssessor,
    SqliteMessageStream,
    WaitCoordinator,
)
from taskweavn.llm.client import LazyLLMClient, LLMClient
from taskweavn.memory import ThoughtConfig, build_store
from taskweavn.observability import (
    LogArchiveManifest,
    LogEvent,
    build_session_logging_config,
    configure_session_logging,
)
from taskweavn.observability.formatting import event_to_pretty
from taskweavn.runtime.local import LocalRuntime
from taskweavn.server import (
    DEFAULT_PLATO_SIDECAR_PORT,
    MainPageSidecarConfig,
    MainPageSidecarDependencies,
    WorkspaceRegistryEntry,
    build_main_page_sidecar_app,
)
from taskweavn.server.settings_config import file_settings_config_store_for
from taskweavn.tools.base import Tool
from taskweavn.tools.code_action_tool import CodeActionTool
from taskweavn.tools.fs import ListDirTool, ReadFileTool, WriteFileTool
from taskweavn.tools.precision_fs import (
    AppendFileTool,
    ReadFileRangeTool,
    ReplaceFileRangeTool,
    SearchWorkspaceTool,
)
from taskweavn.tools.shell import RunCommandTool
from taskweavn.tools.workspace import Workspace

app = typer.Typer(
    name="taskweavn",
    help="TaskWeavn is a task agent with strongly-typed Action/Observation and pluggable Runtime.",
    no_args_is_help=True,
)

logging_app = typer.Typer(
    name="logging",
    help="Inspect structured logging profiles and session archives.",
    no_args_is_help=True,
)
app.add_typer(logging_app, name="logging")

diagnostics_app = typer.Typer(
    name="diagnostics",
    help="Export Product 1.0 diagnostic bundles.",
    no_args_is_help=True,
)
app.add_typer(diagnostics_app, name="diagnostics")


@app.command()
def version() -> None:
    """Print the installed taskweavn version."""
    typer.echo(f"taskweavn {__version__}")


@app.command("plato-sidecar")
def plato_sidecar(
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
            "-w",
            help="Plato workspace root used by the local sidecar.",
        ),
    ] = Path("./plato-workspace"),
    host: Annotated[
        str,
        typer.Option("--host", help="Loopback host for the local sidecar."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(
            "--port",
            help=(
                "Port for the local sidecar. Defaults to the stable Plato dev "
                "port; use 0 to choose a free port."
            ),
        ),
    ] = DEFAULT_PLATO_SIDECAR_PORT,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="LLM model identifier for Collaborator authoring. Defaults to env.",
        ),
    ] = None,
    workspace_registry_json: Annotated[
        str | None,
        typer.Option(
            "--workspace-registry-json",
            envvar="PLATO_WORKSPACE_REGISTRY_JSON",
            help=(
                "Internal Plato desktop workspace registry JSON. Renderer-safe "
                "workspace IDs map to local roots inside the sidecar only."
            ),
        ),
    ] = None,
    global_settings_root: Annotated[
        Path | None,
        typer.Option(
            "--global-settings-root",
            envvar="PLATO_GLOBAL_SETTINGS_ROOT",
            help=(
                "Plato-level settings root. When provided, Settings config is shared "
                "across workspaces."
            ),
        ),
    ] = None,
    enable_read_only_inquiry_llm: Annotated[
        bool,
        typer.Option(
            "--enable-read-only-inquiry-llm/--disable-read-only-inquiry-llm",
            envvar="PLATO_ENABLE_READ_ONLY_INQUIRY_LLM",
            help=(
                "Enable guarded LLM-rendered Read-Only Inquiry answers. "
                "Defaults enabled; set PLATO_ENABLE_READ_ONLY_INQUIRY_LLM=0 "
                "or pass --disable-read-only-inquiry-llm to force deterministic answers."
            ),
        ),
    ] = True,
) -> None:
    """Start the local Plato Main Page backend sidecar."""

    workspace_registry = _parse_workspace_registry_json(workspace_registry_json)
    sidecar = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=workspace,
            host=host,
            port=port,
            workspace_registry=workspace_registry,
            global_settings_root=global_settings_root,
            enable_read_only_inquiry_llm=enable_read_only_inquiry_llm,
        ),
        (
            MainPageSidecarDependencies(
                llm_factory=_settings_backed_llm_factory(
                    default_model="deepseek-v4-pro",
                    global_settings_root=global_settings_root,
                )
            )
            if model is None
            else MainPageSidecarDependencies(llm=LLMClient(model=model))
        ),
    )
    try:
        sidecar.start_in_thread()
        for line in _plato_sidecar_env_lines(
            base_url=sidecar.base_url,
        ):
            typer.echo(line)
        typer.echo("[plato-sidecar] press Ctrl-C to stop")
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        typer.echo("\n[plato-sidecar] stopping")
    finally:
        sidecar.close()


def _settings_backed_llm_factory(
    *,
    default_model: str,
    global_settings_root: Path | None = None,
) -> Callable[[Path], LazyLLMClient]:
    def factory(workspace_root: Path) -> LazyLLMClient:
        settings_store = file_settings_config_store_for(
            workspace_root=workspace_root,
            global_settings_root=global_settings_root,
        )

        def effective_llm_env() -> dict[str, str]:
            return settings_store.effective_env(os.environ)

        return LazyLLMClient(default_model=default_model, env_provider=effective_llm_env)

    return factory


def _parse_workspace_registry_json(raw: str | None) -> tuple[WorkspaceRegistryEntry, ...]:
    if raw is None or raw.strip() == "":
        return ()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("workspace registry must be valid JSON") from exc
    if not isinstance(payload, list):
        raise typer.BadParameter("workspace registry must be a JSON array")

    entries: list[WorkspaceRegistryEntry] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise typer.BadParameter(f"workspace registry entry {index} must be an object")
        workspace_id = item.get("workspaceId")
        root_path = item.get("rootPath")
        label = item.get("label")
        if not isinstance(workspace_id, str) or not workspace_id:
            raise typer.BadParameter(f"workspace registry entry {index} missing workspaceId")
        if not isinstance(root_path, str) or not root_path:
            raise typer.BadParameter(f"workspace registry entry {index} missing rootPath")
        if not isinstance(label, str) or not label:
            raise typer.BadParameter(f"workspace registry entry {index} missing label")
        entries.append(
            WorkspaceRegistryEntry(
                workspace_id=workspace_id,
                root_path=Path(root_path),
                label=label,
                is_current=item.get("isCurrent") is True,
                last_opened_at=(
                    item.get("lastOpenedAt")
                    if isinstance(item.get("lastOpenedAt"), str)
                    else None
                ),
            )
        )
    return tuple(entries)


@app.command("plato-dev")
def plato_dev(
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
            "-w",
            help="Plato workspace root used by the local sidecar.",
        ),
    ] = Path("./plato-workspace"),
    sidecar_host: Annotated[
        str,
        typer.Option("--sidecar-host", help="Loopback host for the local sidecar."),
    ] = "127.0.0.1",
    sidecar_port: Annotated[
        int,
        typer.Option(
            "--sidecar-port",
            help=(
                "Port for the local sidecar. Defaults to the stable Plato dev "
                "port; use 0 to choose a free port."
            ),
        ),
    ] = DEFAULT_PLATO_SIDECAR_PORT,
    frontend_dir: Annotated[
        Path,
        typer.Option("--frontend-dir", help="Path to the Plato frontend package."),
    ] = Path("./frontend"),
    frontend_host: Annotated[
        str,
        typer.Option("--frontend-host", help="Host passed to Vite."),
    ] = "127.0.0.1",
    frontend_port: Annotated[
        int,
        typer.Option("--frontend-port", help="Port passed to Vite."),
    ] = 5173,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="LLM model identifier for Collaborator authoring. Defaults to env.",
        ),
    ] = None,
    enable_read_only_inquiry_llm: Annotated[
        bool,
        typer.Option(
            "--enable-read-only-inquiry-llm/--disable-read-only-inquiry-llm",
            envvar="PLATO_ENABLE_READ_ONLY_INQUIRY_LLM",
            help=(
                "Enable guarded LLM-rendered Read-Only Inquiry answers. "
                "Defaults enabled; set PLATO_ENABLE_READ_ONLY_INQUIRY_LLM=0 "
                "or pass --disable-read-only-inquiry-llm to force deterministic answers."
            ),
        ),
    ] = True,
) -> None:
    """Start Plato backend sidecar and frontend dev server together."""

    if not frontend_dir.exists():
        typer.secho(f"frontend dir not found: {frontend_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    if not (frontend_dir / "package.json").exists():
        typer.secho(
            f"frontend package.json not found: {frontend_dir / 'package.json'}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    llm = LLMClient.from_env() if model is None else LLMClient(model=model)
    sidecar = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=workspace,
            host=sidecar_host,
            port=sidecar_port,
            enable_read_only_inquiry_llm=enable_read_only_inquiry_llm,
        ),
        MainPageSidecarDependencies(llm=llm),
    )
    frontend_process: subprocess.Popen[str] | None = None
    try:
        sidecar.start_in_thread()
        env = _plato_frontend_env(
            base_url=sidecar.base_url,
        )
        frontend_url = f"http://{frontend_host}:{frontend_port}"
        typer.echo(f"[plato-dev] frontend={frontend_url}")
        for line in _plato_sidecar_env_lines(
            base_url=sidecar.base_url,
        ):
            typer.echo(line)
        typer.echo("[plato-dev] starting frontend dev server")
        try:
            frontend_process = _start_plato_frontend(
                frontend_dir=frontend_dir,
                frontend_host=frontend_host,
                frontend_port=frontend_port,
                env=env,
            )
        except FileNotFoundError:
            typer.secho(
                "npm not found; install Node.js/npm before running taskweavn plato-dev",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1) from None
        typer.echo("[plato-dev] press Ctrl-C to stop frontend and sidecar")
        return_code = frontend_process.wait()
        if return_code != 0:
            raise typer.Exit(code=return_code)
    except KeyboardInterrupt:
        typer.echo("\n[plato-dev] stopping")
    finally:
        if frontend_process is not None:
            _terminate_process(frontend_process)
        sidecar.close()


@logging_app.command("profiles")
def logging_profiles(
    log_dir: Annotated[
        Path,
        typer.Option(
            "--log-dir",
            help="Log archive root used to build the default logging config.",
        ),
    ] = Path("./logs"),
) -> None:
    """List built-in session logging profiles."""
    config = build_session_logging_config(log_dir)
    for name, profile in sorted(config.profiles.items()):
        typer.echo(f"{name}\t{profile.description}")


@logging_app.command("manifest")
def logging_manifest(
    session_id: Annotated[str, typer.Option("--session-id", help="Session id.")],
    log_dir: Annotated[
        Path,
        typer.Option("--log-dir", help="Log archive root."),
    ] = Path("./logs"),
) -> None:
    """Print a session archive manifest as JSON."""
    path = log_dir / "sessions" / session_id / "manifest.json"
    if not path.exists():
        typer.secho(f"manifest not found: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    manifest = LogArchiveManifest.model_validate_json(path.read_text(encoding="utf-8"))
    typer.echo(manifest.model_dump_json(indent=2, exclude_none=True))


@logging_app.command("render")
def logging_render(
    log_file: Annotated[Path, typer.Argument(help="Path to a JSONL log file.")],
    limit: Annotated[
        int,
        typer.Option("--limit", help="Render at most this many trailing lines; <=0 means all."),
    ] = 50,
) -> None:
    """Render a JSONL structured log file into compact human-readable lines."""
    if not log_file.exists():
        typer.secho(f"log file not found: {log_file}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    lines = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if limit > 0:
        lines = lines[-limit:]
    for line in lines:
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("log line is not a JSON object")
            row: dict[str, Any] = dict(payload)
            row.pop("msg", None)
            event = LogEvent.model_validate(row)
        except Exception:  # noqa: BLE001 — rendering should keep going.
            typer.echo(line)
            continue
        typer.echo(event_to_pretty(event))


@diagnostics_app.command("export")
def diagnostics_export(
    session_id: Annotated[str, typer.Option("--session-id", help="Session id.")],
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
            "-w",
            help="Plato workspace root to read durable stores from.",
        ),
    ] = Path("./plato-workspace"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Directory where the bundle is written."),
    ] = Path("./diagnostics"),
    create_zip: Annotated[
        bool,
        typer.Option("--zip/--no-zip", help="Also write a .zip next to the bundle dir."),
    ] = True,
    max_messages: Annotated[
        int,
        typer.Option("--max-messages", help="Maximum message summaries to include."),
    ] = 50,
    max_events: Annotated[
        int,
        typer.Option("--max-events", help="Maximum EventStream summaries to include."),
    ] = 100,
    max_log_entries: Annotated[
        int,
        typer.Option(
            "--max-log-entries",
            help="Maximum entries per log category/client-error file.",
        ),
    ] = 40,
) -> None:
    """Export one redacted local diagnostic bundle for a session."""
    exporter = DiagnosticBundleExporter(
        DiagnosticExportOptions(
            workspace_root=workspace,
            session_id=session_id,
            output_dir=output,
            create_zip=create_zip,
            max_messages=max_messages,
            max_events=max_events,
            max_log_entries_per_category=max_log_entries,
        )
    )
    try:
        result = exporter.export()
    except DiagnosticBundleError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    typer.echo(
        json.dumps(
            {
                "bundleId": result.bundle_id,
                "bundleDir": str(result.bundle_dir),
                "zipPath": None if result.zip_path is None else str(result.zip_path),
                "warnings": list(result.manifest.warnings),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


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
            help="Root directory for structured log archives.",
        ),
    ] = Path("./logs"),
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Default structured logging level (TRACE, DEBUG, INFO, ...).",
        ),
    ] = "INFO",
    logging_profile: Annotated[
        str | None,
        typer.Option(
            "--logging-profile",
            help=(
                "Session logging profile, e.g. normal, quiet, debug-llm, "
                "debug-tools, debug-bus, full-debug."
            ),
        ),
    ] = None,
    logging_config: Annotated[
        Path | None,
        typer.Option(
            "--logging-config",
            help="Path to a complete JSON LoggingConfig file.",
        ),
    ] = None,
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
    risk_assessor: Annotated[
        str,
        typer.Option(
            "--risk-assessor",
            help=(
                "Risk assessor used by the autonomy gate. One of: baseline "
                "(default; trust class-level baseline_risk), llm (ask the "
                "loop's LLM to grade dynamic risk), composite (baseline + "
                "llm chained). Only meaningful when --autonomy is set."
            ),
        ),
    ] = "baseline",
) -> None:
    """Run the agent on a task inside a workspace."""
    resolved_session_id = session_id or uuid.uuid4().hex
    try:
        configure_session_logging(
            log_dir,
            session_id=resolved_session_id,
            level=log_level,
            profile=logging_profile,
            config_path=logging_config,
        )
    except (KeyError, ValueError) as exc:
        raise typer.BadParameter(
            str(exc),
            param_hint="--logging-profile/--logging-config/--log-level",
        ) from exc
    validated_autonomy = _validate_autonomy_options(
        autonomy=autonomy,
        risk_assessor=risk_assessor,
    )

    workspace.mkdir(parents=True, exist_ok=True)
    ws = Workspace(workspace)

    llm = (
        LLMClient.from_env() if model is None else LLMClient(model=model)
    )

    runtime = LocalRuntime()
    inspection_db_path = workspace / ".plato" / "inspection.sqlite"
    tools: list[Tool[Any, Any]] = [
        ReadFileTool(ws),
        ReadFileRangeTool(
            ws,
            workspace_id=f"session:{resolved_session_id}",
            inspection_db_path=inspection_db_path,
        ),
        SearchWorkspaceTool(
            ws,
            workspace_id=f"session:{resolved_session_id}",
            inspection_db_path=inspection_db_path,
        ),
        ReplaceFileRangeTool(
            ws,
            workspace_id=f"session:{resolved_session_id}",
            inspection_db_path=inspection_db_path,
        ),
        AppendFileTool(
            ws,
            workspace_id=f"session:{resolved_session_id}",
            inspection_db_path=inspection_db_path,
        ),
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
    bus: InProcessMessageBus | None = None
    stream: SqliteMessageStream | None = None
    gate: AutonomyGate | None = None
    coord: WaitCoordinator | None = None
    responder_thread: threading.Thread | None = None
    if validated_autonomy is not None:
        behavior = AUTONOMY_PRESETS[validated_autonomy]
        msgs_path = messages_db or (log_dir / "messages.sqlite")
        msgs_path.parent.mkdir(parents=True, exist_ok=True)
        stream = SqliteMessageStream(msgs_path)
        bus = InProcessMessageBus(stream)
        assessor = _build_risk_assessor(risk_assessor, llm)
        gate = AutonomyGate(behavior, assessor)
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


def _validate_autonomy_options(
    *,
    autonomy: str | None,
    risk_assessor: str,
) -> AutonomyPresetName | None:
    if autonomy is not None and autonomy not in AUTONOMY_PRESETS:
        valid = ", ".join(sorted(AUTONOMY_PRESETS))
        raise typer.BadParameter(
            f"unknown autonomy preset {autonomy!r}; valid: {valid}",
            param_hint="--autonomy",
        )
    if risk_assessor not in {"baseline", "llm", "composite"}:
        raise typer.BadParameter(
            (
                f"unknown risk assessor {risk_assessor!r}; "
                "valid: baseline, llm, composite"
            ),
            param_hint="--risk-assessor",
        )
    return autonomy


def _build_risk_assessor(name: str, llm: LLMClient) -> RiskAssessor:
    """Resolve ``--risk-assessor <name>`` into a concrete assessor.

    ``baseline``  → :class:`BaselineOnlyAssessor` (cheap, deterministic).
    ``llm``       → :class:`LLMRiskAssessor` using the loop's main LLM.
    ``composite`` → ``CompositeAssessor(baseline, llm)`` so a malformed LLM
                    reply still yields the baseline floor.

    Unknown names raise :class:`typer.BadParameter` so the CLI surfaces a
    standard "Invalid value for --risk-assessor" error.
    """
    if name == "baseline":
        return BaselineOnlyAssessor()
    if name == "llm":
        return LLMRiskAssessor(llm=llm)
    if name == "composite":
        return CompositeAssessor(
            assessors=(BaselineOnlyAssessor(), LLMRiskAssessor(llm=llm)),
        )
    raise typer.BadParameter(
        f"unknown risk assessor {name!r}; valid: baseline, llm, composite",
        param_hint="--risk-assessor",
    )


def _plato_sidecar_env_lines(*, base_url: str) -> tuple[str, ...]:
    return (
        f"[plato-sidecar] baseUrl={base_url}",
        f"[plato-sidecar] health={base_url}/api/v1/health",
        f"[plato-sidecar] sessions={base_url}/api/v1/sessions",
        "[plato-sidecar] Vite env:",
        "VITE_PLATO_API_MODE=http",
        f"VITE_PLATO_API_BASE_URL={base_url}",
    )


def _plato_frontend_env(*, base_url: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "VITE_PLATO_API_MODE": "http",
            "VITE_PLATO_API_BASE_URL": base_url,
        }
    )
    return env


def _plato_frontend_command(*, host: str, port: int) -> list[str]:
    return ["npm", "run", "dev", "--", "--host", host, "--port", str(port)]


def _start_plato_frontend(
    *,
    frontend_dir: Path,
    frontend_host: str,
    frontend_port: int,
    env: dict[str, str],
) -> subprocess.Popen[str]:
    return subprocess.Popen(  # noqa: S603 - developer command, args are fixed.
        _plato_frontend_command(host=frontend_host, port=frontend_port),
        cwd=frontend_dir,
        env=env,
        text=True,
    )


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


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
