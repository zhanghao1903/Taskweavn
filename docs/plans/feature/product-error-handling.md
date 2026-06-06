# Feature Plan: Product Error Handling

> Status: in_progress
> Last Updated: 2026-06-05
> Gap: [Product error handling](../../gaps/README.md)
> Architecture: [LLM Provider Reliability](../../architecture/llm-provider-reliability.md), [Configurable Logging System](../../architecture/configurable-logging-system.md), [UI And Backend Communication](../../architecture/ui-backend-communication.md), [Task Domain/UI Model Separation](../../architecture/task-domain-ui-model-separation.md)
> Product: [Plato UI API Contract](../../product/plato-ui-api-contract.md), [Plato Product 1.0 Frontend QA Runbook](../../product/plato-1-0-frontend-qa-runbook.md)
> Related Plans: [Result And Evidence Exposure Surface](result-exposure-surface.md), [Linear Authoring And Minimal Retry Recovery](linear-authoring-retry-recovery.md), [Diagnostic Bundle Export](diagnostic-bundle-export.md)
> Release Record: TBD

---

## 1. Problem / Gap

Product 1.0 can now run the main local sidecar path, project result/error
summaries, expose retry for failed Tasks, and show Audit Page evidence. The
remaining error-handling gap is product semantics:

- backend `ApiError` codes exist, but they are transport-level categories, not a
  product-level taxonomy;
- LLM provider errors have typed retry/auth/rate/context classifications, but
  those classifications are not consistently translated into user recovery
  actions;
- failed Tasks can expose retry, but users need to know whether retry, edit,
  wait, inspect Audit, open Settings, or export diagnostics is the correct next
  action;
- internal exception strings and `error_ref` values must not become production
  UI copy;
- Audit and Diagnostics need stable error refs so support-oriented evidence can
  be found without exposing raw payloads by default.

Without this layer, recovery behavior will drift across command handlers,
Task execution, LLM providers, Audit projection, and frontend error states.

---

## 2. Architecture References Reviewed

Current facts this plan must preserve:

- `taskweavn.server.ui_contract.errors.ApiError` has stable transport codes:
  `bad_request`, `not_found`, `version_conflict`, `command_rejected`,
  `permission_denied`, `backend_busy`, `resync_required`, `internal_error`, and
  `idempotency_conflict`.
- `QueryResponse` and `CommandResponse` already require either data/result or
  `ApiError`.
- Task projection exposes failed Task state, `error_ref`, and retry
  eligibility.
- Result exposure already persists result/error summaries and maps failed Task
  summaries into `ResultCardView`.
- LLM provider reliability has retry classification for retryable failures,
  rate limits, auth/config/request/capability/context failures, and retry
  exhaustion.
- Configurable logging provides session manifests, category files, provider
  metadata, retry records, and redaction hooks.

---

## 3. Scope

Product 1.0 needs the smallest useful error layer:

1. Define product error categories and recovery actions.
2. Map backend command/query/Task/runtime failures into product error metadata.
3. Keep user-facing copy separate from diagnostic refs.
4. Surface recovery actions through existing UI contracts where possible.
5. Link errors to Audit and Diagnostic Bundle evidence without exposing raw
   logs or raw EventStream payloads by default.
6. Add tests for common Product 1.0 failure paths.

---

## 4. Non-goals

- Do not build a full Settings UI.
- Do not implement automatic Task retry policy.
- Do not implement cross-provider LLM fallback.
- Do not add a full permissions system.
- Do not expose raw logs, prompts, provider payloads, SQLite rows, or
  EventStream observations as default Main Page content.
- Do not replace the existing `ApiError` envelope shape unless a separate UI
  API contract change is approved.

---

## 5. Product Error Model

### 5.1 Product Error Categories

| Category | User meaning | Default recovery |
|---|---|---|
| `input_validation` | The request is incomplete or malformed. | Edit input and resubmit. |
| `missing_context` | The system needs more information or a valid session/task context. | Answer ASK, select context, or refresh. |
| `command_conflict` | The command no longer matches current backend state. | Refresh snapshot and retry if still relevant. |
| `backend_busy` | The sidecar or Task runner is already handling work. | Wait for events or retry later. |
| `network_or_event_sync` | The browser lost contact with the sidecar or event cursor is stale. | Reconnect, resync, or refresh. |
| `llm_auth_or_config` | Provider credentials or model configuration are invalid. | Open first-run/settings guidance or diagnostics. |
| `llm_rate_or_retry_exhausted` | Provider throttled or transient retries were exhausted. | Retry task/command later if safe. |
| `llm_context_or_capability` | The selected model cannot handle the request shape or context size. | Reduce task scope or change model/config. |
| `tool_or_sandbox_failure` | A local tool, file operation, command, or sandbox step failed. | Inspect Audit/Diagnostics; retry only if safe. |
| `task_execution_failed` | The Task reached a terminal failure. | Retry Task when eligible or inspect Audit. |
| `task_cancelled_or_interrupted` | The user/system stopped the Task or recovered a stopped run. | Retry Task when eligible. |
| `audit_evidence_partial` | Evidence exists but is incomplete, hidden, or unavailable. | Inspect Audit detail or export diagnostics. |
| `unexpected_internal` | The backend hit an unclassified failure. | Refresh, export diagnostics, and report. |

### 5.2 Recovery Actions

Product recovery actions should be small, typed, and UI-neutral:

| Action | Meaning |
|---|---|
| `edit_input` | User should modify the current input or Task guidance. |
| `answer_ask` | User should answer a blocking ASK. |
| `retry_command` | User can resend the same command idempotently or with a new command id. |
| `retry_task` | User can rerun the same published Task identity. |
| `refresh_snapshot` | UI should query the canonical snapshot again. |
| `wait_for_events` | UI should wait for SSE/runtime events before declaring failure. |
| `open_audit` | User should inspect trust/evidence context. |
| `open_settings` | User should fix provider/configuration prerequisites. |
| `export_diagnostics` | User/tester should produce a redacted diagnostic bundle. |
| `none` | No safe product action is available. |

### 5.3 Metadata Shape

Product 1.0 can initially carry product error metadata inside existing
`ApiError.details`, result/error summaries, task projection, and Audit records.

Recommended metadata keys:

```json
{
  "productCategory": "llm_rate_or_retry_exhausted",
  "recoveryActions": ["retry_task", "open_audit", "export_diagnostics"],
  "severity": "recoverable",
  "userMessageKey": "task.llm.retry_exhausted",
  "diagnosticRefs": {
    "errorRef": "task_error:session:task:attempt",
    "logManifestRef": "session-log-manifest"
  },
  "auditRef": {
    "scope": "task",
    "taskId": "task-123"
  }
}
```

Rules:

- `message` may be user-readable, but must not include raw provider payloads,
  stack traces, absolute secret paths, or prompt text.
- `details` can include stable refs and sanitized summaries, not raw payloads.
- `error_ref` remains a diagnostic/reference id, not production copy.
- A category can be retryable at transport level but not safe for Task-level
  retry if the underlying action may duplicate side effects.

---

## 6. Implementation Slices

### E1 Product Taxonomy Constants

Status: implemented for the initial backend slice on 2026-06-05.

Deliver:

- product error category and recovery action constants;
- mapper from existing `ApiErrorCode` to default product category/action;
- tests for backwards-compatible `ApiError.details` serialization.

Acceptance:

- existing UI contract envelopes stay valid;
- command/query errors can carry product category and recovery actions without
  changing the top-level shape.

### E2 Backend Error Mapping

Status: implemented for existing `ApiError` helper constructors and current
command/query gateway paths on 2026-06-05.

Deliver:

- helper for command/query gateways to attach product error metadata;
- mappings for bad request, not found, version conflict, command rejected,
  backend busy, resync required, idempotency conflict, and internal error;
- source refs for session/task/command where available.

Acceptance:

- frontend can decide whether to refresh, retry command, edit input, or show
  diagnostics link from metadata;
- internal exceptions are logged and referenced, not exposed as raw copy.

### E3 Runtime And LLM Failure Mapping

Status: partially implemented on 2026-06-05 for task execution summary
metadata and LLM provider classification mapping.

Deliver:

- mapper from LLM provider classifications to product categories;
- mapper from Task execution exceptions/cancellations to task-level product
  errors;
- result/error summary fields or metadata for recovery actions;
- Audit record source refs for failed Task / provider / tool events.

Acceptance:

- auth/config failures lead to `open_settings` or first-run guidance;
- rate/retry exhaustion can expose wait/retry when safe;
- context/capability failures point to edit/reduce scope or config guidance;
- unexpected runtime errors point to diagnostics without leaking raw traces.

### E4 Main Page And Audit Projection

Status: planned.

Deliver:

- Main Page error states use product category/recovery actions when present;
- failed Task cards and result surfaces show retry only when backend projection
  says it is safe;
- Audit records preserve error category, refs, disclosure state, and sanitized
  payload behavior;
- Diagnostics links stay reserved until diagnostic bundle export exists.

Acceptance:

- common Product 1.0 errors tell the user what to do next;
- Audit can explain why an error happened without becoming a raw log viewer.

### E5 QA And Runbook Closure

Status: planned.

Deliver:

- focused backend tests for category/action mapping;
- local sidecar HTTP tests for command error, failed Task retry, provider
  config/auth-style failure, and resync/network-style failure where feasible;
- update Product 1.0 QA notes/runbook if a new externally visible error state
  is added.

Acceptance:

- recoverable errors do not crash Main Page or Audit Page;
- first tester can capture enough refs for support without SQLite/manual log
  spelunking.

---

## 7. Contract / API Changes

Initial Product 1.0 preference:

- keep `ApiError` top-level shape unchanged;
- add product metadata through `details`;
- preserve existing `retryable` but do not treat it as the only recovery signal;
- only add first-class fields after frontend and backend both need them in more
  than one place.

If first-class fields become necessary, update:

- `docs/product/plato-ui-api-contract.md`;
- `frontend/src/shared/api/types.ts`;
- `src/taskweavn/server/ui_contract/errors.py`;
- backend/frontend contract fixture tests.

---

## 8. Tests And Validation

Required backend tests:

- `ApiError` product metadata serialization;
- command gateway mapping for invalid input, not found, conflict, busy, and
  internal exception;
- LLM classification to product category/action;
- Task execution failure/cancellation to result/error summary metadata;
- Audit record mapping for product error refs.

Required frontend/API tests if UI behavior changes:

- Main Page command error renders edit/retry/refresh action as appropriate;
- failed Task retry remains backend-authoritative;
- Audit Page keeps partial/hidden/error states readable;
- diagnostics link is disabled or reserved until bundle export exists.

Manual QA:

- one local sidecar HTTP run where a Task fails naturally or through a fixture;
- one command/query error run;
- one browser refresh/resync run.

---

## 9. Acceptance Criteria

Product 1.0 error handling is acceptable when:

1. every common command/query failure maps to a product category;
2. every failed Task exposes either a safe recovery action or an explicit "no
   safe recovery" state;
3. LLM provider auth/config/rate/context/capability failures produce different
   user guidance;
4. Main Page never depends on raw exception strings for production copy;
5. Audit Page can link errors to evidence refs while preserving hidden/redacted
   payload behavior;
6. diagnostic bundle export can include error refs and logs without exposing
   secrets by default.

---

## 10. Recommended Next Task Prompt

```text
Use the product-workflow-gate skill first.

Task:
Implement Product 1.0 product error taxonomy and backend mapping.

Context:
docs/plans/feature/product-error-handling.md defines the planned taxonomy,
recovery actions, and metadata rules. Keep the existing ApiError top-level
shape unless a contract gap is documented first.

Scope:
1. Add product error category/recovery action constants and mapper helpers.
2. Attach metadata through ApiError.details in command/query gateways.
3. Map LLM provider classifications and Task execution failures where already
   available.
4. Add focused backend contract tests.

Do not implement full Settings UI.
Do not implement automatic retry policy.
Do not expose raw exception, prompt, provider, log, or SQLite payloads.

Output:
- files changed
- tests run
- categories/actions implemented
- remaining UI/Audit/diagnostic gaps
```

---

## 11. Completion Updates

2026-06-05:

- Added shared Product 1.0 error taxonomy and recovery-action helpers under
  `taskweavn.product_errors`.
- Re-exported taxonomy helpers from the UI contract package.
- Attached default product metadata through existing `ApiError.details`
  constructors without changing the top-level `ApiError` shape.
- Added task execution summary metadata for AgentLoop failures, generic
  execution exceptions, external error refs, and LLM provider classifications.
- Stopped using raw exception text as the execution-exception summary
  `error_message`; user-facing copy now uses a stable error-type template.
- Added focused backend tests for metadata helpers, command/query gateway error
  paths, task failure summaries, and LLM failure classification mapping.

Remaining:

- Main Page rendering still needs to consume product metadata for visible
  recovery labels beyond existing retry projection.
- Audit record projection still needs first-class product error refs.
- Diagnostic bundle export still needs to consume product error refs once that
  plan is implemented.
