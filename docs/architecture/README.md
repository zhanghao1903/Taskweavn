# Architecture Docs

> Status: active architecture fact baseline
> Last Updated: 2026-05-22

Architecture docs describe active system facts: object boundaries, lifecycles,
protocols, storage ownership, agent/task responsibilities, and long-term
technical constraints.

These documents are not historical reference material. They are required inputs
for technical design and implementation planning.

---

## 1. Must Read Before Technical Design

For any non-trivial feature plan or code implementation, read:

1. [reference.md](reference.md) — current implementation-oriented architecture reference.
2. [overview.md](overview.md) — Task-first multi-agent architecture overview.
3. [task.md](task.md) — Task domain model and lifecycle.
4. [authoring-domain.md](authoring-domain.md) — RawTask, feasibility, DraftTaskTree, and publish boundary.
5. [task-domain-ui-model-separation.md](task-domain-ui-model-separation.md) — backend facts, UI ViewModels, local UI state, replayable interactions.
6. [ui-backend-communication.md](ui-backend-communication.md) — Query / Command / Event boundary and HTTP/SSE direction.
7. [tool-capability-layer.md](tool-capability-layer.md) — tool pool, capability catalog, and capability-first planning boundary.
8. [workspace-communication-protocol.md](workspace-communication-protocol.md) — system/workspace communication protocol and tool adapter direction.

Feature-specific work should then read the relevant area documents below.

---

## 2. Architecture Fact Areas

| Area | Canonical Docs | Notes |
|---|---|---|
| Core agent loop and implemented substrate | [reference.md](reference.md), [interaction-layer.md](interaction-layer.md) | Action/Observation, EventStream, MessageStream, autonomy gate, wait coordination, loop integration. |
| Task domain and TaskBus | [task.md](task.md), [bus.md](bus.md), [bus-v2.md](bus-v2.md) | Task lifecycle, TaskBus authority, Routing Agent assignment, cooperative interruption, publish/dispatch direction. |
| Authoring domain | [authoring-domain.md](authoring-domain.md), [authoring-command-protocol.md](authoring-command-protocol.md), [collaborator-agent-task-authoring.md](collaborator-agent-task-authoring.md) | RawTask, feasibility, DraftTaskTree, Collaborator, Authoring Commands, publish boundary. |
| UI/backend boundary | [ui-backend-communication.md](ui-backend-communication.md), [task-domain-ui-model-separation.md](task-domain-ui-model-separation.md) | ViewModel projection, Query/Command/Event, frontend/backend contract direction. |
| Tool and workspace capability | [tool-capability-layer.md](tool-capability-layer.md), [workspace-communication-protocol.md](workspace-communication-protocol.md) | CapabilityCatalog, tool pools, system-state mutation, workspace operations. |
| Agent model | [agent.md](agent.md), [multi-agent-collaboration.md](multi-agent-collaboration.md), [multi-agent-collaboration_en.md](multi-agent-collaboration_en.md) | Agent templates, Routing Agent role, Execution Agent instances, future multi-agent collaboration direction. |
| Sessions | [session.md](session.md) | Session boundary, status, persistence, workspace relationship. |
| LLM providers | [llm-provider-reliability.md](llm-provider-reliability.md) | Provider abstraction, retry, DeepSeek thinking, OpenRouter routing. |
| Logging and observability | [configurable-logging-system.md](configurable-logging-system.md) | Structured logging, session archives, hot update, diagnostics substrate. |
| Architecture review | [review.md](review.md) | Review notes and plan inputs. |

---

## 3. Relationship To Other Docs

| Doc Type | Relationship |
|---|---|
| [Product docs](../product/) | Define user intent and UX expectations. Architecture turns that into system boundaries. |
| [Gap registry](../gaps/) | Lists missing capabilities and points to the architecture docs that constrain them. |
| [Plans](../plans/) | Explain how a selected gap will be implemented. Plans must cite relevant architecture docs. |
| [ADRs](../decisions/) | Record durable decisions when architecture changes or tradeoffs are expensive to reverse. |
| [Releases](../releases/) | Record what actually shipped and what architecture facts are now implemented. |

---

## 4. Rules

1. Do not start detailed technical design without reading the relevant active architecture docs.
2. If a plan needs a system boundary that architecture does not describe, update architecture first or create an ADR.
3. If implementation disproves an architecture assumption, update the architecture doc and release record.
4. Do not move active architecture facts to archive merely to tidy the tree.
5. Archive only generated exports, superseded experiments, or historical material that no longer defines current system facts.
