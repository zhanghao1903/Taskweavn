# Gap Registry

> Status: active
> Last Updated: 2026-05-28
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

## 3. Gap Table

| Gap | Area | Priority | Status | Architecture Facts | Plan / Source | Notes |
|---|---|---:|---|---|---|---|
| UI/backend contract baseline | UI / backend | P0 | done | [ui-backend-communication](../architecture/ui-backend-communication.md), [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md) | [contract baseline plan](../plans/feature/ui-backend-contract-baseline.md), [technical design](../plans/feature/ui-backend-contract-baseline-technical-design.zh-CN.md), [release](../releases/ui-backend-contract-baseline.md), [product contract draft](../product/plato-ui-api-contract.md) | Contract models, mapping adapters, Query Gateway baseline, Command Gateway baseline, Event Projection constructors, shared frontend/backend JSON fixture parity, and sidecar transport shell are in place. Durable SSE replay remains a separate gap. |
| Local sidecar API shell | Server / UI | P0 | done | [ui-backend-communication](../architecture/ui-backend-communication.md), [llm-provider-reliability](../architecture/llm-provider-reliability.md) | [sidecar API shell plan](../plans/feature/local-sidecar-api-shell.md), [technical design](../plans/feature/local-sidecar-api-shell-technical-design.zh-CN.md), [release](../releases/local-sidecar-api-shell.md) | Framework-neutral HTTP transport, command validation, SSE frame shell, optional auth, and stdlib loopback HTTP binding are in place. Durable SSE replay remains out of scope. |
| Main Page real backend integration | UI / backend | P0 | in_progress | [ui-backend-communication](../architecture/ui-backend-communication.md), [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md), [authoring-domain](../architecture/authoring-domain.md) | [Main Page integration plan](../plans/feature/main-page-real-backend-integration.md), [backend composition technical design](../plans/feature/main-page-real-backend-integration-technical-design.zh-CN.md), [frontend runtime plan](../plans/feature/main-page-frontend-runtime-integration.md), [frontend runtime technical design](../plans/feature/main-page-frontend-runtime-integration-technical-design.zh-CN.md), [checkpoint](../releases/main-page-frontend-runtime-integration.md), [Main Page UX](../product/plato-main-page-ux-flow.md), [Frontend design](../product/plato-frontend-technical-design.md) | Stage checkpoint only. Local sidecar assembly, HTTP client, runtime env switch, session-centric snapshot query identity, command response handling, command coverage, frontend logs, and conservative UiEvent invalidation are in place. The gap is not closed: real browser/Electron smoke, session creation/selection, pending/error UX, confirmation/message hardening, TaskNode edit controls, file-change projection, audit/trust surfaces, and durable event behavior still need follow-up work. |
| TaskBus execution lifecycle | Task / agents | P0 | done | [task](../architecture/task.md), [bus-v2](../architecture/bus-v2.md), [agent](../architecture/agent.md) | [release](../releases/taskbus-execution-lifecycle.md) | Minimal lifecycle is in place: claim_next, running, complete, fail, skip-as-failed, retry-through-publisher, and persistent SQLite status updates. Full agent runtime execution remains separate from TaskBus state authority. |
| Completion-time `task_after` pipeline | Pipeline / TaskBus | P1 | deferred | [task](../architecture/task.md), [bus-v2](../architecture/bus-v2.md) | [pipeline plan](../plans/feature/pipeline-task-loading.md), [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Moved out of Product 1.0. Publish-time `task_before` / `task_begin` are done; automatic after-tasks are useful for 1.1 but not required for the 1.0 closed loop. |
| Fixed-route task execution bridge | Task / agents | P0 | in_progress | [task](../architecture/task.md), [bus](../architecture/bus.md), [agent](../architecture/agent.md), [ADR-0010](../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md) | [fixed-route execution plan](../plans/feature/fixed-route-task-execution-bridge.md), [technical design](../plans/feature/fixed-route-task-execution-bridge-technical-design.zh-CN.md), [checkpoint](../releases/fixed-route-task-execution-bridge.md) | Slice 6 reached: `FixedRouteTaskExecutor`, resident Default Agent protocol, AgentLoop-backed sidecar assembly, one-tick sidecar seam, Main Page execution projection, sidecar-owned background dispatcher, publish `startImmediately` trigger, and explicit execution dispatch route are in place. Gap remains open for durable result payload behavior and user-facing smoke. No Router, Agent Manager, assignment fields, or Main Page reassignment UI are included. |
| Routing Agent assignment productization | Task / agents | P1 | deferred | [agent](../architecture/agent.md), [tool-capability-layer](../architecture/tool-capability-layer.md), [task](../architecture/task.md), [bus](../architecture/bus.md), [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0012](../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md) | [minimal assignment plan](../plans/feature/minimal-agent-assignment-semantics.md), [technical design](../plans/feature/minimal-agent-assignment-semantics-technical-design.zh-CN.md) | Deferred out of Product 1.0. Router runtime, optional Routing Agent policy, assignment fields, assigned-only claim, Agent Manager, and stale pending sweep belong to Product 1.1+ when multiple execution Agents or custom routing become product needs. |
| Cooperative task interruption | Task / agents | P0 | planned | [task](../architecture/task.md), [bus](../architecture/bus.md), [interaction-layer](../architecture/interaction-layer.md), [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md) | TBD | User/system can request stop; TaskBus records intent, Agent/runtime owns safe points and acknowledges terminal outcome. Pending can stop immediately; running is cooperative. |
| Message and confirmation UI integration | Interaction / UI | P0 | unplanned | [interaction-layer](../architecture/interaction-layer.md), [ui-backend-communication](../architecture/ui-backend-communication.md), [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md) | [UI API interfaces](../plans/ui/ui-api-interfaces.md) | Message substrate exists; UI command/event path remains. |
| File Change Summary | Trust / UI | P0 | unplanned | [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md), [task](../architecture/task.md) | [UI file summary plan](../plans/ui/file-change-summary.md) | Parent node must aggregate child node file changes. |
| Audit / Trust page implementation | Trust / UI | P0 | planned | [configurable-logging-system](../architecture/configurable-logging-system.md), [interaction-layer](../architecture/interaction-layer.md), [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md) | [Audit PRD](../product/plato-audit-page-prd.md), [Audit UX](../product/plato-audit-page-ux-flow.md), [Audit page plan](../plans/ui/audit-page-project-implementation-plan.md) | Product docs exist; implementation and evidence projection remain. |
| Product error handling | Product / runtime | P0 | unplanned | [llm-provider-reliability](../architecture/llm-provider-reliability.md), [configurable-logging-system](../architecture/configurable-logging-system.md), [ui-backend-communication](../architecture/ui-backend-communication.md) | TBD | Needs product-level taxonomy and recovery actions. |
| Settings and first run | Product / config | P0 | unplanned | [configurable-logging-system](../architecture/configurable-logging-system.md), [llm-provider-reliability](../architecture/llm-provider-reliability.md) | [settings/logs/audit boundary](../product/plato-settings-logs-audit-boundary.md) | Needed before non-developer testing. |
| Diagnostic bundle | Observability | P0 | unplanned | [configurable-logging-system](../architecture/configurable-logging-system.md) | TBD | Session archive exists; user/tester export and redaction remain. |
| Packaging and distribution | Release | P0 | planned | [ui-backend-communication](../architecture/ui-backend-communication.md), [configurable-logging-system](../architecture/configurable-logging-system.md) | TBD | Electron + Python sidecar strategy discussed; needs executable release plan if not already present. |
| Result packaging cards | Result / UI | P1 | planned | [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md), [authoring-domain](../architecture/authoring-domain.md) | [result packaging plan](../plans/feature/result-packaging-agent-cards.md), [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Product 1.1 capability. 1.0 only needs a clear result view; richer card packaging is not a 1.0 blocker. |
| Agent protocol and governance | Agents / extensibility | P1 | unplanned | [agent](../architecture/agent.md), [tool-capability-layer](../architecture/tool-capability-layer.md), [bus](../architecture/bus.md), [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md) | [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Product 1.1 TODO: define the baseline Agent contract, what an Agent must satisfy to join the system, and later special protocols for Routing, Execution, Collaborator, Audit, and Result Packaging Agents. Custom Agent creation and validation are advanced features outside 1.0. |
| Skills integration | Capability / product | P1 | unplanned | [agent](../architecture/agent.md), [tool-capability-layer](../architecture/tool-capability-layer.md), [authoring-domain](../architecture/authoring-domain.md) | [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Research track for reusable capabilities, skill metadata, feasibility, and TaskNode assignment semantics. |
| MCP integration | Tools / external systems | P1 | unplanned | [tool-capability-layer](../architecture/tool-capability-layer.md), [interaction-layer](../architecture/interaction-layer.md), [configurable-logging-system](../architecture/configurable-logging-system.md) | [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Research track for external tool/data integration through MCP while preserving confirmation, risk, and audit boundaries. |
| File and multimodal support | Input / context | P1 | unplanned | [authoring-domain](../architecture/authoring-domain.md), [task-domain-ui-model-separation](../architecture/task-domain-ui-model-separation.md), [ui-backend-communication](../architecture/ui-backend-communication.md) | [Product 1.1 plan](../product/plato-1-1-product-plan.md) | Research track for files, images, documents, and other multimodal inputs as first-class Task context and evidence. |
| Persistent authoring stores | Authoring | P0 | done | [authoring-domain](../architecture/authoring-domain.md), [authoring-command-protocol](../architecture/authoring-command-protocol.md), [ADR-0009](../decisions/ADR-0009-single-active-session-worktree.md) | [RawTask / DraftTaskTree persistence plan](../plans/feature/raw-task-draft-tree-persistence.md), [technical design](../plans/feature/raw-task-draft-tree-persistence-technical-design.zh-CN.md), [release](../releases/raw-task-draft-tree-persistence.md) | Closed for Product 1.0 authoring recovery: SQLite RawTask/DraftTaskTree stores, active authoring state, sidecar assembly, publish identity alignment, authoring command idempotency, and API command response idempotency are in place. Post-publish editing policy remains separate. |
| Centralized runtime configuration | Config | P1 | planned | [configurable-logging-system](../architecture/configurable-logging-system.md), [llm-provider-reliability](../architecture/llm-provider-reliability.md) | [runtime config plan](../plans/feature/centralized-runtime-configuration.md), [ADR-0007](../decisions/ADR-0007-centralized-runtime-configuration.md) | Logging control exists; unified config plane remains. |

---

## 4. When To Create A Plan

Create or update a plan only when at least one of these is true:

1. the gap is selected as current or next implementation work;
2. the gap crosses frontend/backend, storage, protocol, or agent boundaries;
3. the gap needs detailed technical design before code;
4. the gap will be implemented across multiple sessions or branches;
5. the gap requires a new ADR or changes an accepted architecture boundary.

Do not create a plan just because a gap exists.

---

## 5. Update Rule

When work changes a gap:

1. update this table;
2. update the relevant plan if one exists;
3. update architecture docs if a system boundary changed;
4. add or update an ADR if the decision is expensive to reverse;
5. add or update a release record when the gap is meaningfully closed;
6. update roadmap only if priority, sequencing, or phase baseline changes.
