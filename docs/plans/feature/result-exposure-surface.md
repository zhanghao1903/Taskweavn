# Feature Plan: Result And Evidence Exposure Surface

> Status: planned
> Type: Product 1.0 UI projection / result evidence boundary
> Last Updated: 2026-05-30
> Related Plans: [Fixed-Route Task Execution Bridge](fixed-route-task-execution-bridge.md), [Main Page Real Backend Integration](main-page-real-backend-integration.md), [Audit Page Contract](../../engineering/audit-page-contract.md)
> Related Contracts: [UI ViewModel Contract](../../frontend/ui-viewmodel-contract.md), [API UI Mapping](../../frontend/api-ui-mapping.md), [UI API Contract](../../product/plato-ui-api-contract.md)

---

## 1. Problem

The fixed-route execution bridge can now move published Tasks through pending,
running, done, and failed. The Main Page can expose task status, but the user
still lacks enough product-facing evidence to understand what happened.

Current exposure gaps:

- task result is mostly a status plus `result_ref` / `error_ref`;
- file changes are not summarized into the Main Page snapshot;
- Agent execution is not yet consistently written into the user-facing
  `MessageStream`;
- raw `Observation` / EventStream facts exist, but they do not have a default
  product surface;
- Audit Page contracts exist, but evidence projection is not wired yet.

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

Deliver:

- minimal durable result/error summary object;
- stable result/error ids usable by `TaskBus.result_ref` / `error_ref`;
- tests for restart-read stability.

### P8.E2 AgentLoop To MessageStream Bridge

Deliver:

- success message for `LoopResult.final_answer`;
- failure message for bridge/AgentLoop failures;
- task/session correlation in message context.

### P8.E3 Main Snapshot Projection

Deliver:

- `MainPageSnapshot.result` projection from result summary;
- failed Task error projection;
- no raw observation payload in snapshot.

### P8.E4 File Change Summary Projection

Deliver:

- minimal deterministic file summary projection;
- partial/hidden evidence flags where applicable;
- link from Task/result to Audit-ready evidence refs.

### P8.E5 Audit Entry Closure

Deliver:

- route-ready audit entry from session/task/result/file context;
- return context preservation;
- structured not_available state when Audit records are not populated yet.

---

## 8. Non-goals

- Do not implement the full Audit Page UI in this work package.
- Do not expose raw logs as Main Page content.
- Do not implement rich result packaging cards for Product 1.0.
- Do not add Routing Agent summary policy.
- Do not solve full context governance here.

---

## 9. Open Questions

1. Should Product 1.0 store result summaries in a dedicated table, or reuse a
   typed MessageStream/EventStream ref with a stable result id?
2. Should file summary projection be driven by observed tool outputs first, or
   by workspace diff snapshots?
3. Should failed Task summaries be stored as first-class result objects, or as
   error objects with `error_ref` only?

