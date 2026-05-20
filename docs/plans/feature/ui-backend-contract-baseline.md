# Feature Plan: UI/backend Contract Baseline

> Status: in_progress
> Type: 后端主线 / UI contract foundation
> Last Updated: 2026-05-20
> Gap: [UI/backend contract baseline](../../gaps/README.md)
> Architecture: [UI And Backend Communication](../../architecture/ui-backend-communication.md), [Task Domain/UI Model Separation](../../architecture/task-domain-ui-model-separation.md), [Authoring Domain](../../architecture/authoring-domain.md), [Interaction Layer](../../architecture/interaction-layer.md)
> Product: [Plato UI API Contract](../../product/plato-ui-api-contract.md), [Plato Main Page UX Flow](../../product/plato-main-page-ux-flow.md), [Plato Frontend Technical Design](../../product/plato-frontend-technical-design.md)
> Technical Design: [中文详细技术方案](ui-backend-contract-baseline-technical-design.zh-CN.md)
> Release Record: TBD

---

## 1. Problem / Gap

Plato Main Page 前端已经有一版 API 类型、HTTP adapter 和事件订阅抽象；后端也已经有 Task ViewModel、TaskProjectionService、CollaboratorApiAdapter、TaskCommandService、MessageStream 和 TaskBus 基础。

但两边中间还缺少一层明确、稳定、可测试的 **UI/backend contract baseline**：

```text
Backend domain / stores / bus
  -> UI contract models
  -> Query / Command / Event / Error envelopes
  -> future UI Gateway
  -> future HTTP + SSE sidecar transport
  -> Plato frontend adapter
```

如果直接开始做 sidecar HTTP server，风险是：

- 前端 TypeScript 类型、后端 Pydantic 模型、产品 contract 文档三者漂移；
- 后端把内部领域对象直接暴露给 UI；
- `accepted` command、SSE event、snapshot query 的语义混在一起；
- 错误模型和 cursor/version 规则临时拼装，后续难以维护；
- Main Page 真实集成时无法判断问题属于 UI、transport、projection 还是 domain。

本计划先把 contract 层拆出来并硬化，再推进 sidecar API shell。

---

## 2. Architecture References Reviewed

| Document | Relevant Constraint |
|---|---|
| [UI And Backend Communication](../../architecture/ui-backend-communication.md) | Query / Command / Event 三分；Session 是主通信边界；API 返回 ViewModel；HTTP + SSE 是第一版方向。 |
| [Task Domain/UI Model Separation](../../architecture/task-domain-ui-model-separation.md) | UI 不消费裸 `TaskDomain` / `DraftTaskNode`；Task card/detail/timeline 由 projection 产生。 |
| [Authoring Domain](../../architecture/authoring-domain.md) | RawTask / DraftTaskTree 属于 authoring domain；Collaborator authoring 不直接进入执行 TaskBus。 |
| [Interaction Layer](../../architecture/interaction-layer.md) | Session Message Stream 是唯一消息事实源；Task message 是 session messages 的 task-scoped projection。 |
| [Plato UI API Contract](../../product/plato-ui-api-contract.md) | Main Page 需要 `MainPageSnapshot`、命令响应、SSE event、错误可见性。 |
| [UI API Interfaces Archive](../ui/ui-api-interfaces.md) | 子 UI 文档共用的接口需求和 TaskRef 规则。 |

---

## 3. Current Code Facts

| Area | Existing implementation | Gap |
|---|---|---|
| Frontend contract types | `frontend/src/shared/api/types.ts` defines `QueryResponse`, `CommandResponse`, `MainPageSnapshot`, `UiEvent`. | Backend has no matching Pydantic contract package. |
| Frontend HTTP adapter | `frontend/src/shared/api/platoApi.ts` uses documented `/api/v1/sessions/...` paths and SSE URL shape. | No backend gateway or transport exists for these paths. |
| Backend read models | `taskweavn.task.views` defines server-core task card/detail/message/confirmation/file/summary projections. | These are useful and should remain internal read models; they are not transport-facing, and names/shapes differ from frontend contract. |
| Backend projection service | `DefaultTaskProjectionService` combines task stores, draft store, message stream, file summaries, result summaries. | No `MainPageSnapshot` assembler or UI query gateway. |
| Backend command services | `DefaultTaskCommandService` and `DefaultCollaboratorApiAdapter` return `CommandResult`. | No command envelope, refresh hint, request id, error envelope, or endpoint-facing payload models. |
| Backend server package | `taskweavn.server.api_publish` provides framework-neutral API publish transport. | No Plato UI contract/gateway package. |
| Events | Frontend expects `UiEvent`; backend has MessageStream/EventStream/TaskBus facts. | No event projection contract or cursor model. |

---

## 4. Goals

This work should create a stable backend contract baseline for Plato UI without starting a concrete web server.

Deliverables:

1. Python Pydantic contract package under `taskweavn.server.ui_contract`.
2. Split contract groups:
   - snapshot/query models;
   - command request/response models;
   - event envelope models;
   - error models;
   - shared ID/view models.
3. Deterministic JSON serialization with frontend-compatible camelCase keys.
4. Backend contract tests for frozen/forbid-extra behavior, envelope invariants, event/error enums, and snapshot JSON shape.
5. Mapping rules from existing backend projection models to transport-facing UI contract models.
6. A clear implementation path for Query Gateway, Command Gateway, Event Projection, then HTTP/SSE transport.
7. Documentation updates tying the gap to this plan and technical design.

---

## 5. Non-goals

- 不实现 FastAPI / Starlette / ASGI server。
- 不实现 Electron sidecar process management。
- 不实现真实 SSE retention store。
- 不让 UI 直接连接 TaskBus 或 SQLite。
- 不实现 TaskBus `claim/complete/fail` 执行生命周期。
- 不完成 Main Page real backend integration。
- 不一次性实现所有 query/command payload 的最终字段细节。
- 不引入 OpenAPI generation 或 schema codegen；可以后续再做。
- 不解决多用户权限、presence、多人协作或 WebSocket。

---

## 6. Proposed Design

### 6.1 Contract package comes before transport

先新增 framework-neutral contract 包：

```text
src/taskweavn/server/ui_contract/
  __init__.py
  base.py
  errors.py
  envelopes.py
  view_models.py
  snapshots.py
  commands.py
  events.py
  gateways.py
  mapping.py
```

第一片只要求模型和测试稳定，不要求每个文件一次性都实现完整逻辑。

### 6.2 Backend internal models are not UI contract models

`taskweavn.task.views` 继续作为 server-core projection models。

`taskweavn.server.ui_contract` 是 transport-facing models。

两者通过 adapter/mapping 转换：

```text
TaskDomain / DraftTaskNode / AgentMessage
  -> taskweavn.task.views
  -> taskweavn.server.ui_contract
  -> JSON camelCase
  -> frontend/src/shared/api/types.ts
```

这样后端可以继续演化 domain/projection，而 UI 只看稳定 contract。

Do not delete or mutate `taskweavn.task.views` into transport models. Query Gateway should call `TaskProjectionService`, then use `server.ui_contract.mapping` as the single conversion boundary.

### 6.3 Snapshot is the first query boundary

`MainPageSnapshot` 是第一版最重要的 query：

- 前端初始化依赖它；
- SSE resync 依赖它；
- Main Page mock/live adapter 已围绕它建立；
- 它能暴露 contract drift 最快。

因此第一轮 Query Gateway 不追求所有 query path，而是优先实现：

```text
get_session_snapshot(session_id) -> QueryResponse[MainPageSnapshot]
```

局部 query 之后再补。

### 6.4 Commands return accepted/rejected plus refresh hint

Command 不承诺返回最新完整视图。

```text
UI command
  -> CommandResponse(ok, result, error, refresh)
  -> UI pending state
  -> event or snapshot query reflects final state
```

第一版 `RefreshHint` 应能告诉 UI：

- 是否等待事件；
- 建议重查哪些 query；
- 影响哪些 `TaskRef`；
- 影响哪些粗粒度 UI scope，例如 session、task tree、task subtree、messages、confirmations。

`CommandResult` 需要同时支持真实 Task 和 authoring-only 对象：

- `affectedTaskRefs` 只承载 draft/published Task；
- RawTask、RawTaskAsk、draft tree、draft subtree 等通过 `ObjectRef` / `AffectedObjectRef` 表达；
- `debugRefs` 只承载追踪 id，不作为自由业务 metadata 使用。

### 6.5 Events are patch hints, not full ViewModels

`UiEvent` 第一版只做 coarse-grained invalidation / patch hint：

- `task.tree.changed`
- `task.node.changed`
- `message.appended`
- `confirmation.created`
- `confirmation.resolved`
- `session.resync_required`
- `command.completed`
- `command.failed`

完整数据通过 query 获取，不塞进 event payload。

---

## 7. Implementation Slices

### Slice 1 — Contract Models

Output:

- `ApiError`
- `QueryResponse[T]`
- `CommandRequest[T]`
- `CommandResponse`
- `RefreshHint`
- `ObjectRef`
- `AffectedObjectRef`
- `AffectedScope`
- `UiEvent`
- `EventCursor`
- `MainPageSnapshot`
- shared ViewModels matching frontend baseline.

Acceptance:

- Pydantic models are frozen and reject unknown fields.
- JSON output uses camelCase.
- Python snapshot JSON matches the frontend contract shape.
- Error/event codes are enum-checked.
- Command result can reference non-Task authoring objects without overloading `TaskRef`.
- No HTTP server needed.

### Slice 2 — Contract Mapping Adapters

Output:

- map `taskweavn.task.views.TaskTreeView` to contract `TaskTreeView`;
- map `SessionMessageView` / `ConfirmationActionView` / file/result summaries;
- handle `TaskRef` and TaskNode id compatibility;
- add golden snapshot fixture tests.

Acceptance:

- Existing server-core projection can produce a contract snapshot fragment.
- Mapping code is deterministic and covered by tests.
- Parent/child file summary semantics are preserved.

### Slice 3 — Query Gateway Baseline

Output:

```python
class UiQueryGateway(Protocol):
    def get_session_snapshot(self, session_id: str) -> QueryResponse[MainPageSnapshot]: ...
```

First implementation can use:

- `TaskProjectionService`;
- `MessageStream`;
- lightweight static/default project/workflow provider;
- optional result/file/audit providers.

Acceptance:

- `get_session_snapshot` works for empty session, draft tree session, pending confirmation session, and completed result session.
- Errors return `QueryResponse(ok=False, error=...)` instead of leaking exceptions.

### Slice 4 — Command Gateway Baseline

Output:

```python
class UiCommandGateway(Protocol):
    def append_session_input(...): ...
    def generate_task_tree(...): ...
    def append_task_input(...): ...
    def update_task_node(...): ...
    def resolve_confirmation(...): ...
    def publish_task_tree(...): ...
```

Acceptance:

- Existing `DefaultCollaboratorApiAdapter` and `DefaultTaskCommandService` are wrapped, not bypassed.
- `CommandResult` is wrapped into `CommandResponse`.
- Rejected command maps to stable `ApiError(code="command_rejected")`.
- `expectedVersion` and `idempotencyKey` reach backend services where supported.
- `TaskRefResolver` owns `taskNodeId -> TaskRef` resolution; command handlers do not guess draft/published identity.

### Slice 5 — Event Projection Baseline

Output:

- event envelope and cursor model;
- deterministic event constructors from message/confirmation/task changes;
- no SSE server yet.

Acceptance:

- `message.appended`, `confirmation.created`, `confirmation.resolved`, `task.tree.changed`, `session.resync_required` can be constructed and serialized.
- Event payload stays thin and query-driven.

### Slice 6 — Contract Parity And Documentation

Output:

- backend contract tests;
- frontend type alignment notes;
- optional shared JSON fixture consumed by frontend tests later;
- update gap/release docs when implemented.

Acceptance:

- Backend and frontend field names do not drift.
- `docs/product/plato-ui-api-contract.md` remains consistent with implementation.

---

## 8. Frontend Work

Frontend already has a useful baseline. This plan does not require immediate frontend implementation, but it should produce contract artifacts that frontend can consume later.

Expected later frontend follow-up:

- add tests that load backend-produced snapshot fixtures;
- keep `permission_denied` aligned between backend and frontend error unions;
- use `appendSessionInput(mode="generate_task_tree")` for the Main Page natural-language flow; reserve independent `generateTaskTree` for future specific workflows / ready RawTask continuation;
- keep `selectedTaskNodeId`, panel mode, input draft, expanded nodes in local UI state.

---

## 9. Backend Work

Backend work should proceed in this order:

1. contract models;
2. mapping adapters;
3. snapshot query gateway;
4. command gateway;
5. event projection constructors;
6. framework-neutral transport only in a later plan or later slice.

The first implementation PR should avoid HTTP/SSE. It should prove the boundary in pure Python tests.

---

## 10. Contract / API Changes

The contract should align with the current documented frontend paths, but this plan does not implement routes yet:

```text
GET  /api/v1/sessions/{sessionId}/snapshot
POST /api/v1/sessions/{sessionId}/input
POST /api/v1/sessions/{sessionId}/task-tree/generate
PATCH /api/v1/sessions/{sessionId}/tasks/{taskNodeId}
POST /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/input
POST /api/v1/sessions/{sessionId}/task-tree/publish
POST /api/v1/sessions/{sessionId}/confirmations/{confirmationId}/respond
GET  /api/v1/sessions/{sessionId}/events?cursor=...
```

The important first step is the model and semantic contract, not the HTTP router.

---

## 11. Tests And Validation

Backend tests should cover:

- model validation and unknown-field rejection;
- frozen behavior;
- camelCase JSON output;
- query response success/error envelopes;
- command response accepted/rejected envelopes;
- event type validation;
- snapshot serialization;
- mapping from server-core projection models;
- no raw domain object leakage in contract JSON.

Frontend tests should later cover:

- TypeScript adapter can consume backend-produced fixture JSON;
- snapshot loading;
- command pending/rejected behavior;
- event resync behavior.

---

## 12. Risks And Open Questions

| Topic | Risk | Plan Handling |
|---|---|---|
| `generateTaskTree(prompt)` vs RawTask flow | Frontend command shape is simpler than backend authoring flow. | Technical design defines a gateway rule and uses `ObjectRef` / `debugRefs` for RawTask handoff. |
| Parent-node edits may invalidate descendants | Precise descendant patching may be brittle and expensive for LLM. | Technical design reserves `replace_subtree` / `replace_children`; UI refreshes by `AffectedScope`. |
| camelCase vs snake_case | Python and TS can drift silently. | Contract models must serialize with aliases and tests must assert JSON keys. |
| `TaskRef` vs `taskNodeId` | Draft and published tasks need stable identity without confusing UI. | Contract keeps both compatibility `taskNodeId` and extensible `taskRef`. |
| Event retention | SSE replay store not designed yet. | Baseline only defines event envelope/cursor, not retention. |
| Error taxonomy | Product and architecture docs differ slightly. | Technical design chooses a canonical first-version enum. |
| Project/Workflow facts | Backend currently focuses on session/task. | Snapshot gateway can use static/default providers until product navigation matures. |

---

## 13. Acceptance Criteria

This plan is ready for implementation when:

- the technical design is reviewed;
- the gap registry points to this plan;
- first implementation slice is clearly limited to contract models and tests;
- sidecar API shell remains a follow-up, not hidden scope creep.

Current implementation:

- Slice 1 contract models and tests are implemented.
- Slice 2 mapping adapters are implemented with deterministic server-core projection -> UI contract pure functions for Task tree, Task card, message, confirmation, file summary, and result card fragments.
- Slice 3 Query Gateway baseline has started with framework-neutral `DefaultUiQueryGateway.get_session_snapshot`.
- Query Gateway composes `SessionReader`, `TaskProjectionService`, static Project/Workflow providers, and mapping adapters. It does not reimplement projection logic and does not introduce HTTP/SSE.
- Slice 4 Command Gateway baseline has started with framework-neutral `DefaultUiCommandGateway` wrappers for session input, generate tree, task input, node update, publish tree, and resolve confirmation.
- Slice 5 Event Projection baseline has started with pure `UiEvent` constructors for session status, resync, task tree/node changes, message append, confirmation lifecycle, result/file/audit updates, and command completion/failure.
- Event projection remains framework-neutral: no SSE server, no durable event replay store, and no UI state reads.

The gap is closed for the current roadmap when:

- backend has stable UI contract models;
- snapshot/query/command/event/error contracts are covered by tests;
- frontend contract types are aligned or documented with exact deltas;
- a release record documents what shipped and which follow-ups remain.

---

## 14. Completion Updates

When implementation completes:

1. mark this plan `done`;
2. update [Gap Registry](../../gaps/README.md);
3. add a release record under `docs/releases/`;
4. update [Plato UI API Contract](../../product/plato-ui-api-contract.md) if fields changed;
5. update [UI And Backend Communication](../../architecture/ui-backend-communication.md) if the boundary changed;
6. update frontend API docs/tests if TypeScript types changed.
