# App Control Tool Packages Project Plan

## 1. 背景

本企划定义两个可独立发布、可被第三方开发者复用的 Python package：

1. `computer-use-macos`
2. `wechat-desktop-tool`

目标是把 macOS GUI 自动化能力和微信桌面端语义能力拆成清晰的服务包能力。调用方可以是任意 Agent 应用、自动化应用、测试工具或本地脚本。package 本身不绑定任何特定产品、任务系统、会话系统、LLM 框架或 UI 投射模型。

核心原则：

- Tool 只接受 Command，产生 Observation。
- 调用方负责决策、授权、状态管理、事件记录和 UI 展示。
- 权限主体是 helper app 或调用方进程，不是 PyPI package。
- package 提供稳定协议、SDK、CLI、helper 模板和可测试实现。

## 2. 项目目标

### 2.1 `computer-use-macos`

提供通用 macOS 桌面控制能力，作为底层 app-control backend。

能力范围：

- macOS readiness 检查
- helper app 发现、启动、连接和诊断
- Accessibility / Apple Events / Screen Recording 等权限状态检测
- 通用 GUI 控制 primitive
- command / observation 协议
- 同步调用、流式事件、可选本地服务模式
- helper app 模板和打包工具

### 2.2 `wechat-desktop-tool`

提供微信桌面端语义工具能力，构建在 `computer-use-macos` 或兼容的 app-control client 之上。

能力范围：

- 打开或聚焦微信
- 定位联系人
- 读取当前聊天窗口可见消息
- 输入草稿
- 提交当前草稿
- 返回微信语义 Observation
- 不承担业务决策和产品授权

## 3. 非目标

以下内容不属于两个 package 的责任：

- LLM 决策
- Agent loop 实现
- 任务生命周期
- 会话系统
- 审计系统
- 产品 UI
- 用户授权交互界面
- 业务策略判断
- 是否允许自动发送消息
- 是否需要人工确认
- 群发、营销、批量消息自动化
- 远程控制或跨设备网络协议

如果调用方需要这些能力，应在 package 外部实现。

## 4. Package 边界

## 4.1 `computer-use-macos`

一句话边界：

```text
computer-use-macos 负责控制 macOS，不知道具体 app 怎么用。
```

它应该提供：

- `readiness`
- `observe`
- `open_app`
- `focus_app`
- `click`
- `type_text`
- `press_key`
- `hotkey`
- `wait`
- helper app lifecycle
- helper packaging template
- command / observation base schema

它不应该提供：

- 微信联系人解析
- 微信消息读取
- 微信发送
- 任意 app 的业务语义
- 任意调用方专属状态模型

## 4.2 `wechat-desktop-tool`

一句话边界：

```text
wechat-desktop-tool 负责知道微信怎么用，不负责 macOS 权限主体。
```

它应该提供：

- `open_wechat`
- `focus_contact`
- `observe_current_chat`
- `read_visible_messages`
- `draft_message`
- `submit_draft`
- 可选 convenience API：`send_message`

它不应该提供：

- helper app 打包
- TCC 权限主体
- 业务授权策略
- LLM
- 调用方任务系统
- 调用方日志系统

## 4.3 依赖方向

第一版建议：

```text
wechat-desktop-tool
  -> depends on computer-use-macos protocol/client

computer-use-macos
  -> no dependency on wechat-desktop-tool
```

如果协议独立性变强，后续可以拆出第三个极小包：

```text
app-control-protocol
  <- computer-use-macos
  <- wechat-desktop-tool
```

第一版不建议过早拆第三个包。

## 5. 推荐仓库形态

第一阶段建议使用一个 monorepo，两个独立 package，两个 PyPI distribution。

```text
app-control-tools/
  README.md
  docs/
    protocol.md
    helper-packaging.md
    permissions.md
    wechat-desktop-tool.md
    release.md

  packages/
    computer-use-macos/
      pyproject.toml
      src/computer_use_macos/
        __init__.py
        client.py
        commands.py
        observations.py
        errors.py
        readiness.py
        transport.py
        helper/
          discovery.py
          launcher.py
          manifest.py
          doctor.py
        cli.py
      helper-template/
        README.md
        Info.plist.template
        entitlements.plist
        build.py
      tests/
      examples/

    wechat-desktop-tool/
      pyproject.toml
      src/wechat_desktop_tool/
        __init__.py
        tool.py
        commands.py
        observations.py
        errors.py
        adapter.py
        recipes.py
      tests/
      examples/
```

发布物：

```bash
pip install computer-use-macos
pip install wechat-desktop-tool
```

拆仓库条件：

- `computer-use-macos` 协议稳定
- `wechat-desktop-tool` 有独立 issue 和 release 节奏
- helper app 模板和权限流程稳定
- 两个 package 已经有外部调用方

## 6. Command / Observation 协议

## 6.1 Command Envelope

所有 tool 调用都使用 command envelope。Command 表达“这一次要执行什么”，不表达“是否应该执行”。

```json
{
  "schema": "app_control.command.v1",
  "commandId": "cmd_123",
  "tool": "wechat.desktop",
  "operation": "focus_contact",
  "input": {
    "contact": "文件传输助手"
  },
  "timeoutMs": 30000,
  "idempotencyKey": "optional-client-key",
  "metadata": {
    "caller": "example-app"
  }
}
```

字段规则：

- `schema`: 协议版本。
- `commandId`: 调用方生成，便于日志关联。
- `tool`: 工具名，例如 `macos.computer_use` 或 `wechat.desktop`。
- `operation`: 具体操作。
- `input`: 操作参数。
- `timeoutMs`: 调用方期望的最大执行时间。
- `idempotencyKey`: 可选。底层只用于防重复执行同一个低层命令，不承担业务语义。
- `metadata`: 可选。package 不依赖调用方字段。

## 6.2 Observation Result

Observation 是 tool 返回给调用方的事实结果。

```json
{
  "schema": "app_control.observation.v1",
  "commandId": "cmd_123",
  "tool": "wechat.desktop",
  "operation": "focus_contact",
  "status": "ok",
  "success": true,
  "summary": "Focused WeChat contact.",
  "observation": {
    "focusedContact": "文件传输助手",
    "windowTitle": "微信"
  },
  "evidence": {
    "textExtract": "文件传输助手"
  },
  "timing": {
    "startedAt": "2026-06-28T00:00:00Z",
    "durationMs": 1240
  }
}
```

失败返回：

```json
{
  "schema": "app_control.observation.v1",
  "commandId": "cmd_123",
  "tool": "wechat.desktop",
  "operation": "focus_contact",
  "status": "failed",
  "success": false,
  "failureKind": "contact_not_found",
  "message": "Could not resolve the requested WeChat contact.",
  "recoveryHint": "Open WeChat main window and check the contact display name.",
  "retryable": true,
  "observation": {},
  "evidence": {
    "textExtract": "搜索结果为空"
  }
}
```

状态集合：

- `ok`
- `not_found`
- `not_ready`
- `permission_missing`
- `timeout`
- `failed`
- `unknown`

`unknown` 表示 tool 无法确认动作是否成功。调用方不应自动重试可能产生副作用的命令。

## 6.3 Stream Event

长操作可以暴露事件流。

```json
{
  "schema": "app_control.event.v1",
  "commandId": "cmd_123",
  "seq": 3,
  "type": "observation",
  "phase": "resolve_contact",
  "status": "ok",
  "summary": "Selected contact.",
  "data": {
    "contact": "文件传输助手"
  }
}
```

调用方决定事件去哪里：

- 控制台输出
- 自己的日志系统
- 自己的 Agent memory
- 自己的 UI
- 自己的审计系统

package 不反向依赖调用方事件系统。

## 7. Python API

## 7.1 `computer-use-macos`

```python
from computer_use_macos import ComputerUseClient, HelperConfig

client = ComputerUseClient(
    HelperConfig(
        helper_app_path="/Applications/Acme Computer Use Helper.app",
        bundle_id="com.acme.computer-use-helper",
        allowed_apps=("WeChat", "TextEdit"),
        transport="unix_socket",
    )
)

readiness = client.readiness()
result = client.open_app("WeChat")
result = client.type_text("hello")
result = client.press_key("Return")
```

Command API：

```python
result = client.run_command(
    {
        "schema": "app_control.command.v1",
        "commandId": "cmd_1",
        "tool": "macos.computer_use",
        "operation": "open_app",
        "input": {"app": "WeChat"},
        "timeoutMs": 10000,
    }
)
```

Stream API：

```python
for event in client.run_stream(command):
    print(event)
```

## 7.2 `wechat-desktop-tool`

```python
from computer_use_macos import ComputerUseClient, HelperConfig
from wechat_desktop_tool import WeChatDesktopTool

computer_use = ComputerUseClient(
    HelperConfig(
        helper_app_path="/Applications/Acme Computer Use Helper.app",
        bundle_id="com.acme.computer-use-helper",
        allowed_apps=("WeChat",),
    )
)

wechat = WeChatDesktopTool(app_control=computer_use)

wechat.open_wechat()
wechat.focus_contact("文件传输助手")
wechat.draft_message("你好")
wechat.submit_draft()
```

读取可见消息：

```python
messages = wechat.read_visible_messages(limit=20)
```

Command API：

```python
result = wechat.run_command(
    {
        "schema": "app_control.command.v1",
        "commandId": "cmd_2",
        "tool": "wechat.desktop",
        "operation": "focus_contact",
        "input": {"contact": "文件传输助手"},
    }
)
```

## 8. Helper App 策略

## 8.1 为什么需要 helper app

macOS TCC 权限授予的是实际执行 GUI 控制的进程身份，而不是 Python package。

因此：

- PyPI package 不能直接作为稳定权限主体。
- helper app 才是稳定的 Accessibility / Apple Events 权限主体。
- 开发者应打包自己的 helper app，并让最终用户授权这个 helper。

## 8.2 开发者打包自己的 helper

提供 CLI：

```bash
python -m computer_use_macos helper init \
  --name "Acme Computer Use Helper" \
  --bundle-id "com.acme.computer-use-helper" \
  --team-id "ABCDE12345"
```

生成：

```text
computer-use-helper/
  Helper.app source/template
  Info.plist
  entitlements.plist
  helper_config.json
  build.sh
  notarize.sh
  README.md
```

构建：

```bash
python -m computer_use_macos helper build ./computer-use-helper
python -m computer_use_macos helper doctor ./computer-use-helper
```

## 8.3 Helper app 职责

helper app 只负责底层执行：

- 启动本机 IPC server
- 校验本地 client token
- 检查 TCC 权限
- 执行 macOS primitive command
- 返回 observation

helper app 不负责：

- LLM
- 业务授权策略
- 自动发送策略
- UI 投射
- 调用方任务状态

## 8.4 传输方式

第一版优先：

- Unix domain socket

后续可选：

- localhost HTTP
- XPC

推荐第一版使用 Unix socket，原因：

- 本机边界更清晰
- 比 localhost HTTP 少暴露面
- 便于用文件权限限制访问

## 9. 权限模型

## 9.1 package 层权限

package 只做 readiness 检测和错误返回。

示例：

```json
{
  "status": "missing_accessibility",
  "helperInstalled": true,
  "helperRunning": true,
  "accessibilityTrusted": false,
  "recoveryHint": "Open System Settings > Privacy & Security > Accessibility and enable Acme Computer Use Helper."
}
```

## 9.2 调用方授权

是否允许执行某个 command，由调用方决定。

package 不判断：

- 是否允许发送消息
- 是否需要用户确认
- 是否允许读取聊天记录
- 是否允许自动聊天

调用方应在调用前做：

```text
authorize(command) -> allowed / denied / needs_approval
```

如果调用方传入 command，package 默认认为调用方已经完成授权。

## 9.3 底层安全边界

即便不做业务授权，package 仍需要底层安全边界：

- app allowlist
- timeout
- local token
- no remote access by default
- no screenshot by default
- no hidden bulk expansion
- unknown 状态不自动重试
- structured failure

## 10. `computer-use-macos` Operation 设计

## 10.1 `readiness`

输入：

```json
{}
```

输出：

```json
{
  "status": "ready",
  "platform": "Darwin",
  "helper": {
    "installed": true,
    "running": true,
    "bundleId": "com.acme.computer-use-helper"
  },
  "permissions": {
    "accessibility": true,
    "screenRecording": false,
    "appleEvents": true
  },
  "enabledOperations": [
    "observe",
    "open_app",
    "focus_app",
    "click",
    "type_text",
    "press_key",
    "hotkey",
    "wait"
  ]
}
```

## 10.2 `observe`

读取当前前台 app、窗口标题、可访问 UI 摘要。

不得默认返回完整隐私内容。调用方需要显式请求可见文本摘要。

## 10.3 `open_app`

打开或聚焦 app。

输入：

```json
{"app": "WeChat"}
```

## 10.4 `click`

点击明确目标。

目标可以是：

- 坐标
- accessibility selector
- 文本锚点
- 调用方上一步 observation 中返回的 element id

第一版优先支持 accessibility selector 和坐标。

## 10.5 `type_text`

向当前焦点输入文本。

必须返回：

- typed chars
- focused target summary if available
- submitted: false

## 10.6 `press_key`

按键，例如 `Return`。

必须返回：

- key
- target summary if available
- action attempted

## 11. `wechat-desktop-tool` Operation 设计

## 11.1 `open_wechat`

组合调用：

```text
computer_use.open_app("WeChat")
computer_use.observe(...)
```

输出微信窗口 readiness。

## 11.2 `focus_contact`

目标：

打开指定联系人聊天窗口。

输入：

```json
{"contact": "文件传输助手"}
```

过程：

- 确认微信主窗口可用
- 聚焦搜索入口
- 清空搜索框
- 输入联系人名称
- 选择匹配结果
- 验证当前聊天窗口对象

输出：

```json
{
  "focusedContact": "文件传输助手",
  "confidence": 0.95,
  "windowTitle": "微信"
}
```

## 11.3 `read_visible_messages`

目标：

读取当前联系人聊天窗口中可见消息。

输入：

```json
{"limit": 20}
```

输出：

```json
{
  "messages": [
    {
      "direction": "incoming",
      "text": "明天下午可以",
      "visibleTimestamp": "14:32"
    }
  ],
  "truncated": false
}
```

隐私规则：

- package 返回调用方请求的可见文本。
- package 不上传、不持久化、不外发。
- 调用方负责授权和记录策略。

## 11.4 `draft_message`

目标：

在当前聊天输入框中输入草稿，但不提交。

输入：

```json
{"message": "你好"}
```

输出：

```json
{
  "draftReady": true,
  "messageHash": "sha256:...",
  "messageChars": 2
}
```

## 11.5 `submit_draft`

目标：

提交当前草稿。

输入：

```json
{"method": "keyboard_return"}
```

输出：

```json
{
  "submitted": true,
  "sendAttempted": true,
  "method": "keyboard_return"
}
```

失败或未知：

```json
{
  "status": "unknown",
  "failureKind": "submit_unverified",
  "sendAttempted": true,
  "recoveryHint": "Check WeChat manually before retrying."
}
```

## 11.6 `send_message`

`send_message` 是 convenience API，不是核心 primitive。

推荐内部实现：

```text
open_wechat
focus_contact
draft_message
submit_draft
```

调用方如果需要授权、确认或策略判断，应调用更细粒度 operation。

## 12. 错误模型

通用错误字段：

- `failureKind`
- `message`
- `recoveryHint`
- `retryable`
- `phase`
- `operation`
- `evidence`

`computer-use-macos` 常见错误：

- `helper_not_found`
- `helper_not_running`
- `permission_missing`
- `app_not_allowed`
- `app_not_found`
- `window_not_available`
- `accessibility_lookup_failed`
- `focus_failed`
- `timeout`
- `unknown`

`wechat-desktop-tool` 常见错误：

- `wechat_not_ready`
- `wechat_not_logged_in`
- `wechat_window_unavailable`
- `contact_not_found`
- `contact_ambiguous`
- `input_not_focused`
- `draft_failed`
- `submit_failed`
- `submit_unknown`

## 13. 日志与 Observation 路由

package 只产生 observation，不拥有调用方日志系统。

提供三种方式：

1. 同步返回 `ToolObservation`
2. `run_stream` 迭代 `ToolEvent`
3. 可选 observer callback

Python Protocol：

```python
class ToolObserver(Protocol):
    def on_event(self, event: ToolEvent) -> None: ...
```

调用方使用示例：

```python
class MyObserver:
    def on_event(self, event):
        my_logger.info(event.model_dump())

wechat.run_command(command, observer=MyObserver())
```

依赖方向：

```text
caller -> package
caller provides observer
package emits protocol event
caller stores/projects event
```

package 不 import 调用方日志、事件或任务模块。

## 14. 开发者体验

## 14.1 安装

```bash
pip install computer-use-macos
pip install wechat-desktop-tool
```

## 14.2 初始化 helper

```bash
python -m computer_use_macos helper init \
  --name "Acme Computer Use Helper" \
  --bundle-id "com.acme.computer-use-helper"
```

## 14.3 检查权限

```bash
python -m computer_use_macos doctor \
  --helper-app "/Applications/Acme Computer Use Helper.app"
```

## 14.4 运行示例

```bash
python -m wechat_desktop_tool examples send-message \
  --contact 文件传输助手 \
  --message 你好
```

示例命令默认不提供业务授权判断。示例文档必须明确说明：调用者负责确认自己有权执行该动作。

## 15. 测试策略

## 15.1 Unit tests

覆盖：

- command schema validation
- observation schema validation
- error mapping
- helper config parsing
- app allowlist
- timeout handling
- fake app-control client
- fake WeChat UI tree

## 15.2 Contract tests

确保：

- `wechat-desktop-tool` 只依赖 app-control protocol
- `computer-use-macos` 不依赖微信 package
- command / observation JSON 兼容
- failureKind 稳定

## 15.3 Integration tests

本机 macOS 可选测试：

- TextEdit smoke
- WeChat readiness smoke
- WeChat focus contact smoke
- WeChat draft smoke
- WeChat submit smoke 仅允许显式 opt-in

测试标记：

```bash
pytest -m macos
pytest -m wechat
pytest -m destructive
```

发送类测试默认跳过，必须显式设置：

```bash
WECHAT_TOOL_ALLOW_SEND=1 pytest -m wechat_send
```

## 16. 发布策略

## 16.1 PyPI distributions

```text
computer-use-macos
wechat-desktop-tool
```

版本建议：

- 初始版本：`0.1.0`
- pre-1.0 阶段允许小版本破坏性变化，但必须写 migration notes
- command / observation schema 必须版本化

## 16.2 Helper app 分发

提供模板，不强制提供统一 helper。

开发者有三种选择：

1. 自己打包 helper app
2. 使用模板生成 helper app
3. 开发阶段使用 direct process mode

推荐生产使用自己签名和 notarize 的 helper app。

## 16.3 Trusted Publisher

建议两个 PyPI package 都配置 Trusted Publisher。

发布流水线：

```text
tag package/computer-use-macos/v0.1.0
  -> build
  -> test
  -> publish computer-use-macos

tag package/wechat-desktop-tool/v0.1.0
  -> build
  -> test
  -> publish wechat-desktop-tool
```

## 17. Milestones

## M0: Protocol draft

交付：

- command schema
- observation schema
- error schema
- stream event schema
- app-control client Protocol

验收：

- 两个 package 都能 import 协议对象
- schema round-trip 测试通过

## M1: `computer-use-macos` package MVP

交付：

- Python SDK
- direct process backend
- helper client interface
- readiness
- open_app
- observe
- type_text
- press_key
- doctor CLI

验收：

- TextEdit smoke 可运行
- readiness 能明确报告权限状态
- 不依赖任何具体 app tool

## M2: helper app template MVP

交付：

- helper app template
- Info.plist 模板
- entitlements 模板
- build CLI
- helper manifest
- launch/discovery

验收：

- 开发者可以生成自有 helper app
- helper app 可被 macOS Accessibility 授权
- SDK 能连接 helper

## M3: `wechat-desktop-tool` MVP

交付：

- WeChatDesktopTool
- open_wechat
- focus_contact
- draft_message
- submit_draft
- read_visible_messages 初版
- fake app-control tests

验收：

- 不依赖调用方产品模型
- 使用 fake client 可完成完整流程测试
- 本机 opt-in smoke 可发送到受控联系人

## M4: Service mode

交付：

- local service command endpoint
- polling result
- optional SSE event stream
- local token
- Unix socket transport

验收：

- 非 Python 调用方可以通过本地服务调用 command
- observation 能通过 polling 或 event stream 读取

## M5: Developer preview

交付：

- README
- Quickstart
- helper packaging guide
- permissions guide
- examples
- migration notes
- PyPI `0.1.0`

验收：

- 新开发者能在 30 分钟内完成 TextEdit smoke
- 新开发者能在 60 分钟内完成 WeChat focus/draft smoke

## 18. 风险

## 18.1 macOS 权限不稳定

风险：

- 开发阶段进程身份变化导致 TCC 授权失效。

缓解：

- 推荐 helper app。
- direct process mode 只作为开发调试。
- doctor 输出明确权限主体。

## 18.2 微信 UI 变化

风险：

- 微信版本、语言、窗口布局变化导致 contact resolution 失败。

缓解：

- 返回结构化 failureKind。
- 封装版本探测。
- 保持 operation 小粒度。
- 不把失败自动升级为发送。

## 18.3 自动发送风险

风险：

- 调用方滥用工具自动发送消息。

缓解：

- package 不提供业务授权。
- 文档明确调用方负责 authorization。
- 默认示例使用受控联系人。
- `submit_draft` 对 unknown 不自动重试。

## 18.4 协议过早固定

风险：

- 第一版 schema 不足以支撑后续 app tools。

缓解：

- 使用 `schema` version。
- pre-1.0 保持变更空间。
- 先稳定核心字段，扩展字段放入 `metadata`。

## 19. 第一版推荐实现顺序

1. 建立 monorepo 和两个 package skeleton。
2. 定义 `ToolCommand` / `ToolObservation` / `ToolEvent` / `ToolError`。
3. 实现 fake app-control backend。
4. 实现 `computer-use-macos` direct backend 的 TextEdit smoke。
5. 实现 helper app template 和 doctor。
6. 实现 `wechat-desktop-tool` 基于 fake backend 的单元测试。
7. 实现 WeChat focus/draft 本机 smoke。
8. 发布 `0.1.0a1`。
9. 补文档和 examples。
10. 发布 `0.1.0`。

## 20. 成功标准

这个项目成功的标志不是某个具体产品能调用，而是任意开发者可以独立完成：

```python
from computer_use_macos import ComputerUseClient
from wechat_desktop_tool import WeChatDesktopTool

computer_use = ComputerUseClient.from_helper_manifest("helper.json")
wechat = WeChatDesktopTool(app_control=computer_use)

wechat.focus_contact("文件传输助手")
wechat.draft_message("你好")
result = wechat.submit_draft()
print(result.status)
```

并且：

- 权限主体清晰。
- 调用协议清晰。
- observation 可被调用方自由消费。
- package 不反向依赖调用方。
- 两个 package 可以独立发布、独立测试、独立演进。
