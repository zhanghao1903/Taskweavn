# TaskWeavn Project Plan

> Status: active
> Last Updated: 2026-05-18
> Maintained By: planning session
> Product Baseline: Plato 1.0
> Architecture Baseline: A1
> Related: [Global Roadmap](../roadmap.md), [Docs Operating Model](docs-operating-model.md), [Capability Map](../capabilities/index.md), [Plato 1.0 Gap Analysis](../product/versions/1.0/gap-analysis.md), [Current Architecture](../architecture/current.md), [Release Records](../releases/)

---

## 1. Purpose

This file is the operational project plan. It is narrower than the global roadmap:

- the roadmap explains phase direction;
- this file explains the next work queue and how implementation sessions should start.

Current rule: new implementation work should start from a capability packet and then create or update a feature plan package.

```text
docs/capabilities/<capability>/README.md
  -> docs/plans/features/<feature>/
      overview.md
      contract.md
      frontend.md
      backend.md
      integration.md
      acceptance.md
```

Historical plans are archived in [legacy docs](../archive/legacy-2026-05-18/). They can be mined for detail, but they are not the active work queue.

---

## 2. Current Project Shape

TaskWeavn is now a Task-first local assistant platform. Plato is the first product built on it.

Current working model:

- **User-facing product:** Plato.
- **Project/system name:** TaskWeavn.
- **Active product version:** Plato 1.0.
- **Active architecture version:** A1.
- **Current implementation focus:** turn the server-core Task/authoring/message foundations into a usable desktop product.

The key product workflow is:

```text
natural language
  -> RawTask
  -> feasibility / clarification
  -> DraftTaskTree
  -> user edits and confirms
  -> publish to TaskBus
  -> execute Tasks
  -> project messages, files, audit, diagnostics, and results into UI
```

---

## 3. Completed Foundation

| Foundation | Status | Evidence |
|---|---:|---|
| Phase 1 core ReAct agent | done | Typed events, tools, runtime, LLM client, CLI. |
| Phase 2 sandbox/audit/thought store | done | CodeAction, Docker sandbox, AuditAgent, SQLite ThoughtStore. |
| Phase 3.1-3.8 Interaction Layer | done | [release](../releases/phase-3-interaction-layer-through-3-8.md) |
| LLM provider reliability | done | [release](../releases/llm-provider-reliability.md) |
| Configurable logging | done | [release](../releases/configurable-logging-system.md) |
| Task domain/UI model separation | done | [release](../releases/task-domain-ui-model-separation.md) |
| Collaborator authoring foundation | done | [release](../releases/collaborator-agent-task-authoring.md) |
| Task publishers and initial TaskBus publish path | done / partial | [release](../releases/task-publishers-schedule-api.md) |

---

## 4. Immediate Work Queue

Recommended order for Plato 1.0:

| Order | Capability | Why Now | Plan State |
|---:|---|---|---|
| 1 | [Main Page real backend](../capabilities/main-page-real-backend/) | The product must stop being fixture-driven. | create feature package |
| 2 | [UI/backend contracts](../contracts/ui-backend/) | Frontend/backend split needs stable query, command, event, error, and viewmodel contracts. | expand contract docs |
| 3 | [Settings and first run](../capabilities/settings-and-first-run/) | Non-developer users need provider/workspace setup before testing. | create feature package |
| 4 | [Task execution](../capabilities/task-execution/) | Published Tasks need a real claim/execute/update lifecycle. | create feature package |
| 5 | [Message and confirmation](../capabilities/message-and-confirmation/) | Human-in-the-loop UX must be real, not CLI-only. | create feature package |
| 6 | [File change summary](../capabilities/file-change-summary/) | Task-centered trust depends on visible file impact. | create feature package |
| 7 | [Audit trust](../capabilities/audit-trust/) | Trust page is key for early users and testers. | create feature package |
| 8 | [Product error handling](../capabilities/product-error-handling/) | Failures must become recoverable user states. | create feature package |
| 9 | [Diagnostic bundle](../capabilities/diagnostic-bundle/) | Early testing needs supportable failure reports. | create feature package |
| 10 | [Packaging and distribution](../capabilities/packaging-and-distribution/) | Trusted alpha needs double-click app packaging. | release plan exists |

The order can change, but a change should update this file and the relevant capability packets.

---

## 5. Plan Package Rule

For each substantial capability, create:

```text
docs/plans/features/<feature>/
  overview.md
  contract.md
  frontend.md
  backend.md
  integration.md
  acceptance.md
```

Use only the needed files. For example, packaging work belongs under `docs/plans/release/`, not `docs/plans/features/`.

Frontend and backend should not become separate product plans. They are separate implementation tracks inside one capability plan. This keeps product intent unified while keeping implementation context small.

---

## 6. Completion Rule

When an implementation session completes a package:

1. mark the package result in its plan files;
2. update the relevant capability packet;
3. update [Plato 1.0 Gap Analysis](../product/versions/1.0/gap-analysis.md) if status changed;
4. update [contracts](../contracts/) if UI/backend boundaries changed;
5. add or update a decision record under [decisions](../decisions/) if a costly choice changed;
6. add a release record under [releases](../releases/) for completed milestones;
7. update [global roadmap](../roadmap.md) only if sequence or baseline changed.

This keeps project state readable without turning every implementation detail into roadmap noise.
