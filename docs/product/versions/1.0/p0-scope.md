# Plato 1.0 P0 Scope

> Status: active
> Last Updated: 2026-05-18
> Product Version: 1.0
> Architecture Version: A1
> Related: [Overview](overview.md), [Gap Analysis](gap-analysis.md), [Capability Map](../../../capabilities/index.md)

---

## 1. P0 Definition

P0 means the product should not be offered to non-familiar early users without it.

Trusted alpha builds can temporarily bypass parts of packaging/signing, but the product goal remains signed local desktop delivery.

---

## 2. P0 List

| P0 | Capability | User Outcome |
|---:|---|---|
| 1 | [Settings and first run](../../../capabilities/settings-and-first-run/) | User can configure LLM provider and workspace without env vars. |
| 2 | [Main Page real backend](../../../capabilities/main-page-real-backend/) | Main Page controls a real session, not mock fixtures. |
| 3 | [Task authoring](../../../capabilities/task-authoring/) | User input becomes editable Draft Task Tree. |
| 4 | [Task execution](../../../capabilities/task-execution/) | Published Tasks run and update state. |
| 5 | [Message and confirmation](../../../capabilities/message-and-confirmation/) | User sees process messages and resolves confirmations in context. |
| 6 | [File Change Summary](../../../capabilities/file-change-summary/) | User sees changed files per Task and parent subtree. |
| 7 | [Audit Trust](../../../capabilities/audit-trust/) | User can inspect what Plato did and why. |
| 8 | [Product-level error handling](../../../capabilities/product-error-handling/) | User sees recoverable errors and next actions. |
| 9 | [Diagnostic bundle](../../../capabilities/diagnostic-bundle/) | User/tester can export redacted diagnostic evidence. |
| 10 | [Packaging and distribution](../../../capabilities/packaging-and-distribution/) | User double-clicks a macOS app; non-familiar users get signed/notarized DMG. |

---

## 3. P0 Boundaries

### 3.1 Settings And First Run

Must include:

- provider selection;
- API key input/storage path;
- model selection or default;
- provider connectivity test;
- workspace default location;
- basic logging/diagnostic profile.

Can defer:

- full advanced config center;
- task-level overrides;
- complex provider routing UI.

### 3.2 Main Page Real Backend

Must include:

- real session snapshot;
- real task tree projection;
- real message and confirmation projection;
- command submission;
- event refresh or subscription;
- useful loading/error states.

Can defer:

- advanced layout customization;
- multiple open windows;
- complex offline reconciliation.

### 3.3 Task Authoring

Must include:

- natural language input to RawTask / DraftTaskTree;
- TaskNode selection;
- TaskNode guidance or edit command;
- publish command.

Can defer:

- advanced structured import UI;
- full marketplace/capability authoring;
- visible multi-agent planning controls.

### 3.4 Task Execution

Must include:

- Task publish to TaskBus;
- minimal claim/execute/complete/fail lifecycle;
- status updates visible in Main Page;
- result and failure output.

Can defer:

- multi-agent scheduling fairness;
- parallel execution policies;
- complex retry orchestration.

### 3.5 Message And Confirmation

Must include:

- session message stream;
- task-scoped projection;
- confirmation card;
- response command;
- timeout/default decision visibility.

Can defer:

- rich markdown/threading;
- mobile-style notifications;
- advanced unread routing.

### 3.6 File Change Summary

Must include:

- direct file changes for a Task;
- recursive child summary for parent Tasks;
- session-level aggregate;
- link from completed Task detail.

Can defer:

- full visual diff;
- semantic code review;
- enterprise audit export.

### 3.7 Audit Trust

Must include:

- Audit / Trust page or panel;
- task/session evidence timeline;
- action/message/file/result references;
- user-readable severity or status labels.

Can defer:

- compliance-grade query system;
- raw log search;
- complex filtering.

### 3.8 Error Handling

Must include:

- provider auth/config errors;
- provider retry exhaustion;
- backend/sidecar startup failure;
- command rejection;
- version conflict / resync;
- task failure.

Can defer:

- full self-healing;
- automated bug report upload.

### 3.9 Diagnostic Bundle

Must include:

- redacted session logs;
- manifest;
- app/version/config fingerprint;
- relevant events/messages metadata;
- clear user-facing export path.

Can defer:

- automatic upload;
- workspace file inclusion by default.

### 3.10 Packaging And Distribution

Must include:

- macOS Apple Silicon;
- Electron shell;
- Python sidecar;
- local-only backend binding;
- signed/notarized DMG for non-familiar users.

Trusted alpha can use unsigned/ad-hoc build with explicit warning.

---

## 4. P1 Candidates

- Result packaging cards.
- Centralized runtime configuration full hierarchy.
- Pipeline completion-time `task_after`.
- Agent assignment improvements.
- RAG / summarization.

---

## 5. Not In 1.0

See [Capability Map](../../../capabilities/index.md#5-not-in-plato-10).
