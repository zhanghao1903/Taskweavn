# Plato 1.0 Acceptance

> Status: draft
> Last Updated: 2026-05-18
> Product Version: 1.0
> Architecture Version: A1
> Related: [Overview](overview.md), [P0 Scope](p0-scope.md), [Gap Analysis](gap-analysis.md)

---

## 1. Acceptance Philosophy

Plato 1.0 is accepted when it can be used as a local desktop product by an early user, not when every internal architecture idea is implemented.

The acceptance standard is user-visible:

```text
Can a user launch Plato, configure it, express a goal, review Tasks, run work,
answer confirmations, inspect results/files/audit, and export diagnostics when needed?
```

---

## 2. Product Acceptance Checklist

| Area | Acceptance |
|---|---|
| Launch | User can double-click Plato app and see the Main Page. |
| First run | User can configure provider and workspace without CLI/env vars. |
| Provider | User can test provider connectivity and see clear errors. |
| Main Page | Main Page shows real Project/Workflow/Session/Task/message state. |
| Task authoring | User can input a natural-language goal and receive a Draft TaskTree. |
| Task editing | User can select a TaskNode and append guidance or edit supported fields. |
| Publish | User can publish the Draft TaskTree into executable Tasks. |
| Execution | Task statuses move through queued/running/waiting/done/failed. |
| Confirmation | User can resolve a confirmation attached to a TaskNode. |
| Result | User can see a result or failure summary. |
| File changes | User can see direct and parent-subtree file changes. |
| Audit | User can open an Audit / Trust surface for session/task evidence. |
| Error handling | Common failures show clear recovery actions. |
| Diagnostics | User can export a redacted diagnostic bundle. |
| Packaging | Non-familiar users can install a signed/notarized macOS Apple Silicon DMG. |

---

## 3. Technical Acceptance Checklist

| Area | Acceptance |
|---|---|
| Contracts | UI/backend contracts are documented and examples match implementation. |
| Sidecar | Backend binds to local-only address and uses per-launch auth token. |
| Events | UI can refresh or subscribe to session changes without manual reload. |
| Persistence | Session, task, messages, events, config, and logs survive app restart where required. |
| Idempotency | Important commands are idempotent or safely rejected. |
| Errors | Provider/config/command/task/sidecar failures map to product error model. |
| Logs | Session logs are archived with manifest and redaction. |
| Tests | Frontend unit/interaction tests, backend tests, and at least one end-to-end smoke path pass. |
| Packaging | App bundle starts/stops sidecar cleanly and passes Gatekeeper verification for beta builds. |

---

## 4. User Test Acceptance

Minimum user tests before broader beta:

1. Easy: create a simple file or document from a natural-language goal.
2. Medium: generate a small multi-file project with reviewable TaskTree and confirmations.
3. Hard: run a longer project session, inspect file summaries and audit evidence, then export diagnostics.

Each test should record:

- setup;
- goal input;
- expected TaskTree;
- confirmation points;
- final output;
- file changes;
- observed confusion;
- logs/diagnostics if failure occurs.

---

## 5. Release Blockers

Block 1.0 beta if:

- provider setup requires editing env vars;
- Main Page has no canonical tracked source or depends on fixtures;
- Task publish does not lead to visible execution;
- confirmations cannot be resolved through UI;
- file changes cannot be attributed to Tasks;
- audit/trust evidence is unavailable;
- diagnostic export is unavailable;
- non-familiar users must bypass macOS security warnings.
