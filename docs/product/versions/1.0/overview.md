# Plato 1.0 Overview

> Status: active product version package
> Last Updated: 2026-05-18
> Product Version: 1.0
> Architecture Version: A1
> Related: [P0 Scope](p0-scope.md), [Gap Analysis](gap-analysis.md), [Acceptance](acceptance.md), [Capability Map](../../../capabilities/index.md)

---

## 1. Product Promise

Plato 1.0 should let a non-developer user describe a goal in natural language, review the system's task plan, confirm important actions, watch execution progress, inspect results and file changes, and trust what happened enough to keep using the product.

The first release is not trying to be the strongest agent system. It is trying to prove a different product mental model:

```text
Task is the primary user interaction object.
Chat is an input and explanation surface.
Files are execution artifacts.
Audit is a trust surface.
```

---

## 2. Target User

Plato 1.0 targets individual users, not organizations.

Primary users:

- non-deep-technical users who want AI help with slightly complex work;
- light technical users or creators who can review tasks and file changes;
- trusted alpha/beta testers willing to install a local desktop app.

Not primary users:

- enterprise teams needing permissions and admin controls;
- developers expecting a full IDE replacement;
- organizations needing compliance-grade audit;
- multi-user collaboration groups.

---

## 3. Core User Flow

```text
Launch Plato
  -> configure provider/workspace if needed
  -> describe a goal
  -> Collaborator drafts Task Tree List
  -> user reviews/edits TaskNodes
  -> user publishes Tasks
  -> execution updates Task status and messages
  -> user resolves confirmations when needed
  -> user inspects Result, File Change Summary, and Audit / Trust evidence
  -> user exports diagnostics if something fails
```

---

## 4. P0 Capability Set

Plato 1.0 P0 consists of:

1. Settings and first run.
2. Main Page connected to real backend.
3. Task authoring.
4. Task execution.
5. Message and confirmation flow.
6. File Change Summary.
7. Audit / Trust page.
8. Product-level error handling.
9. Diagnostic bundle.
10. macOS Apple Silicon local app packaging.

See [P0 Scope](p0-scope.md) for detail.

---

## 5. Architecture Version

Plato 1.0 uses Architecture A1:

- Task-first product model.
- Authoring Domain separated from Execution TaskBus.
- One session message stream with task projections.
- UI/backend contract through Query / Command / Event.
- Local-first desktop packaging with Python sidecar.
- Structured logging and diagnostic archive as trust/debug substrate.

See [A1 Overview](../../../architecture/versions/a1-product-1.0/overview.md).

---

## 6. Current Baseline

Current implementation has strong server-core foundations:

- Action / Observation / EventStream.
- AgentLoop.
- Session and workspace layout.
- Interaction Layer: risk, autonomy, MessageStream, MessageBus, gate, wait.
- LLM provider reliability and retry.
- Structured logging and archives.
- RawTask / DraftTaskTree / Collaborator authoring.
- TaskPublisher and SQLite TaskBus publish/read surface.
- Publish persistence and framework-neutral API publish transport.
- Plato frontend baseline under `frontend/src`: Main Page scaffold, state catalog, typed mock/API adapter, shared API types, and UI primitives.

The main 1.0 gap is productization:

```text
server-core foundations + frontend baseline
  -> real desktop product with sidecar API, real Main Page integration, settings, audit, diagnostics, and packaging
```

---

## 7. Non-Goals For 1.0

| Non-goal | Reason |
|---|---|
| Multi-user collaboration | Personal assistant scope; multi-user would add heavy permission and interaction complexity. |
| Full multi-agent canvas | Task-first interaction is the product mental model; visible agent canvas can wait. |
| Marketplace / third-party tool platform | Architecture should reserve the space, but 1.0 should not carry platform burden. |
| Complex workflow engine | Keep pipeline/publishing simple enough to ship. |
| Enterprise compliance audit | Trust page should help users and testers, not replace compliance systems. |
| Mobile companion app | Desktop local-first delivery first. |

---

## 8. Product Quality Bar

1. Users can start the app without developer setup.
2. Users know what Plato plans to do before execution.
3. Users can intervene at TaskNode level.
4. Users can see progress and confirmation requests in context.
5. Users can inspect result and file changes.
6. Users can understand failures and export diagnostics.
7. The app feels like Plato, not a wrapped CLI.
