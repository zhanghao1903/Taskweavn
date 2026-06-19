# Runtime Input And Contract Revision Program

> Status: active program index
>
> Last Updated: 2026-06-14
>
> Owner: Product / Backend UI Gateway / Frontend / TaskBus
>
> Related:
> [Contract Revision And Execution Loops](../../architecture/contract-revision-and-execution-loops.md),
> [Plato Runtime Input Model](../../product/plato-runtime-input-model.md),
> [Plato Session Content Model](../../product/plato-session-content-model.md),
> [Runtime Input Router Contract](runtime-input-router-contract.md),
> [Read-Only Inquiry Context](read-only-inquiry-context.md),
> [Read-Only Inquiry Context Technical Design](read-only-inquiry-context-technical-design.md),
> [Contract Revision Command Skills](contract-revision-command-skills.md),
> [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md)

---

## 1. Purpose

This program doc is the source of truth for the cross-feature closure map around
runtime input, read-only inquiry, contract revision commands, Session
Conversation / Activity, and Router audit/diagnostic linkage.

Individual feature plans should own their local contract and implementation
slices. They should not duplicate the full dependency matrix from this document.

---

## 2. Program Boundary

The program answers how Plato turns Main Page natural-language input into one
of these outcomes:

- answer a read-only question;
- record guidance as typed context;
- revise Plan or TaskNode product state through commands;
- resolve ASK or confirmation lifecycle;
- create an execution request that enters TaskBus;
- show durable user-facing Activity / Conversation records;
- link routed input to Audit and diagnostics without exposing raw internals.

The program does not own workspace mutation. Workspace changes remain owned by
TaskBus execution under an accepted contract.

---

## 3. Document Ownership

| Document | Owns | Does not own |
|---|---|---|
| This program doc | Cross-feature dependency order, readiness map, closure criteria, maintenance rules | Per-feature schema details or implementation design |
| [Runtime Input Router Contract](runtime-input-router-contract.md) | Router request/response, route decision, deterministic foundation, Router slices | Inquiry answer generation, command skill schemas, TaskBus execution |
| [Runtime Input Router Technical Design](runtime-input-router-contract-technical-design.md) | RIR-1/RIR-2 implementation boundary and accepted deterministic Router design | Full program dependency matrix |
| [Read-Only Inquiry Context](read-only-inquiry-context.md), [technical design](read-only-inquiry-context-technical-design.md) | No-mutation question answering plan, evidence context boundary, and implementation design | Router classification or product-state command mutation |
| [Contract Revision Command Skills](contract-revision-command-skills.md) | Guidance, Plan/TaskNode mutation, ASK/confirmation resolve, execution handoff commands | Read-only answers or workspace tool execution |
| [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md) | Typed Activity query/projection and frontend surface | Product-state source of truth or raw chat transcript |
| Audit / diagnostic docs | Evidence, disclosure, support export, trust plane | Primary collaboration flow or Router classification |

---

## 4. Dependency Matrix

| Capability | Why it matters | Source document | Readiness | Blocks |
|---|---|---|---|---|
| Plan / TaskNode foundation | Router command routes need stable Plan/TaskNode identity and lifecycle sync. | [Plan / TaskNode Contract Migration](plan-tasknode-contract-migration.md) | completed | Contract revision commands |
| Session Conversation / Activity | Routed input must be replayable and understandable after reload. | [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md) | completed foundation; Router writes deferred | Router default frontend path |
| Runtime Input Router deterministic foundation | One Main Page input needs a safe route decision before any side effect. | [Runtime Input Router Contract](runtime-input-router-contract.md), [API contract](../../engineering/runtime-input-router-api-contract.md) | RIR-1/RIR-2 implemented | Read-only inquiry, guidance, execution handoff |
| Read-only inquiry | Users need answer-only questions over files, diffs, results, Audit, diagnostics, and status. | [Read-Only Inquiry Context](read-only-inquiry-context.md), [technical design](read-only-inquiry-context-technical-design.md) | accepted for Product 1.1 local runtime: transient Main Page Activity display, durable answered-question replay preserving safe evidence refs, safe planning diagnostic refs, diagnostic bundle support descriptor, explicit Inquiry refs including result refs, workspace-scoped file/diff/audit href context, Audit evidence `recordId + evidenceId` focused route wiring, Activity ref actions including redacted diagnostic export, real sidecar no-mutation acceptance, configured Electron smoke, guarded LLM provider/seam tests, default sidecar LLM runtime wiring with explicit deterministic fallback controls, `npm run electron:smoke:read-only-inquiry-llm`, `npm run electron:smoke:packaged-read-only-inquiry-llm`, and `npm run electron:smoke:launcher`; richer bundle section descriptors, optional result/detail deep links, localization polish, and signed installer no-mutation hardening are non-blocking follow-ups | Evidence display and acceptance |
| Guidance command | User guidance must become typed context, not hidden chat. | [Contract Revision Command Skills](contract-revision-command-skills.md) | planned; technical design needed | RIR guidance route |
| Plan/TaskNode command skills | Contract-changing input needs versioned, auditable commands. | [Contract Revision Command Skills](contract-revision-command-skills.md) | planned; technical design needed | RIR command routes |
| Execution request handoff | Workspace-changing text must create executable contract work, not run tools directly. | [Contract Revision Command Skills](contract-revision-command-skills.md) | planned; technical design needed | RIR execution request route |
| Durable Router session content | Router decisions and outcomes need durable replay beyond route-result metadata. | [Plato Session Content Model](../../product/plato-session-content-model.md), this program | planned; store/projection design needed | Conversation replay, diagnostics |
| Ambiguous intent classifier | Natural language needs more than deterministic command phrases. | [Plato Runtime Input Model](../../product/plato-runtime-input-model.md), [Runtime Input Router Technical Design](runtime-input-router-contract-technical-design.md) | planned; classifier design needed | Broad `auto` mode |
| Router audit/diagnostic linkage | Users and support need to inspect why a route happened and what side effect occurred. | Audit/diagnostic plans plus this program | planned; Router-specific linkage design needed | Product-complete acceptance |
| Real acceptance suite | Boundaries need regression protection with real sidecar/Electron data. | This program, per-feature plans | planned | Product-complete closure |

---

## 5. Implementation Order

1. Keep RIR-1/RIR-2 deterministic foundation as the current accepted Router
   baseline.
2. Treat Read-Only Inquiry as accepted for Product 1.1 local runtime. Keep
   richer diagnostic bundle section descriptors, localization polish, optional
   result/detail links, and signed installer no-mutation hardening as
   non-blocking follow-ups while RIR proceeds.
3. Accept and implement Contract Revision Command Skills technical design,
   starting with `record_guidance`.
4. Wire RIR-3 question and guidance routes into the accepted downstream
   capabilities.
5. Add command-backed Plan/TaskNode patch/create/delete and
   `create_execution_task` handoff.
6. Persist Router decisions/outcomes as durable Session content and Activity.
7. Migrate Main Page submit to Runtime Input Router by default.
8. Add bounded ambiguous-intent classification.
9. Link Router decisions to Audit/diagnostic refs and promote remaining
   Electron and broader route acceptance coverage.

Implementation design for steps 6-7:
[Router-first Main Page Input And Durable Activity Technical Design](router-first-main-input-durable-activity-technical-design.zh-CN.md).

---

## 6. Product-Complete Closure Criteria

The program is product-complete when:

1. Main Page input routes through Runtime Input Router by default.
2. Read-only questions return answers with evidence refs and `no_effect`.
3. Guidance is persisted as typed context through command-backed facts.
4. ASK and confirmation answers work from both explicit UI and routed input.
5. Contract-changing requests use versioned/idempotent command skills.
6. Workspace-changing requests create executable contract work and enter TaskBus
   only through the accepted execution path.
7. Every route produces durable user-visible Conversation / Activity evidence.
8. Router decisions link to downstream command, Audit, and diagnostic refs.
9. Low-confidence and unsupported input never mutates product state or
   workspace files.
10. Real sidecar/Electron acceptance covers happy paths, rejected commands,
    unsupported routes, and no-mutation guarantees.

---

## 7. Maintenance Rules

Use this doc for cross-feature sequencing and readiness. Use each feature plan
for local implementation detail.

When a runtime-input-related slice changes:

1. Update the owning feature plan's slice status.
2. Update this program doc only if dependency order, readiness, or closure
   criteria changed.
3. Update [Gap Registry](../../gaps/README.md) for status and canonical entry
   links.
4. Update [Project Roadmap](../../project/roadmap.md) only if priority or work
   queue changes.
5. Update API contracts only when request/response shapes change.
6. Update architecture docs or ADRs only when a loop boundary or durable
   decision changes.

Avoid copying the full dependency matrix into feature plans. Link back here
instead.
