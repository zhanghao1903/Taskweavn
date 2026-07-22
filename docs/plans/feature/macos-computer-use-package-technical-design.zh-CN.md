# macOS Computer-Use Capability Package 技术方案

> Status: Historical package technical design. The original single-package
> `macos-computer-use` boundary was superseded by the published package suite:
> `app-control-protocol`, `computer-use-macos`, and `wechat-desktop-tool`.
> 当前 Plato 迁移方案见
> [App-Control Tool Package Migration](app-control-tool-package-migration.zh-CN.md)。
>
> Last Updated: 2026-06-19
>
> Feature Plan: [macOS Computer-Use Capability Package](macos-computer-use-package.md)
>
> Related:
> [macOS Computer-Use Backend](macos-computer-use-backend.md),
> [Local Computer-Use Tool Foundation](local-computer-use-tool.md),
> [Confirmation UI Spec](../../ux/confirmation-ui-spec.md),
> [Tool Capability Layer](../../architecture/tool-capability-layer.md),
> [Execution Plane Service And Task API](execution-plane-service-task-api.md)

---

## 1. 目标

本方案把真实 macOS computer-use 能力定义为一个可独立发布的 Python 包，
而不是 Taskweavn/Plato 内部模块。

注意：本方案记录的是旧的单包设计。当前实现已拆分为：

```text
app-control-protocol  -> ToolCommand / ToolObservation / ToolEvent 协议
computer-use-macos    -> macOS app-control primitives / helper transport
wechat-desktop-tool   -> WeChat semantic desktop commands
```

核心目标：

1. 包只提供 macOS 桌面自动化能力；
2. 包不集成 LLM、AgentLoop、TaskBus、Session、Audit 或 UI；
3. 包可以独立发布给社区使用；
4. Plato 后续通过包依赖引入，而不是直接引用源码；
5. Plato 只实现 adapter、confirmation、Task API 和 evidence/audit 映射。

设计边界：

```text
External Agent App / Plato
  -> caller-owned task/session/confirmation/runtime policy
  -> macos-computer-use public API
  -> macOS readiness / accessibility / app / input primitives
  -> structured result
```

## 2. 包边界

### 2.1 包内职责

`macos-computer-use` 负责：

- macOS 平台判断；
- Accessibility 权限探测；
- 可选 Screen Recording readiness 报告；
- app allowlist；
- `observe`；
- `open_app`；
- 低风险 semantic `click`；
- focused editable `type_text`；
- `wait`；
- target freshness / ambiguity 检查；
- high-risk metadata；
- sanitized diagnostics。

### 2.2 包外职责

调用方负责：

- LLM 决策；
- Agent 工具调用；
- Task / Plan / Session 生命周期；
- durable confirmation；
- ASK；
- audit record；
- event stream；
- workspace persistence；
- 业务特定 adapter，例如 WeChat 联系人解析；
- 网络任务分发；
- UI 展示。

包可以返回“需要确认”的结构化结果，但不创建确认，不展示确认，也不存储确认。

## 3. 推荐目录结构

第一阶段可以放在当前 monorepo 的 `packages/` 下，后续可独立拆仓：

```text
packages/macos-computer-use/
  pyproject.toml
  README.md
  LICENSE
  src/macos_computer_use/
    __init__.py
    client.py
    models.py
    readiness.py
    accessibility.py
    app_control.py
    target_resolution.py
    input_control.py
    policy.py
    errors.py
    logging.py
  tests/
    test_models.py
    test_readiness.py
    test_policy.py
    test_fake_client.py
  examples/
    textedit_smoke.py
```

不建议直接新增：

```text
src/taskweavn/computer_use/macos.py
```

Plato 内部只应新增 adapter，例如：

```text
src/taskweavn/tools/computer_use_macos_adapter.py
```

## 4. Public API

### 4.1 Client

建议对外只暴露一个主入口：

```python
from macos_computer_use import MacOSComputerUseClient

client = MacOSComputerUseClient(
    allowed_apps=("TextEdit",),
    allow_coordinate_click=False,
)
```

方法：

```python
client.readiness() -> ComputerUseReadiness
client.observe(target_app: str | None = None) -> ComputerUseResult
client.open_app(app: str) -> ComputerUseResult
client.click(target: str, *, snapshot_id: str | None = None) -> ComputerUseResult
client.type_text(text: str, *, target_app: str | None = None) -> ComputerUseResult
client.wait(target: str | None = None, timeout_seconds: float = 5.0) -> ComputerUseResult
```

第一版不暴露 Agent 风格的自由动作解释器。调用方必须显式选择 operation。

### 4.2 Models

建议模型：

```python
ComputerUseStatus = Literal[
    "ok",
    "blocked",
    "needs_user",
    "not_available",
    "failed",
]

ComputerUseOperation = Literal[
    "readiness",
    "observe",
    "open_app",
    "click",
    "type_text",
    "wait",
]
```

```python
class ComputerUseReadiness(BaseModel):
    status: Literal[
        "ready",
        "unsupported_platform",
        "backend_disabled",
        "missing_accessibility",
        "missing_screen_recording",
        "needs_manual_setup",
        "error",
    ]
    platform: str
    accessibility_trusted: bool
    screen_recording_available: bool | None = None
    enabled_operations: tuple[ComputerUseOperation, ...] = ()
    setup_hint: str | None = None
    diagnostics: dict[str, str] = Field(default_factory=dict)
```

```python
class ComputerUseResult(BaseModel):
    operation: ComputerUseOperation
    status: ComputerUseStatus
    success: bool
    summary: str
    text_extract: str | None = None
    snapshot_id: str | None = None
    risk: RiskDecision | None = None
    metadata: dict[str, str | bool | int | float] = Field(default_factory=dict)
```

```python
RiskLevel = Literal["low", "medium", "high"]

class RiskDecision(BaseModel):
    level: RiskLevel
    requires_confirmation: bool
    risk_label: str | None = None
    reason: str
    action_fingerprint: str | None = None
```

注意：包内 `RiskDecision` 只表达风险，不负责确认生命周期。

## 5. 内部接口

为保证测试不依赖真实 GUI，生产实现必须通过 seam 注入：

```python
class PermissionProbe(Protocol):
    def platform_name(self) -> str: ...
    def accessibility_trusted(self) -> bool: ...
    def screen_recording_available(self) -> bool | None: ...
```

```python
class AppController(Protocol):
    def open_app(self, app_name: str, bundle_id: str | None) -> AppOpenResult: ...
    def frontmost_app(self) -> AppIdentity | None: ...
```

```python
class AccessibilityClient(Protocol):
    def observe(self, target_app: str | None) -> UiSnapshot: ...
    def focused_editable(self) -> EditableTarget | None: ...
    def press(self, target: ResolvedTarget) -> None: ...
```

```python
class InputController(Protocol):
    def type_text(self, text: str) -> None: ...
```

```python
class SafetyPolicy(Protocol):
    def evaluate(self, action: InternalAction, snapshot: UiSnapshot | None) -> RiskDecision: ...
```

测试默认使用 fake 实现；真实 macOS 实现只在手工 smoke 中运行。

## 6. 安全策略

默认安全策略：

1. 不 allowlist 的 app 直接 blocked；
2. 缺 Accessibility 时不降级到盲坐标点击；
3. `type_text` 不按 Enter，不发送；
4. password / secure input 永久 blocked；
5. system dialog blocked；
6. pay/delete/install/submit/send 等 high-risk target blocked；
7. raw coordinate click 默认 disabled；
8. target 多义时 `needs_user`；
9. stale snapshot blocked；
10. raw screenshot 不默认启用。

high-risk 返回示例：

```json
{
  "operation": "click",
  "status": "blocked",
  "success": false,
  "summary": "computer-use action requires confirmation",
  "risk": {
    "level": "high",
    "requires_confirmation": true,
    "risk_label": "external_message",
    "reason": "Target looks like a send action.",
    "action_fingerprint": "..."
  },
  "metadata": {
    "confirmation_required": true,
    "confirmation_title": "Confirm external message",
    "confirmation_body": "Approve sending the drafted message to the selected contact."
  }
}
```

## 7. 打包方案

### 7.1 pyproject

包必须是标准 Python 包，不依赖 Taskweavn 的构建系统。

推荐：

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "macos-computer-use"
version = "0.1.0"
description = "LLM-free macOS desktop automation primitives for agent applications."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "Apache-2.0" }

[project.optional-dependencies]
dev = ["pytest", "ruff", "mypy"]
```

也可以使用 setuptools，但不要引入 Taskweavn 特定构建逻辑。

### 7.2 构建产物

必须产出：

- wheel；
- sdist；
- README；
- license；
- typed package metadata，如后续加入 `py.typed`。

验收命令形态：

```text
uv build packages/macos-computer-use
python -m pip install dist/macos_computer_use-*.whl
python -c "import macos_computer_use"
```

实际 CI 命令可在实现时根据 monorepo 工具链调整，但产物必须保持标准 Python
包格式。

## 8. 对外发布方案

推荐发布路径：

1. 本地构建 wheel/sdist；
2. clean venv 安装；
3. TestPyPI 发布；
4. TestPyPI clean install；
5. GitHub Release；
6. PyPI 发布；
7. 发布 README、permission setup、safety policy、manual smoke。

优先使用 PyPI Trusted Publishing，避免 API token 写入仓库或本地文档。

Release tag 建议：

```text
macos-computer-use-v0.1.0
```

发布前检查：

- 包无 Taskweavn import；
- 包无 LLM/provider import；
- 包无网络依赖；
- package tests 不需要 macOS GUI 权限；
- macOS 手工 smoke 可选，但 release notes 必须标明验证环境；
- README 明确 Accessibility 权限由用户手动授予。

## 9. Plato 接入方案

Plato 不直接引用源码，后续通过依赖引入：

```toml
dependencies = [
  "macos-computer-use>=0.1,<0.2; sys_platform == 'darwin'",
]
```

如果希望非 macOS 平台也能安装 Plato，可改为 optional extra 或 runtime optional
import：

```python
try:
    from macos_computer_use import MacOSComputerUseClient
except ImportError:
    MacOSComputerUseClient = None
```

Plato adapter：

```text
ComputerUseAction
  -> PlatoMacOSComputerUseAdapter
  -> MacOSComputerUseClient
  -> ComputerUseResult
  -> ComputerUseObservation
```

Adapter 映射：

| Package Result | Plato Mapping |
|---|---|
| `ok` | `ComputerUseObservation(status="ok", success=True)` |
| `blocked` + `confirmation_required` | observation blocked -> Agent calls `request_confirmation` |
| `needs_user` | observation needs_user -> ASK or user-facing setup state |
| `not_available` | backend unavailable/readiness gap |
| `failed` | sanitized error observation and Task failure/retry path |

Plato 保留：

- disabled backend；
- scripted backend；
- sidecar enablement gate；
- EventStream observation persistence；
- confirmation durable store；
- Audit/evidence refs；
- Task API / AgentLoop wiring。

## 10. 测试策略

### 10.1 Package Tests

不要求真实 macOS 权限：

- readiness fake probe；
- unsupported platform；
- missing Accessibility；
- allowlist；
- risk classification；
- blocked high-risk metadata；
- type text length limit；
- coordinate click disabled；
- stale target blocked；
- import/package metadata。

### 10.2 Package Manual Smoke

本机 macOS：

1. `readiness()` without Accessibility；
2. grant Accessibility；
3. `open_app("TextEdit")`；
4. `observe(target_app="TextEdit")`；
5. focus TextEdit document；
6. `type_text("hello")`；
7. high-risk target simulation returns blocked。

### 10.3 Plato Adapter Tests

使用 fake package client：

- package `ok` -> Plato observation ok；
- package `blocked confirmation_required` -> request confirmation path；
- package `needs_user` -> ASK/setup surface；
- package `not_available` -> disabled/readiness projection；
- package `failed` -> sanitized failure；
- no package installed on non-macOS -> fallback disabled backend。

## 11. 与 UI-TARS 的关系

UI-TARS 更接近完整 GUI Agent / VLM 自动化框架。当前目标是发布一个干净的、
LLM-free、可被任意 Agent 应用调用的能力包，因此不把 UI-TARS SDK 作为核心
依赖。

后续可以把 UI-TARS 或其他视觉模型作为可选 adapter/experiment，但不能污染
基础包 API。

## 12. 实施顺序

1. **Pkg-0 Docs**
   - 本方案；
   - package plan；
   - gap registry；
   - backend adapter 文档同步。

2. **Pkg-1 Skeleton**
   - package skeleton；
   - public models；
   - fake client；
   - packaging tests。

3. **Pkg-2 Readiness**
   - permission probe seam；
   - macOS readiness；
   - fake tests；
   - README setup。

4. **Pkg-3 Observe/Open**
   - Accessibility observe seam；
   - allowlisted open app；
   - TextEdit manual smoke。

5. **Pkg-4 Safe Input**
   - semantic click；
   - focused type_text；
   - risk policy；
   - blocked high-risk metadata。

6. **Pkg-5 Publish**
   - TestPyPI；
   - clean install；
   - GitHub release；
   - PyPI。

7. **Pkg-6 Plato Adapter**
   - dependency import；
   - adapter mapping；
   - confirmation handoff；
   - sidecar smoke。

## 13. Open Questions

1. 包是否从一开始就新建独立仓库？
2. package name 是否最终确定为 `macos-computer-use`？
3. 许可证选择 Apache-2.0 还是 MIT？
4. 第一版是否要求 `pyobjc`，还是先使用 subprocess + system APIs 的更窄方案？
5. screenshot 是否永远保持独立 optional capability？
