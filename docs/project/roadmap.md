# TaskWeavn Project Plan

> Status: active
> Last Updated: 2026-06-18
> Maintained By: planning session
> Phase Baseline: Product 1.0 local unsigned RC accepted; Product 1.1 workspace-aware foundation has started
> Related: [Global Roadmap](../roadmap.md), [Gap Registry](../gaps/), [Planning Workflow](../planning_workflow.md), [Architecture](../architecture/), [Phase 3 Release Record](../releases/phase-3-interaction-layer-through-3-8.md), [Collaborator Authoring Release](../releases/collaborator-agent-task-authoring.md), [User Traceability](../user_model/traceability.md)

---

## 1. Current Project Shape

TaskWeavn is being rebuilt from an early ReAct code agent into a Task-first collaboration system.

The original technical path came from [Interaction Layer Design](../architecture/interaction-layer.md). That path is still valid through Phase 3.8, but the next project plan is now adjusted by newer architecture work:

- Task is the core user interaction object.
- The UI should show Task Tree Lists, Task cards, confirmations, messages, and file summaries.
- RawTask and feasibility belong to Authoring Domain before Task Tree drafting.
- Collaborator plans against a read-only CapabilityCatalog and mutates authoring state through Authoring Commands, not the full concrete tool pool.
- Collaborator Agent becomes the system role that drafts and edits Task Trees with the user.
- TaskPublisher becomes the single boundary from user/collaborator/pipeline/scheduler/API/custom trees into TaskBus.
- Reliability and logging must be strengthened before large user tests.

The immediate authoring work is grounded in:

- [UN-105](../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md): task fit, feasibility, and capability boundary disclosure.
- [UN-101](../user_model/needs/UN-101-photo-curation-batch-screening.md): batch task trees with human review checkpoints.
- [UN-102](../user_model/needs/UN-102-courseware-html-generation.md): editable content-generation task trees.
- [UN-103](../user_model/needs/UN-103-car-purchase-decision-support.md): clarification/evaluation before high-risk information work.

Planning now uses a lightweight routing model:

```text
Architecture facts
  -> Gap Registry
  -> Plan package
  -> Implementation
  -> Release record
```

Do not convert every unplanned gap into a plan. Create a plan only when the gap
is selected for current or near-term execution, or when detailed technical
design is needed before implementation.

---

## 2. Completed Foundation

### Phase 1 — Core ReAct Agent

Status: done.

Delivered:

- Typed `Action` / `Observation`.
- EventStream abstraction.
- LLMClient facade.
- Basic tools and local runtime.
- ReAct loop and CLI entry.

### Phase 2 — CodeAction, Sandbox, Audit, Thought Store

Status: done.

Delivered:

- `CodeAction`.
- Docker sandbox execution.
- AuditAgent.
- SQLite ThoughtStore.
- Phase 2 user tests and examples.

### Phase 3.1-3.8 — Interaction Layer Foundation

Status: done.

| Slice | Delivered |
|---|---|
| 3.1 | Session, WorkspaceLayout, SQLite EventStream. |
| 3.2 | RiskScore, RiskAssessment, BaselineOnlyAssessor, AutonomyBehavior, action baseline risks. |
| 3.3 | AgentMessage, MessageStream, SQLite MessageStream, task_id correlation across events and messages. |
| 3.4 | InProcessMessageBus and Subscription. |
| 3.5 | AutonomyGate and WaitCoordinator. |
| 3.6a | AgentLoop gate/wait integration. |
| 3.6b | Async autonomy drain via pending decisions. |
| 3.6c | Minimum interactive CLI surface for autonomy gating. |
| 3.7 | LLMRiskAssessor and CompositeAssessor. |
| 3.8 | Derived Session.status from EventStream + MessageStream; `archived` remains stored override. |

See [Phase 3 release record](../releases/phase-3-interaction-layer-through-3-8.md).

---

## 3. Replanned Work Streams

The next project plan is organized as work streams instead of continuing the old linear Phase 3.9-3.13 order. Each stream can produce one or more implementation branches.

### P3B — Reliability And Observability

Status: accepted baseline, follow-up hardening planned. Priority: P0/P1.

| Package | Source Plan | Implementation Goal |
|---|---|---|
| LLM provider/retry/thinking | [LLM provider plan](../plans/feature/llm-provider-retry-thinking.md) | Done: provider abstraction, retry policy, DeepSeek provider, thinking metadata, OpenRouter provider pinning. |
| Configurable logging | [Logging plan](../plans/feature/configurable-logging-system.md) | Done: global/session/category rules, JSONL + pretty display, same-process hot update, archives. |
| Centralized runtime configuration | [Runtime configuration plan](../plans/feature/centralized-runtime-configuration.md) | Follow-up: global/workspace/session/task config, effective snapshots, config store, config bus, hot updates. |

Acceptance:

- Temporary LLM failures do not immediately collapse long-running sessions.
- DeepSeek thinking can be enabled without losing reasoning/tool-call continuity.
- Testers can raise log level for a session/category and locate archived logs.
- Config changes should later be resolved, audited, and hot-applied through one shared control plane.

### P3C — Task Authoring Foundation

Status: server-core authoring foundation done; TaskPublisher bridge done in P3D. Priority: P0.

| Package | Source Plan | Implementation Goal |
|---|---|---|
| Task domain/UI model separation | [Task model/UI separation](../plans/feature/task-domain-ui-model-separation.md) | Done: stable backend Task plus TaskCard/TaskNode ViewModel projection. |
| Collaborator Agent | [Collaborator Agent plan](../plans/feature/collaborator-agent-task-authoring.md) | Done: mock-LLM draft Task Tree generation, selected-node refinement, validation, publish boundary, and UI/API adapter. |
| RawTask and feasibility authoring flow | [Collaborator Agent plan](../plans/feature/collaborator-agent-task-authoring.md) | Done: RawTask, FeasibilityReport, RawTaskAsk, RawTaskAnswer, and Authoring Domain boundary before DraftTaskTree generation. |
| CapabilityCatalog, tool-pool boundary, and Authoring Command Protocol | [Tool Capability Layer](../architecture/tool-capability-layer.md), [Authoring Command Protocol](../architecture/authoring-command-protocol.md) | Done as first server-core boundary: capability-first planning, no workspace tool pool on Collaborator, command-first system-state mutation. |
| UI API contracts | [UI API interfaces](../plans/ui/ui-api-interfaces.md) | Done for authoring adapter surface; concrete transport and UI integration remain follow-ups. |

Acceptance:

- Natural language can be transformed into a draft Task Tree List.
- Ambiguous, unsupported, unsafe, or partially feasible user input can be represented as RawTask without entering TaskBus.
- User edits and confirmations are recorded as replayable facts.
- UI can render Task cards from projections without owning backend truth.
- Current server-core satisfies these through services, in-memory stores, mock LLM tests, and `CommandResult` adapter contracts. User-facing end-to-end validation waits for API transport and UI.

### P3D — Task Publishing And Pipeline

Status: TaskPublisher server-core release candidate done; pipeline loading partially implemented at publish-time. Priority: P0.

| Package | Source Plan | Implementation Goal |
|---|---|---|
| TaskPublisher abstraction | [Task Publisher plan](../plans/feature/task-publishers-schedule-api.md), [release](../releases/task-publishers-schedule-api.md) | Done: TaskBus-backed publisher, SQLite TaskBus, custom tree parser, idempotent publish service, scheduler/API adapters, publish-time pipeline expansion. |
| Pipeline task loading | [Pipeline loading plan](../plans/feature/pipeline-task-loading.md) | Partial: task_before/task_begin publish-time expansion done; task_after completion-time orchestration is moved to Product 1.1. |
| Agent assignment constraints | [Pipeline loading plan](../plans/feature/pipeline-task-loading.md) | Task can require/prefer an Agent Template while preserving capability validation. |

Acceptance:

- All publish sources go through one validation and publish boundary.
- Pipeline tasks are normal Tasks with publisher metadata.
- API and scheduled publishing are idempotent and auditable.

### P3E — Task-first UI And Product 1.0 Local RC

Status: accepted for Product 1.0 local unsigned RC. Main Page, Settings,
Audit, Diagnostics, ASK/confirmation, fixed-route execution, result/error
projection, file summary, packaged Electron smoke, mounted unsigned DMG smoke,
and manual Finder launch have Product 1.0 closure records. Remaining work in
this area is Product 1.1+ hardening unless it directly blocks the accepted
local RC path. Priority: done for Product 1.0; follow-ups are routed through
the Gap Registry.

| Package | Source Plan | Implementation Goal |
|---|---|---|
| Plato MVP product/UX baseline | [Plato MVP PRD](../product/plato-mvp-prd.md), [Main Page UX Flow](../product/plato-main-page-ux-flow.md) | Product scope, user path, screen states, and Main Page behavior. |
| Figma UI baseline 1.0 | [Figma UI Baseline](../product/plato-figma-ui-baseline.md) | Current visual/layout source for implementation. |
| Frontend technical design | [Plato Frontend Technical Design](../product/plato-frontend-technical-design.md) | Technology choice, architecture, state/API boundaries, implementation slices. |
| Main Page frontend runtime integration | [Frontend runtime plan](../plans/feature/main-page-frontend-runtime-integration.md), [release](../releases/main-page-frontend-runtime-integration.md) | Done / accepted for Product 1.0 Main Page frontend/backend integration. |
| Workspace inspection foundation | [Product 1.1 workspace inspection milestone](../plans/feature/product-1-1-workspace-inspection-milestone.md), [Git/Diff/File Viewer API contract](../engineering/git-diff-file-viewer-api-contract.md) | Accepted Product 1.1 P0 foundation: workspace git status, changed files, structured diff, text file viewer, inspection evidence, and Main/Audit/Outcome links are in place. |
| UI system text and localization foundation | [UI system text plan](../plans/feature/product-copy-localization-foundation.md), [contract](../engineering/product-copy-localization-contract.md) | Implemented Product 1.1 foundation: typed UI text registry, `en-US` / `zh-CN` catalogs, and Main/Settings/Audit/Diagnostics/Workspace Inspection chrome migration. |
| Early UI interaction model | [Task-first UI overview](../plans/task-first-ui-interaction.md) | Superseded as implementation plan; retained as concept seed. |
| Early UI sub-designs | [UI plan directory](../plans/ui/) | Historical planning archive unless explicitly pulled into new frontend work. |
| Result packaging cards | [Result packaging plan](../plans/feature/result-packaging-agent-cards.md), [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Product 1.1 capability for richer information-style presentation; not a Product 1.0 blocker. |

Acceptance:

- Users can see the Task topology and interact with Task cards.
- Session message stream and task-scoped projections are consistent.
- Suitable information-style answers can render as card sets without losing the raw text answer.
- Finished Task Nodes are read-only; pending/running nodes expose only valid actions.
- Frontend work starts from a clean scaffold and Figma-state stories, not the deprecated experimental frontend.

### P4 — Multi-Agent Task Execution / Agent Productization

Status: deferred Product 1.1+ research. Priority: P1 only after workspace,
runtime input, Plan/TaskNode, and context foundations make multiple execution
Agents a concrete user need.

Focus:

- baseline Agent protocol and governance;
- optional Routing Agent policy;
- assignment facts and assigned-only claim behavior;
- Agent Manager health/failure behavior;
- multi-agent event/message/log replay.

### P5 — Context, Memory, Retrieval, Summarization, And Analytics

Status: planned / selective Product 1.1+. Priority: P1/P2 after the
workspace-aware coding loop and runtime input modes stabilize.

Focus:

- Task, Plan, Session, and Inquiry Context boundaries;
- read-only inquiry context over file/diff/result/audit facts;
- advanced usage analytics beyond the completed Product 1.1 token ledger;
- later semantic retrieval and cross-session memory;
- task-aware summarization and evaluation sets.

---

## 4. Superseded Or Moved Items

| Old Item | New Plan |
|---|---|
| Phase 3.9 PlanTool | Merged into Collaborator Agent and draft Task Tree authoring. A simple file-based plan tool can be revived later as support infrastructure. |
| Phase 3.10 shared/ append-only | Moved to P4 multi-agent/shared workspace work. |
| Phase 3.11 in-session RAG | Moved to P5 after stable Task/message/log archives. |
| Phase 3.12 cross-session RAG | Moved to P5 and remains optional. |
| Phase 3.13 conversation summarization | Moved to P5; should become Task-aware summarization. |

---

## 5. Product 1.1 Current Work Queue

The source of truth for individual gap status is [Gap Registry](../gaps/).
This queue records the current sequencing implied by that registry.

Completed foundation:

- **[Plan / TaskNode contract migration](../plans/feature/plan-tasknode-contract-migration.md)** —
  accepted after PR #74. Product 1.1 now has durable Plan/TaskNode storage,
  active Plan identity, publish handoff, stored Plan query preference,
  execution lifecycle sync, result/file/detail reads, and Audit identity
  normalization. Legacy DraftTaskTree compatibility remains until Router and
  frontend migration no longer need it.
- **[Session Conversation / Activity timeline](../plans/feature/session-conversation-activity-timeline.md)** —
  typed Activity view models, HTTP query, backend projection, frontend
  API/types, contract fixtures, and Main Page Activity drawer are in place.
  Router-written activity records remain with the Runtime Input Router track.
- **[Execution Web Search / Fetch](../plans/feature/execution-web-search-capability.md)** —
  controlled external evidence retrieval is implemented for Product 1.1:
  Tavily-backed `web_search`, selected-URL `web_fetch`, global Settings
  enablement, write-only key storage, URL safety policy, gated execution tool
  registration, Context/Audit/diagnostics descriptors, and offline-first tests
  are in place.
- **[UI system text and localization](../plans/feature/product-copy-localization-foundation.md)** —
  typed `en-US` / `zh-CN` catalogs, deterministic locale resolution, Settings
  language selector with renderer-local persistence, Main/Settings/Audit/
  Diagnostics/Workspace Inspection chrome migration, and product-error recovery
  labels are in place.
- **[Skill Governance backend foundation](../plans/feature/product-1-1-skill-governance.md)** —
  `SkillRegistry`, `SkillActivation`, `SkillContextSource`, budget policy,
  permission merge, trace metadata, diagnostics-safe summary export, and the
  internal `precision-file-editing` proof are now on `main`. UI/debug exposure
  and broader routing remain future tracks.
- **[Execution Plane Service / Task API planning](../plans/feature/execution-plane-service-task-api.md)** —
  Product 1.1 now has an accepted direction and executable plan package for
  treating Execution Plane as a service-capable boundary. EP0-EP3 should remain
  additive: service DTOs, embedded TaskApiService, Plato compatibility path,
  and local sidecar Task API shell without changing Product 1.0 Main Page
  behavior.

Recommended implementation order is governed by the
[Runtime Input And Contract Revision Program](../plans/feature/runtime-input-and-contract-revision-program.md)
for runtime input, read-only inquiry, contract revision commands, Activity, and
Audit/diagnostic linkage.

1. **[Runtime Input Router contract](../plans/feature/runtime-input-router-contract.md)** —
   RIR-0 is accepted and RIR-1/RIR-2 deterministic foundation is implemented:
   additive request/response contract, `RouteDecision`, HTTP route,
   deterministic active ASK/confirmation and selected-task stop/retry routing,
   non-mutating unsupported outcomes, and activity metadata. The question route
   now reaches the accepted Read-only Inquiry foundation, and command-backed
   guidance is available through Contract Revision Command Skills. Continue
   with Main Page Router-first submit, durable Router Activity for every route
   outcome, and Router-wide Audit/diagnostic linkage.
2. **[Read-only inquiry context](../plans/feature/read-only-inquiry-context.md)** —
   foundation is implemented: contract models, frontend transport
   types/fixtures, deterministic status answers, result/file-summary refs,
   explicit Activity/Audit ref summaries, Workspace Inspection file/diff
   summaries, safe planning diagnostic refs, Router `inquiryResult`, transient
   Main Page notice plus Activity strip/overlay display, durable
   answered-question Activity replay through MessageStream with safe evidence
   refs preserved, workspace-scoped file/diff/audit hrefs, read-only diagnostic
   bundle support descriptor, explicit Inquiry refs including result refs,
   Activity ref actions, focused no-mutation tests, real sidecar no-mutation
   acceptance, and configured Electron smoke. Audit evidence
   `recordId + evidenceId` focused route wiring is also implemented with
   focused backend/frontend tests, real sidecar acceptance, and desktop shell
   coverage; Main Page Activity diagnostic refs can invoke the redacted
   diagnostic export action. Guarded LLM provider/seam tests, default sidecar
   LLM runtime wiring with explicit fallback controls, LLM sidecar no-mutation
   acceptance, and
   `npm run electron:smoke:read-only-inquiry-llm` for the configured desktop
   shell path plus `npm run electron:smoke:packaged-read-only-inquiry-llm` for
   the unsigned package-dir path are in place. The guarded LLM answer provider
   is now enabled by default in sidecar assembly with explicit deterministic
   fallback controls. `npm run electron:smoke:launcher` verifies the
   launcher-backed local runtime with provider-independent read-only inquiry
   fallback. Read-Only Inquiry is accepted for the Product 1.1 local runtime.
   Follow-ups are non-blocking: richer diagnostic bundle section descriptors if
   needed, Router Activity/Conversation persistence for non-answer outcomes,
   localization polish, optional result/detail deep links, and signed installer
   no-mutation hardening.
3. **[Contract revision command skills](../plans/feature/contract-revision-command-skills.md)** —
   command substrate is implemented on `main`: command protocol,
   `record_guidance`, ASK/confirmation routed resolution, Plan/TaskNode
   patch/create/delete, and `create_execution_task` handoff. Remaining Product
   1.1 closure is Router-first UX, durable route evidence, Router-wide
   Audit/diagnostic refs, and real Electron/sidecar acceptance for the full P0
   route set.
4. **[Execution Plane Service / Task API](../plans/feature/execution-plane-service-task-api.md)** —
   keep the accepted service boundary moving as additive local slices. Current
   follow-ups should preserve the Plato compatibility path while closing
   external app auth, remote worker claim/lease, callbacks, and vertical
   workflow packages later.
5. **Localization follow-ups** — Electron native menu localization,
   translator extraction/lint tooling, backend-owned language preference if
   centralized configuration accepts it, and bilingual smoke only when Product
   1.1 acceptance needs it.
6. **Result packaging and completion-time `task_after`** — improve result
   comprehension and post-completion automation after the Plan/TaskNode and
   input-mode boundaries are clear.
7. **Skills, MCP, Agent protocol, and routing productization** — keep as
   research/productization tracks until workspace trust, precision tools, and
   runtime input are stable.

Product 1.0 is accepted as a local unsigned release candidate. Product 1.1
should improve trust and controllability before expanding automation breadth:
workspace inspection, precision file tools, token usage analytics, workspace
archive/delete data management, UI system text foundation, execution web
search/fetch, Skill Governance backend foundation, Plan/TaskNode migration, and
Conversation / Activity Timeline are completed; Contract Revision Command
Skills are implemented as the command substrate; Runtime Input Router-first UX,
durable Router Activity, Router Audit/diagnostic closure, Execution Plane
Service / Task API hardening, result packaging, and
protocol productization are the next actionable tracks.

---

## 6. Project Governance

When an implementation session finishes a package:

1. Update the package plan under `docs/plans/` or `docs/issues/`.
2. Update [Gap Registry](../gaps/) if status, priority, or plan routing changed.
3. Update this file if status or priority changed.
4. Update [Global Roadmap](../roadmap.md) if phase sequencing changed.
5. Add/update an ADR under [../decisions/](../decisions/) if a decision changed.
5. Add/update a release record under [../releases/](../releases/) if a milestone completed.

This project plan is intentionally operational: it should help pick the next branch and understand why that branch matters.
