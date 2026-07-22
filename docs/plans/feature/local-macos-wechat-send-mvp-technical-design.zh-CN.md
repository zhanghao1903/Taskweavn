# Local macOS WeChat Send MVP 技术方案

> Status: Historical design. The deterministic repo-local WeChat runtime,
> helper HTTP protocol, and manual smoke scripts described here were retired by
> [App-Control Tool Package Migration](app-control-tool-package-migration.zh-CN.md).
> The active implementation uses the package-backed `wechat_desktop` Agent tool.
>
> Last Updated: 2026-06-22
>
> Plan:
> [Local macOS WeChat Send MVP](local-macos-wechat-send-mvp.md)
>
> PRD:
> [Remote WeChat Message Task Via Execution Plane](../../product/remote-wechat-message-task-prd.md)
>
> Related:
> [Local Computer-Use Tool Foundation](local-computer-use-tool.md),
> [macOS Computer-Use Capability Package](macos-computer-use-package.md),
> [macOS Computer-Use Backend](macos-computer-use-backend.md),
> [Confirmation UI Spec](../../ux/confirmation-ui-spec.md),
> [Execution Plane Service And Task API](execution-plane-service-task-api.md)

---

## 1. 设计目标

本方案定义本地 macOS 微信发送 MVP 的实现边界：

```text
Local Task API
  -> TaskApiService
  -> TaskBus / AgentLoop
  -> runtime skill
  -> wechat_desktop tool
  -> app-control-protocol ToolCommand
  -> computer_use tool
  -> computer-use-macos package
  -> ToolObservation / ToolEvent evidence
  -> product-level confirmation policy when submit is requested
  -> idempotency key / result projection
  -> TaskResult / TaskError / EvidenceRef
```

目标不是一次性实现远程 ExecutionEnv，而是先验证一个更小的闭环：

- 本机 macOS；
- 真实桌面控制；
- 微信联系人定位；
- 消息草稿；
- 高风险确认；
- 发送幂等；
- 结果和证据投影。

## 2. 非目标

本方案不实现：

- LAN / remote ExecutionEnv；
- claim / lease / heartbeat；
- Windows UI Automation；
- 微信群发；
- 文件、图片、语音发送；
- 自动生成营销话术；
- CRM 写回；
- 截图证据和红线脱敏；
- 生产级安全审计。

## 3. 模块边界

当前活跃实现状态：

- 旧 deterministic WeChat runtime、repo-local WeChat adapter、send-boundary
  store、helper HTTP protocol 和旧 manual smoke scripts 已删除，不再作为活跃
  实现路径。
- Plato 现在通过 `app-control-protocol`、`computer-use-macos` 和
  `wechat-desktop-tool` 三个外部包接入桌面能力。
- 活跃模块是 `src/taskweavn/integrations/app_control/`、
  `src/taskweavn/integrations/wechat_tool/`、
  `src/taskweavn/tools/computer_use_macos_adapter.py`、
  `src/taskweavn/tools/wechat_desktop.py` 和 TaskBus / Agent loop。
- 真实 macOS 验收证据已迁移到
  [App-Control Tool Package Smoke Runbook](app-control-tool-package-smoke-runbook.zh-CN.md)；
  旧的 2026-06-22 deterministic-runtime smoke 只作为历史背景，不再证明当前
  package-backed 路径。

### 3.1 Package 层：`computer-use-macos` / `wechat-desktop-tool`

职责：

- macOS readiness；
- Accessibility observe；
- allowlisted `open_app`；
- target-resolved `click`；
- focused editable `type_text`；
- low-level risk metadata；
- sanitized result/error。

不负责：

- Plato Task / Session；
- WeChat 业务语义；
- confirmation 存储；
- LLM / AgentLoop；
- evidence 持久化。

### 3.2 Plato adapter 层

已实现模块：

```text
src/taskweavn/tools/computer_use_macos_adapter.py
```

职责：

- 根据 runtime config 创建 package client；
- 将 `ComputerUseAction` 映射到 package operation；
- 将 package result 映射回 `ComputerUseObservation`；
- 将 package readiness 映射到 sidecar/tool readiness；
- 对 high-risk package metadata 生成 blocked observation；
- 不包含 WeChat 专用流程。

### 3.3 WeChat tool 层

已实现模块：

```text
src/taskweavn/tools/wechat_desktop.py
src/taskweavn/integrations/wechat_tool/
src/taskweavn/types/wechat_desktop.py
```

职责：

- 将 Agent loop 的工具调用映射为 `wechat-desktop-tool` command builder；
- 暴露 open/focus/draft/observe/submit 等命令化能力；
- 返回 `ToolObservation` / `ToolEvent`，包含 status、failure_kind、safe
  metadata 和 evidence；
- 不判断“是否应该发送”，只执行上层已授权的命令。

### 3.4 Product policy / idempotency 层

当前 package-backed 路径不再使用 repo-local `wechat_send_boundary.py`。

职责：

- 由 TaskBus / Router / Agent loop 持有任务状态；
- 由产品层确认机制决定 submit 是否被允许；
- 由 API / task input 提供 idempotency key；
- 由结果和 evidence projection 保存安全观测，不持久化原始聊天记录；
- unknown / timeout / failure_kind 进入结构化错误和人工恢复路径。

## 4. 配置设计

新增配置应保持显式 opt-in：

```toml
[computer_use]
enabled = true
backend = "macos"

[computer_use.macos]
allowed_apps = ["WeChat", "TextEdit"]
allow_coordinate_click = false
allow_screenshot = false

[integrations.wechat_desktop]
enabled = true
app_name = "WeChat"
bundle_id = "com.tencent.xinWeChat"
require_confirmation_before_send = true
```

规则：

- 默认仍然使用 disabled/scripted backend；
- 真实 macOS backend 只在配置开启时注册；
- WeChat adapter 只在 computer-use macOS backend ready 后可用；
- screenshot 默认关闭。

## 5. 核心模型

### 5.1 Task input

```python
@dataclass(frozen=True)
class WeChatSendTaskInput:
    contact_display_name: str
    message_text: str
    contact_alias: str | None = None
    external_ref: dict[str, str] | None = None
    operator_note: str | None = None
```

校验：

- `contact_display_name` 非空；
- `message_text` 非空；
- `message_text` 长度受配置限制；
- 不接受文件、图片、语音字段；
- policy 必须包含 `requiresHumanConfirmation=true`。

### 5.2 Contact resolution

```python
@dataclass(frozen=True)
class WeChatContactCandidate:
    display_name: str
    subtitle: str | None
    stable_hint: str | None
    confidence: float

@dataclass(frozen=True)
class WeChatContactResolution:
    status: Literal["resolved", "ambiguous", "not_found", "needs_user", "failed"]
    selected: WeChatContactCandidate | None
    candidates: tuple[WeChatContactCandidate, ...]
    observation_ref: str | None
    reason: str | None
```

规则：

- `resolved` 只允许一个高置信候选；
- 多候选必须进入 ASK / intervention；
- 不存储完整联系人列表，只存储安全摘要。

### 5.3 Draft state

```python
@dataclass(frozen=True)
class WeChatDraftState:
    contact_summary: str
    message_hash: str
    message_preview: str
    draft_observation_ref: str | None
    status: Literal["drafted", "failed"]
```

`message_preview` 只用于 confirmation/UI。持久化时可以存完整消息，也可以按后续隐私策略只存 hash + preview；MVP 可存任务输入中的完整 `message_text`，但不得采集微信窗口中无关聊天内容。

### 5.4 Action fingerprint

```python
@dataclass(frozen=True)
class WeChatSendActionFingerprint:
    execution_id: str
    idempotency_key: str
    contact_summary_hash: str
    message_hash: str
    draft_observation_ref: str | None
    app_identity: str
```

用途：

- 绑定 confirmation；
- 防止确认 A 联系人后发送 B 联系人；
- 防止确认 A 文案后发送 B 文案；
- 防止重复发送。

### 5.5 Send boundary

```python
SendBoundaryStatus = Literal[
    "not_started",
    "drafted",
    "confirmation_requested",
    "confirmed",
    "send_attempted",
    "sent",
    "not_sent",
    "unknown",
]
```

状态语义：

| Status | Meaning | Retry rule |
|---|---|---|
| `not_started` | 还没有操作微信。 | 可重试。 |
| `drafted` | 已写入草稿，未确认。 | 可恢复到确认。 |
| `confirmation_requested` | 已发起确认。 | 等待用户。 |
| `confirmed` | 用户已确认，尚未尝试发送。 | 可继续发送。 |
| `send_attempted` | 已尝试点击发送，结果未落定。 | 不自动重试。 |
| `sent` | 发送动作成功完成或足够可信。 | 终态，不重发。 |
| `not_sent` | 用户拒绝/取消或安全失败前未发送。 | 终态，需新任务。 |
| `unknown` | 可能已发送，也可能未发送。 | 终态/人工复核，不自动重试。 |

## 6. SQLite 持久化建议

实现表：

```sql
CREATE TABLE IF NOT EXISTS wechat_send_boundaries (
  execution_id TEXT PRIMARY KEY,
  idempotency_key TEXT NOT NULL,
  task_ref_kind TEXT NOT NULL,
  task_ref_id TEXT NOT NULL,
  contact_summary_hash TEXT NOT NULL,
  message_hash TEXT NOT NULL,
  action_fingerprint TEXT NOT NULL,
  status TEXT NOT NULL,
  confirmation_id TEXT,
  draft_observation_ref TEXT,
  send_observation_ref TEXT,
  result_ref TEXT,
  error_ref TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_wechat_send_boundaries_idempotency
  ON wechat_send_boundaries(idempotency_key);

CREATE UNIQUE INDEX IF NOT EXISTS idx_wechat_send_boundaries_fingerprint
  ON wechat_send_boundaries(action_fingerprint);
```

最小策略：

- `idempotency_key` 防重复任务；
- `action_fingerprint` 防重复发送动作；
- `unknown` 和 `sent` 都阻止自动发送；
- `drafted` / `confirmation_requested` 支持重启恢复到确认状态。

## 7. 执行流程

### 7.1 Publish / dispatch

1. `POST /api/v1/tasks` 收到 `communication.wechat.send_message`。
2. `TaskApiService` 校验 input/policy。
3. 根据 `idempotencyKey` 查询 send-boundary：
   - `sent`: 返回已有 result；
   - `unknown`: 返回 blocked/manual-review；
   - `not_sent`: 返回 terminal result；
   - 其他状态：恢复执行。
4. 发布到 TaskBus。
5. AgentLoop 获得任务上下文。

### 7.2 Readiness

1. `PlatoMacOSComputerUseAdapter.readiness()`。
2. 校验：
   - macOS；
   - feature flag；
   - Accessibility；
   - WeChat allowlist；
   - package import。
3. 不 ready 时：
   - task failed 或 waiting_for_user，取决于是否需要用户操作；
   - 写入 safe `TaskError`。

### 7.3 Draft

1. `WeChatDesktopAdapter.open_or_focus()`。
2. `WeChatDesktopAdapter.resolve_contact(input)`。
3. `WeChatDesktopAdapter.draft_message(resolution, message_text)`。
4. 写入 send-boundary `drafted`。
5. 生成 action fingerprint。

### 7.4 Confirmation

1. 调用 `request_confirmation`。
2. confirmation body 必须包含：
   - 联系人摘要；
   - 完整消息预览；
   - 风险说明；
   - `action_fingerprint`；
   - `send_boundary_status=drafted`。
3. TaskBus 进入 `waiting_for_user`。
4. 用户拒绝：
   - send-boundary -> `not_sent`；
   - task result/error 记录未发送。
5. 用户确认：
   - 读取 confirmation；
   - 验证 action fingerprint；
   - send-boundary -> `confirmed`。

### 7.5 Send

1. `WeChatDesktopAdapter.send_after_confirmation(fingerprint)`。
2. 发送前再次 observe 当前窗口：
   - app 仍为 WeChat；
   - 当前联系人仍匹配；
   - 输入框文本仍匹配 message hash 或可验证摘要。
3. send-boundary -> `send_attempted`。
4. 执行一次发送动作。
5. 根据 package/adapter observation：
   - 明确成功：`sent`；
   - 明确未发送：`not_sent`；
   - 不确定：`unknown`。

## 8. Confirmation authorizer

建议模块：

```text
src/taskweavn/runtime/confirmation_authorizer.py
```

核心接口：

```python
class ConfirmationAuthorizer(Protocol):
    def verify_wechat_send(
        self,
        *,
        confirmation_id: str,
        action_fingerprint: WeChatSendActionFingerprint,
    ) -> ConfirmationAuthorizationResult:
        ...
```

验证规则：

- confirmation 存在；
- status 为 resolved/approved；
- confirmation scope 匹配 execution/task；
- embedded action fingerprint 匹配；
- 未过期；
- 未被用于另一次 send；
- `approve_session` 不自动放行后续不同 fingerprint。

## 9. WeChat adapter 策略

### 9.1 不做坐标脚本

首版不应硬编码绝对坐标。优先顺序：

1. Accessibility 语义 target；
2. bounded text/role target；
3. 用户 intervention；
4. debug-only 坐标 fallback。

### 9.2 操作分解

```python
class WeChatDesktopAdapter:
    def readiness(self) -> WeChatReadiness: ...
    def open_or_focus(self) -> WeChatOperationResult: ...
    def resolve_contact(self, input: WeChatSendTaskInput) -> WeChatContactResolution: ...
    def draft_message(
        self,
        resolution: WeChatContactResolution,
        message_text: str,
    ) -> WeChatDraftState: ...
    def send_after_confirmation(
        self,
        fingerprint: WeChatSendActionFingerprint,
    ) -> WeChatSendAttemptResult: ...
```

### 9.3 失败分类

| Code | Meaning | Runtime behavior |
|---|---|---|
| `wechat_not_installed` | 未安装微信。 | failed / setup required。 |
| `wechat_not_logged_in` | 未登录或锁定。 | waiting_for_user 或 failed。 |
| `wechat_not_observable` | Accessibility 无法读取目标。 | failed / setup required。 |
| `contact_not_found` | 未找到联系人。 | ASK / failed safe。 |
| `contact_ambiguous` | 多个候选。 | ASK。 |
| `draft_failed` | 无法写入输入框。 | failed, not_sent。 |
| `confirmation_required` | 等待用户确认。 | waiting_for_user。 |
| `confirmation_mismatch` | 确认与 action 不匹配。 | failed, not_sent。 |
| `send_unknown` | 尝试发送后状态不明。 | unknown, manual review。 |

### 9.4 W7: verified input + keyboard submit

2026-06-20 confirm smoke 结果显示，当前 send boundary 的瓶颈不在 confirmation，
而在微信“发送”按钮的 Accessibility lookup：WeChat 的 tree 较大且局部节点可能很慢，
导致 AppleScript 在扫描或点击阶段 timeout。继续寻找 send button 会让 MVP 依赖一个
脆弱目标。

W7 的最终决策是：本地 MVP 不点击“发送”按钮，改为使用更贴近真实用户操作的
keyboard Return submit。这个路径的前提是输入框和草稿内容已经在 confirmation 前被
验证过。

```text
resolve contact
  -> focus message input
  -> clear existing draft
  -> type exact message
  -> request confirmation with fingerprint
  -> on confirm, submit with keyboard Return
  -> record keyboard submit evidence
```

#### 9.4.1 Focus and draft invariants

发送前必须满足：

- 联系人已经通过受控路径选中；
- 当前输入框不是搜索框；
- 输入框可写；
- 旧草稿已通过 Select All + Delete 清空；
- 目标消息已通过 `type_text` 写入；
- confirmation payload 绑定同一 contact/message fingerprint。

这些事实通过 observation ref 和 evidence metadata 表达，不持久化原始聊天上下文。

#### 9.4.2 Submit boundary

确认后发送边界只做最小动作：

```text
frontmost WeChat process
  -> key code 36
  -> short bounded delay
  -> return phase=keyboard_submit, send_method=keyboard_return,
     send_attempted=true
```

关键规则：

- keyboard submit 只在 confirmation approved 且 fingerprint 匹配后执行；
- submit 之前不再扫描 `AXFocusedUIElement`，避免第二次慢树扫描导致 timeout；
- submit 之后不读取原始聊天内容；
- 如果 AppleScript 在 submit 过程中失败或 timeout，保持
  `wechat_send_unknown` / manual review，不自动重试；
- 如果 submit 返回 ok，MVP 中标记为 `sent`，但语义是
  “send action completed”，不是微信服务端 delivery receipt。

### 9.5 Accepted local smoke

2026-06-22 的 controlled confirm/send-once smoke 已通过：

- contact：`文件传输助手`；
- idempotency key：`manual-wechat-smoke-20260622-keyboard-submit-e05a-03`；
- execution id：`exec_c47432a39d1b5a0da94d15d16dd1827e`；
- confirmation id：`217fddb7310f47b4968f852734457e64`；
- result：`wechat_send_result`，`sendBoundaryStatus=sent`；
- evidence：`phase=keyboard_submit`、`send_method=keyboard_return`、
  `send_attempted=true`、`confirmation_required=true`、
  `confirmed_by_user=true`；
- replay：同 key terminal replay 返回同一 execution 和 `done` 终态，没有第二次发送。

### 9.6 Timeout / error taxonomy

下一阶段仍需保留明确的错误分类：

| Failure kind | Boundary status | send_attempted | Plato mapping | Retry rule |
|---|---|---:|---|---|
| `window_unavailable` | `not_sent` | false | `wechat_not_observable` / setup | 用户打开主窗口后可重试 |
| `contact_not_found` | `not_sent` | false | `wechat_contact_not_found` | 用户复核联系人后可重试 |
| `contact_ambiguous` | `not_sent` | false | `wechat_contact_ambiguous` | 需要人工消歧 |
| `input_not_focused` | `not_sent` | false | `wechat_input_not_ready` | 修复 UI/focus 后可重试 |
| `type_text_failed` | `not_sent` | false | `wechat_draft_failed` | 修复输入后可重试 |
| `keyboard_submit_error` | `unknown` | unknown/true | `wechat_send_unknown` | 不自动重试，人工复核 |
| `accessibility_error` | `not_sent` 或 `unknown` | unknown/false | `wechat_not_observable` | 修复权限/UI 后重试 |

当前 MVP 已跑通 keyboard submit。更细的 WeChat-specific error code mapping 可以作为
后续 hardening，不阻塞本地 vertical proof。

## 10. Result / Evidence 投影

成功结果 payload：

```json
{
  "kind": "wechat_send_result",
  "contactSummary": "张三",
  "messagePreview": "你好，样品已寄出，麻烦查收。",
  "sendBoundaryStatus": "sent",
  "confirmationId": "confirmation:...",
  "evidenceRefs": [...]
}
```

失败结果 payload：

```json
{
  "kind": "wechat_send_error",
  "phase": "contact_resolution",
  "sendBoundaryStatus": "not_sent",
  "retryable": false,
  "operatorActionNeeded": "Choose the exact contact manually.",
  "evidenceRefs": [...]
}
```

Evidence refs：

- task request；
- readiness observation；
- contact resolution summary；
- draft observation；
- confirmation event；
- send observation；
- final result/error。

禁止默认持久化：

- 原始聊天记录；
- 全量 Accessibility tree；
- 未脱敏截图；
- 凭据、二维码、支付、安全提示。

## 11. UI 投影要求

复用现有 Main Page / Activity / confirmation 机制：

- `running`: 正在打开/查找/草稿；
- `waiting_for_user`: 等待确认发送；
- `done`: 已发送或用户拒绝后安全完成，具体看 result kind；
- `failed`: 前置检查或安全边界失败；
- `rejected`: policy 不允许或 capability 缺失。

确认 UI 最小内容：

- 标题：确认发送微信消息；
- 联系人；
- 消息全文；
- 风险说明；
- 操作按钮：发送 / 取消；
- 可选：查看证据或任务详情。

## 12. 测试矩阵

自动化测试使用 fake package client 和 fake WeChat adapter。

| Area | Cases |
|---|---|
| package adapter | package missing, disabled, ready, missing accessibility, operation error |
| readiness | WeChat missing, not logged in, not observable, ready |
| contact resolver | resolved, not_found, ambiguous, needs_user |
| draft | exact text drafted, draft failed, text too long |
| confirmation | pending blocks, reject, approve, mismatch, expired |
| idempotency | duplicate after sent, restart after drafted, unknown blocks retry |
| result/evidence | success payload, failure payload, safe evidence refs |
| UI contract | waiting_for_user projection, final Activity entries |

手动 smoke：

旧 `scripts/manual_wechat_send_smoke.py` 已删除。当前 package-backed smoke
使用 [App-Control Tool Package Smoke Runbook](app-control-tool-package-smoke-runbook.zh-CN.md)
和 `scripts/manual_wechat_desktop_tool_smoke.py`：

1. Smoke A：只验证 package import / CLI contract，不打开微信。
2. Smoke B：打开微信、聚焦 `文件传输助手`、写入草稿、observe；不得提交。
3. Smoke C：在单独授权后，使用 fresh idempotency key 执行一次
   `--allow-submit --confirm-submit SEND`。
4. Smoke D：复用同一个 idempotency key 验证不会重复发送。

真实发送 smoke 仍需人工确认微信窗口中的联系人、草稿内容和最终聊天记录。

## 13. 历史实施顺序

以下 W1-W7 是旧 deterministic runtime 的实施顺序，仅作为历史背景。
当前实现和验收以
[App-Control Tool Package Migration](app-control-tool-package-migration.zh-CN.md)
和 [App-Control Tool Package Smoke Runbook](app-control-tool-package-smoke-runbook.zh-CN.md)
为准。

推荐顺序：

1. **W1 Adapter readiness**
   - package dependency；
   - Plato adapter；
   - readiness tests。
2. **W2 WeChat draft-only**
   - fake adapter；
   - real adapter skeleton；
   - contact/draft tests；
   - no send。
3. **W3 Confirmation gate**
   - confirmation request；
   - fingerprint/context binding；
   - authorizer。
4. **W4 Send-boundary store**
   - SQLite；
   - idempotency；
   - restart recovery。
5. **W5 Send execution + result/evidence projection**
   - send-after-confirmation；
   - result/error payload；
   - Activity；
   - safe evidence refs。
6. **W6 Runtime wiring**
   - `communication.wechat.send_message` local Task API / AgentLoop route；
   - fake integration tests；
   - idempotency replay resume；
   - sidecar opt-in assembly；
   - result/error/evidence query。
7. **Manual real WeChat smoke**
   - local checklist；
   - release notes；
   - known limits。
8. **W7 verified input + keyboard submit**
   - clear existing draft before typing；
   - submit with keyboard Return after confirmation；
   - accepted controlled smoke against `文件传输助手`。

## 14. Blockers

- WeChat macOS Accessibility tree stability is unknown.
- WeChat bundle id / localized app name must be verified.
- Safe send target identification may require manual smoke before code is
  considered reliable.
- Screenshot evidence is intentionally blocked until redaction exists.
- Business use needs security and abuse policy beyond this MVP.

## 15. 当前 Runtime Wiring Notes

当前 package-backed 路径不再使用专用 `WeChatSendRuntimeHandler`。

- `communication.wechat.send_message` 由 Router/Task API 发布到 TaskBus。
- ExecutionEnv 只描述本地 app-control capability，不是 app-specific runtime。
- Agent loop 根据 runtime skill 使用 `wechat_desktop` 和 `computer_use` 工具。
- `wechat_desktop` 工具通过 `wechat-desktop-tool` package 发出
  `ToolCommand`，并接收 `ToolObservation` / `ToolEvent`。
- `computer_use` macOS backend 通过 `computer-use-macos` package 执行 direct 或
  helper-backed app-control 操作。
- submit 仍必须由产品层策略或人工授权控制；package 工具只执行命令，不决定业务
  是否应该发送。
- 旧 deterministic runtime 的 2026-06-22 smoke 已被三包路径取代，不能作为当前
  package-backed 验收证据。

## 16. Manual Smoke Checklist

真实微信 smoke 必须单独执行和记录。当前检查清单以
[App-Control Tool Package Smoke Runbook](app-control-tool-package-smoke-runbook.zh-CN.md)
为准，使用 `scripts/manual_wechat_desktop_tool_smoke.py` 和三包路径：

1. 确认 `app-control-protocol`、`computer-use-macos` 和
   `wechat-desktop-tool` 来自当前 `uv.lock`。
2. 确认旧 `macos-computer-use` compatibility package 不是 Plato dependency。
3. 确认 macOS Accessibility 已授权给实际控制 UI 的进程或 helper app。
4. 确认微信已安装、已登录、未锁定。
5. 使用受控测试联系人 `文件传输助手` 和非敏感唯一测试消息。
6. 先执行 no-submit focus/draft/observe smoke，并人工确认没有发送。
7. 只有获得单独授权后，才执行带 `--allow-submit --confirm-submit SEND`
   的 submit-once smoke。
8. 使用同一 idempotency key 执行 replay/no-duplicate 检查。

## 17. 下一步任务 Prompt

```text
Use the product-workflow-gate skill first.

Task:
Run the package-backed Local macOS WeChat smoke and archive evidence.

Do not change frontend UI.
Do not use retired scripts or repo-local helper/runtime endpoints.
Do not run submit without explicit authorization for that run.
Do not auto-retry unknown submit or send_attempted boundaries.
Do not add remote ExecutionEnv, LAN auth, Windows, or screenshot evidence.

Required work:
1. Read app-control-tool-package-smoke-runbook.zh-CN.md.
2. Run Smoke A.
3. Run Smoke B against `文件传输助手` and archive evidence JSON.
4. After explicit authorization, run Smoke C with a fresh idempotency key.
5. Run Smoke D with the same idempotency key and verify no duplicate message.
6. Update the migration plan/runbook with the actual evidence paths and any
   blocker.

Output:
- files changed
- Smoke A result
- Smoke B result
- Smoke C result
- Smoke D result
- tests run
- remaining blockers
```
