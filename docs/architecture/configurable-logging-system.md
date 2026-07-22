# Configurable Logging System

> Status: fact-calibrated current architecture
>
> Last verified: 2026-07-10
>
> Original document:
> [configurable-logging-system.original.md](archive/original/configurable-logging-system.original.md)
>
> Verification record:
> [fix-log/configurable-logging-system.md](fix-log/configurable-logging-system.md)
>
> Related implementation history:
> [feature plan](../plans/feature/configurable-logging-system.md) and
> [release record](../releases/configurable-logging-system.md)

## 1. Purpose

Taskweavn has an implemented process-local structured logging system. It
provides category-based rules, context, JSONL/pretty sinks, session archives,
profiles, same-process control APIs, and a compatibility bridge for the early
four-channel logger.

This document describes current behavior. In particular, it distinguishes:

- the structured backend logging manager;
- the sidecar-specific archive layout;
- Main Page trace logging, which is a separate helper;
- frontend console/error logging, which is a separate TypeScript system;
- diagnostic bundles, which read and sanitize selected log summaries.

Logs are diagnostic material. They are not the source of truth for Task,
TaskBus, EventStream, MessageStream, Plan, Audit, or runtime configuration.

## 2. Implemented Module Boundary

The structured backend implementation lives in
`src/taskweavn/observability/`:

```text
levels.py                  LogLevel normalization and severity comparison
models.py                  event, context, rule, sink, profile, config, manifest
context.py                 ContextVar-backed ambient LogContext
logger.py                  category-bound ObjectLogger
manager.py                 process-wide LoggingManager and archive helpers
sinks.py                   file, console, and null sinks
formatting.py              JSONL and pretty rendering
redaction.py               recursive key-based data redaction
events.py                  declared category/event taxonomy
bridge.py                  stdlib logging compatibility handler
setup.py                   legacy and session configuration entry points
control.py                 same-process profile/level/archive service
runtime_config_consumer.py live logging.level ConfigBus consumer
main_page_trace.py         separate environment-controlled trace helper
```

Sidecar integration is owned by
`src/taskweavn/server/main_page_logging.py`. Frontend logging is owned by
`frontend/src/shared/logging/frontendLogger.ts`. Diagnostic export is owned by
`src/taskweavn/diagnostics/bundle.py`.

## 3. Data Model

### 3.1 Levels

The closed level set is:

```text
TRACE DEBUG INFO WARNING ERROR CRITICAL OFF
```

`TRACE` has numeric value 5. `OFF` is a sentinel that disables emission.
String normalization is case-insensitive. Integers are mapped to the nearest
defined severity band.

### 3.2 Categories

The current `LogCategory` set is:

```text
action observation llm llm_io task tool bus agent session runtime
sandbox audit risk gate wait config
```

The category schema is broader than current producer coverage. `task`,
`agent`, `session`, `runtime`, and `risk` have no declared ObjectLogger event
names in `LOG_EVENTS_BY_CATEGORY` today. They remain valid rule, profile, sink,
and manifest categories.

`bus` ObjectLogger events currently come from the interaction
`InProcessMessageBus`, not from the TaskBus lifecycle. TaskBus and execution
paths currently use the separate `main_page_trace` helper for many runtime
traces.

### 3.3 Context and event

`LogContext` is frozen and rejects extra fields. It supports:

```text
session_id task_id agent_id trace_id action_id observation_id message_id
tool_name model provider provider_request_id workspace_root
```

`use_log_context` stores ambient context in a `ContextVar`. Explicit non-null
event context fields override ambient fields.

`LogEvent` contains:

```text
ts level category event message context data schema_version
```

The JSONL formatter also writes legacy `msg`, whose value is the event name.
`msg` is a compatibility alias; `event` is the structured event field.

### 3.4 Configuration

`LoggingConfig` is immutable and contains:

- global enable flag and default level;
- archive root;
- named sink configurations;
- category rules;
- named profiles;
- session patches;
- ordered scoped overrides.

`LogRule` contains category, level, sink names, `payload_mode`, and `redact`.
`LogScope` can match session, task, agent, tool, model, and provider fields.
`LogOverride` can replace level, sinks, or payload mode and can expire.

The configuration loader accepts complete JSON `LoggingConfig` files. YAML is
explicitly rejected by the current implementation.

## 4. Logging Manager

### 4.1 Process-wide singleton

`get_logging_manager()` returns one module-level `LoggingManager`. ObjectLogger,
the stdlib bridge, CLI session configuration, sidecar logging, runtime config,
and logging control all use this singleton unless a test or direct library
caller constructs a separate manager.

`build_main_page_workspace_runtime` calls `configure_sidecar_logging`, which
applies a configuration to that singleton. The current multi-workspace runtime
does not allocate an independent logging manager per workspace.

### 4.2 Snapshot replacement

The manager owns a `LoggingSnapshot` containing an immutable config, concrete
sinks, and creation time. `apply_config`:

1. builds a complete new snapshot;
2. swaps it under a re-entrant lock;
3. closes old sinks;
4. emits `config.updated` through the new snapshot.

The built-in sinks have no long-lived file handle, so their `close` methods are
currently no-ops. Snapshot replacement is atomic at the manager reference; it
is not a cross-process configuration protocol.

### 4.3 Rule resolution

Effective rule resolution is:

1. category rule, or a default rule with no sinks when absent;
2. matching session patch, if the context has a session id;
3. each matching, unexpired global override in tuple order.

Later matching overrides can replace values set by earlier ones. Expired
overrides are ignored at read time but are not removed by a background cleanup
task.

### 4.4 Emission and lazy data

An event is skipped when:

- `LoggingConfig.enabled` is false;
- effective `payload_mode` is `off`;
- the event level is below the effective level.

When `data` is a callable, the manager invokes it only after those checks pass.
This is the implemented lazy-payload guarantee. A rule with no configured or
resolvable sink produces no output, but the manager currently evaluates and
constructs the event before discovering that there is nowhere to dispatch it.

There is an important current limitation: the manager does not transform data
according to `summary` versus `full`. It does not pass the effective payload
mode to the callable and does not remove fields for `summary`. Therefore:

- `off` suppresses the entire event, not just `data`;
- `summary` and `full` are stored in the effective rule;
- call sites determine the actual payload shape;
- changing only `summary` to `full` does not automatically add detail.

Architecture and UI copy must not claim automatic summary/full payload
selection until producers implement that behavior.

## 5. Redaction Boundary

When a rule has `redact: true`, `LoggingManager` recursively redacts `data`
mapping values whose keys contain:

```text
api_key authorization cookie password secret token
```

Known token-usage counter keys such as `input_tokens` and `total_tokens` are
excluded from token-key redaction.

This is a narrow key-based boundary:

- string values are not scanned for embedded secrets;
- `message` is not redacted;
- `LogContext` is not redacted;
- keys such as `content`, `messages`, `prompt`, `arguments`, and `payload` are
  not removed by the logging redactor;
- a rule can set `redact: false`;
- frontend error files and Main Page trace files do not pass through this
  manager redactor.

Consequently, a raw log archive can contain sensitive input, output, file
content, tool arguments, stack traces, or local paths. A diagnostic bundle has
a stronger secondary sanitizer, but that does not retroactively make the raw
archive safe to share.

## 6. Sinks and Formats

### 6.1 File sink

`FileSink` renders a path per event, creates parent directories, takes an
in-process lock, rotates if needed, opens the file in append mode, writes one
line, and closes it.

Supported path variables are:

```text
archive_root category session_id task_id agent_id date
```

Missing context values render as `_unknown`. The lock protects one sink
instance within one process; there is no cross-process file-lock protocol.

Size-based rotation checks the current file size before writing. Backups use
`.1` through the configured `backup_count`. The default session configuration
uses 10 MiB and five backups.

### 6.2 Console and null sinks

`ConsoleSink` writes JSONL or pretty lines to stderr. `NullSink` discards
events. Pretty output includes time, level, category/event, and selected
context identifiers; it does not render the full data payload.

### 6.3 JSONL authority

JSONL is the persisted structured format in the built-in configurations.
Pretty rendering is a display format for console and CLI inspection. It is not
a separate fact store.

## 7. Built-in Configurations and Profiles

### 7.1 Legacy configuration

`configure_logging(log_dir, level)` preserves the old public API and four
channel names:

```text
tool action observation llm
```

It configures `<log_dir>/<channel>.log`, installs a `StructuredLogHandler` on
each stdlib logger, and delegates actual events through `LoggingManager`.
`get_channel_logger` rejects unknown channel names.

The compatibility handler is a `logging.FileHandler` subclass so old cleanup
and tests still recognize it. It does not use the old `JSONLineFormatter` for
the final write; it forwards to the structured manager.

### 7.2 Session configuration

`build_session_logging_config` creates:

- `session_file` at
  `{archive_root}/sessions/{session_id}/{category}.jsonl`;
- `global_config_file` at
  `{archive_root}/global/{category}.jsonl`;
- rules for every category at the requested level;
- `config` output to both session and global sinks;
- six built-in profiles.

Profiles are:

| Profile | Current patch |
| --- | --- |
| `normal` | empty patch |
| `quiet` | session default level `WARNING` |
| `debug-llm` | `llm` at DEBUG/full |
| `debug-tools` | `tool`, `runtime`, `sandbox` at DEBUG/full |
| `debug-bus` | `bus`, `task`, `agent`, `gate`, `wait` at DEBUG/full |
| `full-debug` | every category at DEBUG/full |

`debug-llm` does not patch `llm_io`. Because `llm_io` already has the base
INFO rule in the default configuration, the profile name is not a reliable
privacy boundary for raw LLM I/O.

### 7.3 Disabled configuration

Before explicit configuration, and when sidecar session logging is disabled,
the manager uses a config with `enabled: false`, no sinks, and no rules.

## 8. Control and Runtime Configuration

### 8.1 Same-process control service

`LoggingControlService` implements:

- list profiles;
- read an effective category rule;
- apply a session profile;
- set a global or session category level, optionally with an expiry;
- mark a generic session archive manifest closed.

The service is a reusable Python API. Production source inspection found no
sidecar HTTP route or production construction of `LoggingControlService`; its
direct call sites are tests.

### 8.2 Runtime Config consumer

The runtime configuration catalog declares `logging.level` and
`logging.profile` as live keys. The implemented
`RuntimeConfigLoggingConsumer`, however, applies only `logging.level`.

For a global/workspace event it sets every category globally. For a session
event it appends a session-scoped level override for every category. Other
accepted keys, including `logging.profile`, are reported as skipped by this
consumer.

### 8.3 Settings profile

The Settings API can validate, store, and report `logging.selectedProfile`.
Sidecar startup configuration can also provide `logging_profile`, which is
applied when a session archive is initialized.

The inspected settings-update path does not call `LoggingControlService`, and
the Runtime Config logging consumer does not apply `logging.profile`. A stored
Settings profile is therefore not evidence that the active process changed its
session logging profile live. Product/engineering docs correctly keep live
profile scope semantics deferred.

## 9. Archive Layouts

### 9.1 Generic CLI/runtime layout

`configure_session_logging` uses the generic layout:

```text
<log-dir>/sessions/<session-id>/manifest.json
<log-dir>/sessions/<session-id>/<category>.jsonl
<log-dir>/global/config.jsonl
```

It can load a complete JSON config, apply one profile, and write a manifest.
`LoggingManager.write_session_manifest` resolves configured file sinks into
`files` and unresolved path templates into `templates`. The manifest also
records config hash, optional active config path, rotation summary, and
optional close time.

### 9.2 Plato sidecar layout

`configure_sidecar_logging` rewrites sink paths to the workspace layout:

```text
<workspace>/.plato/sessions/<session-id>/logs/<category>.jsonl
<workspace>/.plato/sessions/<session-id>/logs/manifest.json
<workspace>/.plato/logs/global/config.jsonl
```

The sidecar initializer runs for a configured existing session and for sessions
created through the lifecycle gateway. Creating a manifest emits an Audit
records invalidation when a UI event store is available.

The sidecar uses a custom manifest writer. It lists every `LOG_CATEGORIES`
entry as `<category>.jsonl` even if no producer has written that file. The
sidecar `config` rule writes only to the global config sink, so a listed session
`config.jsonl` can be absent. Diagnostic export treats missing listed files as
warnings.

Manifest closure is implemented by the generic manager/control service and
covered by tests. No production sidecar lifecycle call currently marks the
sidecar manifest `closed_at`.

### 9.3 CLI archive compatibility

`taskweavn logging manifest --log-dir ...` assumes the generic
`<log-dir>/sessions/<session-id>/manifest.json` layout. It is not a sidecar
workspace-manifest resolver. `taskweavn logging render <file>` works with any
explicit JSONL path, including a sidecar category file.

## 10. Current Structured Emitters

`LOG_EVENTS_BY_CATEGORY` is the declared ObjectLogger event taxonomy:

| Category | Declared events and current source |
| --- | --- |
| `action` | `emit`; in-memory and SQLite EventStream append |
| `observation` | `emit`; in-memory and SQLite EventStream append |
| `llm` | `agent_input`, `agent_output`, `request`, `response`, `retry`; LLM helpers/providers/retry |
| `llm_io` | `agent_input`, `agent_output`; application-level raw LLM I/O helpers |
| `tool` | `invoke`, `result`; `LocalRuntime` |
| `bus` | `close`, `publish`, `response_received`, `response_timeout`, `subscribe`, `wait_closed`; interaction MessageBus |
| `audit` | `llm_failed`, `parse_failed`, `request`, `result`; Audit Agent |
| `gate` | `decision`; autonomy gate |
| `wait` | `bus_closed`, `got_response`, `got_response_after_wait`, `pending`, `timeout_proceed`, `timeout_skip`; wait coordinator |
| `sandbox` | container, image, execute start/result/failure events; sandbox runtime |
| `config` | `updated`, `profile_applied`, `level_set`, `session_archive_closed`; manager/control |
| `task`, `agent`, `session`, `runtime`, `risk` | no declared ObjectLogger events |

The taxonomy test statically verifies literal ObjectLogger calls against this
map. It does not cover events emitted through ordinary stdlib loggers or the
dynamic `main_page_trace(event, ...)` helper.

## 11. Payload Reality

The current producer payloads do not uniformly implement the intended
"lightweight INFO, full DEBUG" policy:

- `llm` request/response events contain provider, model, counts, usage, retry,
  and other summary metadata.
- `llm_io.agent_input` emits full message/tool structures at INFO.
- `llm_io.agent_output` emits content, reasoning content, raw assistant
  message data, and tool-call arguments at INFO.
- Action and Observation EventStream `emit` events pass `event.to_dict()` at
  INFO.
- `tool.invoke` passes the full action payload at INFO; `tool.result` is a
  summary.

These payloads still pass through key-based manager redaction when enabled, but
content under ordinary keys is retained. The architecture must treat the raw
archive as sensitive local data.

## 12. Main Page Trace

`main_page_trace` is not an ObjectLogger category. It:

- uses the stdlib logger `taskweavn.main_page.trace`;
- is enabled by `PLATO_MAIN_PAGE_TRACE` unless set to a false-like value;
- can mirror to stdout with `PLATO_MAIN_PAGE_TRACE_PRINT=1`;
- can append direct JSONL with `PLATO_MAIN_PAGE_TRACE_FILE`;
- suppresses a fixed set of high-frequency event names;
- does not use `LoggingManager` rules, sinks, context models, or redaction.

Runtime Config resolves the corresponding environment values into diagnostic
keys, but that does not make this helper part of the structured logging
manager.

## 13. Frontend Logging and Client Errors

The frontend logger is a separate system with levels:

```text
debug info warn error silent
```

It selects level from local storage, `VITE_PLATO_LOG_LEVEL`, or a development
/production default. Enabled entries are written to the browser console.

Only frontend `error` entries notify the configured sink. In HTTP mode, when a
runtime session id is available, the sink posts the entry to:

```text
POST /api/v1/sessions/{sessionId}/client-logs/errors
```

`FileClientErrorLogSink` appends the supplied payload to
`frontend-errors.jsonl` with receive time and session id. The raw write path
does not apply logging redaction. The sidecar wrapper emits an Audit-records
invalidation after writing.

Frontend levels and backend `LoggingConfig` are not synchronized.

## 14. Diagnostic Export

Diagnostic export is available through:

- `taskweavn diagnostics export`;
- `POST /api/v1/sessions/{sessionId}/diagnostics/export`;
- Main Page, Settings, and the read-only Diagnostics handoff route in the
  frontend.

The frontend Diagnostics route exports and reports a bundle. It is not a full
interactive log browser.

The exporter reads the sidecar log manifest, tails a bounded number of rows per
listed category, records missing/truncated warnings, and separately reads
frontend errors. Bundle writes apply a stronger sanitizer that:

- reuses secret-key redaction;
- omits prompt/tool-argument/raw-payload-like keys;
- redacts secret fragments inside strings;
- normalizes absolute workspace paths;
- truncates long strings;
- labels each included file as redacted.

This is a derived support artifact. It does not alter the source logs and does
not become a system fact store.

## 15. CLI and HTTP Surfaces

Implemented logging CLI commands:

```text
taskweavn logging profiles
taskweavn logging manifest --log-dir <dir> --session-id <id>
taskweavn logging render <jsonl> --limit <n>
```

The `taskweavn run` command accepts `--log-dir`, `--log-level`,
`--logging-profile`, and `--logging-config`.

HTTP-adjacent surfaces include settings readiness/config, Runtime Config
schema/effective/explain/change/snapshot/patch routes, frontend client-error
ingest, and diagnostic export. There is no general raw-log streaming or
category-query HTTP API in the current route matcher.

## 16. Invariants

1. Structured logs are diagnostics, not domain state.
2. JSONL is the built-in persisted format; pretty is display-only.
3. Event/category names should remain stable once consumers depend on them.
4. Disabled events must not evaluate callable data.
5. Session and scoped configuration resolution depends on populated
   `LogContext`; missing session context routes default sink templates to
   `_unknown`.
6. A manifest is an index of expected/configured files, not proof that every
   file exists or contains events.
7. Raw archives and exported diagnostic bundles have different disclosure
   policies.
8. Frontend, Main Page trace, and structured backend logging are separate
   channels unless an explicit adapter connects them.

## 17. Current Limits

1. `summary` and `full` do not automatically change producer payload shape.
2. Raw `llm_io`, EventStream, and Tool payloads can be detailed at INFO.
3. Key-based logging redaction does not sanitize messages, context, arbitrary
   string values, prompt-like fields, or tool/file content.
4. `LoggingControlService` has no production HTTP/UI control binding.
5. Runtime Config applies `logging.level` live but not `logging.profile`.
6. Settings can store a profile without proving it was applied to the active
   process.
7. The manager is process-wide and not isolated per workspace.
8. Sidecar manifests can list category files that were never produced.
9. Sidecar manifest closure is not wired to production lifecycle shutdown.
10. Main Page trace and frontend error files bypass structured manager
    redaction.
11. No remote sink, centralized log service, OpenTelemetry pipeline,
    cross-process hot update, retention daemon, or full log-browser API is
    implemented.

## 18. Source Map

Primary backend sources:

- `src/taskweavn/observability/levels.py`
- `src/taskweavn/observability/models.py`
- `src/taskweavn/observability/context.py`
- `src/taskweavn/observability/logger.py`
- `src/taskweavn/observability/manager.py`
- `src/taskweavn/observability/sinks.py`
- `src/taskweavn/observability/formatting.py`
- `src/taskweavn/observability/redaction.py`
- `src/taskweavn/observability/events.py`
- `src/taskweavn/observability/bridge.py`
- `src/taskweavn/observability/setup.py`
- `src/taskweavn/observability/control.py`
- `src/taskweavn/observability/runtime_config_consumer.py`
- `src/taskweavn/observability/main_page_trace.py`
- `src/taskweavn/server/main_page_logging.py`
- `src/taskweavn/server/client_logs.py`
- `src/taskweavn/diagnostics/bundle.py`

Primary frontend sources:

- `frontend/src/shared/logging/frontendLogger.ts`
- `frontend/src/app/platoRuntime.ts`
- `frontend/src/pages/diagnostics/DiagnosticsLogsRoute.tsx`

## 19. Summary

The configurable logging foundation is implemented and broadly useful, but
its precise boundary is narrower than the old design implied. Category rules,
profiles, sinks, manifests, legacy compatibility, same-process control, live
level changes, frontend error ingest, and redacted diagnostic export exist.
Automatic summary/full payload shaping, live profile application, per-workspace
manager isolation, uniformly safe raw logs, and a full logs UI do not.
