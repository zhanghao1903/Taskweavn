# Local Computer-Use Tool Foundation 技术方案

> Status: implemented foundation / C1-C4 accepted
>
> Last Updated: 2026-06-19
>
> Feature Plan: [Local Computer-Use Tool Foundation](local-computer-use-tool.md)
>
> Related:
> [Remote WeChat Message Task PRD](../../product/remote-wechat-message-task-prd.md),
> [Execution Plane Service And Task API](execution-plane-service-task-api.md),
> [Execution Plane Technical Design](execution-plane-service-task-api-technical-design.zh-CN.md),
> [Tool Capability Layer](../../architecture/tool-capability-layer.md),
> [Workspace Communication Protocol](../../architecture/workspace-communication-protocol.md)

---

## 1. 目标

本方案只解决第一阶段问题：

```text
本机 API 请求
  -> Execution Plane Task API
  -> 本机 TaskBus
  -> 本机 fixed-route Default Agent
  -> AgentLoop 调用 computer_use tool
  -> 返回结果、事件、证据
```

它不解决：

- A 电脑到 B 电脑的网络分发；
- 远程 ExecutionEnv 注册 / claim / lease / heartbeat；
- 真实 WeChat Desktop 自动化；
- 真实发送消息；
- 截图脱敏生产策略；
- Windows/macOS 权限申请与安装包授权流程。

核心目标是先证明：

1. 本地 `POST /api/v1/tasks` 可以发布一个需要 `computer_use` 能力的任务；
2. 任务可以进入现有 AgentLoop；
3. Agent 能看到并调用 `computer_use`；
4. 工具调用会产生结构化 Observation；
5. 任务最终完成或失败可以被 Task API 查询；
6. 真实桌面自动化 backend 可以在后续替换，而不改 AgentLoop 主链路。

## 2. 当前能力基线

已有能力：

| 能力 | 当前状态 |
|---|---|
| `TaskRequest` / `TaskExecution` DTO | 已有 |
| `EmbeddedTaskApiService` | 已有，但真实 sidecar assembly 仍需检查是否注入 |
| `/api/v1/tasks` HTTP shell | 已有 |
| TaskBus pending/running/done/failed 生命周期 | 已有 |
| fixed-route Default Agent | 已有 |
| AgentLoop tool schema / runtime executor | 已有 |
| ASK / waiting_for_user | 已有 |
| result/error summary | 已有 |
| EventStream | 已有 |

主要缺口：

| 缺口 | 影响 |
|---|---|
| `computer_use` Action/Observation/Tool 不存在 | Agent 无法表达桌面操作 |
| 本地 sidecar Task API 未必注入真实 `TaskApiService` | `/api/v1/tasks` 可能只存在 route shell |
| Task API publish 后是否触发 dispatcher 不稳定 | API 发布后可能只停留在 pending |
| ExecutionEnv 默认能力没有 `computer_use` | capability match 会拒绝 |
| 没有可测试 backend | 无法做无 GUI 的 CI 测试 |
| 没有真实桌面 backend | 不能做真实微信自动化 |
| 没有截图/证据脱敏 | 不能安全暴露真实 UI 证据 |

## 3. 设计原则

1. **先本地，后网络**  
   第一版只允许 loopback local sidecar，不引入 LAN auth。

2. **先工具 contract，后真实桌面 backend**  
   AgentLoop 只依赖 `ComputerUseBackend` 协议，不直接依赖 macOS/Windows API。

3. **默认安全失败**  
   未显式启用 backend 时，`computer_use` 返回结构化 unavailable/error，不执行任何 OS 操作。

4. **高风险操作必须可确认**  
   真实发送消息属于 high-risk outbound side effect。此方案只定义工具，不允许无确认发送。

5. **可测试优先**  
   第一版必须有 `ScriptedComputerUseBackend`，使 CI 能验证 local API -> Agent -> tool -> result。

6. **证据引用优先，不暴露 raw payload**  
   截图、文本抽取、窗口标题等都通过 safe summary / EvidenceRef 进入上层，默认不暴露原始敏感内容。

## 4. 目标模块

建议新增：

```text
src/taskweavn/tools/computer_use.py
```

后续可拆分：

```text
src/taskweavn/computer_use/
  models.py
  backend.py
  scripted.py
  macos.py
  windows.py
  evidence.py
```

第一版不需要立刻建完整包。若单文件超过 600-800 行，再拆。

## 5. Tool Contract

### 5.1 Action

建议模型：

```python
ComputerUseOperation = Literal[
    "observe",
    "open_app",
    "click",
    "type_text",
    "press_key",
    "wait",
]

class ComputerUseAction(BaseAction):
    operation: ComputerUseOperation
    instruction: str
    target: str | None = None
    text: str | None = None
    keys: tuple[str, ...] = ()
    x: int | None = None
    y: int | None = None
    timeout_seconds: float = 5.0
    require_confirmation: bool = False
```

字段语义：

| 字段 | 说明 |
|---|---|
| `operation` | 桌面操作类型 |
| `instruction` | 给 backend / 人类审计看的短说明 |
| `target` | 应用名、UI 元素描述、联系人名等弱定位信息 |
| `text` | 需要输入的文本 |
| `keys` | 快捷键或按键 |
| `x/y` | 坐标，第一版允许但不鼓励 |
| `timeout_seconds` | 操作等待上限 |
| `require_confirmation` | 高风险操作前的显式确认标记 |

风险默认值：

```python
baseline_risk = 0.75
```

原因：桌面自动化可能操作外部世界、暴露隐私、误触 UI。

### 5.2 Observation

建议模型：

```python
ComputerUseStatus = Literal[
    "ok",
    "blocked",
    "needs_user",
    "not_available",
    "failed",
]

class ComputerUseObservation(BaseObservation):
    operation: ComputerUseOperation
    status: ComputerUseStatus
    summary: str
    screenshot_ref: str | None = None
    text_extract: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

Observation 规则：

- `success=True` 只用于 `status == "ok"`；
- `blocked` 表示策略拒绝，例如需要确认；
- `needs_user` 表示需要用户解锁、登录、选择联系人等；
- `not_available` 表示 backend 未配置或平台不支持；
- `failed` 表示执行失败。

## 6. Backend Seam

### 6.1 Protocol

```python
class ComputerUseBackend(Protocol):
    def execute(self, action: ComputerUseAction) -> ComputerUseObservation: ...
```

### 6.2 Disabled Backend

默认 backend：

```text
DisabledComputerUseBackend
```

行为：

- 不执行 OS 操作；
- 返回 `status=not_available`；
- summary 说明需要启用 computer-use backend；
- 用于生产安全默认值。

### 6.3 Scripted Backend

测试 backend：

```text
ScriptedComputerUseBackend
```

行为：

- 接收预置的 operation -> observation；
- 记录收到的 action；
- 可模拟成功、失败、需要用户、权限拒绝；
- 不依赖 GUI。

它用于证明：

```text
Task API -> TaskBus -> AgentLoop -> computer_use -> EventStream -> TaskResult
```

### 6.4 Future Backends

后续 backend：

| Backend | 说明 |
---|---|
| `MacOSComputerUseBackend` | AppleScript / Accessibility / screenshots，需权限检查 |
| `WindowsComputerUseBackend` | UI Automation / PowerShell / screenshots，需 Windows packaging |
| `BrowserComputerUseBackend` | Chrome/Browser 插件桥接，适合网页自动化 |
| `WeChatDesktopAdapter` | 不是通用 backend，而是基于 computer-use 的垂直 adapter |

## 7. Tool Class

建议：

```python
class ComputerUseTool(Tool[ComputerUseAction, ComputerUseObservation]):
    name = "computer_use"
    description = (
        "Use controlled local desktop automation for visible UI tasks. "
        "Use only when the task explicitly requires operating a local app. "
        "Do not send external messages or perform irreversible actions unless "
        "the task policy and user confirmation allow it."
    )
```

执行规则：

1. 校验 action；
2. 如果 `require_confirmation=True` 且未接入 confirmation policy，返回 `blocked`；
3. 调用 backend；
4. 捕获异常并返回 `failed`；
5. 不在 tool 内直接写 TaskBus；Task 状态仍由 AgentLoop / executor 控制。

## 8. Sidecar / AgentLoop Wiring

### 8.1 Config

建议扩展 `MainPageSidecarConfig`：

```python
enable_computer_use_tool: bool = False
```

默认 `False`。

原因：

- computer-use 是高风险工具；
- 当前没有真实权限检查；
- 默认挂载会扩大 Agent 的误操作面。

### 8.2 Dependencies

建议扩展 `MainPageSidecarDependencies`：

```python
computer_use_backend: ComputerUseBackend | None = None
```

测试可以注入 scripted backend。

### 8.3 Agent Tool Registration

在 `build_agent_loop_resident_default_agent` 传入：

```python
computer_use_backend=None | backend
enable_computer_use_tool=False | True
```

在 `_SessionAgentLoopRunner.run` 中：

```python
if enable_computer_use_tool:
    tools.append(ComputerUseTool(backend or DisabledComputerUseBackend()))
```

### 8.4 Context Manager Allowed Tools

`_allowed_tools(...)` 增加可选参数：

```python
include_computer_use: bool = False
```

只有启用时才将 `computer_use` 放入 control context。

## 9. Execution Plane Wiring

### 9.1 Local Env Capability

当 `enable_computer_use_tool=True` 时，local default `ExecutionEnv` 应包含：

```text
capabilities: ("execute", "testing", "computer_use")
tool_pool: (..., "computer_use")
```

未启用时不应 advertise `computer_use`。

### 9.2 Embedded Service Assembly

真实 sidecar runtime 应创建：

```python
SqliteExecutionPlaneStore(layout.workspace_execution_plane_db)
EmbeddedTaskApiService(
    task_bus=task_bus,
    store=execution_plane_store,
    env_registry=local_env_registry,
    summary_store=result_summary_store,
)
```

当前 `WorkspaceLayout` 没有 `workspace_execution_plane_db` 时，可选择：

```text
.plato/execution_plane.sqlite
```

### 9.3 API Publish Dispatch

`POST /api/v1/tasks` 当前只发布 TaskExecution。为了让本地 API 调用能驱动
Agent 完成任务，HTTP route 或 service adapter 需要在成功 publish 后触发：

```python
execution_trigger_gateway.request_dispatch(
    execution.session_id,
    reason="manual_control_route" 或新增 "task_api_publish",
    request_id=request_id,
)
```

建议短期复用现有 reason，长期增加：

```python
ExecutionDispatchTriggerReason = Literal[..., "task_api_publish"]
```

注意：

- dispatcher 只负责本地 fixed-route 执行；
- 不要在 `EmbeddedTaskApiService.publish_task` 内直接启动线程；
- HTTP 层或 sidecar assembly 层触发 dispatcher 更清晰。

## 10. Local API Example

```json
{
  "idempotencyKey": "local:computer-use:demo-1",
  "requester": {
    "kind": "external_app",
    "id": "local-script"
  },
  "taskType": "desktop.demo.computer_use",
  "intent": "Use the local desktop automation tool to observe the current screen and report what happened.",
  "input": {
    "instructions": "Call computer_use with operation observe, then finish with a short result."
  },
  "policy": {
    "requiredCapability": "computer_use",
    "allowedTools": ["computer_use"],
    "requiresHumanConfirmation": false,
    "riskLevel": "medium"
  },
  "evidence": {
    "required": ["tool_observation", "result_summary"]
  }
}
```

## 11. Testing Plan

### 11.1 Tool Unit Tests

File:

```text
tests/test_computer_use_tool.py
```

Cases:

1. disabled backend returns `not_available`;
2. scripted backend returns configured observation;
3. backend exception maps to failed observation;
4. action validates operation and timeout;
5. tool exports schema with name `computer_use`.

### 11.2 AgentLoop Tool Test

Add a focused test where fake LLM emits:

```text
computer_use({"operation":"observe","instruction":"Inspect screen"})
agent_finish(...)
```

Assert:

- `computer_use` in tool list;
- observation appended to EventStream;
- loop finishes.

### 11.3 Sidecar Local API Test

Add a test in `tests/test_main_page_sidecar_app.py` or a focused new file:

```text
build sidecar with enable_computer_use_tool=True and scripted backend
POST /api/v1/tasks requiring computer_use
trigger/await fixed-route dispatch or call run_fixed_route_tick
GET /api/v1/tasks/{executionId}
assert status done
assert result exists
assert event stream contains computer_use observation
```

Also test disabled case:

- `enable_computer_use_tool=False`;
- request requiring `computer_use`;
- expect `capability_not_available` / mapped HTTP error.

### 11.4 Regression Tests

Existing fixed-route tests must still pass when computer-use is disabled.

## 12. Safety Model

第一版安全边界：

| Boundary | Decision |
---|---|
| Default enabled | No |
| Real OS action | No |
| WeChat send | No |
| Screenshot raw data | No |
| External message send | Blocked until confirmation strategy |
| Network caller | No, loopback only |
| Evidence | summary-first |

真实 backend 前必须补：

1. platform permission readiness check；
2. screenshot redaction；
3. operator confirmation UI；
4. action risk classifier；
5. exactly-once external side effect tracking；
6. audit evidence visibility policy。

## 13. Implementation Slices

### C1. Contract Only - done

- Add `ComputerUseAction`;
- Add `ComputerUseObservation`;
- Add `ComputerUseBackend`;
- Add disabled/scripted backend;
- Add `ComputerUseTool`;
- Unit tests.

### C2. AgentLoop Registration - done

- Add optional sidecar config/dependency fields;
- Register tool only when enabled;
- Add allowed-tools context flag;
- AgentLoop test with scripted backend.

### C3. Local Task API Assembly - done

- Add `workspace_execution_plane_db`;
- Build `SqliteExecutionPlaneStore`;
- Build `EmbeddedTaskApiService`;
- Advertise `computer_use` local env only when enabled;
- Pass service into `PlatoUiHttpTransport`.

### C4. API Publish To Dispatch - done

- Trigger fixed-route dispatcher after successful `POST /api/v1/tasks`;
- Add focused sidecar test.

### C5. Evidence Hardening - deferred

- Add `EvidenceRef` for computer-use observations;
- Keep raw screenshot out of default API responses;
- Document Audit follow-up.

C1-C4 are accepted for the local foundation. The current proof covers local
API -> AgentLoop -> scripted `computer_use` -> TaskBus completion and EventStream
observation persistence. C5 remains deferred until real screenshot/text evidence
exists.

## 14. Open Questions

1. `computer_use` 是否应该是通用工具名，还是拆成 `desktop_observe` /
   `desktop_click` 等多个细粒度工具？
2. 第一版真实 backend 优先 macOS 还是 Windows？
3. Electron 是否负责权限检查 UI，还是 Python sidecar 自检后通过 Settings
   readiness 暴露？
4. 高风险 action 的确认是复用 ASK，还是新增 Confirmation lifecycle？
5. screenshot evidence 存在哪里：inspection store、audit evidence store，还是
   独立 computer-use evidence store？
6. 对外 API 请求是否允许直接指定 `allowedTools=["computer_use"]`，还是必须
   通过服务器端 capability policy template？

## 15. Accepted Closure

当前 slice 已完成 C1-C4。

仍然不要先做真实微信。
仍然不要先做网络分发。
仍然不要先做完整截图证据系统。

原因：

- 如果本地 Task API -> AgentLoop -> tool 这条链路不闭合，网络和微信只会放大问题；
- computer-use 是高风险工具，必须先有 disabled/scripted backend 和可测试 contract；
- C1-C4 成功后，真实 macOS/Windows backend 才有稳定接口可以接入。

## 16. Validation Evidence

2026-06-19 accepted checks:

- `tests/test_computer_use_tool.py`
  - validates action payload constraints;
  - validates observation success/status invariant;
  - validates disabled and scripted backend behavior;
  - validates confirmation-required blocking behavior.
- `tests/test_main_page_sidecar_app.py`
  - verifies default sidecar rejects `computer_use` Task API requests when the
    local env does not advertise the capability;
  - verifies enabled sidecar accepts a `computer_use` Task API request;
  - verifies fixed-route dispatch runs AgentLoop with `computer_use` in the
    tool schema;
  - verifies `ScriptedComputerUseBackend` receives the action;
  - verifies the task reaches `done`;
  - verifies `ComputerUseObservation` is persisted in the session EventStream.
