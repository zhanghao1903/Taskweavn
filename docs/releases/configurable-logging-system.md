# Release: Configurable Logging System

> Status: done
> Date: 2026-05-13
> Work Stream: Phase 3B — Reliability And Observability
> Related Capability: [Audit Trust](../capabilities/audit-trust/), [Diagnostic Bundle](../capabilities/diagnostic-bundle/)
> Related Plan: [Legacy Configurable Logging System](../archive/legacy-2026-05-18/plans/feature/configurable-logging-system.md)
> Technical Design: [Legacy Configurable Logging System](../archive/legacy-2026-05-18/architecture/configurable-logging-system.md)

---

## 1. Summary

TaskWeavn now has a configurable, structured logging system suitable for long-running sessions and user testing.

The release upgrades the early fixed channel logger into an object-aware observability layer with:

- structured JSONL records;
- category and session-level rules;
- logging profiles;
- session archive manifests;
- same-process runtime control APIs;
- first core-object integrations across Action, Observation, Tool, Runtime, LLM, Audit, Bus, Gate, Wait, and Sandbox.

Logs remain separate from EventStream and MessageStream: they are for debugging, traceability, and archive inspection, not system state replay.

---

## 2. Shipped

### 2.1 Logging Model

- `LogLevel`, including `TRACE` and `OFF`.
- `LogCategory` taxonomy for core objects.
- `LogContext` carrying session/task/agent/action/tool/model context.
- `LoggingConfig`, `LogRule`, sink config, profiles, payload modes, and redaction hooks.

### 2.2 Logging Runtime

- `LoggingManager` with immutable active config snapshots.
- File, console, and null sinks.
- Structured JSONL envelope.
- Lazy payload evaluation so disabled DEBUG/FULL records do not build expensive payloads.
- Backward-compatible bridge for `configure_logging()` and `get_channel_logger()`.

### 2.3 Session Archives

- `configure_session_logging()` creates stable session archive directories.
- `manifest.json` records category files, config hash, templates, rotation metadata, and close markers.
- UI and test tooling can start from the manifest instead of guessing paths.

### 2.4 Control Surface

- Built-in profiles: `normal`, `quiet`, `debug-llm`, `debug-tools`, `debug-bus`, `full-debug`.
- `LoggingControlService` for same-process profile application, scoped level changes, and archive close operations.
- CLI archive inspection commands:
  - `taskweavn logging profiles`
  - `taskweavn logging manifest --session-id <id>`
  - `taskweavn logging render <jsonl>`

### 2.5 Core Integrations

- Event streams emit Action/Observation records.
- Runtime and Tool calls emit invoke/result/failure records.
- LLM provider and retry layer emit request/response/retry/failure records.
- Audit, MessageBus, AutonomyGate, WaitCoordinator, and Sandbox now use native object logs.
- `LOG_EVENTS_BY_CATEGORY` documents and tests the first event-name taxonomy.

---

## 3. Validation

Recorded validation from the accepted implementation branch:

- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv run pytest` — 441 passed, 1 warning

---

## 4. Follow-ups

- Cross-process hot update needs a daemon/server control plane.
- Task/Agent archive indexes should wait until TaskBus and Agent template semantics stabilize.
- Centralized runtime configuration should eventually become the shared resolver for logging, autonomy, audit, LLM, Task, and UI behavior.
- Risk-assessor long-call timeout and observability remains tracked separately.
