# Feature Plans

Feature plans are scoped implementation packets for independent feature sessions.

| File | Feature |
|---|---|
| [centralized-runtime-configuration.md](centralized-runtime-configuration.md) | Centralized hierarchical runtime configuration with hot updates. |
| [collaborator-agent-task-authoring.md](collaborator-agent-task-authoring.md) | System Collaborator Agent and Task authoring tools. |
| [collaborator-workspace-informed-authoring.md](collaborator-workspace-informed-authoring.md) | Planned: bounded read-only Collaborator authoring loop with workspace read/query/search and shared AgentLoop profile contract. |
| [configurable-logging-system.md](configurable-logging-system.md) | Configurable layered logging system. |
| [cooperative-task-interruption.md](cooperative-task-interruption.md) | Done / accepted: Product 1.0 minimal interrupt intent, safe points, stopping projection, Context Manager interruption facts, and cancelled failure outcome. |
| [cooperative-task-interruption-technical-design.zh-CN.md](cooperative-task-interruption-technical-design.zh-CN.md) | Done / accepted 中文详细技术方案：TaskBus interrupt intent、AgentLoop safe points、Context Manager interruption facts、UI stopping projection 和 TaskBus terminal outcome。 |
| [diagnostic-bundle-export.md](diagnostic-bundle-export.md) | Accepted for Product 1.0 local unsigned RC: backend/HTTP/frontend diagnostic export, redacted bundle output, sidecar E2E, and mounted unsigned DMG smoke are in place. |
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
| [message-ask-confirmation-backend.md](message-ask-confirmation-backend.md) | Done / accepted for backend Product 1.0 closure: confirmation hardening, durable ASK store, TaskBus `waiting_for_user`, ASK commands/projections, runtime ASK creation, Context Manager ASK facts, and release docs are complete. |
| [message-ask-confirmation-backend-technical-design.zh-CN.md](message-ask-confirmation-backend-technical-design.zh-CN.md) | Done / accepted 中文详细技术方案：durable ASK store、TaskBus `waiting_for_user`、answer-before-resume、confirmation 幂等、runtime ASK creation、Context Manager ASK facts 和 C7 closure 已完成。 |
| [ask-domain-unification-batch-answer.md](ask-domain-unification-batch-answer.md) | Done on branch / accepted after PR merge: Product 1.0 ASK domain unification guidance, authoring batch answer backend support, and Main Page Authoring ASK projection/UI follow-up. |
| [ask-domain-unification-batch-answer-technical-design.zh-CN.md](ask-domain-unification-batch-answer-technical-design.zh-CN.md) | Done on branch / accepted after PR merge 中文详细技术方案：Authoring ASK 与 Execution ASK UI 语义统一、权威数据源分离、authoring batch answer 和 execution batch 预留。 |
| [ask-confirmation-frontend-integration.md](ask-confirmation-frontend-integration.md) | Done on branch / accepted after PR merge: Product 1.0 frontend implementation for Authoring ASK Work Area, Execution ASK Detail Panel, Confirmation Detail Panel, event/refetch alignment, and QA closure. |
| [audit-entry-closure-technical-slice.md](audit-entry-closure-technical-slice.md) | Validated: Product 1.0 Audit source orchestration through task interaction timelines without changing Audit contract shapes, with real sidecar and local RC smoke coverage. |
| [fixed-route-task-execution-bridge.md](fixed-route-task-execution-bridge.md) | In progress: Product 1.0 fixed-route bridge from TaskBus pending Tasks to Task-run Default Agent execution and complete/fail. |
| [fixed-route-task-execution-bridge-technical-design.zh-CN.md](fixed-route-task-execution-bridge-technical-design.zh-CN.md) | In progress 中文详细技术方案：Task-run Default Agent、TaskBus claim_next、complete/fail 和测试设计。 |
| [linear-authoring-retry-recovery.md](linear-authoring-retry-recovery.md) | Accepted for Product 1.0 local unsigned RC: TaskBus-controlled dependency execution provides the line-first execution closure; manual retry resets the same Task identity and preserves evidence. Stronger generated-line guarantees, stale-running edge policy, and richer retry attempt UI remain follow-up hardening. |
| [minimal-agent-assignment-semantics.md](minimal-agent-assignment-semantics.md) | Deferred: Product 1.1+ TaskBus-centered assignment facts, Router tick, Agent Manager tick, and stale pending sweep. |
| [minimal-agent-assignment-semantics-technical-design.zh-CN.md](minimal-agent-assignment-semantics-technical-design.zh-CN.md) | Deferred 中文详细技术方案：assignment 字段、TaskBus API、SQLite、Router、Agent Manager、projection 和测试设计。 |
| [frontend-api-mock-happy-path.md](frontend-api-mock-happy-path.md) | Deferred: in-memory `PlatoApi` happy path mock for Main/Audit frontend integration. |
| [frontend-api-mock-happy-path-technical-design.zh-CN.md](frontend-api-mock-happy-path-technical-design.zh-CN.md) | Deferred 中文详细技术方案：单 session happy path API mock、状态机、Main/Audit snapshot builders、事件/cursor 和测试设计。 |
| [packaging-electron-release-plan.md](packaging-electron-release-plan.md) | Accepted for Product 1.0 local unsigned RC: bundled Python behind the release-local launcher, release asset checker, unsigned DMG packaging, mounted installer smoke, and manual Finder launch are accepted. Signed/notarized distribution is deferred until Apple Developer credentials are available. |
| [pipeline-task-loading.md](pipeline-task-loading.md) | Pipeline task loading before/begin/after normal tasks. |
| [product-error-handling.md](product-error-handling.md) | Accepted for Product 1.0 local unsigned RC: taxonomy, recovery labels, backend mapping, Audit/Diagnostic refs, sidecar validation, and packaged smoke are in place. |
| [publish-persistence-foundation.md](publish-persistence-foundation.md) | Done: SQLite publish stores, service assembly, API integration coverage, and deterministic idempotency hardening. |
| [publish-persistence-foundation-technical-design.zh-CN.md](publish-persistence-foundation-technical-design.zh-CN.md) | 中文详细技术方案：发布持久化 SQLite schema、store、事务、错误处理和测试设计。 |
| [raw-task-draft-tree-persistence.md](raw-task-draft-tree-persistence.md) | Done: SQLite RawTask/DraftTaskTree persistence, active authoring state, publish identity alignment, and API command response idempotency for Product 1.0 authoring recovery. |
| [raw-task-draft-tree-persistence-technical-design.zh-CN.md](raw-task-draft-tree-persistence-technical-design.zh-CN.md) | Implemented 中文详细技术方案：RawTask/DraftTaskTree SQLite schema、store、active state、publish identity、authoring command idempotency 和 API command response idempotency。 |
| [result-exposure-surface.md](result-exposure-surface.md) | Accepted for Product 1.0 local unsigned RC: Main Page result/error/file summaries, Audit evidence paths, Diagnostic handoff, and packaged smoke are in place. |
| [result-packaging-agent-cards.md](result-packaging-agent-cards.md) | Result Packaging Agent and card-based result presentation. |
| [settings-first-run-readiness.md](settings-first-run-readiness.md) | Done: Product 1.0 Settings/first-run readiness contract for LLM config, logging profiles, and diagnostic export discovery. |
| [settings-first-run-frontend-completion.md](settings-first-run-frontend-completion.md) | Accepted: Product-complete Settings first-run frontend setup flow, including Main Page modal Settings presentation, save/recheck loop, diagnostics action, degraded warnings, Main Page Settings entry, and sidecar E2E/CI coverage. |
| [settings-first-run-frontend-completion-technical-design.md](settings-first-run-frontend-completion-technical-design.md) | Accepted technical design for the Settings first-run frontend completion slices, modal route/state model, API client contract, tests, visual acceptance, and E2E coverage. |
| [task-domain-ui-model-separation.md](task-domain-ui-model-separation.md) | Task domain model and UI ViewModel separation. |
| [task-publishers-schedule-api.md](task-publishers-schedule-api.md) | Done: TaskPublisher abstraction, scheduled publish, API publish, custom task trees, and publish-time pipeline expansion. |
| [ui-backend-contract-baseline.md](ui-backend-contract-baseline.md) | Done: split and harden Plato UI snapshot/query/command/event/error contracts before sidecar transport. |
| [ui-backend-contract-baseline-technical-design.zh-CN.md](ui-backend-contract-baseline-technical-design.zh-CN.md) | 中文详细技术方案：后端 UI contract 包、camelCase 序列化、gateway 协议、mapping、event/error 模型和测试设计。 |
| [workspace-entry-root-semantics.md](workspace-entry-root-semantics.md) | W1 implemented: Product 1.0 desktop Workspace Picker. W2 implemented: workspace-root-as-agent-cwd with `.taskweavn` normal tool protection. |
