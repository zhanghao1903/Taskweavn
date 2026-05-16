# Architecture Docs

Architecture docs describe stable concepts, object lifecycles, system contracts, and long-term design direction.

## Core Principles

1. **User needs drive architecture/plan/feature decisions.**
2. **Architecture design drives plans and feature packages.**
3. **Plans drive implementation.**

These principles enforce one end-to-end attribution chain with two valid paths:

- `User Need -> Architecture -> Plan/Feature -> Implementation (code/tests/releases)`
- `User Need -> Plan/Feature -> Implementation (when architecture boundary is unchanged)`

Every important decision should be traceable back to concrete user problems, not assumption-led design.

## Core References

| File | Purpose |
|---|---|
| [reference.md](reference.md) | Current implementation-oriented architecture reference. |
| [overview.md](overview.md) | Task-first multi-agent architecture overview. |
| [authoring-domain.md](authoring-domain.md) | Authoring Domain boundary: RawTask, feasibility, draft Task Tree, and the bridge into Execution TaskBus. |
| [authoring-command-protocol.md](authoring-command-protocol.md) | Strongly typed Authoring Command Protocol for RawTask/DraftTaskTree system-state mutation. |
| [task.md](task.md) | Task domain model and lifecycle. |
| [tool-capability-layer.md](tool-capability-layer.md) | Tool pool, capability catalog, and capability-first planning boundary. |
| [workspace-communication-protocol.md](workspace-communication-protocol.md) | Higher-level system/workspace communication protocol; Tools become adapters over workspace operations. |
| [task-domain-ui-model-separation.md](task-domain-ui-model-separation.md) | Boundary between backend Task domain facts, UI ViewModels, local UI state, and replayable Task interactions. |
| [ui-backend-communication.md](ui-backend-communication.md) | UI/backend communication contract: Query, Command, Event, HTTP/SSE direction, consistency, and lifecycle. |
| [collaborator-agent-task-authoring.md](collaborator-agent-task-authoring.md) | System Collaborator Agent, Task authoring service, draft tree generation/refinement, validation, and publish boundary. |
| [bus.md](bus.md) | TaskBus v1 design. |
| [bus-v2.md](bus-v2.md) | TaskBus evolution notes. |
| [agent.md](agent.md) | Agent template/instance model. |
| [session.md](session.md) | Session architecture. |
| [interaction-layer.md](interaction-layer.md) | Phase 3 interaction layer technical design. |
| [llm-provider-reliability.md](llm-provider-reliability.md) | LLM provider abstraction, retry, DeepSeek thinking, and OpenRouter routing technical design. |
| [configurable-logging-system.md](configurable-logging-system.md) | Configurable structured logging, hot update, archive, and compatibility design. |
| [multi-agent-collaboration.md](multi-agent-collaboration.md) | Multi-agent collaboration architecture. |
| [multi-agent-collaboration_en.md](multi-agent-collaboration_en.md) | English version of the collaboration architecture. |
| [user/README.md](../user_model/README.md) | User modeling system: user needs/scenarios, do-or-not decisions, current vs future solution shape, and architecture mapping. |
| [review.md](review.md) | Architecture review and plan inputs. |

## Rule of Thumb

Put a document here when it defines a long-lived system boundary or mental model. Put implementation work packages under [../plans/](../plans/).
