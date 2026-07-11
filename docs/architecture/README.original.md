# Architecture Docs

> Status: active architecture fact baseline
> Last Updated: 2026-06-24

Architecture docs describe active system facts: object boundaries, lifecycles,
protocols, storage ownership, agent/task responsibilities, and long-term
technical constraints.

Most files in this directory are required inputs for technical design and
implementation planning. A few older files are retained as historical substrate
or exploratory extension notes. Their status is called out explicitly below so a
future plan does not accidentally treat an old Product 1.0 baseline or a future
Product 1.1+ memo as current implementation fact.

---

## 1. Must Read Before Technical Design

For any non-trivial feature plan or code implementation, read:

1. [overview.md](overview.md) — Product 1.1 local runtime overview and current architecture map.
2. [reference.md](reference.md) — core substrate implementation reference; use overview and release docs for later Product 1.0 / Product 1.1 facts.
3. [contract-revision-and-execution-loops.md](contract-revision-and-execution-loops.md) — core boundary between contract revision and workspace execution.
4. [task.md](task.md) — Task domain model and lifecycle.
5. [authoring-domain.md](authoring-domain.md) — RawTask, feasibility, ASK, DraftTaskTree, and publish boundary.
6. [authoring-command-protocol.md](authoring-command-protocol.md) — command-first mutation boundary for RawTask and DraftTaskTree authoring.
7. [task-domain-ui-model-separation.md](task-domain-ui-model-separation.md) — backend facts, UI ViewModels, local UI state, replayable interactions.
8. [ui-backend-communication.md](ui-backend-communication.md) — Query / Command / Event boundary and HTTP/SSE direction.
9. [agent.md](agent.md) — current Agent boundary, Agent LLM resolver, and deferred Agent Manager/routing model.
10. [context-manager.md](context-manager.md) — execution context governance, current deterministic context assembly, and Product 1.1 extension boundary.
11. [tool-capability-layer.md](tool-capability-layer.md) — tool pool, capability catalog, precision file tools, web retrieval, and capability-first planning boundary.
12. [workspace-communication-protocol.md](workspace-communication-protocol.md) — current workspace inspection / precision tool reality and future workspace operation protocol.
13. [llm-provider-reliability.md](llm-provider-reliability.md) and [configurable-logging-system.md](configurable-logging-system.md) — LLM provider, Agent LLM logging, and diagnostics boundaries.

Feature-specific work should then read the relevant area documents below.

---

## 2. Product 1.1 Alignment Matrix

| Doc | Current Role | Product 1.1 Alignment |
|---|---|---|
| [overview.md](overview.md) | Current architecture map | Canonical Product 1.1 local runtime overview. |
| [contract-revision-and-execution-loops.md](contract-revision-and-execution-loops.md) | Current boundary | Runtime Input Router, Read-only Inquiry, Contract Revision commands, and execution loop separation. |
| [ui-backend-communication.md](ui-backend-communication.md) | Current boundary | Main Page uses Router-first input, durable Conversation / Activity, Audit, Diagnostics, workspace inspection routes, and sidecar HTTP/SSE. |
| [task-domain-ui-model-separation.md](task-domain-ui-model-separation.md) | Current boundary | Domain facts stay backend-owned; Activity and ViewModels are projections. |
| [authoring-domain.md](authoring-domain.md) | Current domain baseline | RawTask/DraftTaskTree/ASK/publish still apply; Product 1.1 routes authoring changes through Runtime Input and command services. |
| [authoring-command-protocol.md](authoring-command-protocol.md) | Current command boundary | Command-first mutation remains required for authoring and contract revision. |
| [task.md](task.md) | Current Task domain | Fixed-route execution, `waiting_for_user`, retry/skip/interrupt, token/result evidence, and future assignment fields are distinguished. |
| [bus.md](bus.md) | Current TaskBus baseline | TaskBus remains execution-state authority; dynamic assignment remains deferred. |
| [session.md](session.md) | Current Session boundary | Session owns conversation/activity, active work, audit, settings-derived runtime, and workspace-root relationship. |
| [agent.md](agent.md) | Current Agent boundary plus extensions | Product 1.1 adds Agent LLM resolver and Router/read-only roles; full Agent Manager/dynamic execution assignment remains deferred. |
| [context-manager.md](context-manager.md) | Current context boundary plus extensions | Deterministic execution context remains baseline; Product 1.1 adds Router/read-only/workspace-inspection context around it. |
| [llm-provider-reliability.md](llm-provider-reliability.md) | Current LLM provider boundary | Global Settings, Agent LLM profiles, Router/read-only LLM roles, LLM input/output logs, and provider diagnostics are current. |
| [configurable-logging-system.md](configurable-logging-system.md) | Current observability boundary | Structured logs, session archives, split LLM input/output vs metadata logs, diagnostics export. |
| [tool-capability-layer.md](tool-capability-layer.md) | Current capability boundary plus extensions | Precision file tools and web search/fetch are current Product 1.1 capabilities; richer capability catalogs remain extension work. |
| [workspace-communication-protocol.md](workspace-communication-protocol.md) | Planning boundary with current slices | Full protocol is not implemented; workspace inspection and precision file tools are implemented slices. |
| [taskbus-service-multi-execution-env.md](taskbus-service-multi-execution-env.md) | Exploratory Product 1.1+ / 1.2 direction | Execution Plane / Task API service direction; not the default Product 1.1 local loop. |
| [bus-v2.md](bus-v2.md) | Exploratory future direction | Multi-agent scheduling and LLM scheduler ideas; not current implementation fact. |
| [reference.md](reference.md), [interaction-layer.md](interaction-layer.md), [multi-agent-collaboration.md](multi-agent-collaboration.md), [multi-agent-collaboration_en.md](multi-agent-collaboration_en.md), [review.md](review.md) | Historical substrate / review input | Useful for design lineage; use current docs above for Product 1.1 behavior. |

---

## 3. Architecture Fact Areas

| Area | Canonical Docs | Notes |
|---|---|---|
| Product 1.1 runtime loop | [overview.md](overview.md), [contract-revision-and-execution-loops.md](contract-revision-and-execution-loops.md), [ui-backend-communication.md](ui-backend-communication.md) | Runtime Input Router, read-only inquiry, command-backed contract revision, execution handoff, durable Conversation / Activity, Audit, Diagnostics. |
| Task domain and TaskBus | [task.md](task.md), [bus.md](bus.md) | Task lifecycle, TaskBus authority, `waiting_for_user` ASK blocking point, retry/skip, cooperative interruption, fixed-route execution. |
| Authoring domain | [authoring-domain.md](authoring-domain.md), [authoring-command-protocol.md](authoring-command-protocol.md), [collaborator-agent-task-authoring.md](collaborator-agent-task-authoring.md) | RawTask, feasibility, authoring ASK, DraftTaskTree, Collaborator, Authoring Commands, publish boundary. |
| UI/backend boundary | [ui-backend-communication.md](ui-backend-communication.md), [task-domain-ui-model-separation.md](task-domain-ui-model-separation.md) | Main Page snapshot, Session conversation, Query/Command/Event, ASK/confirmation, ViewModel projection, workspace inspection links. |
| Tool, workspace, and retrieval capability | [tool-capability-layer.md](tool-capability-layer.md), [workspace-communication-protocol.md](workspace-communication-protocol.md) | Precision file tools, workspace inspection, CapabilityCatalog direction, `web_search`, `web_fetch`, workspace operation policy. |
| Agent and LLM model | [agent.md](agent.md), [llm-provider-reliability.md](llm-provider-reliability.md) | Agent templates, task-scoped runs, Router/read-only roles, Agent LLM profiles, provider reliability, future Agent Manager. |
| Execution context governance | [context-manager.md](context-manager.md) | Context Manager boundary, deterministic execution context, Router/read-only/workspace-inspection context extension points. |
| Sessions and local runtime | [session.md](session.md), [configurable-logging-system.md](configurable-logging-system.md) | Session boundary, sidecar runtime, settings, persistence, logs, diagnostics. |
| Future execution plane | [taskbus-service-multi-execution-env.md](taskbus-service-multi-execution-env.md) | Execution Plane / Task API boundary and multi-environment direction. |
| Historical substrate and review | [reference.md](reference.md), [interaction-layer.md](interaction-layer.md), [multi-agent-collaboration.md](multi-agent-collaboration.md), [multi-agent-collaboration_en.md](multi-agent-collaboration_en.md), [review.md](review.md) | Design lineage and review input, not the source of Product 1.1 truth. |

---

## 4. Relationship To Other Docs

| Doc Type | Relationship |
|---|---|
| [Product docs](../product/) | Define user intent and UX expectations. Architecture turns that into system boundaries. |
| [Gap registry](../gaps/) | Lists missing capabilities and points to the architecture docs that constrain them. |
| [Plans](../plans/) | Explain how a selected gap will be implemented. Plans must cite relevant architecture docs. |
| [ADRs](../decisions/) | Record durable decisions when architecture changes or tradeoffs are expensive to reverse. |
| [Releases](../releases/) | Record what actually shipped and what architecture facts are now implemented. |

---

## 5. Rules

1. Do not start detailed technical design without reading the relevant active architecture docs.
2. If a plan needs a system boundary that architecture does not describe, update architecture first or create an ADR.
3. If implementation disproves an architecture assumption, update the architecture doc and release record.
4. Do not move active architecture facts to archive merely to tidy the tree.
5. Archive only generated exports, superseded experiments, or historical material that no longer defines current system facts.
