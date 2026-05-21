# Main Page Real Backend Integration 技术设计

> Status: in_progress
> Last Updated: 2026-05-21
> Feature Plan: [Main Page Real Backend Integration](main-page-real-backend-integration.md)
> Frontend Runtime Subplan: [Main Page Frontend Runtime Integration](main-page-frontend-runtime-integration.md)
> Gap: [Main Page real backend integration](../../gaps/README.md)

---

## 1. 背景

当前 Main Page 的基础已经拆成三层：

```text
frontend Main Page
  -> createHttpPlatoApi / createHttpMainPageAdapter
  -> LocalSidecarServer / PlatoUiHttpTransport
  -> UiQueryGateway / UiCommandGateway / UiEventSource
  -> server-core services
```

已经完成的部分：

- frontend mock Main Page；
- frontend HTTP API client；
- Python UI contract models；
- UI query/command gateway baseline；
- framework-neutral HTTP transport；
- stdlib loopback sidecar binding。
- Main Page sidecar application assembly；
- `taskweavn plato-sidecar` local dev entrypoint；
- frontend named SSE event subscription compatibility。

本设计最初补的是 **真实后端组合层**：不是新增业务协议，也不是绕过 gateway，而是把已有 server-core 对象组合成一个可启动的 Main Page backend target。

当前事实已经变化：后端组合层和本地 sidecar target 已经基本存在。剩余风险集中在前端运行时：

- Main Page 仍以 fixture `stateId` 作为页面查询和状态切换主轴；
- HTTP mode 仍通过 env 固定单个 session，没有产品化 session 创建/选择；
- 命令 accepted 后仍主要产生本地 synthetic message / decision；
- 页面只消费 `message.appended` 和 `session.resync_required`，还没有完整处理 canonical `UiEventType`；
- backend `message.appended` 事件 payload 是轻量提示，不是完整 `SessionMessageView`。

因此本技术设计后续应被视为两段：已完成的 backend sidecar assembly，以及待完成的 frontend runtime convergence。

---

## 2. 设计原则

### 2.1 Gateway 仍是唯一 UI 后端边界

Sidecar 只能调用：

```python
UiQueryGateway
UiCommandGateway
UiEventSource
```

组合层负责把 gateway 需要的依赖装配好。业务事实仍归属各自 service/store：

- Session fact -> `SessionManager`;
- message fact -> `MessageStream`;
- published Task fact -> `TaskBus`;
- RawTask/DraftTask fact -> authoring stores;
- authoring mutation -> `AuthoringCommandService`;
- natural language authoring -> Collaborator service;
- UI projection -> `TaskProjectionService`;
- transport -> `PlatoUiHttpTransport`。

### 2.2 先走通本地开发 target

第一版目标是让开发者能启动一个 local sidecar，拿到：

- `baseUrl`;
- `sessionId`;
- 可用的 snapshot route；
- 可用的 command route；
- 可用的 SSE resync shell。

Electron packaged lifecycle 仍属于 packaging plan。

### 2.3 明确承认混合持久化

第一版可以使用：

| Object | Store | Persistence |
|---|---|---|
| Session registry | `SessionManager` / SQLite | durable |
| MessageStream | `SqliteMessageStream` | durable |
| Published TaskBus | `SqliteTaskBus` | durable |
| RawTask | `InMemoryRawTaskStore` | volatile |
| DraftTaskTree | `InMemoryDraftTaskStore` | volatile |
| Collaborator template registry | `InMemoryCollaboratorTemplateRegistry` | volatile |
| UiEventSource | resync/static shell | volatile |

这是有意切片，不是最终产品状态。`Persistent authoring stores` 和 `durable SSE replay` 继续作为后续 gap。

---

## 3. 核心对象

### 3.1 MainPageSidecarApp

建议新增：

```python
@dataclass
class MainPageSidecarApp:
    layout: WorkspaceLayout
    session: Session
    session_manager: SessionManager
    message_stream: SqliteMessageStream
    message_bus: InProcessMessageBus
    task_bus: SqliteTaskBus
    raw_task_store: RawTaskStore
    draft_store: DraftTaskStore
    query_gateway: UiQueryGateway
    command_gateway: UiCommandGateway
    transport: PlatoUiHttpTransport
    server: LocalSidecarServer

    @property
    def base_url(self) -> str: ...
    def start_in_thread(self) -> threading.Thread: ...
    def serve_forever(self) -> None: ...
    def close(self) -> None: ...
```

它的职责是生命周期和依赖持有，不实现业务逻辑。

### 3.2 MainPageSidecarConfig

```python
@dataclass(frozen=True)
class MainPageSidecarConfig:
    workspace_root: Path
    session_id: str | None = None
    session_name: str = "Plato session"
    host: str = "127.0.0.1"
    port: int = 52789
    auth_token: str | None = None
```

第一版 `session_id` 语义：

- provided + exists: use it;
- provided + missing: create a new session with generated id? 不建议，因为用户指定 id 可能是错误输入；
- not provided: create new session。

建议第一版：

- provided + missing -> clear error；
- not provided -> create。

### 3.3 MainPageSidecarDependencies

为测试和后续替换预留依赖注入：

```python
@dataclass(frozen=True)
class MainPageSidecarDependencies:
    llm: CollaboratorLLM
    capability_catalog: CapabilityCatalog | None = None
    project_provider: ProjectProvider | None = None
    workflow_provider: WorkflowProvider | None = None
    event_source: UiEventSource | None = None
```

第一版也可以先用 builder 参数而不是单独 dataclass；重点是不要把 LLM/provider 写死到全局环境里。

---

## 4. Dependency Graph

```text
WorkspaceLayout
  -> SessionManager
  -> SqliteMessageStream
  -> SqliteTaskBus

SqliteMessageStream
  -> InProcessMessageBus

InMemoryRawTaskStore
InMemoryDraftTaskStore
StaticCapabilityCatalog
SqliteMessageStream
  -> DefaultAuthoringContextBuilder

RawTaskStore
DraftTaskStore
MessageBus
DefaultTaskPublisher
  -> DefaultAuthoringCommandService

LLM
DefaultAuthoringContextBuilder
DefaultAuthoringCommandService
  -> DefaultCollaboratorAuthoringService

DefaultCollaboratorAuthoringService
DefaultAuthoringCommandService
InMemoryCollaboratorTemplateRegistry
MessageBus
  -> DefaultCollaboratorApiAdapter

SqliteTaskBus
InMemoryDraftTaskStore
SqliteMessageStream
  -> DefaultTaskProjectionService

CollaboratorApiAdapter
DefaultTaskCommandService
TaskRefResolver
  -> DefaultUiCommandGateway

SessionManager
DefaultTaskProjectionService
  -> DefaultUiQueryGateway

DefaultUiQueryGateway
DefaultUiCommandGateway
UiEventSource
  -> PlatoUiHttpTransport
  -> LocalSidecarServer
```

---

## 5. TaskRef Resolution

Frontend `TaskNodeCardView.id` may be backed by:

- draft task id;
- published task id;
- future synthetic UI id.

第一版 resolver 只支持当前 contract 已能表达的真实 id：

```python
class MainPageTaskRefResolver:
    def resolve(self, session_id: str, task_node_id: str) -> TaskRef:
        if draft_store.get_node(session_id, task_node_id) is not None:
            return TaskRef.draft(task_node_id)
        if task_bus.get(session_id, task_node_id) is not None:
            return TaskRef.published(task_node_id)
        raise LookupError(...)
```

如果后续允许 synthetic id，需要在 UI contract 或 projection 中保留 `TaskRef` 映射，而不是在 resolver 猜。

---

## 6. SSE Compatibility

后端 sidecar 的 SSE frame：

```text
id: <cursor>
event: <event.event_type>
data: <UiEvent JSON>

```

浏览器 `EventSource` 对命名 event 的行为是：如果发送了 `event: session.resync_required`，默认 `message` listener 不会收到这个事件。

所以 frontend 必须监听：

- default `message`；
- all canonical `UiEventType` values。

第一片先修这个兼容问题。否则 real sidecar 看起来连上了，但 UI 不会 resync。

当前状态：低层 `createHttpPlatoApi.subscribeSessionEvents` 已经监听 default `message` 和所有 canonical named event。剩余问题不是“收不到事件”，而是“页面如何解释事件”。

事件处理原则：

- `UiEvent` 默认是 invalidation/refetch hint；
- 只有当 payload 明确携带完整 ViewModel 时，前端才做局部 patch；
- `message.appended` 当前只保证 `messageIds`、`taskRefs`、`message_type`、`agent_id` 等轻量字段；
- Main Page 应优先通过 snapshot/messages query 取得完整 `SessionMessageView`。

---

## 7. CLI Entry Point

建议命令：

```text
taskweavn plato-sidecar \
  --workspace ./plato-workspace \
  --session-name "Demo" \
  --host 127.0.0.1 \
  --port 52789
```

输出：

```text
[plato-sidecar] baseUrl=http://127.0.0.1:52789
[plato-sidecar] sessionId=abc12345
[plato-sidecar] vite env:
VITE_PLATO_API_MODE=http
VITE_PLATO_API_BASE_URL=http://127.0.0.1:52789
VITE_PLATO_SESSION_ID=abc12345
```

命令保持前台进程，直到 Ctrl-C。默认端口固定为 `52789`，避免手测时
sidecar 重启后 URL 改变。需要并行运行或端口冲突时，仍可显式传
`--port 0` 让系统选择空闲端口，或传入其它固定端口。

为了降低手测成本，第一版同时提供一键开发命令：

```text
taskweavn plato-dev \
  --workspace ./plato-workspace \
  --session-name "Demo" \
  --sidecar-port 52789 \
  --frontend-dir ./frontend \
  --frontend-host 127.0.0.1 \
  --frontend-port 5173
```

该命令负责：

1. 创建或复用 sidecar session；
2. 启动 `MainPageSidecarApp`；
3. 启动 `npm run dev -- --host <frontend-host> --port <frontend-port>`；
4. 向 frontend 子进程注入：

```text
VITE_PLATO_API_MODE=http
VITE_PLATO_API_BASE_URL=<sidecar baseUrl>
VITE_PLATO_SESSION_ID=<session id>
```

这只是开发/手测入口，不是最终 Electron 打包入口。未来 Electron
main process 会拥有 Python sidecar 生命周期；`plato-dev` 的价值是让当前
backend/frontend 联调不需要两个终端和手工复制 env。默认 sidecar 端口同样
是 `52789`，并保留 `--sidecar-port` 配置。

---

## 8. Testing Strategy

### 8.1 Frontend focused tests

- `platoApi.test.ts` should verify named SSE event listeners.
- `App.test.tsx` / `MainPage` tests should continue to resync on `session.resync_required`.

### 8.2 Backend focused tests

新增 `tests/test_main_page_sidecar_app.py`：

- builder creates a session when `session_id` is absent;
- builder rejects unknown provided session id;
- snapshot route returns live empty session;
- append session input route goes through gateway/Collaborator path with stub LLM;
- resources close idempotently.

### 8.3 Full validation

```text
uv run ruff check src tests
uv run mypy src tests
uv run pytest
npm test
npm run build
npm run lint
git diff --check
```

---

## 9. Open Follow-ups

不在本计划第一版完成：

1. Durable RawTask/DraftTaskTree stores.
2. Durable `UiEventStore` / SSE replay.
3. Frontend create-session workflow.
4. Electron main-process sidecar ownership.
5. Real Task execution lifecycle.
6. Audit page evidence integration.

这些 follow-up 应继续留在 gap registry 或独立 plan，不混进本计划。

---

## 10. Acceptance

完成时应满足：

- developer can start a local sidecar target for Main Page;
- frontend HTTP runtime can load a real snapshot from that sidecar;
- frontend receives named SSE events from the sidecar;
- command routes mutate backend services through `UiCommandGateway`;
- known persistence/replay limitations are visible in docs.
