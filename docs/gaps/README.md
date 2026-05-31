# Gap Registry

> Status: active
> Last Updated: 2026-05-31
> Scope: current capability gaps, routing, and planning readiness
> Related: [Roadmap](../roadmap.md), [Project Plan](../project/roadmap.md), [Architecture](../architecture/), [Plans](../plans/)

---

## 1. Purpose

This file is the lightweight registry for known gaps between the current system
and the intended Plato / TaskWeavn product direction.

It is not a plan directory and it is not a product spec. It answers:

- what important gaps exist;
- which architecture facts constrain each gap;
- whether the gap has an executable plan;
- what should be planned next.

Gaps are allowed to stay `unplanned` until they are selected for execution.
Creating a plan for every known gap too early would create stale documents and
unnecessary coordination load.

---

## 2. Status Values

| Status | Meaning |
|---|---|
| `unplanned` | Known gap, not yet converted into an executable plan. |
| `planned` | A plan exists, but implementation has not started. |
| `in_progress` | Implementation or detailed technical design is underway. |
| `done` | The gap is closed enough for the current roadmap. |
| `deferred` | Worth doing, but intentionally delayed. |
| `not_now` | Explicitly outside the current product / architecture scope. |

---

## 3. Version Buckets

Product 1.0 is the closed-loop single-user product path:

- author a single active draft tree for one Session;
- publish into a line-first Task tree;
- execute through the fixed-route Default Agent bridge;
- expose task progress, result, file summary, confirmations, audit entry, and
  recoverable errors in the Main Page / Audit Page surfaces;
- package enough diagnostics for early technical users.

Product 1.1+ is the expansion path:

- richer result packaging;
- Routing Agent / custom Agent assignment;
- advanced `task_after` pipelines;
- skills, MCP, multimodal input, and broader runtime configuration;
- context governance beyond the accepted Product 1.0 deterministic baseline.

## 4. Product 1.0 Gap Table

| Gap | Area | Priority | Status | Architecture Facts | Plan / Source | Notes |
|---|---|---:|---|---|---|---|
| UI/backend contract baseline | UI / backend | P0 | done | [ui-backend-communication](../architecture/ui-backend-communication.md), [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md) | [contract baseline plan](../plans/feature/ui-backend-contract-baseline.md), [technical design](../plans/feature/ui-backend-contract-baseline-technical-design.zh-CN.md), [release](../releases/ui-backend-contract-baseline.md), [product contract draft](../product/plato-ui-api-contract.md) | Contract models, mapping adapters, Query Gateway baseline, Command Gateway baseline, Event Projection constructors, shared frontend/backend JSON fixture parity, and sidecar transport shell are in place. Durable SSE replay remains a separate gap. |
| Local sidecar API shell | Server / UI | P0 | done | [ui-backend-communication](../architecture/ui-backend-communication.md), [llm-provider-reliability](../architecture/llm-provider-reliability.md) | [sidecar API shell plan](../plans/feature/local-sidecar-api-shell.md), [technical design](../plans/feature/local-sidecar-api-shell-technical-design.zh-CN.md), [release](../releases/local-sidecar-api-shell.md) | Framework-neutral HTTP transport, command validation, SSE frame shell, optional auth, and stdlib loopback HTTP binding are in place. Durable SSE replay remains out of scope. |
| TaskBus execution lifecycle | Task / agents | P0 | done | [task](../architecture/task.md), [bus-v2](../architecture/bus-v2.md), [agent](../architecture/agent.md) | [release](../releases/taskbus-execution-lifecycle.md) | Minimal lifecycle is in place: claim_next, running, complete, fail, skip-as-failed, retry-through-publisher, and persistent SQLite status updates. Full agent runtime execution remains separate from TaskBus state authority. |
| Persistent authoring stores | Authoring | P0 | done | [authoring-domain](../architecture/authoring-domain.md), [authoring-command-protocol](../architecture/authoring-command-protocol.md), [ADR-0009](../decisions/ADR-0009-single-active-session-worktree.md) | [RawTask / DraftTaskTree persistence plan](../plans/feature/raw-task-draft-tree-persistence.md), [technical design](../plans/feature/raw-task-draft-tree-persistence-technical-design.zh-CN.md), [release](../releases/raw-task-draft-tree-persistence.md) | Closed for Product 1.0 authoring recovery: SQLite RawTask/DraftTaskTree stores, active authoring state, sidecar assembly, publish identity alignment, authoring command idempotency, and API command response idempotency are in place. Post-publish editing policy remains separate. |
| Main Page real backend integration | UI / backend | P0 | done | [ui-backend-communication](../architecture/ui-backend-communication.md), [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md), [authoring-domain](../architecture/authoring-domain.md) | [Main Page integration plan](../plans/feature/main-page-real-backend-integration.md), [backend composition technical design](../plans/feature/main-page-real-backend-integration-technical-design.zh-CN.md), [frontend runtime plan](../plans/feature/main-page-frontend-runtime-integration.md), [frontend runtime technical design](../plans/feature/main-page-frontend-runtime-integration-technical-design.zh-CN.md), [release](../releases/main-page-frontend-runtime-integration.md), [Main Page UX](../product/plato-main-page-ux-flow.md), [Frontend design](../product/plato-frontend-technical-design.md) | Accepted on 2026-05-30 as Product 1.0 Main Page frontend/backend integration closure. Local sidecar assembly, HTTP client/runtime switch, session-centric snapshot query identity, command response handling, command coverage, frontend logs, conservative UiEvent invalidation, durable authoring stores, publish identity alignment, fixed-route execution trigger, result/error projection, MessageStream bridge, deterministic file summary projection, and sidecar HTTP user-path smoke are in place. Browser/Electron smoke, UX polish, Audit detail, and durable event replay remain follow-up gaps, not blockers for this integration closure. |
| Fixed-route task execution bridge | Task / agents | P0 | done | [task](../architecture/task.md), [bus](../architecture/bus.md), [agent](../architecture/agent.md), [ADR-0010](../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md) | [fixed-route execution plan](../plans/feature/fixed-route-task-execution-bridge.md), [technical design](../plans/feature/fixed-route-task-execution-bridge-technical-design.zh-CN.md), [release](../releases/fixed-route-task-execution-bridge.md) | Accepted on 2026-05-30 for Product 1.0 fixed-route execution. `FixedRouteTaskExecutor`, AgentLoop-backed Default Agent, sidecar-owned background dispatcher, publish `startImmediately` trigger, explicit execution dispatch route, durable result/error summary refs, execution completion/failure MessageStream bridge, Main Page result/error projection, deterministic file summary projection, and sidecar HTTP user-path smoke are in place. Audit evidence closure, browser UI smoke, richer runtime recovery, Router, Agent Manager, assignment fields, and Main Page reassignment UI are separate follow-ups. |
| Context Manager 1.0 | Execution context | P0 | done | [context-manager](../architecture/context-manager.md), [overview](../architecture/overview.md), [ADR-0010](../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md) | [context manager plan](../plans/feature/context-manager-1-0.md), [technical design](../plans/feature/context-manager-1-0-technical-design.zh-CN.md), [release](../releases/context-manager-1-0.md) | Accepted on 2026-05-31 for Product 1.0 fixed-route execution context governance. Models, renderer, SQLite snapshot/trace store, source adapters, deterministic policy, Default Agent execution-start integration, sidecar assembly, and AgentLoop per-call context provider are in place. Full-suite pytest still has three unrelated pre-existing failures outside the Context Manager path. Excludes Router, Agent Manager, skills engine, MCP, multimodal packing, semantic retrieval, and parallel writer Agents. |
| Result and evidence exposure surface | Result / UI / Trust | P0 | in_progress | [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md), [ui-backend-communication](../architecture/ui-backend-communication.md), [configurable-logging-system](../architecture/configurable-logging-system.md) | [result exposure plan](../plans/feature/result-exposure-surface.md), [Audit page contract](../engineering/audit-page-contract.md), [UI ViewModel contract](../frontend/ui-viewmodel-contract.md) | Product 1.0 closure gap. Durable result/error summaries, execution process messages, Main Page result/error projection, and deterministic observed-fact file summary projection are in place. Remaining Product 1.0 exposure work is audit entry/evidence closure, recoverable error UX, and product smoke. Audit/Diagnostics keep raw evidence and logs. |
| Linear authoring and retry recovery | Authoring / runtime | P0 | in_progress | [authoring-domain](../architecture/authoring-domain.md), [task](../architecture/task.md), [bus](../architecture/bus.md), [ADR-0010](../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md) | [linear authoring / retry recovery plan](../plans/feature/linear-authoring-retry-recovery.md) | Manual retry slice is underway: failed published Tasks expose retry, retry publishes a new pending attempt with `retry_of` metadata, Main Page command contract has a retry route, snapshot projection shows the retry attempt in place of the original failed Task, and TaskBus dependency checks treat the latest successful retry as satisfying the original failed parent. Linear authoring defaults, interrupted-running recovery, and richer retry evidence remain open. Advanced retrieval, summarization, and cross-session context governance remain Product 1.1+. |
| Cooperative task interruption | Task / agents | P0 | planned | [task](../architecture/task.md), [bus](../architecture/bus.md), [interaction-layer](../architecture/interaction-layer.md), [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md) | TBD | User/system can request stop; TaskBus records intent, Agent/runtime owns safe points and acknowledges terminal outcome. Pending can stop immediately; running is cooperative. |
| Message and confirmation UI integration | Interaction / UI | P0 | unplanned | [interaction-layer](../architecture/interaction-layer.md), [ui-backend-communication](../architecture/ui-backend-communication.md), [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md) | [UI API interfaces](../plans/ui/ui-api-interfaces.md) | Message substrate exists; UI command/event path remains. |
| File Change Summary | Trust / UI | P0 | in_progress | [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md), [task](../architecture/task.md) | [UI file summary plan](../plans/ui/file-change-summary.md), [result exposure plan](../plans/feature/result-exposure-surface.md) | Main Page now projects deterministic observed file facts into `fileChangeSummary`, with projection-level child-task roll-up. Remaining gap is Audit evidence/detail closure and final frontend surface validation. |
| Audit / Trust page implementation | Trust / UI | P0 | planned | [configurable-logging-system](../architecture/configurable-logging-system.md), [interaction-layer](../architecture/interaction-layer.md), [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md) | [Audit PRD](../product/plato-audit-page-prd.md), [Audit UX](../product/plato-audit-page-ux-flow.md), [Audit page plan](../plans/ui/audit-page-project-implementation-plan.md) | Product docs exist; implementation and evidence projection remain. |
| Product error handling | Product / runtime | P0 | unplanned | [llm-provider-reliability](../architecture/llm-provider-reliability.md), [configurable-logging-system](../architecture/configurable-logging-system.md), [ui-backend-communication](../architecture/ui-backend-communication.md) | TBD | Needs product-level taxonomy and recovery actions. |
| Settings and first run | Product / config | P0 | unplanned | [configurable-logging-system](../architecture/configurable-logging-system.md), [llm-provider-reliability](../architecture/llm-provider-reliability.md) | [settings/logs/audit boundary](../product/plato-settings-logs-audit-boundary.md) | Needed before non-developer testing. |
| Diagnostic bundle | Observability | P0 | unplanned | [configurable-logging-system](../architecture/configurable-logging-system.md) | TBD | Product 1.0 needs minimal user/tester export and redaction. A full diagnostics/log browser can remain Product 1.1+. |
| Packaging and distribution | Release | P0 | planned | [ui-backend-communication](../architecture/ui-backend-communication.md), [configurable-logging-system](../architecture/configurable-logging-system.md) | TBD | Electron + Python sidecar strategy discussed; needs executable release plan if not already present. |

## 5. Product 1.1+ / Deferred Gap Table

| Gap | Area | Priority | Status | Architecture Facts | Plan / Source | Notes |
|---|---|---:|---|---|---|---|
| Completion-time `task_after` pipeline | Pipeline / TaskBus | P1 | deferred | [task](../architecture/task.md), [bus-v2](../architecture/bus-v2.md) | [pipeline plan](../plans/feature/pipeline-task-loading.md), [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Moved out of Product 1.0. Publish-time `task_before` / `task_begin` are done; automatic after-tasks are useful for 1.1 but not required for the 1.0 closed loop. |
| Routing Agent assignment productization | Task / agents | P1 | deferred | [agent](../architecture/agent.md), [tool-capability-layer](../architecture/tool-capability-layer.md), [task](../architecture/task.md), [bus](../architecture/bus.md), [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0012](../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md) | [minimal assignment plan](../plans/feature/minimal-agent-assignment-semantics.md), [technical design](../plans/feature/minimal-agent-assignment-semantics-technical-design.zh-CN.md) | Deferred out of Product 1.0. Router runtime, optional Routing Agent policy, assignment fields, assigned-only claim, Agent Manager, and stale pending sweep belong to Product 1.1+ when multiple execution Agents or custom routing become product needs. |
| Result packaging cards | Result / UI | P1 | planned | [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md), [authoring-domain](../architecture/authoring-domain.md) | [result packaging plan](../plans/feature/result-packaging-agent-cards.md), [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Product 1.1 capability. Product 1.0 only needs a durable user-readable result summary and minimal result view. |
| Agent protocol and governance | Agents / extensibility | P1 | unplanned | [agent](../architecture/agent.md), [tool-capability-layer](../architecture/tool-capability-layer.md), [bus](../architecture/bus.md), [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md) | [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Product 1.1 TODO: define the baseline Agent contract, what an Agent must satisfy to join the system, and later special protocols for Routing, Execution, Collaborator, Audit, and Result Packaging Agents. Custom Agent creation and validation are advanced features outside 1.0. |
| Skills integration | Capability / product | P1 | unplanned | [agent](../architecture/agent.md), [tool-capability-layer](../architecture/tool-capability-layer.md), [authoring-domain](../architecture/authoring-domain.md) | [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Research track for reusable capabilities, skill metadata, feasibility, and TaskNode assignment semantics. |
| MCP integration | Tools / external systems | P1 | unplanned | [tool-capability-layer](../architecture/tool-capability-layer.md), [interaction-layer](../architecture/interaction-layer.md), [configurable-logging-system](../architecture/configurable-logging-system.md) | [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Research track for external tool/data integration through MCP while preserving confirmation, risk, and audit boundaries. |
| File and multimodal support | Input / context | P1 | unplanned | [authoring-domain](../architecture/authoring-domain.md), [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md), [ui-backend-communication](../architecture/ui-backend-communication.md) | [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Research track for files, images, documents, and other multimodal inputs as first-class Task context and evidence. |
| Centralized runtime configuration | Config | P1 | planned | [configurable-logging-system](../architecture/configurable-logging-system.md), [llm-provider-reliability](../architecture/llm-provider-reliability.md) | [runtime config plan](../plans/feature/centralized-runtime-configuration.md), [ADR-0007](../decisions/ADR-0007-centralized-runtime-configuration.md) | Logging control exists; unified config plane remains. Product 1.0 can proceed with the existing minimal config shape. |

---

## 6. When To Create A Plan

Create or update a plan only when at least one of these is true:

1. the gap is selected as current or next implementation work;
2. the gap crosses frontend/backend, storage, protocol, or agent boundaries;
3. the gap needs detailed technical design before code;
4. the gap will be implemented across multiple sessions or branches;
5. the gap requires a new ADR or changes an accepted architecture boundary.

Do not create a plan just because a gap exists.

---

## 7. Update Rule

When work changes a gap:

1. update this table;
2. update the relevant plan if one exists;
3. update architecture docs if a system boundary changed;
4. add or update an ADR if the decision is expensive to reverse;
5. add or update a release record when the gap is meaningfully closed;
6. update roadmap only if priority, sequencing, or phase baseline changes.
