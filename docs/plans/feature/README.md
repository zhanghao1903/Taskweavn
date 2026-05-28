# Feature Plans

Feature plans are scoped implementation packets for independent feature sessions.

| File | Feature |
|---|---|
| [centralized-runtime-configuration.md](centralized-runtime-configuration.md) | Centralized hierarchical runtime configuration with hot updates. |
| [collaborator-agent-task-authoring.md](collaborator-agent-task-authoring.md) | System Collaborator Agent and Task authoring tools. |
| [configurable-logging-system.md](configurable-logging-system.md) | Configurable layered logging system. |
| [llm-provider-retry-thinking.md](llm-provider-retry-thinking.md) | Done: LLM provider abstraction, retry, and DeepSeek thinking mode. |
| [local-sidecar-api-shell.md](local-sidecar-api-shell.md) | Done: local HTTP/SSE sidecar shell for Plato UI over the backend UI contract gateways. |
| [local-sidecar-api-shell-technical-design.zh-CN.md](local-sidecar-api-shell-technical-design.zh-CN.md) | 中文详细技术方案：Plato local sidecar transport、route mapping、SSE shell、local security 和 lifecycle。 |
| [main-page-real-backend-integration.md](main-page-real-backend-integration.md) | In progress: compose the local sidecar shell with real Main Page backend services and frontend HTTP/SSE runtime. |
| [main-page-real-backend-integration-technical-design.zh-CN.md](main-page-real-backend-integration-technical-design.zh-CN.md) | 中文详细技术方案：Main Page backend composition、sidecar app lifecycle、named SSE compatibility 和 dev entrypoint。 |
| [main-page-frontend-runtime-integration.md](main-page-frontend-runtime-integration.md) | Planned: converge Main Page from fixture-compatible prototype runtime to session snapshot / command response / UiEvent-driven backend facts. |
| [main-page-frontend-runtime-integration-technical-design.zh-CN.md](main-page-frontend-runtime-integration-technical-design.zh-CN.md) | 中文详细技术方案：Main Page adapter boundary、session-centric query、CommandResponse lifecycle、event router 和 resync loop guard。 |
| [minimal-agent-assignment-semantics.md](minimal-agent-assignment-semantics.md) | Planned: TaskBus-centered assignment facts, Router tick, Agent Manager tick, and stale pending sweep. |
| [minimal-agent-assignment-semantics-technical-design.zh-CN.md](minimal-agent-assignment-semantics-technical-design.zh-CN.md) | 中文详细技术方案：assignment 字段、TaskBus API、SQLite、Router、Agent Manager、projection 和测试设计。 |
| [pipeline-task-loading.md](pipeline-task-loading.md) | Pipeline task loading before/begin/after normal tasks. |
| [publish-persistence-foundation.md](publish-persistence-foundation.md) | Done: SQLite publish stores, service assembly, API integration coverage, and deterministic idempotency hardening. |
| [publish-persistence-foundation-technical-design.zh-CN.md](publish-persistence-foundation-technical-design.zh-CN.md) | 中文详细技术方案：发布持久化 SQLite schema、store、事务、错误处理和测试设计。 |
| [result-packaging-agent-cards.md](result-packaging-agent-cards.md) | Result Packaging Agent and card-based result presentation. |
| [task-domain-ui-model-separation.md](task-domain-ui-model-separation.md) | Task domain model and UI ViewModel separation. |
| [task-publishers-schedule-api.md](task-publishers-schedule-api.md) | Done: TaskPublisher abstraction, scheduled publish, API publish, custom task trees, and publish-time pipeline expansion. |
| [ui-backend-contract-baseline.md](ui-backend-contract-baseline.md) | Done: split and harden Plato UI snapshot/query/command/event/error contracts before sidecar transport. |
| [ui-backend-contract-baseline-technical-design.zh-CN.md](ui-backend-contract-baseline-technical-design.zh-CN.md) | 中文详细技术方案：后端 UI contract 包、camelCase 序列化、gateway 协议、mapping、event/error 模型和测试设计。 |
