# Release Records

This directory records completed phases, milestones, and important feature slices.

Release records should answer:

- what shipped;
- which docs and code areas changed;
- what was validated;
- which follow-ups remain.

When a release closes or changes a known gap, update [Gap Registry](../gaps/)
alongside the release record.

## Index

| Release | Status | Summary |
|---|---:|---|
| [Product 1.1 Runtime Input Router Release Evidence](product-1-1-runtime-input-router-release-evidence.md) | done | Product 1.1 beta P0 evidence closure: Runtime Input Router, Contract Revision Command Skills, durable Conversation / Activity, Router Audit / Diagnostics, packaged app, and mounted `1.1-beta` installer smoke. |
| [Product 1.1 Web Retrieval Live Smoke](product-1-1-web-retrieval-live-smoke.md) | P1 runbook | Opt-in Tavily Search/Extract live smoke harness for beta release operators with a real API key. |
| [API Publish Server Transport](api-publish-server-transport.md) | done | Framework-neutral HTTP/RPC adapter for `DefaultApiTaskPublisher` routes and response envelopes. |
| [Configurable Logging System](configurable-logging-system.md) | done | Structured JSONL logging, session archives, profiles, same-process control API, and core object integrations. |
| [Publish Persistence Foundation](publish-persistence-foundation.md) | done | SQLite publish idempotency, audit, scheduler stores, service assembly, and deterministic idempotency hardening. |
| [TaskBus Execution Lifecycle](taskbus-execution-lifecycle.md) | done | Minimal published Task lifecycle: claim, running, complete, fail, skip, and persistent status projection. |
| [Task Publishers, Schedule, API, And Pipeline Expansion](task-publishers-schedule-api.md) | done | TaskBus-backed publishing, custom tree parsing, idempotent publish service, scheduler/API publisher adapters, and publish-time pipeline expansion. |
| [Collaborator Agent And Task Authoring](collaborator-agent-task-authoring.md) | done | RawTask feasibility, Authoring Commands, DraftTaskTree stores, Collaborator service, publish boundary, and UI/API adapter. |
| [LLM Provider Reliability](llm-provider-reliability.md) | done | Provider abstraction, retry, DeepSeek thinking, and OpenRouter routing. |
| [Local Sidecar API Shell](local-sidecar-api-shell.md) | done | Framework-neutral Plato UI HTTP/SSE transport, optional auth, and stdlib loopback sidecar binding. |
| [Fixed-Route Task Execution Bridge](fixed-route-task-execution-bridge.md) | done | Product 1.0 fixed-route execution path through TaskBus, resident Default Agent, background dispatch, durable result/error summaries, MessageStream bridge, Main Page result/file projection, and sidecar HTTP smoke. |
| [Local Computer-Use Tool Foundation](local-computer-use-tool-foundation.md) | done | Local `computer_use` tool contract, disabled/scripted backend, explicit sidecar enablement, local Task API to AgentLoop dispatch, TaskBus completion, and EventStream observation persistence. |
| [Context Manager 1.0](context-manager-1-0.md) | done | Product 1.0 deterministic execution context governance for fixed-route Default Agent LLM calls: v0 context schema, bounded facts/snippets, snapshots/traces, Default Agent integration, and AgentLoop per-call provider. |
| [Context Manager Cache-Aware Rendering](context-manager-cache-aware-rendering.md) | done | Product 1.0 Context Manager hardening: stable start context, append-only transcript reuse, bounded delta/checkpoint messages, interval checkpoint policy, and render metadata hooks. |
| [Cooperative Task Interruption](cooperative-task-interruption.md) | done | Product 1.0 stop intent, stopping projection, AgentLoop safe points, Context Manager interruption facts, and cancelled terminal failure outcomes. |
| [Main Page Frontend Runtime Integration](main-page-frontend-runtime-integration.md) | done | Accepted Main Page frontend/backend integration closure: session-centric runtime adapter, command lifecycle, event invalidation, command coverage, sidecar HTTP runtime, fixed-route execution projection, and deterministic result/file surfaces. |
| [Message, ASK, And Confirmation Backend](message-ask-confirmation-backend.md) | done | Durable execution ASK store, TaskBus `waiting_for_user`, ASK commands/projections, runtime `ask_user`, and Context Manager answered ASK facts. |
| [Phase 3 Interaction Layer through 3.8](phase-3-interaction-layer-through-3-8.md) | done | Session, risk/autonomy, messages, bus, wait, loop integration, LLM risk, derived session status. |
| [RawTask And DraftTaskTree Persistence](raw-task-draft-tree-persistence.md) | done | SQLite authoring persistence, active RawTask/DraftTaskTree recovery, publish identity alignment, and command/API idempotency for Product 1.0 authoring recovery. |
| [Task Domain and UI ViewModel Separation](task-domain-ui-model-separation.md) | done | Task domain/draft models, UI ViewModels, projection, command mapping, replay timeline, and UI API alignment. |
| [UI/backend Contract Baseline](ui-backend-contract-baseline.md) | done | Framework-neutral Plato UI contract package, mapping/query/command/event gateways, frontend type alignment, and shared JSON fixture parity. |
