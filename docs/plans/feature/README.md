# Feature Plans

Feature plans are scoped implementation packets for independent feature sessions.

| File | Feature |
|---|---|
| [centralized-runtime-configuration.md](centralized-runtime-configuration.md) | Centralized hierarchical runtime configuration with hot updates. |
| [collaborator-agent-task-authoring.md](collaborator-agent-task-authoring.md) | System Collaborator Agent and Task authoring tools. |
| [configurable-logging-system.md](configurable-logging-system.md) | Configurable layered logging system. |
| [cooperative-task-interruption.md](cooperative-task-interruption.md) | Planned: Product 1.0 minimal interrupt intent, safe points, stopping projection, and cancelled failure outcome. |
| [cooperative-task-interruption-technical-design.zh-CN.md](cooperative-task-interruption-technical-design.zh-CN.md) | Planned 中文详细技术方案：TaskBus interrupt intent、AgentLoop safe points、Context Manager interruption facts、UI stopping projection 和 TaskBus terminal outcome。 |
| [context-manager-1-0.md](context-manager-1-0.md) | Done: Product 1.0 deterministic execution context governance for the fixed-route Default Agent path. |
| [context-manager-1-0-technical-design.zh-CN.md](context-manager-1-0-technical-design.zh-CN.md) | Implemented 中文详细技术方案：Context Manager 1.0 schema、source adapters、policy、renderer、store、Default Agent 集成和 AgentLoop per-call seam。 |
| [context-manager-cache-aware-rendering.md](context-manager-cache-aware-rendering.md) | Done: Product 1.0 cache-aware append-only rendering hardening for Context Manager LLM calls. |
| [context-manager-cache-aware-rendering-technical-design.zh-CN.md](context-manager-cache-aware-rendering-technical-design.zh-CN.md) | Implemented 中文详细技术方案：stable start context、append-only transcript、context delta、checkpoint policy 和 AgentLoop persisted message seam。 |
| [llm-provider-retry-thinking.md](llm-provider-retry-thinking.md) | Done: LLM provider abstraction, retry, and DeepSeek thinking mode. |
| [local-sidecar-api-shell.md](local-sidecar-api-shell.md) | Done: local HTTP/SSE sidecar shell for Plato UI over the backend UI contract gateways. |
| [local-sidecar-api-shell-technical-design.zh-CN.md](local-sidecar-api-shell-technical-design.zh-CN.md) | 中文详细技术方案：Plato local sidecar transport、route mapping、SSE shell、local security 和 lifecycle。 |
| [main-page-real-backend-integration.md](main-page-real-backend-integration.md) | In progress: compose the local sidecar shell with real Main Page backend services and frontend HTTP/SSE runtime. |
| [main-page-real-backend-integration-technical-design.zh-CN.md](main-page-real-backend-integration-technical-design.zh-CN.md) | 中文详细技术方案：Main Page backend composition、sidecar app lifecycle、named SSE compatibility 和 dev entrypoint。 |
| [main-page-frontend-runtime-integration.md](main-page-frontend-runtime-integration.md) | Planned: converge Main Page from fixture-compatible prototype runtime to session snapshot / command response / UiEvent-driven backend facts. |
| [main-page-frontend-runtime-integration-technical-design.zh-CN.md](main-page-frontend-runtime-integration-technical-design.zh-CN.md) | 中文详细技术方案：Main Page adapter boundary、session-centric query、CommandResponse lifecycle、event router 和 resync loop guard。 |
| [message-ask-confirmation-backend.md](message-ask-confirmation-backend.md) | Planned: Product 1.0 backend closure for MessageStream, execution ASK, TaskBus `waiting_for_user`, and confirmation hardening. |
| [message-ask-confirmation-backend-technical-design.zh-CN.md](message-ask-confirmation-backend-technical-design.zh-CN.md) | Planned 中文详细技术方案：durable ASK store、TaskBus `waiting_for_user`、answer-before-resume、confirmation 幂等和语义修正。 |
| [fixed-route-task-execution-bridge.md](fixed-route-task-execution-bridge.md) | In progress: Product 1.0 fixed-route bridge from TaskBus pending Tasks to Task-run Default Agent execution and complete/fail. |
| [fixed-route-task-execution-bridge-technical-design.zh-CN.md](fixed-route-task-execution-bridge-technical-design.zh-CN.md) | In progress 中文详细技术方案：Task-run Default Agent、TaskBus claim_next、complete/fail 和测试设计。 |
| [linear-authoring-retry-recovery.md](linear-authoring-retry-recovery.md) | In progress: Product 1.0 default linear authoring shape, dependency-safe sequential execution, minimal manual retry, and retry evidence capture. |
| [minimal-agent-assignment-semantics.md](minimal-agent-assignment-semantics.md) | Deferred: Product 1.1+ TaskBus-centered assignment facts, Router tick, Agent Manager tick, and stale pending sweep. |
| [minimal-agent-assignment-semantics-technical-design.zh-CN.md](minimal-agent-assignment-semantics-technical-design.zh-CN.md) | Deferred 中文详细技术方案：assignment 字段、TaskBus API、SQLite、Router、Agent Manager、projection 和测试设计。 |
| [frontend-api-mock-happy-path.md](frontend-api-mock-happy-path.md) | Deferred: in-memory `PlatoApi` happy path mock for Main/Audit frontend integration. |
| [frontend-api-mock-happy-path-technical-design.zh-CN.md](frontend-api-mock-happy-path-technical-design.zh-CN.md) | Deferred 中文详细技术方案：单 session happy path API mock、状态机、Main/Audit snapshot builders、事件/cursor 和测试设计。 |
| [pipeline-task-loading.md](pipeline-task-loading.md) | Pipeline task loading before/begin/after normal tasks. |
| [publish-persistence-foundation.md](publish-persistence-foundation.md) | Done: SQLite publish stores, service assembly, API integration coverage, and deterministic idempotency hardening. |
| [publish-persistence-foundation-technical-design.zh-CN.md](publish-persistence-foundation-technical-design.zh-CN.md) | 中文详细技术方案：发布持久化 SQLite schema、store、事务、错误处理和测试设计。 |
| [raw-task-draft-tree-persistence.md](raw-task-draft-tree-persistence.md) | Done: SQLite RawTask/DraftTaskTree persistence, active authoring state, publish identity alignment, and API command response idempotency for Product 1.0 authoring recovery. |
| [raw-task-draft-tree-persistence-technical-design.zh-CN.md](raw-task-draft-tree-persistence-technical-design.zh-CN.md) | Implemented 中文详细技术方案：RawTask/DraftTaskTree SQLite schema、store、active state、publish identity、authoring command idempotency 和 API command response idempotency。 |
| [result-exposure-surface.md](result-exposure-surface.md) | Planned: Product 1.0 result, evidence, audit, and diagnostics exposure boundary for Main Page and Audit Page closure. |
| [result-packaging-agent-cards.md](result-packaging-agent-cards.md) | Result Packaging Agent and card-based result presentation. |
| [task-domain-ui-model-separation.md](task-domain-ui-model-separation.md) | Task domain model and UI ViewModel separation. |
| [task-publishers-schedule-api.md](task-publishers-schedule-api.md) | Done: TaskPublisher abstraction, scheduled publish, API publish, custom task trees, and publish-time pipeline expansion. |
| [ui-backend-contract-baseline.md](ui-backend-contract-baseline.md) | Done: split and harden Plato UI snapshot/query/command/event/error contracts before sidecar transport. |
| [ui-backend-contract-baseline-technical-design.zh-CN.md](ui-backend-contract-baseline-technical-design.zh-CN.md) | 中文详细技术方案：后端 UI contract 包、camelCase 序列化、gateway 协议、mapping、event/error 模型和测试设计。 |
