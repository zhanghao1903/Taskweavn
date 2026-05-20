# Local Sidecar API Shell 技术设计

> Status: done
> Last Updated: 2026-05-21
> Feature Plan: [Local Sidecar API Shell](local-sidecar-api-shell.md)
> Gap: [Local sidecar API shell](../../gaps/README.md)

---

## 1. 背景

`UI/backend contract baseline` 已经完成：

- Python 侧有 `taskweavn.server.ui_contract`；
- 前端有 `createHttpPlatoApi`；
- snapshot / command / event / error fixture 已经能跨 Python 和 TypeScript 校验；
- `Local sidecar API shell` 是 `Main Page real backend integration` 前置的主路径 gap。

本设计的目标不是做完整后端业务集成，而是把 **本地 API shell** 定义清楚：

```text
HTTP/SSE 请求
  -> Transport Adapter
  -> UiQueryGateway / UiCommandGateway / UiEventSource
  -> server-core
```

它是 UI 和 server-core 之间的“插座”，不是新的业务层。

---

## 2. 设计原则

### 2.1 Transport 不拥有业务事实

Transport 只处理：

- path / method / query；
- JSON decode / encode；
- request id；
- HTTP status；
- CORS / token；
- SSE frame；
- gateway 调用。

Transport 不直接读取：

- `TaskDomain`;
- `DraftTaskNode`;
- `RawTask`;
- SQLite row;
- `MessageStream` 原始 payload;
- `TaskBus` internal event。

### 2.2 Gateway 是应用边界

第一版只允许 transport 调用：

```python
UiQueryGateway
UiCommandGateway
UiEventSource
```

如果某个 endpoint 需要直接访问 store，说明 gateway 缺能力，应该补 gateway 或另开 plan，而不是让 sidecar 绕过边界。

### 2.3 HTTP/SSE 是产品协议，不是内部对象镜像

HTTP 路由应该稳定服务前端，不应该一比一映射内部 service 方法。

允许：

- `GET /api/v1/sessions/{sessionId}/snapshot`
- `POST /api/v1/sessions/{sessionId}/input`

避免：

- `/api/v1/draft-stores/...`
- `/api/v1/message-stream/raw-query`
- `/api/v1/task-bus/internal-events`

### 2.4 先做可测 shell，再接真实运行时

本计划第一优先级是：

- route 正确；
- envelope 正确；
- error 正确；
- SSE frame 正确；
- gateway 调用正确。

真实业务集成属于下一步 `Main Page real backend integration`。

---

## 3. 模块建议

建议新增：

```text
src/taskweavn/server/
  transport.py              # shared HttpApiRequest / HttpApiResponse / error helpers
  ui_http.py                # PlatoUiHttpTransport, route matching, JSON request parsing
  ui_events.py              # UiEventSource Protocol, SSE frame serialization
  sidecar.py                # stdlib loopback HTTP binding / app assembly
```

如果不想马上抽 `transport.py`，也可以先复制小模型，之后再和 `api_publish.py` 合并。推荐抽出公共 transport 模型，因为 API publish 和 Plato UI 都需要同类 request/response envelope。

---

## 4. 核心对象

### 4.1 HttpApiRequest

```python
class HttpApiRequest(BaseModel):
    method: str
    path: str
    headers: dict[str, str] = {}
    query: dict[str, str] = {}
    body: dict[str, Any] | None = None
```

说明：

- `path` 不带 scheme/host；
- `query` 由 concrete binding 解析；
- `body` 是 JSON object；非 object JSON 视为 invalid body；
- 第一版不需要 multipart / streaming body。

### 4.2 HttpApiResponse

```python
class HttpApiResponse(BaseModel):
    status_code: int
    headers: dict[str, str]
    body: dict[str, Any] | str
```

JSON route 默认：

```python
headers={"content-type": "application/json"}
```

SSE route 默认：

```python
headers={
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
    "connection": "keep-alive",
}
```

如果后续要做真正 streaming，`HttpApiResponse.body` 可能需要拆成普通响应和 streaming 响应两个模型。第一版技术设计先保留扩展点。

### 4.3 PlatoUiHttpTransport

```python
class PlatoUiHttpTransport:
    def __init__(
        self,
        *,
        query_gateway: UiQueryGateway,
        command_gateway: UiCommandGateway,
        event_source: UiEventSource | None = None,
        auth: SidecarAuth | None = None,
    ) -> None: ...

    def handle(self, request: HttpApiRequest) -> HttpApiResponse: ...
```

职责：

- route match；
- method check；
- auth check；
- request validation；
- gateway dispatch；
- response serialization。

### 4.4 UiEventSource

```python
class UiEventSource(Protocol):
    def subscribe(
        self,
        session_id: str,
        *,
        cursor: str | None = None,
    ) -> Iterator[UiEvent]: ...
```

第一版实现可以是：

- `StaticUiEventSource`：测试用；
- `InMemoryUiEventSource`：单进程事件 broker；
- `ResyncOnlyEventSource`：无法 replay 时只返回 `session.resync_required`。

### 4.5 LocalSidecarServer

第一版 concrete binding 采用方案 A：Python stdlib local HTTP server。

```python
@dataclass(frozen=True)
class LocalSidecarConfig:
    host: str = "127.0.0.1"
    port: int = 0
    allow_remote: bool = False
    allowed_origin_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "::1")
    allow_null_origin: bool = True


class LocalSidecarServer:
    def __init__(
        self,
        transport: PlatoUiHttpTransport,
        *,
        config: LocalSidecarConfig | None = None,
    ) -> None: ...

    @property
    def base_url(self) -> str: ...
    def serve_forever(self) -> None: ...
    def start_in_thread(self) -> threading.Thread: ...
    def shutdown(self) -> None: ...
    def server_close(self) -> None: ...
```

选择 stdlib binding 的原因：

- 第一版不引入 FastAPI/Starlette/uvicorn 等运行时依赖；
- 真实 localhost 测试足以验证 Electron renderer 的目标形态；
- binding 层很薄，只做 HTTP -> `HttpApiRequest` 转换，退出成本低；
- 如果后续需要 ASGI、streaming SSE、middleware、observability，可以保留 `PlatoUiHttpTransport`，只替换 binding。

---

## 5. Route Mapping

### 5.1 Health

```text
GET /api/v1/health
```

Response：

```json
{
  "ok": true,
  "data": {
    "name": "Plato Sidecar",
    "version": "0.1.0"
  },
  "error": null
}
```

### 5.2 Snapshot Query

```text
GET /api/v1/sessions/{sessionId}/snapshot
```

Dispatch：

```python
query_gateway.get_session_snapshot(session_id)
```

返回：

- `200` + `QueryResponse[MainPageSnapshot]`
- transport 级错误才用 4xx/5xx

### 5.3 Session Input

```text
POST /api/v1/sessions/{sessionId}/input
```

Body：

```python
CommandRequest[AppendSessionInputPayload]
```

校验：

- body 必须是 JSON object；
- `body.sessionId == path.sessionId`；
- `payload.content` 非空；
- `payload.mode` 必须为 `global_guidance | generate_task_tree`。

Dispatch：

```python
command_gateway.append_session_input(request)
```

### 5.4 Generate Task Tree

```text
POST /api/v1/sessions/{sessionId}/task-tree/generate
```

Body：

```python
CommandRequest[GenerateTaskTreePayload]
```

主工作流不依赖这个 endpoint；它保留给 ready RawTask continuation 或未来特定入口。

### 5.5 Update Task Node

```text
PATCH /api/v1/sessions/{sessionId}/tasks/{taskNodeId}
```

Body：

```python
CommandRequest[UpdateTaskNodePayload]
```

Dispatch：

```python
command_gateway.update_task_node(session_id, task_node_id, request)
```

注意：

- `updateMode=replace_subtree` 需要通过 `AffectedScope(task_subtree)` 通知 UI 重查；
- sidecar 不做 subtree diff。

### 5.6 Append Task Input

```text
POST /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/input
```

Body：

```python
CommandRequest[AppendTaskInputPayload]
```

Dispatch：

```python
command_gateway.append_task_input(session_id, task_node_id, request)
```

### 5.7 Publish Task Tree

```text
POST /api/v1/sessions/{sessionId}/task-tree/publish
```

Body：

```python
CommandRequest[PublishTaskTreePayload]
```

Dispatch：

```python
command_gateway.publish_task_tree(request)
```

### 5.8 Resolve Confirmation

```text
POST /api/v1/sessions/{sessionId}/confirmations/{confirmationId}/respond
```

Body：

```python
CommandRequest[ResolveConfirmationPayload]
```

Dispatch：

```python
command_gateway.resolve_confirmation(session_id, confirmation_id, request)
```

### 5.9 Session Events

```text
GET /api/v1/sessions/{sessionId}/events?cursor=...
```

Dispatch：

```python
event_source.subscribe(session_id, cursor=cursor)
```

SSE frame：

```text
id: <event.cursor>
event: <event.event_type>
data: <event.model_dump_json(by_alias=True)>

```

第一版允许 `ResyncOnlyEventSource`：

```python
UiEvent(event_type="session.resync_required", ...)
```

---

## 6. Error Mapping

### 6.1 Transport errors

Transport errors use HTTP status codes:

| Case | HTTP | Code |
|---|---:|---|
| unknown route | 404 | `not_found` |
| method mismatch | 405 | `bad_request` |
| missing/invalid token | 401 | `permission_denied` |
| malformed JSON / non-object body | 400 | `bad_request` |
| path/body session mismatch | 400 | `bad_request` |
| Pydantic validation failure | 400 | `bad_request` |
| unexpected exception | 500 | `internal_error` |

Transport error body should reuse the UI `ApiError` shape when possible:

```json
{
  "ok": false,
  "requestId": "...",
  "data": null,
  "error": {
    "code": "bad_request",
    "message": "request body does not match CommandRequest",
    "retryable": false,
    "details": {}
  }
}
```

### 6.2 Gateway errors

Gateway-produced `QueryResponse` / `CommandResponse` should pass through unchanged.

That means:

- query not found may still be `200` with `ok=false`;
- command rejected may still be `200` with `ok=false`;
- transport only owns protocol failure, not business result semantics。

---

## 7. Local Security

第一版 sidecar 不是公网服务。

默认策略：

1. bind `127.0.0.1` only；
2. startup 生成随机 token；
3. renderer 每个 request 带 `Authorization: Bearer <token>`；
4. EventSource 不能自定义 header，需二选一：
   - 使用 query token：`/events?cursor=...&token=...`；
   - 或使用 Electron main process proxy。

第一版建议：

- HTTP JSON routes 使用 `Authorization` header；
- SSE 暂用 query token，但只允许 loopback；
- token 不写入日志；
- 未来打包阶段再评估 main-process proxy。

---

## 8. Lifecycle

### 8.1 Development lifecycle

```text
developer starts sidecar
  -> sidecar binds localhost port
  -> frontend Vite points baseUrl to sidecar
  -> frontend calls /health
  -> manual UI testing
```

### 8.2 Packaged lifecycle

```text
Electron main starts
  -> allocate localhost port
  -> generate token
  -> spawn Python sidecar
  -> wait for /api/v1/health
  -> provide baseUrl/token to renderer
  -> renderer uses createHttpPlatoApi
  -> app quit terminates sidecar
```

### 8.3 Failure lifecycle

| Failure | Expected UI behavior |
|---|---|
| sidecar not started | show startup/retry state |
| health timeout | show diagnostic action |
| command validation failed | show command error |
| gateway `internal_error` | show retry/report action |
| SSE disconnected | reconnect with last cursor |
| cursor cannot replay | receive `session.resync_required`, re-query snapshot |

---

## 9. Testing Strategy

### 9.1 Backend tests

```text
tests/test_local_sidecar_server.py
tests/test_ui_http_transport.py
tests/test_ui_sse_transport.py
```

Cases:

- health route;
- snapshot route calls query gateway;
- all command routes call expected gateway method;
- URL decoding;
- method mismatch;
- unknown route;
- invalid JSON/body;
- session mismatch;
- Pydantic validation errors;
- gateway exception -> internal_error;
- SSE frame format;
- resync event fallback.
- real localhost health / command / SSE / auth / origin checks.

### 9.2 Frontend tests

Existing:

- `frontend/src/shared/api/platoApi.test.ts`
- `frontend/src/shared/api/backendContractFixtures.test.ts`

Potential additions:

- token/header injection if API client changes;
- EventSource query token URL if chosen.

---

## 10. Implementation Order

Recommended first implementation:

1. Extract shared transport request/response helpers from `api_publish.py` only if useful.
2. Add `PlatoUiHttpTransport` with health + snapshot route.
3. Add command routes one by one with tests.
4. Add `UiEventSource` Protocol and SSE serializer.
5. Add resync-only event source.
6. Add stdlib local HTTP binding with real localhost tests.

The risky part is not route code; it is accidentally mixing transport with business state. Keep route code boring.

---

## 11. Open Questions

These do not block Slice 1, but should be resolved before a packaged app:

1. EventSource auth: query token vs Electron main-process proxy.
2. Durable event replay: independent `UiEventStore` vs projecting from MessageStream/EventStream.
3. Sidecar process ownership: Electron always spawns sidecar, or developer can connect to an existing sidecar.
4. Startup diagnostics: where to expose logs when sidecar fails before UI fully loads.
5. Future binding upgrade: when stdlib HTTP becomes insufficient, whether to move to FastAPI/Starlette/uvicorn or a custom Electron main-process bridge.

---

## 12. Acceptance

本技术设计完成后的实现应满足：

- frontend current API client can target sidecar routes;
- backend transport remains framework-neutral and unit-testable;
- command/query/event contract remains unchanged;
- SSE fallback story is explicit;
- local security defaults are not postponed into ambiguity;
- Main Page real backend integration can start from a concrete local API target.
