# Plato Computer Use Helper.app 技术方案

> Status: proposed / helper-boundary planning
>
> Last Updated: 2026-06-26
>
> Related:
> [macOS Computer-Use Capability Package](macos-computer-use-package.md),
> [macOS Computer-Use Package Technical Design](macos-computer-use-package-technical-design.zh-CN.md),
> [macOS Computer-Use Backend](macos-computer-use-backend.md),
> [macOS Computer-Use Backend Technical Design](macos-computer-use-backend-technical-design.zh-CN.md),
> [Local macOS WeChat Send MVP](local-macos-wechat-send-mvp.md),
> [Execution Plane Service And Task API](execution-plane-service-task-api.md),
> [ADR-0020 Execution Plane As Service / Task API Boundary](../../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md)

---

## 1. 背景

Plato 已经验证了本地 macOS WeChat send MVP，但当前开发链路暴露出一个稳定性问题：
macOS TCC 权限主体不稳定。

在开发环境中，同一个操作可能由不同进程发起：

- Electron app；
- Electron helper / renderer；
- Node；
- `uv`；
- `.venv/bin/python`；
- `/opt/anaconda3/bin/python3.12`；
- Terminal / Codex 启动的 shell；
- 未来 packaged Plato。

macOS TCC 不按业务任务、session 或 Plato workspace 授权，也不是简单按 PID 持久授权。
PID 只用于运行时定位当前进程。持久授权通常与进程的 executable path、bundle id、
code signing requirement、responsible process 和 app bundle identity 相关。

如果让频繁变化的 Electron dev process 或随机 Python interpreter 直接调用
Accessibility、Screen Recording、keyboard/input 或 Apple Events，用户会反复遇到：

- 明明授权过，但当前链路仍显示 missing accessibility；
- Terminal smoke 可用，Electron sidecar 不可用；
- 打包/重启/换 Python 后权限失效；
- 错误证据无法解释到底哪个进程缺权限。

因此需要把 macOS TCC 权限主体从 Plato 主应用和开发进程中拆出来，形成一个稳定的
Helper app。

## 2. 目标

定义 `Plato Computer Use Helper.app` 的技术边界：

1. 固定 macOS TCC 权限主体；
2. 承载 Accessibility、Screen Recording、Automation / Apple Events 等敏感权限；
3. 通过 IPC/localhost API 向 Plato 暴露 computer-use 能力；
4. 内部消费独立发布的 `macos-computer-use` 包；
5. 同时支持开发阶段和正式发布阶段；
6. 输出可投射到 Plato Settings、Conversation、Audit、Diagnostic Bundle 的 readiness 和 error evidence。

## 3. 非目标

本方案不实现：

- `macos-computer-use` 包自身的 API 设计；
- WeChat adapter 的联系人解析和发送策略；
- 远程 ExecutionEnv 注册/claim/lease；
- Windows computer-use；
- 自动绕过 macOS 权限弹窗；
- 自动授予 TCC 权限；
- root/privileged helper；
- 系统级 MDM 部署策略。

## 4. 三层边界

```text
Plato.app
  Product / Control Plane
  - Session / Task / Confirmation / Audit / UI
  - Router / Execution Plane client
  - Settings readiness display
  - Does not call macOS AX directly

Plato Computer Use Helper.app
  Permission / Capability Process
  - Stable macOS app identity
  - Owns TCC permissions
  - Runs computer-use operations
  - Exposes local IPC/HTTP API
  - Returns structured readiness/result/evidence

macos-computer-use
  Reusable Capability Package
  - LLM-free Python package
  - macOS observe/open_app/click/type_text/app adapters
  - No Plato Session/Task/Confirmation semantics
```

依赖方向：

```text
Plato.app
  -> Helper API
      -> macos-computer-use package
          -> macOS Accessibility / Screen Recording / input APIs
```

禁止方向：

```text
Plato.app
  -> direct AX / Screen Recording / keyboard event calls

Plato sidecar Python
  -> direct AX / Screen Recording / keyboard event calls in production path
```

## 5. Helper 身份设计

### 5.1 Bundle ID

建议 bundle id：

```text
com.taskweavn.plato.computer-use-helper
```

开发阶段可使用独立 dev bundle id：

```text
com.taskweavn.plato.computer-use-helper.dev
```

建议原则：

- release helper 使用稳定 bundle id；
- dev helper 使用稳定 dev bundle id；
- 不要在同一个 bundle id 下频繁改变 signing identity；
- 不要让未打包 Python interpreter 成为 TCC 权限主体；
- Settings UI 必须显示当前 helper bundle id、path、version 和 readiness。

### 5.2 Process Identity 硬约束

Helper 不能只是启动外部 Python 脚本的壳。

真正调用以下能力的进程必须属于稳定 Helper identity：

- Accessibility tree read；
- AXPress；
- mouse / keyboard event；
- Screen Recording；
- app-specific Automation / Apple Events；
- pasteboard-based text insertion，如果后续启用；
- screenshot capture，如果后续启用。

不推荐：

```text
Helper.app
  -> /opt/anaconda3/bin/python3.12 script.py
      -> AX calls
```

这种结构会让 TCC 很可能归因到外部 Python interpreter，而不是 Helper。

推荐：

```text
Helper.app
  Contents/MacOS/PlatoComputerUseHelper
    - embedded Python runtime or packaged executable
    - imports bundled macos_computer_use
    - performs AX calls in the helper-owned process tree
```

如果第一版必须用 subprocess，必须在 readiness 里明确报告实际执行 AX 调用的
process path，并把该方案标为 dev-only。

### 5.3 Signing

开发阶段：

- 可以先用 ad-hoc signing 或本地 self-signed certificate；
- 目标是稳定 bundle id、固定安装路径、减少 rebuild；
- 不要求 notarization；
- 允许用户手动授权 dev helper。

正式发布：

- Helper 必须随 Plato 一起 signed；
- Helper 和 Plato 最好使用同一 Team ID；
- Release artifact 需要 notarization；
- Helper 版本必须可诊断；
- 权限引导文案必须说明用户在系统设置中看到的是 `Plato Computer Use Helper`。

## 6. 安装与分发

### 6.1 用户视角

用户只安装一个产品：

```text
Plato.dmg / Plato.pkg
```

安装后系统中可以存在两个 app bundle：

```text
Plato.app
Plato Computer Use Helper.app
```

用户不应被要求手动下载两个产品。但在 macOS 权限设置中，用户可能看到
`Plato Computer Use Helper`，这是预期行为。

### 6.2 Release 安装路径

候选 A：显式 app 路径

```text
/Applications/Plato.app
/Applications/Plato Computer Use Helper.app
```

优点：

- TCC 主体清晰；
- 用户容易在系统设置中理解；
- helper 可独立重启和诊断。

缺点：

- Applications 中出现两个 app，产品感较弱。

候选 B：嵌入 Plato 支持目录

```text
/Applications/Plato.app
~/Library/Application Support/Plato/Plato Computer Use Helper.app
```

优点：

- 用户安装感知更像一个产品；
- helper 生命周期由 Plato 管理。

缺点：

- 路径迁移和更新要更谨慎；
- 用户在 TCC 设置中看到 helper 时需要 UI 解释。

候选 C：嵌入主 app bundle

```text
/Applications/Plato.app/Contents/Library/LoginItems/Plato Computer Use Helper.app
```

优点：

- 打包完整；
- release 管理集中。

缺点：

- 更新、启动和 TCC 归因需要更严格验证；
- 对当前阶段实现复杂度偏高。

第一版建议：**候选 B**。如果 TCC 验证不稳定，降级到候选 A。

### 6.3 开发安装路径

开发阶段建议固定安装：

```text
~/Applications/Plato Computer Use Helper Dev.app
```

或者：

```text
~/Library/Application Support/PlatoDev/Plato Computer Use Helper Dev.app
```

开发时不要每次启动 Electron 都 rebuild helper。推荐流程：

1. 单独 build/install helper dev app；
2. 用户给 helper dev app 授权；
3. Electron dev app 通过配置连接 helper；
4. helper 通过配置加载本地 editable `macos-computer-use` 或 bundled package。

## 7. Helper 启动模式

### 7.1 Manual Run Mode

用于早期开发：

```text
open "~/Applications/Plato Computer Use Helper Dev.app"
```

Helper 启动本地 server：

```text
127.0.0.1:<dynamic_port>
```

端口写入：

```text
~/Library/Application Support/PlatoDev/computer-use-helper.json
```

### 7.2 Plato Managed Mode

Plato 启动时：

1. 查找 helper manifest；
2. 检查 helper version；
3. 如果 helper 未运行，启动 helper；
4. 等待 `/healthz`；
5. 调用 `/v1/readiness`；
6. 将 readiness 投射到 Settings 和 capability registry。

### 7.3 Release Background Mode

正式产品可以进一步支持 login item / launch service，但第一版不要求。

不建议第一版实现 privileged daemon。computer-use 不需要 root。

## 8. IPC / Local API

第一版建议使用 localhost HTTP API。原因：

- 与现有 sidecar HTTP 模型一致；
- 易测试；
- 易记录 request/response evidence；
- 未来可以换成 XPC，不影响 Plato 上层 contract。

### 8.1 安全边界

Helper 只监听 loopback：

```text
127.0.0.1
::1
```

每次启动生成本地 token：

```json
{
  "endpoint": "http://127.0.0.1:49321",
  "tokenRef": "stored in owner-only file",
  "pid": 12345,
  "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
  "version": "0.1.0"
}
```

Manifest 文件权限必须 owner-only。

Plato 请求必须带：

```text
Authorization: Bearer <local helper token>
```

第一版不接受远程网络请求。远程 ExecutionEnv 以后单独设计。

### 8.2 API Surface

```text
GET  /healthz
GET  /v1/info
GET  /v1/readiness
POST /v1/operations/observe
POST /v1/operations/open-app
POST /v1/operations/click
POST /v1/operations/type-text
POST /v1/operations/press-key
POST /v1/apps/wechat/draft-message
POST /v1/apps/wechat/send-confirmed
POST /v1/shutdown
```

第一版最小实现可以只暴露：

```text
GET  /healthz
GET  /v1/info
GET  /v1/readiness
POST /v1/apps/wechat/draft-message
POST /v1/apps/wechat/send-confirmed
```

通用 operations 可以跟随 `macos-computer-use` 包成熟度逐步开放。

### 8.3 Request Envelope

```json
{
  "requestId": "req_...",
  "idempotencyKey": "plato:session:task:operation",
  "caller": {
    "app": "Plato",
    "workspaceId": "workspace-id",
    "sessionId": "session-id",
    "taskExecutionId": "exec-id"
  },
  "operation": "wechat.draft_message",
  "input": {},
  "policy": {
    "allowedApps": ["WeChat"],
    "allowScreenshot": false,
    "allowCoordinateClick": false,
    "requiresConfirmationBeforeSend": true,
    "maxTextLength": 1000
  }
}
```

### 8.4 Response Envelope

```json
{
  "requestId": "req_...",
  "operation": "wechat.draft_message",
  "status": "ok",
  "success": true,
  "summary": "Drafted message for contact 文件传输助手.",
  "failureKind": null,
  "phase": "draft",
  "risk": {
    "level": "high",
    "requiresConfirmation": true,
    "reason": "External message send requires confirmation.",
    "actionFingerprint": "sha256:..."
  },
  "evidence": {
    "kind": "computer_use_operation",
    "safeSummary": "WeChat contact resolved and draft inserted.",
    "targetApp": "WeChat",
    "targetContact": "文件传输助手",
    "redaction": "no_raw_chat_history"
  },
  "diagnostics": {}
}
```

Statuses：

```text
ok
blocked
needs_user
not_available
failed
unknown
```

`unknown` 表示可能发生了外部副作用但无法确认，Plato 不允许自动重试。

## 9. Readiness Schema

Helper readiness 必须区分三类状态：

1. Helper 自身是否可用；
2. macOS permission 是否可用；
3. app-specific capability 是否可用。

### 9.1 Schema

```json
{
  "status": "ready",
  "helper": {
    "installed": true,
    "running": true,
    "version": "0.1.0",
    "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
    "path": "/Users/.../Plato Computer Use Helper Dev.app",
    "pid": 12345,
    "codeSignature": {
      "teamId": null,
      "signingMode": "ad_hoc",
      "stableRequirement": false
    }
  },
  "permissions": {
    "accessibility": {
      "status": "granted",
      "trusted": true,
      "checkedByProcessPath": ".../Contents/MacOS/PlatoComputerUseHelper"
    },
    "screenRecording": {
      "status": "not_required",
      "available": null
    },
    "automation": {
      "status": "unknown",
      "targets": {}
    }
  },
  "operations": {
    "observe": "ready",
    "open_app": "ready",
    "type_text": "ready",
    "wechat_draft_message": "ready",
    "wechat_send_confirmed": "ready"
  },
  "apps": {
    "WeChat": {
      "allowed": true,
      "installed": true,
      "running": true,
      "loggedIn": "unknown",
      "frontmostReady": false,
      "capability": "needs_user"
    }
  },
  "setupHints": [
    {
      "code": "open_accessibility_settings",
      "label": "Grant Accessibility to Plato Computer Use Helper"
    }
  ],
  "diagnostics": {
    "platform": "Darwin",
    "pythonRuntime": "embedded",
    "packageVersion": "macos-computer-use 0.1.0"
  }
}
```

### 9.2 Top-level Status

```text
ready
helper_not_installed
helper_not_running
helper_untrusted
missing_accessibility
missing_screen_recording
automation_not_authorized
app_not_allowed
app_not_installed
app_needs_user
error
```

### 9.3 Functional Probes

Readiness 不能只报告 API 权限布尔值，还要支持 bounded functional probe：

```text
observe_frontmost_app
open_allowed_app
focus_text_field
type_draft_without_submit
wechat_contact_resolution_no_send
```

所有 probe 必须默认 no-send、no-delete、no-payment。

## 10. Plato 集成

### 10.1 Runtime Config

Plato 增加 helper 级配置：

```toml
[computer_use]
enabled = true
provider = "helper"

[computer_use.helper]
enabled = true
endpoint_manifest_path = "~/Library/Application Support/PlatoDev/computer-use-helper.json"
auto_start = true
expected_bundle_id = "com.taskweavn.plato.computer-use-helper.dev"
min_version = "0.1.0"

[computer_use.macos]
allowed_apps = ["WeChat", "TextEdit"]
allow_coordinate_click = false
allow_screenshot = false

[integrations.wechat_desktop]
enabled = true
require_confirmation_before_send = true
```

`wechat` 不应成为一级 runtime config 对象。它属于 app integration / skill / workflow
capability 配置。

### 10.2 Capability Registry

Plato 只在 helper readiness 满足时注册：

```text
communication.wechat_desktop_send
computer_use.observe
computer_use.open_app
computer_use.type_text
```

当 helper 不可用时，Router / Execution Plane 应返回：

```text
capability_not_available
```

同时附带具体 evidence：

```text
helper_not_running
missing_accessibility
app_not_allowed
wechat_needs_user
```

### 10.3 Confirmation

高风险动作仍由 Plato 管：

```text
Plato
  -> ask helper to draft
  -> helper returns actionFingerprint
  -> Plato creates confirmation
  -> user confirms
  -> Plato sends send-confirmed request with confirmation proof
  -> helper verifies fingerprint and sends
```

Helper 不创建 confirmation UI。

Helper 必须拒绝没有 confirmation proof 的 send operation。

## 11. WeChat Send Helper Flow

```text
User input / Task API
  -> Router / TaskRequest
  -> Execution Plane
  -> capability match: communication.wechat_desktop_send
  -> Helper readiness
  -> /v1/apps/wechat/draft-message
      - open/focus WeChat
      - resolve contact
      - clear input
      - type exact draft
      - return fingerprint
  -> Plato confirmation
  -> /v1/apps/wechat/send-confirmed
      - verify same contact/message/fingerprint
      - keyboard submit
      - observe post-send boundary
  -> TaskResult / TaskError / EvidenceRef
```

失败分类必须保留：

```text
phase:
  readiness
  open_app
  contact_resolution
  draft
  confirmation
  send
  post_send_observe

failureKind:
  helper_not_available
  missing_accessibility
  app_not_allowed
  app_not_installed
  app_not_ready
  contact_not_found
  contact_ambiguous
  input_not_focused
  confirmation_missing
  confirmation_mismatch
  send_unknown
  operation_timeout
  unexpected_error
```

## 12. Dev Packaging

### 12.1 第一阶段：Repo 内 helper prototype

```text
apps/plato-computer-use-helper/
  pyproject.toml
  src/plato_computer_use_helper/
    server.py
    models.py
    manifest.py
    readiness.py
    operations.py
  packaging/macos/
    Info.plist
    build_helper_app.sh
```

或者作为 `packages/` 下的内部包：

```text
packages/plato-computer-use-helper/
```

第一阶段不需要对外发布 Helper。它是 Plato 的产品组件，不是社区包。

### 12.2 Dev helper 如何加载本地 package

允许 dev manifest 指向本地 editable package：

```json
{
  "macosComputerUsePackagePath": "/private/tmp/macos-computer-use/src",
  "mode": "development"
}
```

但实际 AX 调用仍必须发生在 helper process 内。不能退化成外部 Python 进程做 AX。

### 12.3 Dev 验收

最小 dev 验收：

1. helper 可启动；
2. `/healthz` 返回；
3. `/v1/info` 显示 bundle id/path/version；
4. `/v1/readiness` 能明确报告 Accessibility granted/missing；
5. TextEdit no-send smoke 通过；
6. WeChat reject/no-send contact resolution smoke 通过；
7. 不启用 helper 时 Plato 返回 `capability_not_available` 且 conversation 显示具体原因；
8. helper 启用且授权后，Plato 可以注册 `communication.wechat_desktop_send`。

## 13. Release Packaging

### 13.1 Artifact

正式产品分发一个安装包：

```text
Plato.dmg
```

里面包含：

```text
Plato.app
Plato Computer Use Helper.app
```

或者 `Plato.app` 安装时释放 helper 到 Application Support。

### 13.2 Version Compatibility

Plato 必须检查 helper 版本：

```text
helper.version >= min_version
helper.apiVersion compatible with Plato
macos-computer-use package version compatible
```

不兼容时：

- 不注册 computer-use capability；
- Settings 显示升级建议；
- Router/Execution 返回 `capability_not_available` 和 `helper_version_mismatch`。

### 13.3 Update Strategy

第一版：

- Plato 启动时检查 helper version；
- 如果 bundled helper version 更新，提示用户重新安装/更新 helper；
- 不做后台静默替换已授权 helper，避免 TCC 状态变化难以解释。

后续：

- 可设计 helper self-update 或 installer update。

## 14. Security

### 14.1 Local API

- 只监听 loopback；
- startup token；
- manifest owner-only；
- request id / idempotency key；
- policy must be explicit；
- no remote caller in first release。

### 14.2 Operation Policy

默认拒绝：

- 坐标点击；
- screenshot；
- password field；
- system dialog；
- unallowlisted app；
- external send without confirmation proof；
- ambiguous target；
- stale target；
- repeated unknown send。

### 14.3 Evidence Redaction

Helper 不返回：

- raw chat transcript；
- full screenshot；
- password value；
- unrelated app UI tree；
- credential/token。

Helper 返回：

- target app；
- phase；
- safe summary；
- selected contact name；
- message hash/fingerprint；
- operation result；
- bounded diagnostics。

## 15. Testing Strategy

### 15.1 Unit Tests

- manifest read/write；
- auth token verification；
- readiness schema；
- status mapping；
- operation envelope validation；
- idempotency behavior；
- redaction policy。

### 15.2 Integration Tests

使用 fake `macos-computer-use` client：

- helper readiness ready/missing；
- app not allowed；
- contact not found；
- draft returns fingerprint；
- send-confirmed rejects missing/mismatch proof；
- unknown send blocks replay。

### 15.3 Manual Smoke

受控 smoke：

1. TextEdit observe/open/type no-submit；
2. WeChat preflight；
3. WeChat reject/no-send；
4. WeChat confirm/send-once to `文件传输助手`；
5. same idempotency key replay no duplicate send；
6. restart helper and re-query evidence。

真实发送 smoke 必须显式授权，且使用 fresh idempotency key。

## 16. Implementation Slices

### H0: Decision And Contract

- 本文档；
- schema fixtures；
- capability/error taxonomy；
- Settings projection requirements。

### H1: Helper Prototype

- local HTTP server；
- manifest；
- `/healthz`、`/v1/info`、`/v1/readiness`；
- fake package client；
- tests。

### H2: macOS Dev App Wrapper

- build `.app`；
- fixed dev bundle id；
- helper startup；
- readiness from helper process；
- Accessibility prompt guidance。

### H3: Plato Adapter To Helper

- runtime config `provider="helper"`；
- helper client；
- capability registry integration；
- Settings readiness projection；
- Router/Execution error evidence。

### H4: WeChat Draft/Send Through Helper

- move WeChat desktop runtime calls behind helper；
- draft-message API；
- send-confirmed API；
- preserve existing send-boundary idempotency；
- real reject/no-send smoke。

### H5: Release Packaging

- helper bundled with Plato installer；
- signing/notarization plan；
- version compatibility；
- release smoke。

## 17. Acceptance Criteria

Helper boundary is accepted when:

1. Plato no longer needs direct macOS Accessibility permission for computer-use actions;
2. helper readiness reports the actual permission subject path and bundle id;
3. missing Accessibility produces actionable UI and conversation evidence;
4. helper can run a no-send TextEdit smoke from Electron dev path;
5. WeChat send path can be routed through helper with the existing confirmation boundary;
6. same idempotency key cannot duplicate a send across helper/Plato restarts;
7. release packaging can explain to users why `Plato Computer Use Helper` appears in macOS Privacy settings。

## 18. Open Questions

1. 第一版 helper 用 Python embedded executable、PyInstaller、Briefcase、还是 Swift/Node wrapper？
2. helper 是否放在 `/Applications` 还是 Application Support？
3. dev helper 是否使用独立 bundle id？
4. release 前是否必须 Apple Developer signing/notarization？
5. 是否需要 XPC 替代 localhost HTTP？
6. Screen Recording 是否在 1.1 纳入，还是继续 deferred？
7. app-specific Automation / Apple Events 是否完全避免，还是作为 adapter-specific optional capability？

## 19. Recommendation

当前阶段建议：

1. 先实现 dev-only Helper prototype；
2. IPC 使用 localhost HTTP + startup token；
3. bundle id 使用 `com.taskweavn.plato.computer-use-helper.dev`；
4. helper 内部直接运行 packaged/embedded `macos-computer-use`，不要外包给系统 Python；
5. Plato 通过 `provider="helper"` 接入；
6. release signing/notarization 在真实 packaging slice 处理。

这能先解决开发阶段 TCC 权限主体不稳定的问题，同时不把 `macos-computer-use`
社区包污染成 Plato 专用组件。
