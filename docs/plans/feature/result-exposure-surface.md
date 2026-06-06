# Feature Plan: Result And Evidence Exposure Surface

> Status: in_progress
> Type: Product 1.0 UI projection / result evidence boundary
> Last Updated: 2026-06-05
> Related Plans: [Fixed-Route Task Execution Bridge](fixed-route-task-execution-bridge.md), [Main Page Real Backend Integration](main-page-real-backend-integration.md), [Audit Page Contract](../../engineering/audit-page-contract.md), [Audit Page Runtime Event/Refetch Design](../ui/audit-page-runtime-event-refetch-technical-design.md)
> Related Follow-up Plans: [Product Error Handling](product-error-handling.md), [Diagnostic Bundle Export](diagnostic-bundle-export.md)
> Related Contracts: [UI ViewModel Contract](../../frontend/ui-viewmodel-contract.md), [API UI Mapping](../../frontend/api-ui-mapping.md), [UI API Contract](../../product/plato-ui-api-contract.md)

---

## 1. Problem

The fixed-route execution bridge can now move published Tasks through pending,
running, done, and failed. The Main Page can expose task status, but the user
still lacks enough product-facing evidence to understand what happened.

Current remaining exposure gaps:

- file changes now have a minimal Main Page projection and Audit Page can
  project first-pass file evidence records, but richer timeline ordering still
  needs to use the task interaction timeline source instead of ad hoc source
  ordering;
- raw `Observation` / EventStream facts exist and can be summarized into Audit
  records in the first backend path, but they are not default Main Page content;
- Audit Page contracts, projection-backed routes, request-time sanitized
  payload disclosure, AP-013A runtime event/refetch design, AP-013B
  frontend event router/hook, AP-013C live refresh/stale/disconnected UI, and
  AP-013D workspace-backed UI event replay source exist; AP-013E emits the
  first AgentLoop/EventStream task-scoped audit event, and AP-013F emits
  config/log/confirmation source changes; final user-path validation remains
  open.
- recoverable error summary and recovery actions are visible through result /
  task projection paths in some cases, but the product-level error taxonomy is
  now owned by the separate Product Error Handling plan.

Without a clear exposure boundary, the product risks mixing three different
concepts:

1. what the Agent says it completed;
2. what deterministic system facts prove happened;
3. whether those facts are trustworthy.

---

## 2. Product Principle

Use separate responsibility owners:

```text
Agent      -> "what I completed" user-readable execution summary
Projector  -> "what system facts prove" deterministic evidence summary
Audit      -> "whether the evidence is trustworthy" verdict and explanation
```

Raw logs and raw observations are not default Main Page content. They are
evidence and diagnostics material.

---

## 3. Exposure Surfaces

### 3.1 Main Page: Work Control Surface

Main Page should show the minimum information a user needs to continue work:

- current TaskTree and selected Task status;
- task progress and execution result summary;
- user-readable process messages;
- actionable confirmations;
- file change summary;
- audit entry link;
- recoverable error summary and recovery actions.

Main Page should not expose raw EventStream rows, raw `Observation` payloads,
raw tool arguments, or debug logs by default.

### 3.2 Audit Page: Trust And Evidence Surface

Audit Page should show evidence and trust state:

- audit verdict;
- audit scope and entry context;
- evidence references;
- result, file, confirmation, config, and log/evidence records;
- hidden evidence and permission-limited states;
- stale snapshot and records-changed recovery states.

Audit Page may use summarized observation/event material, but it should not
turn raw payloads into default user copy unless the visibility policy allows it.

### 3.3 Diagnostics: Debug And Support Surface

Diagnostics should show support-oriented material:

- raw EventStream observations;
- raw logs;
- sidecar/runtime debug records;
- config and environment snapshots;
- diagnostic bundle export with redaction.

Diagnostics is not the user-facing success path.

---

## 4. Summary Responsibility Model

### 4.1 Execution Result Summary

Owner: Task execution Agent / Default Agent / AgentLoop bridge.

Source material:

- `LoopResult.final_answer`;
- `agent_finish(final_answer=...)`;
- structured bridge failure when execution does not finish.

Product use:

- populate a minimal `TaskResultSummary` or `ResultCardView`;
- append an informational `MessageStream` message such as task completed /
  task failed;
- let `TaskBus.result_ref` or `TaskBus.error_ref` point to a durable result or
  error object.

Rules:

- the Agent may describe what it attempted and completed;
- the Agent summary is not the source of truth for file diffs or audit verdict;
- failed execution should produce a concise user-facing error summary plus a
  stable `error_ref`.

### 4.2 File And Evidence Summary

Owner: deterministic projector.

Source material:

- EventStream observations;
- TaskBus lifecycle facts;
- workspace diff / file write facts;
- MessageStream and confirmation facts;
- result/error refs.

Product use:

- populate `FileChangeSummaryView`;
- populate Audit evidence records;
- preserve evidence refs for later inspection.

Rules:

- file summary must come from observed file facts, not casual Agent prose;
- if evidence is partial, hidden, or permission-limited, the UI must show that
  state explicitly;
- missing evidence is not the same as passed evidence.

### 4.3 Audit Summary

Owner: Trust Plane / audit projector.

Source material:

- audit records;
- evidence refs;
- task/result/file/confirmation/config/log facts;
- canonical audit verdict model.

Product use:

- populate `AuditPageSnapshot`;
- populate `AuditRecord` / `AuditRecordDetail`;
- expose passed, warning, failed, inconclusive, and not_available verdicts.

Rules:

- Audit owns trust judgement;
- Audit should reference evidence, not replace deterministic projectors;
- Audit Page must preserve hidden evidence and permission denied semantics.

---

## 5. Product 1.0 Target

Product 1.0 should close the user-visible execution loop with the smallest
durable exposure layer:

1. Persist an execution result summary for successful Task runs.
2. Persist an execution error summary for failed Task runs.
3. Write task completion/failure messages into `MessageStream`.
4. Project `ResultCardView` into `MainPageSnapshot.result`.
5. Project `FileChangeSummaryView` into `MainPageSnapshot.file_change_summary`
   when file evidence exists.
6. Keep Audit entry links route-ready, even if full Audit UI implementation is
   separate.
7. Keep raw observation/log exposure behind Audit or Diagnostics surfaces.

Acceptance:

- a completed Task has a user-readable summary, not only status `done`;
- a failed Task has a user-readable error and retry/recovery affordance source;
- file changes are summarized separately from Agent prose;
- Main Page does not need raw EventStream access;
- Audit and Diagnostics retain durable refs for deeper inspection.

---

## 6. Deferred Product 1.1+ Work

The following remain useful but should not block the 1.0 closed loop:

- rich result packaging cards;
- Result Packaging Agent;
- Routing Agent or custom Agent summary policies;
- full diagnostics/log browser;
- effective configuration explorer;
- MCP / Skills / multimodal evidence integration;
- context governance, summarization, and budget policy.

---

## 7. Implementation Phases

### P8.E1 Result Summary Store

Status: implemented as the backend storage foundation.

Deliver:

- minimal durable result/error summary object;
- stable result/error ids usable by `TaskBus.result_ref` / `error_ref`;
- tests for restart-read stability.

Implementation note:

- `TaskExecutionSummary` and `SqliteTaskExecutionSummaryStore` store readable
  result/error payloads in `.taskweavn/results.sqlite`.
- AgentLoop success refs point to stored `kind="result"` summaries.
- Successful non-AgentLoop executors that omit `result_ref` receive a generated
  `task_result:{session_id}:{task_id}:completed` summary ref.
- AgentLoop unfinished and execution exception refs point to stored
  `kind="error"` summaries.
- Main Page projection of these summaries remains P8.E3.

### P8.E2 AgentLoop To MessageStream Bridge

Status: implemented for fixed-route execution completion/failure messages.

Deliver:

- success message for `LoopResult.final_answer`;
- failure message for bridge/AgentLoop failures;
- task/session correlation in message context.

Implementation note:

- `FixedRouteTaskExecutor` publishes an informational session message after
  `TaskBus.complete(...)` / `TaskBus.fail(...)`.
- Message context carries `task_ref_kind`, `execution_status`, `title`,
  `result_ref` or `error_ref`, and summary metadata when available.
- Failed task messages set `ui_kind="error"` so UI contract mapping can expose
  error tone without parsing prose.
- MessageStream write failure does not overturn the already-committed TaskBus
  lifecycle fact.

### P8.E3 Main Snapshot Projection

Status: implemented for current session-level `MainPageSnapshot.result`.

Deliver:

- `MainPageSnapshot.result` projection from result summary;
- failed Task error projection;
- no raw observation payload in snapshot.

Implementation note:

- `TaskExecutionSummaryViewStore` projects durable execution summaries into
  task projection `TaskSummaryView`.
- `DefaultUiQueryGateway` selects the latest terminal published Task with a
  readable summary and maps it into `ResultCardView`.
- Failed Task summaries are projected into the same result surface with a
  `Failure reason` section.
- Snapshot message merging prefers the raw session `MessageStream` projection
  over task-tree latest-message projection when both point at the same
  message id, preserving execution titles and error kind.

### P8.E4 File Change Summary Projection

Status: implemented for deterministic Main Page summary projection from
observed file facts.

Deliver:

- minimal deterministic file summary projection;
- observed file facts from session-scoped `SqliteEventStream`;
- `MainPageSnapshot.file_change_summary` when file evidence exists;
- keep file evidence separate from Agent prose/result summaries.

Implementation note:

- `AgentLoop.run(..., task_id=...)` can now use the published Task id supplied
  by the fixed-route bridge, so EventStream rows correlate with TaskBus Tasks.
- `EventStreamFileChangeStore` projects `FileWriteObservation` and
  `CodeExecutionObservation` file facts into `TaskFileChangeSummary`.
- `DefaultTaskProjectionService` owns recursive child-task roll-up because it
  has Task tree context.
- `DefaultUiQueryGateway` maps the latest published Task with file-change
  evidence into `MainPageSnapshot.file_change_summary`.
- Agent final answers remain result summaries; file change copy is generated
  only from observed facts.

Deferred to P8.E5 / Audit:

- broader hidden/partial evidence states beyond the AP-012 first pass;
- evidence record ids and Audit detail links;
- runtime audit event emission/source coverage beyond the AP-013F
  AgentLoop/config/log/confirmation source set.

### P8.E5 Audit Entry Closure

Status: implemented for backend source orchestration; frontend Audit validation
remains pending.

Technical slice: [Audit Entry Closure](audit-entry-closure-technical-slice.md).

Current facts:

- Main Page can route to Audit Page with session/task return context.
- `DefaultUiQueryGateway` can return Audit Page snapshot, record list, record
  detail, and evidence detail through the frontend API methods.
- Audit projection now accepts a task interaction timeline source for message,
  confirmation, file, result/error, and draft publication closure records while
  preserving existing Audit contract shapes.
- EventStream action/observation records, config evidence, and log evidence
  remain on their typed providers.
- The first projection path maps Task projection, MessageStream,
  confirmations, file changes, task result/error summaries, EventStream
  action/observation/AuditObservation facts, session log archive references,
  and config manifest references when present.
- `TaskInteractionTimelineService` exists as a read-only task timeline source,
  but it is not yet the Audit Page gateway's orchestration source.
- Runtime event/refetch has first coverage through workspace-backed
  `SqliteUiEventSource` and `audit.records_changed` emissions for AgentLoop,
  config, log, and confirmation source changes.

Deliver:

- route-ready audit entry from session/task/result/file context;
- return context preservation;
- structured not_available state when Audit records are not populated yet.
- AP-013 live runtime audit event source/emission so Audit Page does not
  require manual refresh while execution facts continue to change.

Backend work:

1. Add an Audit source orchestration step that can consume
   `TaskInteractionTimelineService` entries for task-scoped ordering while
   preserving the current snapshot/record/detail contract.
2. Keep source-specific mappers additive:
   - task lifecycle / result / error summaries;
   - deterministic file-change facts;
   - confirmation and ASK-related facts;
   - EventStream action / observation / AuditObservation facts;
   - config manifest and log archive references.
3. Preserve explicit `partial`, `not_available`, `hidden`, `redacted`,
   `permission_denied`, `stale`, and query-error states. Missing source facts
   must not become silent success records.
4. Keep sanitized payload generation request-time only. Do not persist
   sanitized payload copies.
5. Emit `audit.records_changed` for newly covered source writes when the source
   can affect the current session/task Audit Page view.
6. Add a real HTTP-mode user-path validation that opens Audit from Main Page,
   inspects at least one result/file record, one runtime/event record, and one
   config or log reference when available.

Contract boundaries:

- Do not return raw EventStream rows, MessageStream rows, SQLite rows, or log
  payloads to the frontend.
- Do not require frontend code to reconstruct audit records from raw sources.
- Do not rewrite `AuditPageSnapshot`, `AuditRecord`, or evidence detail shapes
  unless a contract gap is documented first.
- Do not expand Main Page into a raw evidence or diagnostics surface.

Tests and validation:

- backend gateway tests for timeline-ordered records across task lifecycle,
  result/error, file, confirmation, EventStream, config, and log source refs;
- HTTP route tests for snapshot, list records, record detail, and evidence
  detail with partial/hidden/error states;
- event-source tests for source writes that emit `audit.records_changed`;
- frontend HTTP-mode regression that keeps A1-A14 mock fixtures as parity
  fixtures while proving at least one real sidecar Audit path;
- QA note update that records whether evidence ordering is clear enough for a
  Product 1.0 user test.

Acceptance:

- a completed or failed Product 1.0 Task can be opened from Main Page into
  Audit Page with coherent task/session scope and return context;
- Audit records are ordered by backend-projected task/evidence chronology, not
  frontend guesses;
- result, file, confirmation, EventStream, config, and log reference records
  appear when their source facts exist;
- missing or permission-limited source facts are labeled as partial,
  not_available, hidden, redacted, or permission_denied;
- Audit Page can update or mark itself stale through runtime events during the
  covered source changes;
- no raw payload is exposed by default.

Handoffs:

- User-facing recovery labels, retry affordance policy, and common error
  taxonomy are owned by [Product Error Handling](product-error-handling.md).
- Raw support export, redaction, and tester diagnostic packaging are owned by
  [Diagnostic Bundle Export](diagnostic-bundle-export.md).

---

## 8. Non-goals

- Do not implement the full Audit Page UI in this work package.
- Do not expose raw logs as Main Page content.
- Do not implement rich result packaging cards for Product 1.0.
- Do not add Routing Agent summary policy.
- Do not solve full context governance here.

---

## 9. Open Questions And Decisions

1. Decision for Product 1.0: file summary projection is driven by observed
   tool/EventStream file facts first. Workspace diff snapshots can be added as
   a later evidence source when observed facts are incomplete.
2. Open: how much of the execution completion/failure message should be authored by
   AgentLoop vs a deterministic bridge template for non-AgentLoop executions?
3. Open: whether the next Audit hardening implementation should prioritize
   richer timeline ordering first or AuditAgent verdict mapping first. The
   current Product 1.0 recommendation is timeline/source orchestration first
   because it improves existing records without changing the trust verdict
   model.
