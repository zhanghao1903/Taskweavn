# Fix Log: configurable-logging-system.md

> Architecture document:
> [../configurable-logging-system.md](../configurable-logging-system.md)
>
> Original:
> [../configurable-logging-system.original.md](../configurable-logging-system.original.md)
>
> Calibration date: 2026-07-10

## Workflow Gate Report

1. User request summary: calibrate one architecture document at a time against
   current docs and code, preserve the old document, and record evidence in a
   per-document fix log.
2. Detected workflow phase: P5/P8 architecture and backend-integration
   maintenance, with P9 tests used as verification evidence.
3. Task type: documentation-only architecture fact calibration.
4. Required upstream artifacts: logging feature/release records, observability
   models and manager, sinks/formatting/redaction, sidecar assembly, Runtime
   Config integration, current emitters, frontend logging, diagnostic export,
   and tests.
5. Found artifacts: all required artifacts were present.
6. Missing or weak artifacts: the old architecture document mixed intended
   payload policy with implemented behavior and did not fully include sidecar,
   frontend, Runtime Config, and diagnostic-export facts.
7. Whether implementation is allowed now: yes. The change is documentation
   only and current behavior is inspectable.
8. Prework required before implementation: preserve the original and inspect
   code, product/engineering docs, and tests before rewriting.
9. Proposed execution scope: replace only
   `docs/architecture/configurable-logging-system.md` and add this fix log.
10. Acceptance criteria: original preserved; manager, payload, redaction,
    archive, control, emitter, frontend, and diagnostic boundaries stated from
    code; targeted validation passes.
11. Risks and assumptions: the principal risk is treating schema fields,
    profiles, and release intent as proof that producers automatically select
    safe summary/full payloads.

## Sources Inspected

Architecture, product, plan, release, and engineering docs:

- `docs/architecture/configurable-logging-system.md`
- `docs/plans/feature/configurable-logging-system.md`
- `docs/releases/configurable-logging-system.md`
- `docs/plans/feature/diagnostic-bundle-export.md`
- `docs/plans/feature/centralized-runtime-configuration.md`
- `docs/product/plato-settings-logs-audit-boundary.md`
- `docs/engineering/runtime-config-settings-diagnostics-integration.md`

Structured logging code:

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

Backend integration and producer code:

- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/main_page_logging.py`
- `src/taskweavn/server/main_page_sessions.py`
- `src/taskweavn/server/client_logs.py`
- `src/taskweavn/server/main_page_audit_events.py`
- `src/taskweavn/server/settings_readiness.py`
- `src/taskweavn/server/settings_config.py`
- `src/taskweavn/runtime_config/defaults.py`
- `src/taskweavn/diagnostics/bundle.py`
- `src/taskweavn/llm/logging.py`
- `src/taskweavn/llm/retry.py`
- `src/taskweavn/core/event_stream.py`
- `src/taskweavn/core/sqlite_event_stream.py`
- `src/taskweavn/runtime/local.py`
- `src/taskweavn/runtime/sandbox.py`
- `src/taskweavn/interaction/bus.py`
- `src/taskweavn/interaction/gate.py`
- `src/taskweavn/interaction/wait.py`
- `src/taskweavn/audit/agent.py`

Frontend code:

- `frontend/src/shared/logging/frontendLogger.ts`
- `frontend/src/app/platoRuntime.ts`
- `frontend/src/pages/diagnostics/DiagnosticsLogsRoute.tsx`
- `frontend/src/pages/settings/SettingsRoute.tsx`
- `frontend/src/pages/main-page/httpMainPageAdapter.ts`

Tests selected for verification:

- `tests/test_logging_models.py`
- `tests/test_logging_manager.py`
- `tests/test_observability.py`
- `tests/test_logging_archive.py`
- `tests/test_logging_control.py`
- `tests/test_logging_event_taxonomy.py`
- `tests/test_runtime_config_logging_consumer.py`
- `tests/test_main_page_trace.py`
- `tests/test_main_page_sidecar_config.py`
- `tests/test_main_page_sidecar_app.py`
- `tests/test_diagnostic_bundle_export.py`
- `tests/test_ui_http_transport.py`
- `tests/test_llm_providers.py`
- `tests/test_llm_retry_policy.py`
- `tests/test_llm_contracts.py`
- `frontend/src/app/platoRuntime.test.ts`
- `frontend/src/pages/diagnostics/DiagnosticsLogsRoute.test.tsx`
- `frontend/src/e2e/diagnosticsBundleExport.e2e.test.tsx`
- `frontend/src/pages/settings/SettingsRoute.test.tsx`
- `frontend/src/pages/main-page/httpMainPageAdapter.test.ts`

## Verified Facts

### Models and manager

1. `LogLevel` includes TRACE and OFF and normalizes string/int values.
2. `LogCategory` includes `llm_io` in addition to the original category set.
3. `LogContext`, config, rules, profiles, overrides, events, and manifests are
   frozen Pydantic models that reject extra fields.
4. Ambient context uses a `ContextVar`; explicit non-null fields override it.
5. JSONL serialization writes both `event` and compatibility `msg`.
6. The module-level `_GLOBAL_MANAGER` is returned by `get_logging_manager`.
7. `apply_config` builds a new snapshot, swaps it under lock, closes old sinks,
   and emits `config.updated` using the new snapshot.
8. Effective rules apply base category rule, session patch, then matching
   unexpired overrides in tuple order.
9. Expired overrides are ignored but not removed in a background task.
10. Missing category rules resolve to the default level with no sinks.
11. A callable data payload is evaluated only after enable, payload-mode, and
    level checks pass.
12. `payload_mode=off` suppresses the entire event.
13. The manager has no separate behavior for `summary` versus `full` payloads.
14. No production call site outside observability control reads effective
    `payload_mode` to build a different payload.

### Redaction and sinks

15. Manager redaction applies only to `LogEvent.data`.
16. It recursively masks values under common secret-looking keys.
17. Token-usage counters are explicitly excluded from token-key redaction.
18. It does not scan strings or redact event message and context.
19. FileSink opens and closes a file for each event, with an in-process lock.
20. FileSink has size-based rotation with numbered backups.
21. The default session rotation is 10 MiB with five backups.
22. There is no cross-process file lock or remote sink.
23. ConsoleSink writes JSONL or pretty output to stderr; NullSink discards.

### Configurations, profiles, and control

24. Legacy compatibility retains `configure_logging`, `get_channel_logger`,
    four channel names, and `.log` filenames.
25. The compatibility class is named `StructuredLogHandler`, not
    `StructuredBridgeHandler`.
26. `configure_session_logging` supports a full JSON config, optional profile,
    and generic session manifest.
27. YAML logging config is explicitly rejected.
28. Built-in profiles are normal, quiet, debug-llm, debug-tools, debug-bus, and
    full-debug.
29. `debug-llm` patches only `llm`; it does not patch `llm_io`.
30. LoggingControlService implements profile, level, effective-rule, and close
    operations as a Python API.
31. Production source has no construction or HTTP binding of
    `LoggingControlService`; direct constructions are in tests.
32. RuntimeConfigLoggingConsumer applies only `logging.level`.
33. It applies a level to every category at global or session scope.
34. Other accepted Runtime Config keys are reported as skipped.
35. The catalog marks `logging.profile` live, but the logging consumer does not
    apply it.
36. Settings validates, stores, and reports a selected logging profile.
37. The inspected settings update does not invoke LoggingControlService.

### Archive and sidecar

38. Generic session archives live under
    `<log-dir>/sessions/<session-id>/`.
39. Sidecar archives live under
    `<workspace>/.plato/sessions/<session-id>/logs/`.
40. Sidecar global config logs live under
    `<workspace>/.plato/logs/global/`.
41. Existing configured sessions and newly created sidecar sessions receive a
    manifest.
42. Sidecar manifest creation can emit an Audit records invalidation.
43. The sidecar custom manifest lists every category unconditionally.
44. Sidecar config events are routed only to the global config sink, so the
    listed session `config.jsonl` may be absent.
45. Diagnostic export treats listed-but-missing log files as warnings.
46. Generic archive closure exists and is tested, but no production sidecar
    lifecycle call closes its manifest.
47. The logging manifest CLI assumes the generic layout; the render CLI accepts
    any explicit JSONL file.
48. Every workspace runtime configures the same process-wide manager; no
    per-workspace manager is assembled.

### Emitter and payload facts

49. ObjectLogger producers currently exist for action, observation, llm,
    llm_io, tool, bus, audit, gate, wait, sandbox, and config.
50. `task`, `agent`, `session`, `runtime`, and `risk` have empty declared event
    taxonomies.
51. The `bus` producer is the interaction MessageBus, not TaskBus.
52. The taxonomy test statically checks literal ObjectLogger event calls.
53. LLM summary events contain metadata, counts, usage, and retry information.
54. `llm_io.agent_input` writes full message/tool structures at INFO.
55. `llm_io.agent_output` writes content, reasoning, assistant-message data,
    and tool-call arguments at INFO.
56. EventStream Action/Observation emitters pass full `to_dict()` payloads at
    INFO.
57. LocalRuntime `tool.invoke` passes the action payload at INFO.
58. These payloads are not reduced by `payload_mode=summary` in the manager.

### Adjacent logging and diagnostics

59. Main Page trace uses a separate stdlib logger and optional direct
    stdout/file output controlled by environment variables.
60. Main Page trace does not pass through LoggingManager redaction.
61. Frontend logging has its own levels and configuration sources.
62. Only frontend error entries notify the HTTP sink.
63. The frontend error sink appends raw supplied payloads to
    `frontend-errors.jsonl` without manager redaction.
64. The sidecar wrapper emits an Audit invalidation after a frontend error
    append.
65. Diagnostic export reads bounded log tails and frontend errors.
66. Diagnostic bundle writes use stronger sanitization: secret fragments,
    prompt/tool/raw keys, paths, and long strings are sanitized.
67. The Diagnostics frontend route is an export handoff, not a full log
    browser.
68. Frontend log level and backend LoggingConfig are not synchronized.

## Stale or Corrected Claims

1. The old category list omitted implemented `llm_io`.
2. The old document described `task`, `agent`, `session`, `runtime`, and `risk`
   as if they were integrated producers. Their current taxonomy entries are
   empty.
3. The old integration table said LocalRuntime emitted both tool and runtime
   categories. Current LocalRuntime emits only `tool`.
4. The old document implied Bus logging covered general TaskBus behavior.
   ObjectLogger bus events come from the interaction MessageBus.
5. The old payload-mode section said `off` could keep event/context while
   dropping data. Current manager suppresses the complete event.
6. The old document said the manager builds data according to payload mode.
   It only gates disabled/off/level and then evaluates the supplied payload.
7. The old document stated summary mode excludes raw prompt/response by
   default. `llm_io` writes full I/O at INFO and manager summary mode does not
   remove it.
8. The old LLM DEBUG/full example implied profile-controlled raw payloads.
   Current debug-llm does not patch `llm_io`.
9. The old Tool/Runtime section implied full action payload was DEBUG-only.
   `tool.invoke` emits the action payload at INFO.
10. The old redaction language was too broad. Logging redaction is key-based
    data redaction, not message/context/string/prompt sanitization.
11. The old compatibility section named `StructuredBridgeHandler`; the class is
    `StructuredLogHandler`.
12. The old archive discussion did not distinguish generic CLI archives from
    `.plato` sidecar session archives.
13. The old document did not state that sidecar manifests list files that can
    be absent, including session config logs.
14. The old document implied archive close markers were part of normal sidecar
    lifecycle. The API exists, but production sidecar closure is not wired.
15. The old hot-update discussion did not include Runtime Config. Current live
    consumer applies level only, not profile.
16. The old document did not distinguish stored Settings profile from active
    process application.
17. The old document did not expose process-wide manager coupling across
    workspace runtimes.
18. The old document did not separate Main Page trace and frontend logging from
    the structured backend manager.
19. The old document did not capture frontend error ingest and Audit
    invalidation.
20. The old document did not clearly separate raw log redaction from stronger
    diagnostic-bundle sanitization.
21. The old document treated Diagnostics/Logs as mostly future. Diagnostic
    export and a frontend handoff route now exist, while a full log browser does
    not.

## New Document Decisions

1. Describe code behavior separately from release intent and planned policy.
2. Treat `payload_mode` as an effective-rule field with only `off` enforced by
   the manager today.
3. Make detailed INFO payloads and raw-archive sensitivity explicit.
4. Separate generic CLI and sidecar archive layouts.
5. Separate structured backend logging, Main Page trace, and frontend logging.
6. Treat diagnostic bundles as sanitized derived artifacts, not proof that raw
   logs are safe.
7. Record the exact live Runtime Config and Settings profile limits.
8. Record declared category taxonomy separately from actual producer coverage.

## Validation Log

Validation commands run after this rewrite:

```bash
git diff --check
uv run pytest tests/test_logging_models.py tests/test_logging_manager.py tests/test_observability.py tests/test_logging_archive.py tests/test_logging_control.py tests/test_logging_event_taxonomy.py tests/test_runtime_config_logging_consumer.py tests/test_main_page_trace.py tests/test_main_page_sidecar_config.py tests/test_main_page_sidecar_app.py tests/test_diagnostic_bundle_export.py tests/test_ui_http_transport.py tests/test_llm_providers.py tests/test_llm_retry_policy.py tests/test_llm_contracts.py
npm --prefix frontend run test -- src/app/platoRuntime.test.ts src/pages/diagnostics/DiagnosticsLogsRoute.test.tsx src/e2e/diagnosticsBundleExport.e2e.test.tsx src/pages/settings/SettingsRoute.test.tsx src/pages/main-page/httpMainPageAdapter.test.ts
```

Results:

- `git diff --check`: passed.
- Backend pytest: 157 passed.
- Frontend Vitest: 4 files passed, 1 file skipped; 38 tests passed, 1 test
  skipped.
- The skipped test was the real-sidecar diagnostic export E2E. Its required
  `PLATO_E2E_*` environment variables were not present, so the test suite used
  its declared `describe.skip` path.
