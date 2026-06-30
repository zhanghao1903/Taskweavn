# macOS Computer-Use Backend 技术方案

> Status: Historical backend technical design. The repo-local helper/backend
> implementation described here was retired by
> [App-Control Tool Package Migration](app-control-tool-package-migration.zh-CN.md).
> 当前实现通过 `computer-use-macos` 包和 `MacOSComputerUseBackend` 接入。
>
> Last Updated: 2026-06-19
>
> Feature Plan: [macOS Computer-Use Backend](macos-computer-use-backend.md)
>
> Related:
> [App-Control Tool Package Migration](app-control-tool-package-migration.zh-CN.md),
> [App-Control Tool Package Smoke Runbook](app-control-tool-package-smoke-runbook.zh-CN.md),
> [Historical macOS Computer-Use Capability Package](macos-computer-use-package.md),
> [Local Computer-Use Tool Foundation](local-computer-use-tool.md),
> [Remote WeChat Message Task PRD](../../product/remote-wechat-message-task-prd.md),
> [Tool Capability Layer](../../architecture/tool-capability-layer.md),
> [Confirmation UI Spec](../../ux/confirmation-ui-spec.md),
> [Execution Plane Technical Design](execution-plane-service-task-api-technical-design.zh-CN.md)

---

## 1. 目标

本方案定义真实 macOS `computer_use` backend 的最小可执行设计。

关键修订：本方案记录的是旧的单包 backend 设计。当前实现已迁移到
`computer-use-macos` 包；Taskweavn/Plato 内部的 macOS backend 只是 adapter，
负责把包结果接入 `ComputerUseObservation`、runtime logs、EventStream 和 Audit。

目标不是立刻完成 WeChat 自动发消息，而是先建立一个安全边界清晰的
本机桌面自动化 backend：

```text
AgentLoop
  -> computer_use tool
  -> MacOSComputerUseBackend
  -> computer-use-macos ComputerUseClient
  -> observe/open_app/click/type_text
  -> sanitized ComputerUseObservation
```

第一版必须满足：

1. 未授权时明确返回 readiness 缺口；
2. 未启用时不执行任何 OS 操作；
3. `observe` 优先使用 Accessibility 结构化信息，不默认截图；
4. `open_app` 只允许 allowlist；
5. `click/type_text` 必须经过 readiness、target、risk 检查；
6. 高风险操作必须接入 confirmation；
7. CI 测试不依赖真实 macOS GUI 权限；
8. 手工 smoke 可以在 macOS 本机验证。

## 2. 当前代码基线

已有：

| 模块 | 当前状态 |
|---|---|
| `ComputerUseAction` | 已有 `observe/open_app/click/type_text/press_key/wait` contract。 |
| `ComputerUseObservation` | 已有 `ok/blocked/needs_user/not_available/failed` 状态。 |
| `ComputerUseBackend` | 已有 backend protocol seam。 |
| `DisabledComputerUseBackend` | 默认安全 backend，永不操作 OS。 |
| `ScriptedComputerUseBackend` | 已支持 AgentLoop / Task API 测试。 |
| `ComputerUseTool` | 已注册工具，并在 `require_confirmation=True` 时返回 blocked。 |
| `RequestConfirmationTool` | 已能创建 durable confirmation 并让任务进入 `waiting_for_user`。 |
| Main Page confirmation UI | 已能展示/resolve pending confirmation。 |

主要缺口：

| 缺口 | 影响 |
|---|---|
| 没有 macOS readiness probe | 前端/运行时无法知道缺少哪个权限。 |
| 没有真实 macOS backend | 不能验证本机桌面动作。 |
| 没有 target resolver | `click/type_text` 容易退化成危险坐标操作。 |
| 没有 backend-side risk policy | prompt 约束不足以防止高风险误操作。 |
| 没有 confirmation authorizer | high-risk 操作无法验证用户授权是否覆盖当前动作。 |
| 没有 manual smoke 契约 | 真实桌面 backend 无法稳定验收。 |

## 3. 模块设计

建议新增独立能力包：

```text
packages/macos-computer-use/
  pyproject.toml
  README.md
  src/macos_computer_use/
  __init__.py
  client.py
  models.py
  policy.py
  readiness.py
  accessibility.py
  app_control.py
  target_resolution.py
  input_control.py
```

Taskweavn/Plato 内部只保留 adapter：

```text
src/taskweavn/tools/computer_use_macos_adapter.py
```

不要把真实 backend、policy、readiness、target resolver 全部塞进
`src/taskweavn/tools/computer_use.py`。该文件应继续保持工具 facade 和
backend protocol 的职责。

Plato 依赖方式应是标准包依赖，而不是源码相对路径：

```toml
dependencies = [
  "macos-computer-use>=0.1,<0.2; sys_platform == 'darwin'",
]
```

### 3.1 Readiness Models

包内建议新增：

```python
MacOSComputerUseReadinessStatus = Literal[
    "ready",
    "unsupported_platform",
    "backend_disabled",
    "missing_accessibility",
    "missing_screen_recording",
    "needs_manual_setup",
    "error",
]

class MacOSComputerUseReadiness(BaseModel):
    status: MacOSComputerUseReadinessStatus
    platform: str
    accessibility_trusted: bool
    screen_recording_available: bool | None = None
    screen_recording_required: bool = False
    enabled_operations: tuple[ComputerUseOperation, ...] = ()
    setup_hint: str | None = None
    diagnostics: dict[str, str] = Field(default_factory=dict)
```

`screen_recording_available=None` 表示当前未启用截图模式，因此不探测或
不要求 Screen Recording。

### 3.2 Probe Seam

建议新增：

```python
class MacOSPermissionProbe(Protocol):
    def platform_name(self) -> str: ...
    def accessibility_trusted(self) -> bool: ...
    def screen_recording_available(self) -> bool | None: ...
```

生产实现：

- `platform.system() == "Darwin"` 判断平台；
- Accessibility 使用系统 API 探测授权状态；
- Screen Recording 只在截图模式开启后探测；
- Automation / Apple Events 不作为第一版必需权限。

测试实现：

- fake probe 返回固定 readiness；
- 不调用真实 Apple API；
- 不要求 CI runner 具备 GUI 会话。

## 4. macOS API 策略

### 4.1 Accessibility

用途：

- frontmost app / focused element / UI tree 观察；
- semantic target 查找；
- AXPress；
- 低风险 UI 操作。

原则：

- 缺少 Accessibility 时不尝试 fallback 到盲坐标点击；
- 读取内容必须 bounded；
- 密码/secure text 字段只返回类型，不返回值；
- UI tree 作为临时操作上下文，不默认作为 raw evidence 持久化。

### 4.2 App Launch

第一版 `open_app` 推荐使用：

```text
open -a <allowlisted app name>
```

或后续使用 NSWorkspace。

规则：

- app 必须来自 allowlist；
- 不允许通过 `open_app` 打开任意 URL 或文件；
- 打开后需要 verify frontmost app 或可见窗口；
- app 登录/解锁/更新弹窗返回 `needs_user`。

### 4.3 Screen Capture

第一版不默认截图。

原因：

- Screen Recording 权限更敏感；
- 截图可能包含聊天记录、客户数据、账号信息；
- 还没有截图脱敏 pipeline。

如后续加入：

- 必须单独 readiness；
- 只允许 evidence ref，不暴露 raw screenshot；
- 默认 permission-limited；
- 需要脱敏/裁剪策略。

### 4.4 AppleScript / Apple Events

第一版不依赖 AppleScript。

原因：

- app scriptability 不稳定；
- Automation 权限和 entitlement 会增加打包复杂度；
- 对聊天类 app 的真实发送行为更容易绕过 UI confirmation。

如果后续使用 AppleScript，必须作为 app-specific adapter，不进入通用
`MacOSComputerUseBackend` 的默认路径。

## 5. Backend Flow

```text
ComputerUseTool.execute(action)
  -> ComputerUsePolicyGate.evaluate(action, readiness, latest_snapshot)
  -> if blocked: ComputerUseObservation(status="blocked", metadata=...)
  -> MacOSComputerUseBackend.execute_allowed(action)
  -> sanitized ComputerUseObservation
```

注意：真实 OS 操作之前必须经过 policy gate。不要只依赖 Agent prompt。

## 6. Operation 设计

### 6.1 `observe`

输入要求：

- `operation="observe"`；
- `target` 可选；
- 如果指定 target app，则只观察该 app/window。

输出：

```python
ComputerUseObservation(
    operation="observe",
    status="ok" | "needs_user" | "not_available" | "failed",
    summary="Frontmost app: TextEdit. Focused editable document.",
    text_extract="bounded sanitized text",
    metadata={
        "appBundleId": "...",
        "windowTitle": "...",
        "elementCount": "42",
        "snapshotId": "...",
    },
)
```

规则：

- max text extract 默认不超过 4,000 chars；
- 不返回 password value；
- 不返回 raw UI tree；
- 不返回 screenshot；
- 记录 `snapshotId` 供 `click` target freshness 校验。

### 6.2 `open_app`

输入要求：

- `operation="open_app"`；
- `target` 必填；
- target 必须匹配 allowlist。

输出：

- `ok`: app 已打开/聚焦；
- `needs_user`: app 需要登录、解锁、更新或手动选择；
- `blocked`: app 不在 allowlist；
- `failed`: 打开失败。

建议 allowlist 配置：

```python
allowed_apps = {
    "TextEdit": "com.apple.TextEdit",
    "WeChat": "com.tencent.xinWeChat",
}
```

WeChat 可以出现在 allowlist，但发送消息不是本 slice 验收内容。

### 6.3 `click`

输入要求：

- `target` 优先；
- `x/y` 仅 debug/manual-smoke 模式允许；
- 必须有 fresh `snapshotId` 或当前观察上下文；
- Accessibility ready。

推荐 target resolver：

```python
class MacOSUiTargetResolver(Protocol):
    def resolve_click_target(
        self,
        target: str,
        snapshot_id: str | None,
    ) -> ResolvedUiTarget: ...
```

目标选择规则：

1. 优先匹配 role + accessible name；
2. 多个匹配时返回 `needs_user` 或要求 ASK；
3. target 过期返回 `blocked`；
4. send/pay/delete/install/permission/system prompt 返回 `blocked` 并要求 confirmation；
5. 密码/security prompt 永久 blocked。

### 6.4 `type_text`

输入要求：

- `text` 必填；
- 当前 focused element 必须是 editable；
- focused app/window 必须符合 action target 或当前 task policy；
- Accessibility ready。

规则：

- 不自动按 Enter；
- 不自动发送；
- 不输入 password/secure text 字段；
- `text` 长度使用现有 `ComputerUseAction.text` 上限，后续可按 backend config 再收紧；
- 如果使用 clipboard paste，必须保存/恢复剪贴板，并把该行为写入 metadata；
- 更保守的第一版可以只支持短文本 key events。

## 7. Confirmation 接入

### 7.1 风险分类

建议新增：

```python
ComputerUseRiskLevel = Literal["low", "medium", "high"]

class ComputerUseRiskDecision(BaseModel):
    level: ComputerUseRiskLevel
    requires_confirmation: bool
    reason: str
    risk_label: str | None = None
    action_fingerprint: str
```

高风险判定：

- target 或 instruction 包含 send/发送/submit/pay/delete/install 等动作；
- 点击聊天发送按钮；
- 点击付款、删除、安装、授权、系统设置；
- 向外部沟通工具提交内容；
- target ambiguity；
- 需要暴露屏幕/聊天 evidence。

### 7.2 Blocked Observation

如果高风险且没有确认：

```python
ComputerUseObservation(
    operation=action.operation,
    status="blocked",
    success=False,
    summary="computer-use action requires user confirmation",
    metadata={
        "confirmationRequired": True,
        "riskLabel": "external message",
        "actionFingerprint": "...",
        "recommendedConfirmation": {
            "title": "Confirm external message",
            "body": "Approve sending the drafted message to the selected contact.",
            "options": ["confirm", "reject"],
            "allowSessionApproval": True,
        },
    },
)
```

Agent guidance 需要明确：

```text
If computer_use returns blocked with confirmationRequired=true,
call request_confirmation with the recommended title/body/options.
Do not retry the same high-risk computer_use action until the confirmation
is resolved.
```

### 7.3 Confirmation Authorizer

仅 prompt 约束不够。后续实现 high-risk 真执行前，需要一个 authorizer：

```python
class ComputerUseConfirmationAuthorizer(Protocol):
    def is_confirmed(
        self,
        *,
        session_id: str,
        task_id: str,
        confirmation_id: str,
        action_fingerprint: str,
    ) -> bool: ...
```

由于 `ComputerUseAction` 当前没有 typed `session_id/task_id` 字段，第一版可
通过 `metadata` 传递：

```json
{
  "sessionId": "...",
  "taskId": "...",
  "confirmationId": "...",
  "actionFingerprint": "..."
}
```

如果后续发现该字段成为通用 contract，应再把它提升为 typed field。

### 7.4 Session Approval

当前 confirmation UI 支持 `approve_session` 作为选项值，但 Product 1.0
语义是“记录该响应”，不是“自动绕过后续确认”。

真实 macOS backend 第一版沿用该规则：

- 可以展示 `approve_session`；
- 可以记录用户选择；
- 不自动 bypass future high-risk action；
- 如要支持整个会话通过，需要单独设计 `SessionApprovalPolicy`：
  - task type scope；
  - app scope；
  - target/contact scope；
  - message class scope；
  - TTL；
  - revocation；
  - audit record。

## 8. 失败语义

| 场景 | Observation Status | Summary |
|---|---|---|
| backend 未启用 | `not_available` | computer-use backend is not enabled |
| 非 macOS | `not_available` | macOS backend is unsupported on this platform |
| 缺 Accessibility | `blocked` 或 `not_available` | Accessibility permission is required |
| app 不在 allowlist | `blocked` | app is not allowlisted |
| app 需要登录/解锁 | `needs_user` | app requires manual setup |
| target 多义 | `needs_user` | multiple matching targets |
| high risk 未确认 | `blocked` | confirmation required |
| target 过期 | `blocked` | target snapshot is stale |
| OS 调用异常 | `failed` | sanitized exception type |

## 9. 测试计划

### 9.1 Unit Tests

不调用真实 OS：

- fake permission probe -> readiness matrix；
- allowlist app resolver；
- policy classification；
- blocked high-risk metadata；
- no coordinate click unless debug flag；
- password/secure target blocked；
- stale snapshot blocked；
- confirmation authorizer accepted/rejected。

### 9.2 Integration Tests

仍使用 fake backend/probe：

```text
Task API -> AgentLoop -> computer_use observe/open_app -> observation -> Task done
Task API -> AgentLoop -> computer_use high-risk click -> blocked -> request_confirmation
```

第一版可以先只验证 blocked handoff metadata，不强行完成真实 confirmation
round-trip，避免过早耦合 Agent prompt 行为。

### 9.3 Manual macOS Smoke

需要本机运行：

1. backend disabled -> readiness `backend_disabled`；
2. backend enabled but no Accessibility -> `missing_accessibility`；
3. grant Accessibility -> readiness `ready` for structure operations；
4. `open_app` TextEdit -> app opens/focuses；
5. `observe` -> returns frontmost app/window summary；
6. `type_text` into local unsaved TextEdit doc -> text appears；
7. high-risk send-like click -> blocked, not executed。

## 10. 实现顺序

推荐切片：

0. **M0 Package Skeleton**
   - 新增 `packages/macos-computer-use`；
   - public models / client；
   - package build/import tests；
   - 不依赖 Taskweavn。

1. **M1 Readiness Probe**
   - package readiness models；
   - fake probe；
   - macOS probe seam；
   - tests。

2. **M2 Backend Skeleton**
   - package `MacOSComputerUseClient`；
   - `observe/open_app/wait`；
   - Plato adapter config gate；
   - TextEdit manual smoke doc。

3. **M3 Safe Mutation**
   - target resolver；
   - `click` semantic target；
   - `type_text` focused editable；
   - block unsafe targets。

4. **M4 High-Risk Confirmation**
   - risk decision；
   - blocked observation metadata；
   - authorizer seam；
   - confirmation metadata verification。

5. **M5 Local Operator Smoke**
   - one CLI/API smoke；
   - no WeChat send；
   - update release notes。

6. **M6 Package Release**
   - wheel/sdist；
   - TestPyPI；
   - clean macOS install；
   - PyPI `0.1.0` if release criteria pass。

## 11. 非目标

- 不在本方案中做 Windows；
- 不在本方案中做网络分发；
- 不在本方案中做 WeChat 真实发送；
- 不在本方案中做截图 evidence；
- 不在本方案中做完整 computer vision；
- 不在本方案中做 session-level confirmation bypass；
- 不把 AppleScript 作为默认 backend 路径。
- 不把真实 macOS 能力直接实现为 Plato 内部不可复用模块。

## 12. Open Questions

1. `ComputerUseAction` 是否应提升 `session_id/task_id/confirmation_id` 为 typed
   field，还是继续放在 metadata？
2. `click` 是否需要新增 `target_role` / `target_label` 结构化字段，减少自由文本
   target 的歧义？
3. 高风险 confirmation resolve 后，是由 Agent 重试 action，还是 runtime 自动恢复
   pending action？
4. `type_text` 第一版使用 key events 还是 clipboard paste + restore？
5. Readiness 是否需要进入 Settings/first-run UI，还是先只在 diagnostics/API 中暴露？
