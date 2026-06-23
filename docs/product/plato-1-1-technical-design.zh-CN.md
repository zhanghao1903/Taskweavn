# Plato Product 1.1 Technical Design

> Status: planning baseline
>
> Last Updated: 2026-06-18
>
> Product Plan: [Plato Product 1.1 Plan](plato-1-1-product-plan.md)
>
> Related:
> [Gap Registry](../gaps/README.md),
> [Project Roadmap](../project/roadmap.md),
> [Execution Plane Service And Task API Plan](../plans/feature/execution-plane-service-task-api.md),
> [Execution Plane Technical Design](../plans/feature/execution-plane-service-task-api-technical-design.zh-CN.md),
> [ADR-0020](../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md)

---

## 1. Purpose

This document is the Product 1.1 technical design baseline.

Product 1.0 proves the local Task-first closed loop:

```text
Goal
  -> Plan / TaskNode
  -> publish
  -> execute
  -> result / file summary / audit entry
  -> outcome review
```

Product 1.1 should not restart the product from scratch. It should strengthen
the product along two axes:

1. **Workspace-aware collaboration**: make local work inspectable, editable,
   recoverable, and explainable.
2. **Service-capable execution**: make the execution substrate reusable by
   Plato and, later, by external applications through a Task API.

The design goal is to preserve the Product 1.0 user loop while turning the
runtime into a more general work execution and evidence capture platform.

## 2. Source Of Truth Hierarchy

| Layer | Source |
|---|---|
| Product scope | `plato-1-1-product-plan.md` |
| Semantic model | Task, Session, Runtime Input, Plan Cycle, Outcome Review product docs |
| Gap routing | `docs/gaps/README.md` |
| Architecture boundaries | `docs/architecture/` and ADRs |
| Executable work packages | `docs/plans/feature/` |
| API / UI contracts | `docs/engineering/`, `docs/frontend/`, feature plans |
| Implementation facts | code, tests, release records |

Rules:

1. Product docs define user meaning.
2. Architecture docs define system boundaries.
3. Plans define implementation slices.
4. Implementation must not invent new product semantics in code.
5. If a boundary changes, update the ADR or architecture doc before broad
   implementation.

## 3. Product 1.1 Technical Thesis

Product 1.1 should converge on this system shape:

```text
Plato Product Plane
  - Session / Plan / TaskNode UX
  - Runtime input routing
  - Outcome review
  - Main / Audit / Settings / Diagnostics surfaces

Execution Plane
  - Task API boundary
  - TaskBus-backed lifecycle
  - AgentLoop runtime
  - tool and skill policy
  - result / error / evidence refs
  - execution env registry

Workspace / Evidence Plane
  - git status and diff
  - file viewer and precision file tools
  - captured observations
  - diagnostic-safe exports

Context Plane
  - session/task context assembly
  - active skills
  - runtime input facts
  - compact trace and recovery metadata
```

The Execution Plane should become reusable. Plato is the first client, but not
the only possible client.

## 4. Product 1.1 Work Streams

### 4.1 Workspace Trust And File Evidence

Status: baseline foundation implemented; follow-up hardening remains.

Responsibilities:

- expose git status and diff safely;
- expose text file viewing;
- support line-scoped read/search/replace/append tools;
- produce file summary and evidence refs;
- keep raw file content behind permission and redaction boundaries.

Primary docs:

- [Product 1.1 Workspace Inspection Milestone](../plans/feature/product-1-1-workspace-inspection-milestone.md)
- [Git, Diff, And File Viewer API Contract](../engineering/git-diff-file-viewer-api-contract.md)
- [Precision File Tools](../plans/feature/precision-file-tools.md)

### 4.2 Runtime Input And Contract Revision

Status: current Product 1.1 control-plane track.

Problem:

User text can mean different things:

- ask a question without mutating workspace state;
- provide guidance that changes execution context;
- issue a command that changes the Plan / TaskNode contract;
- answer an ASK or confirmation.

The UI should not force users to learn these categories up front. Product 1.1
should keep one primary input surface and let Runtime Input Router classify and
dispatch safely.

Responsibilities:

- deterministic routes for active ASK, confirmation, stop, retry, and selected
  task actions;
- read-only inquiry route that never mutates workspace state;
- command-backed guidance and Plan / TaskNode mutation;
- Activity / Conversation writes for user-visible traceability;
- explicit unsupported route outcomes.

Primary docs:

- [Runtime Input Model](plato-runtime-input-model.md)
- [Runtime Input And Contract Revision Program](../plans/feature/runtime-input-and-contract-revision-program.md)
- [Runtime Input Router Contract](../plans/feature/runtime-input-router-contract.md)
- [Contract Revision Command Skills](../plans/feature/contract-revision-command-skills.md)

### 4.3 Execution Plane Service And Task API

Status: planned Product 1.1 platform boundary.

Problem:

Current execution is useful beyond the Plato UI. External tools or vertical
apps may want to publish tasks, let an execution environment claim them, and
query result/evidence without adopting Plato's Session UI.

Decision:

Treat Execution Plane as a service-capable boundary. Start embedded and
in-process; design as if HTTP/RPC service extraction will happen later.

Responsibilities:

- accept typed `TaskRequest` objects;
- enforce requester, idempotency, capability, permission, and evidence policy;
- expose `TaskExecution`, `TaskEvent`, `TaskResult`, `TaskError`, and
  `EvidenceRef`;
- maintain local default `ExecutionEnv`;
- prepare claim / lease / heartbeat semantics;
- keep business-specific vertical schemas outside core.

Primary docs:

- [ADR-0020](../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md)
- [TaskBus Service And Multi-Execution-Env Memo](../architecture/taskbus-service-multi-execution-env.md)
- [Execution Plane Service And Task API Plan](../plans/feature/execution-plane-service-task-api.md)
- [Execution Plane Service And Task API Technical Design](../plans/feature/execution-plane-service-task-api-technical-design.zh-CN.md)

### 4.4 Context, Skills, MCP, And Computer Use

Status: mixed. Skill governance backend foundation exists; broader product
activation and MCP/computer-use remain future tracks.

Responsibilities:

- keep Agent lifecycle separate from Context lifecycle;
- let Context Manager assemble session/task/run context deterministically;
- activate skills as bounded context sources, not tool permission escalators;
- merge tool requirements with runtime policy;
- reserve MCP and computer-use support behind explicit capability, permission,
  evidence, and confirmation policy.

Primary docs:

- [Context Manager](../architecture/context-manager.md)
- [Product 1.1 Skill Governance](../plans/feature/product-1-1-skill-governance.md)
- [Skill Governance Technical Design](../plans/feature/product-1-1-skill-governance-technical-design.zh-CN.md)
- [Codex / Claude Skill Context Governance Research](../reference/codex-claude-skill-context-governance.md)
- [macOS Computer-Use Capability Package](../plans/feature/macos-computer-use-package.md)
- [macOS Computer-Use Package Technical Design](../plans/feature/macos-computer-use-package-technical-design.zh-CN.md)

### 4.5 Conversation, Activity, Outcome Review, And Audit

Status: Activity foundation exists; Outcome Review and richer Audit/evidence
flows remain follow-up polish and integration.

Responsibilities:

- treat Conversation / Activity as typed collaboration records, not raw LLM
  transcript display;
- expose Task outcome, result summary, file summary, errors, and evidence;
- support post-plan Outcome Review and follow-up planning;
- keep Audit as read-side trust surface.

Primary docs:

- [Session Content Model](plato-session-content-model.md)
- [Outcome Review Model](plato-outcome-review-model.md)
- [Session Conversation / Activity Timeline](../plans/feature/session-conversation-activity-timeline.md)
- [Audit Page Contract](../engineering/audit-page-contract.md)

## 5. Architecture Boundaries

### 5.1 Product Plane

Owns:

- Workspace / Session / Plan / TaskNode UX;
- runtime input interpretation;
- product state commands;
- user-facing status and recovery copy;
- Main Page, Audit Page, Settings, Diagnostics, and Outcome Review.

Does not own:

- low-level tool execution mechanics;
- execution environment claim/lease;
- external business workflow schemas;
- raw evidence payload exposure.

### 5.2 Execution Plane

Owns:

- task intake and idempotency;
- execution lifecycle state;
- Agent runtime dispatch;
- tool runtime and permission policy application;
- result/error/evidence refs;
- environment registry and future claim/lease.

Does not own:

- Plato-only Session semantics;
- user-facing screen composition;
- vertical CRM/ecommerce domain models;
- Audit record narration.

### 5.3 Context Plane

Owns:

- session/task/run context source ordering;
- context budget policy;
- skill context injection;
- trace metadata;
- restart and retry context recovery inputs.

Does not own:

- task lifecycle authority;
- tool permission grants;
- Product UI routing decisions.

### 5.4 Audit / Evidence Plane

Owns:

- safe evidence refs;
- audit record projection;
- hidden / permission-limited evidence semantics;
- diagnostic-safe export.

Does not own:

- execution dispatch;
- direct workspace mutation.

## 6. Core Contracts

Product 1.1 implementation should preserve these contract boundaries:

| Contract | Owner | Purpose |
|---|---|---|
| `MainPageSnapshot` / UI ViewModels | Product/UI backend | Render current product state. |
| Runtime Input request/result | Product Plane | Classify and dispatch user text. |
| Plan / TaskNode contract | Product Plane | Represent work contract and post-publish lifecycle. |
| `TaskRequest` / `TaskExecution` | Execution Plane | Service-level execution boundary. |
| `TaskEvent` / `TaskResult` / `TaskError` / `EvidenceRef` | Execution + Evidence Plane | Queryable execution trace and results. |
| Skill descriptor / activation / context source | Context Plane | Bounded skill context injection. |
| Audit snapshot/record/evidence | Audit Plane | Trust and review surface. |

### 6.1 Runtime Input Contract

Product 1.1 should keep one primary user input surface, but backend routing must
preserve distinct outcomes.

| Input Intent | Mutates Plan/Task? | Mutates Workspace? | Durable Record | Execution Target |
|---|---:|---:|---|---|
| ASK answer | maybe | no | ASK resolution + Activity | waiting Task / AgentLoop |
| Confirmation response | maybe | maybe after approval | confirmation resolution + Activity | TaskBus / AgentLoop |
| Read-only inquiry | no | no | inquiry Activity / answer record | Inquiry runtime |
| Guidance | no direct mutation | no direct mutation | guidance fact + Activity | Context Manager for current Session/Task |
| Command | yes | maybe through TaskBus | command result + Activity | Product command handler or TaskBus |
| Unsupported / ambiguous | no | no | rejected/needs-clarification result | Product UI recovery |

Routing rules:

1. Active ASK and confirmation affordances take precedence over free-form
   interpretation.
2. Read-only inquiry must never publish a Task, mutate Plan/TaskNode, or write
   files.
3. Guidance can change context, but it must not silently rewrite the work
   contract.
4. Workspace-changing commands must become auditable commands or Tasks.
5. Unsupported input must produce a visible recoverable outcome instead of being
   treated as chat.

### 6.2 Plan And TaskNode Contract

Plan and TaskNode remain Product Plane concepts. Execution Plane should not own
their user-facing meaning.

Minimum Product 1.1 fields:

| Object | Required Identity | Required Runtime Fields | Notes |
|---|---|---|---|
| Plan | `plan_id`, `session_id`, version | title, summary, lifecycle status, active task refs, result refs | One active Plan per Session by default. Follow-up Plans are new versions or new Plan records, not hidden chat turns. |
| TaskNode | `task_node_id`, `plan_id` | intent, instructions, acceptance criteria, execution status, result/error refs, file summary refs | TaskNode is the user-visible work contract. |
| Published Task | `task_id`, optional `task_node_id` | TaskBus lifecycle, attempts, dependencies, retry state | Execution state authority is TaskBus / Execution Plane. |
| Activity Item | `activity_id`, scope refs | type, timestamp, summary, safe refs | User-visible collaboration trace, not raw logs. |

State separation rules:

1. Plan lifecycle, TaskNode readiness, execution status, confirmation status,
   permission/action availability, and audit verdict stay separate.
2. A failed execution does not automatically mean the Plan is failed.
3. A completed TaskNode should point to result/error/evidence refs, not only a
   prose message.
4. Post-publish editing must be modeled as contract revision, not direct
   mutation of historical execution facts.

### 6.3 Execution Plane Task API Contract

Execution Plane should expose a service-level contract that is independent of
Plato Main Page composition.

Core DTOs:

| DTO | Purpose |
|---|---|
| `TaskRequest` | Typed task publication request from Plato or external clients. |
| `TaskExecution` | Current execution lifecycle and stable IDs. |
| `TaskEvent` | Queryable execution event stream. |
| `TaskResult` | Durable user-readable result summary and structured refs. |
| `TaskError` | Durable failure summary, retryability, and diagnostic-safe refs. |
| `EvidenceRef` | Safe pointer to file, diff, log, audit, or external evidence. |
| `ExecutionEnv` | Local or future remote execution environment capability record. |

First implementation rules:

1. Start embedded and in-process; sidecar HTTP is an adapter over the same
   service.
2. Use idempotency keys for publish/cancel/retry where repeated client requests
   are expected.
3. Capability matching must fail with structured errors, not fallback to an
   arbitrary Agent.
4. Local default `ExecutionEnv` is enough for Product 1.1 foundation.
5. Claim/lease/heartbeat can remain internal or planned until remote execution
   environments are introduced.
6. External vertical schemas must live outside the core Task API. For example,
   ecommerce outreach can publish a typed task, but CRM-specific entities are
   workflow-package or external-app data.

### 6.4 Workspace And Evidence Contract

Workspace-aware collaboration depends on deterministic evidence.

Minimum evidence sources:

- git status summary;
- changed file list;
- text file line-range reads;
- diff summaries;
- line-scoped edit evidence;
- execution result/error summary refs;
- Activity and Audit refs.

Rules:

1. Agent prose is not the authority for file changes.
2. File summaries must derive from observed facts or workspace inspection, not
   only LLM-generated text.
3. Large files, binary files, secrets, and permission-limited evidence must
   produce explicit partial/hidden states.
4. UI may display summaries, but detailed raw evidence must stay behind safe
   refs and permission checks.

### 6.5 Context, Skills, MCP, And Computer-Use Policy

Product 1.1 should treat context as a lifecycle separate from Agent instances.

Context lifecycle:

```text
Session context
  -> Plan context
  -> Task context
  -> Run context
  -> Inquiry context
```

Rules:

1. Agent lifecycle does not own context lifecycle.
2. Skill activation injects bounded context and policy metadata; it must not
   silently grant tools.
3. Tool permission is the intersection of system policy, workspace policy,
   skill requirements, Task policy, and user confirmation.
4. MCP and computer-use must declare capability, risk, evidence requirements,
   and confirmation policy before execution.
5. Credentialed desktop automation is not a default Product 1.1 capability; it
   requires a separate proof and stricter evidence capture.

### 6.6 UI And Product Surfaces

Product 1.1 frontend work should preserve Product 1.0 visual intent while
clarifying information architecture.

Required surfaces:

| Surface | Product 1.1 Responsibility |
|---|---|
| Main Page | Primary Session/Plan/Task collaboration surface. |
| Conversation / Activity | User-visible collaboration record and task activity timeline. |
| Plan card / overlay | Work contract, current progress, and task status. |
| Details panel | Selected Task/Plan/Result/ASK/Confirmation details. |
| Audit Page | Trust read-side for records/evidence. |
| Settings / Diagnostics | Runtime configuration, usage, logs, diagnostic bundle. |
| Outcome Review | Completed Plan acceptance, risks, follow-up planning. |

UI rules:

1. Do not expose raw LLM transcript as the primary product model.
2. Conversation should be typed collaboration content.
3. Plan and Task remain the contract layer.
4. File/diff/Audit can be linked or inspected, but they should not become the
   primary collaboration layer for ordinary users.

### 6.7 Storage, Restart, And Migration Strategy

Product 1.1 should prefer additive durable stores and compatibility adapters.

Storage requirements:

| Data | Durability Requirement |
|---|---|
| Plan / TaskNode | restart-safe active Plan and task contract |
| TaskBus lifecycle | restart-safe pending/running/done/failed/retry state |
| Result/Error summaries | durable refs for UI and Audit |
| Activity items | durable user-visible collaboration trace |
| Runtime input outcomes | durable enough to explain guidance/command/question effects |
| Skill activations | durable activation and trace metadata |
| Usage events | durable aggregated token usage |
| Evidence refs | durable safe references; raw evidence governed separately |

Migration strategy:

1. Keep legacy DraftTaskTree compatibility until Plan/TaskNode routes fully own
   frontend and backend projections.
2. Introduce Execution Plane as an additive service; do not replace Main Page
   runtime behavior in the first slice.
3. Prefer adapters that map existing TaskBus and Plan facts into new DTOs.
4. Remove old compatibility paths only after route, frontend, tests, and release
   notes prove the replacement.

## 7. Implementation Sequence

Product 1.1 should not attempt all directions at once. Recommended sequencing:

1. **Close Runtime Input Router command path.**
   Guidance and command-backed Plan/TaskNode mutation should be stable before
   the product expands broad execution entry points.

2. **Implement Execution Plane EP0-EP3.**
   Add service DTOs, embedded service, Plato compatibility path, and local
   sidecar shell without changing Main Page behavior.

3. **Add ExecutionEnv registry foundation.**
   Represent local default env and capability matching before remote workers.

4. **Harden Activity / Outcome Review.**
   Make Plan completion, result acceptance, follow-up plan creation, and
   evidence review coherent for real users.

5. **Productize skills and MCP incrementally.**
   Keep skills as context/policy first. Add MCP/computer-use only behind clear
   capability, permission, evidence, and confirmation gates. macOS
   computer-use should be packaged as a neutral LLM-free capability package and
   consumed by Plato through an adapter.

6. **Run one vertical proof.**
   Use a low-risk workflow such as email/browser draft assistance before
   WeChat or high-risk outbound automation.

## 8. Test And QA Strategy

### 8.1 Backend Contract Tests

- strict DTO validation;
- unknown-field rejection;
- idempotency replay/conflict;
- permission/capability mismatch;
- result/error/evidence query;
- Runtime Input Router route outcomes;
- skill activation and context budget traces.

### 8.2 Integration Tests

- Main Page closed loop still works after Execution Plane boundary insertion;
- `POST /tasks` local route can publish/query in dev/local mode;
- read-only inquiry does not mutate workspace state;
- command-backed Plan/TaskNode mutation emits Activity facts;
- result/evidence refs are stable across restart where applicable.

### 8.3 Manual / Product QA

- start Product 1.1 local app;
- create Plan;
- execute task;
- ask a question while preserving workspace;
- provide guidance while a task is running;
- inspect result/file/diff/evidence;
- accept outcome and start a follow-up plan.

## 9. Acceptance Criteria

Product 1.1 planning baseline is coherent when:

1. Product 1.1 scope is clear: workspace-aware collaboration plus
   service-capable execution.
2. Product 1.0 closed loop remains stable and is not reopened by platform work.
3. Runtime Input, Plan/TaskNode, Execution Plane, Context/Skills, and
   Audit/Evidence have separate owners.
4. Execution Plane can serve Plato first and external apps later without
   leaking Plato Session semantics into core DTOs.
5. Skills and MCP are treated as context/capability/policy problems before UI
   marketplace or broad routing.
6. Test strategy covers contract, integration, restart/retry, and user-path
   smoke.

## 10. Non-Goals

- No Product 1.1 UI redesign in this document.
- No public SaaS / multi-tenant auth design.
- No immediate remote worker implementation.
- No WeChat-first automation MVP.
- No ecommerce CRM replacement.
- No full custom Agent marketplace.
- No direct dependency on canonical Figma implementation.
- No broad Main Page rewrite solely for Product 1.1.

## 11. Open Decisions

1. Does Product 1.1 expose local external Task API preview, or keep it internal
   until EP0-EP3 prove stable?
2. Should external callers authenticate through local bearer token, workspace
   trust file, or sidecar-only origin policy first?
3. How should ASK/confirmation events be delivered to external clients:
   polling, SSE, webhook, or Product UI only?
4. Should context retry state be stored per Session, per Task, or both?
5. Which computer-use evidence is mandatory before Product 1.1 allows
   credentialed desktop automation?
6. Which first vertical proof best validates the Execution Plane without
   forcing a business-specific product fork?
