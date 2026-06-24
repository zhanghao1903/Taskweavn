# UI Natural-Language WeChat Send Task Technical Design

状态：completed
最后更新：2026-06-24

## 0. 当前实现状态

已实现：

- 有界 WeChat send intent resolver。
- 明确联系人/消息 slot extraction。
- 缺失联系人或消息时返回 non-mutating clarification。
- 多联系人/群发类输入返回 unsupported，不创建任务。
- Runtime Input Router 在 LLM planner 前优先处理确定性 WeChat send。
- Router 在存在 Execution Plane service 时发布
  `communication.wechat.send_message` `TaskRequest`。
- Router 在没有 Execution Plane service 时可回退为创建 contract-revision
  execution TaskNode。
- workspace-scoped HTTP runtime-input route 已覆盖 Main Page API 路径到
  Execution Plane WeChat TaskRequest 的 handoff。
- fake runtime integration 已覆盖自然语言 route 后的 reject/no-send 与
  confirm/send-once。
- 缺失 contact/message 后的 pending clarification completion 已实现：
  - Router 在 outcome 中返回 `pendingClarification`；
  - Main Page controller 在本地保存该对象；
  - 下一次 runtime-input 请求通过 `clientState.pendingClarification` 回传；
  - follow-up answer 补全 slot 后进入同一条 confirmation-gated WeChat
    send task 创建路径。
- Main Page renderer/Electron 用户路径 smoke 已实现并于 2026-06-24 通过：
  - `npm run electron:smoke:runtime-input-wechat`；
  - 从 Main Page 输入栏提交缺消息的微信发送请求；
  - 验证 missing-message clarification；
  - 再提交 follow-up message；
  - 在 seeded fixture 未启用 computer-use 时验证 capability-disabled
    安全反馈，且不会发送真实消息。
- controlled real local smoke to `文件传输助手` 已于 2026-06-24 通过：
  - local sidecar: `http://127.0.0.1:58027`；
  - session: `a436ec2f`；
  - execution: `exec_93d596a34767537297a69bd6502e2f10`；
  - confirmation: `d601fc72dc53417fa1fc96db9f0958c2`；
  - idempotency key: `manual-wechat-smoke-20260624-e05a-authorized-02`；
  - final status: `done`；
  - result kind: `wechat_send_result`；
  - send boundary status: `sent`；
  - evidence shows `send_method=keyboard_return`,
    `send_attempted=true`, `confirmed_by_user=true`；
  - terminal same-key replay returned `done` for the same execution。

## 1. 目标

本设计定义 Plato 如何从 Main Page 的自然语言输入创建一个本地 macOS 微信发送任务，并复用现有 Execution Plane、WeChat runtime、confirmation、result/evidence projection。

核心目标不是新增一套聊天机器人，而是把当前已经跑通的 WeChat send capability 接入 Plato 产品主路径：

```text
用户输入
-> Runtime Input Router
-> bounded WeChat intent + slot extraction
-> Execution Plane TaskRequest
-> WeChat runtime draft
-> confirmation
-> send/reject
-> result/error/evidence projection
```

## 2. 上游约束

### 行为源

- Runtime Input Router 决定一段用户输入属于 question、guidance、command、ASK answer、confirmation response，还是 workspace/external execution request。
- 一次用户输入只能产生一个主副作用。
- 低置信度路由不得修改 Plan、TaskBus、workspace，也不得触发外部发送。

### 执行源

- WeChat send task type 固定为：

```text
communication.wechat.send_message
```

- 必须包含：

```json
{
  "input": {
    "contactDisplayName": "...",
    "messageText": "..."
  },
  "policy": {
    "requiredCapability": "communication.wechat_desktop_send",
    "requiresHumanConfirmation": true,
    "riskLevel": "high"
  }
}
```

### 安全源

- 微信发送属于 high-risk action。
- 无论用户是否说“直接发送”，第一版都必须经过 confirmation。
- 缺少联系人或消息内容时，不允许创建发送任务。

## 3. 目标架构

```text
Main Page ContextInputBar
  -> POST runtime input route endpoint
  -> RuntimeInputRouter
  -> WeChatSendIntentResolver
  -> WeChatSendTaskRequestBuilder
  -> TaskApiService / EmbeddedExecutionPlaneService
  -> WeChatSendRuntimeHandler
  -> Confirmation lifecycle
  -> Result/Error/Evidence stores
  -> MainPageSnapshot projection
```

Router 不直接调用 computer-use tool。Router 只负责分类、提取 slot、创建结构化 execution request。真正执行仍由 Execution Plane 和 WeChat runtime 承担。

## 4. 支持的首批输入模式

第一版只支持高确定性的中文模式。

### 接受模式

```text
给微信{contact}发送一条消息：{message}
给{contact}发微信：{message}
在微信给{contact}发送：{message}
用微信给{contact}发消息：{message}
```

其中中文冒号、英文冒号、换行后的消息正文都应支持。

### 示例

```text
给微信文件传输助手发送一条消息：Plato 本地发送测试。发送前让我确认。
```

提取结果：

```json
{
  "contactDisplayName": "文件传输助手",
  "messageText": "Plato 本地发送测试。"
}
```

“发送前让我确认”属于用户约束/安全提示，不应进入 messageText。

### 拒绝或澄清模式

以下输入不得直接创建任务：

- 没有联系人：`帮我发一条微信：明天开会`
- 没有消息：`给微信文件传输助手发消息`
- 多联系人或群发：`给 A 和 B 都发微信...`
- 模糊 App：`给文件传输助手发一下`
- 模糊动作：`联系一下文件传输助手`
- 低置信度复杂意图：`帮我处理一下微信里的事情`

## 5. Slot 模型

```ts
type WeChatSendSlots = {
  contactDisplayName: string;
  messageText: string;
  operatorNote?: string;
  originalText: string;
  confidence: "high" | "medium" | "low";
  missingSlots: Array<"contactDisplayName" | "messageText">;
};
```

实现时不要求 TypeScript；后端可使用 Python dataclass 或 Pydantic model。这里表达的是稳定语义。

### 规范化规则

- trim 首尾空白。
- 统一全角/半角冒号。
- 去掉明确的确认提示短语：
  - `发送前让我确认`
  - `先让我确认`
  - `需要我确认`
- 不自动改写联系人名称。
- 不自动翻译消息内容。
- 不从历史消息中猜测缺失联系人。

## 6. Router Outcome

建议新增或复用 Runtime Input Router 的 execution handoff outcome。

语义字段：

```json
{
  "kind": "execution_request",
  "target": "execution_plane",
  "taskType": "communication.wechat.send_message",
  "requiresConfirmation": true,
  "riskLevel": "high",
  "slots": {
    "contactDisplayName": "文件传输助手",
    "messageText": "Plato 本地发送测试。"
  }
}
```

如果 slot 缺失：

```json
{
  "kind": "clarification_required",
  "missingSlots": ["messageText"],
  "prompt": "要发送给文件传输助手的消息内容是什么？"
}
```

## 7. TaskRequest Builder

Router handoff 成功后，构造 Execution Plane request。

### Request shape

```json
{
  "idempotencyKey": "runtime-input:{sessionId}:{routeCommandId}",
  "requester": {
    "kind": "plato",
    "id": "runtime-input-router"
  },
  "externalRef": {
    "system": "plato",
    "kind": "runtime_input",
    "id": "{routeCommandId}"
  },
  "taskType": "communication.wechat.send_message",
  "input": {
    "contactDisplayName": "文件传输助手",
    "messageText": "Plato 本地发送测试。",
    "operatorNote": "Created from Plato Main Page input."
  },
  "policy": {
    "requiredCapability": "communication.wechat_desktop_send",
    "allowedTools": ["computer_use", "wechat_desktop"],
    "requiresHumanConfirmation": true,
    "riskLevel": "high"
  },
  "metadata": {
    "sessionId": "{sessionId}",
    "source": "main_page_runtime_input",
    "originalUserInputHash": "{hash}"
  }
}
```

### Idempotency 规则

- 同一次 route command 的重放必须返回同一个 execution。
- 用户再次主动提交同一段文本，可以创建新的 route command，因此可以是新的发送意图。
- 如果同一个 idempotency key 对应不同 contact/message，必须返回 idempotency conflict，不能发送。

这一区分很重要：transport retry 要幂等，用户主动重复提交不应被系统强行吞掉。

## 8. Confirmation 接入

WeChat runtime 继续负责 high-risk confirmation。

Router 不做确认，不模拟确认，不把“发送前让我确认”当作可选项。确认边界统一由 Execution Plane / confirmation lifecycle 处理。

流程：

1. Router 创建 task。
2. WeChat runtime 完成 draft 或 pre-send preparation。
3. Runtime 创建 confirmation。
4. Main Page 显示 confirmation card。
5. 用户 confirm/reject。
6. Runtime 根据结果 send/no-send。

如果用户在输入栏中回答当前活跃 confirmation，Runtime Input Router 的 confirmation response 优先级仍应高于普通 WeChat send intent。

## 9. Clarification / ASK 策略

第一版建议按风险分层：

- 缺少 contact/message：返回 non-mutating clarification。
- 用户补充回答后，再完成 slot 并创建 task。
- 如果当前 ASK lifecycle 已经稳定，可将 clarification 升级为 durable ASK。

当前实现采用轻量 pending clarification，而不是 durable ASK：

- 后端 outcome 携带 `pendingClarification`，包含缺失 slot、已知联系人或消息、
  原始输入和 reason code。
- 前端 Main Page controller 将该对象暂存在本地 state。
- 下一次输入提交时，前端把 pending clarification 放入
  `clientState.pendingClarification`。
- Router 优先处理 stop/retry、ASK 和 confirmation，然后再处理 pending
  clarification，避免用户显式控制命令被补全逻辑吞掉。
- pending clarification 不是持久对象；刷新页面或重启 App 后会丢失。若未来
  需要 restart recovery，应升级为 ASK lifecycle 或 durable session content。

最小策略：

```text
User: 给微信文件传输助手发消息
Plato: 要发送什么内容？
User: Plato 本地测试
Plato: 创建微信发送任务，并进入确认。
```

在 clarification 完成前，系统不得打开 WeChat 或创建 send task。

## 10. Runtime Configuration

创建任务前应检查或依赖 Execution Plane 检查：

- task api / execution plane enabled
- local computer-use backend available
- macOS accessibility readiness
- WeChat runtime enabled
- high-risk confirmation enabled

如果 readiness 不满足，Router 可以返回 execution unsupported/readiness error；也可以创建 task 后由 Execution Plane 返回 structured error。推荐：

- 明显配置关闭：Router 直接返回 unsupported，不创建 task。
- macOS/WeChat 实际 readiness：交给 Execution Plane，便于 evidence 记录。

## 11. Main Page Projection

UI 不需要第一时间新增大组件。优先复用现有 surfaces：

- Conversation：保留用户输入和系统任务创建/完成摘要。
- Plan & Progress：显示 WeChat send task 的状态。
- Activity：显示 draft、waiting_for_confirmation、rejected/sent/error。
- Detail：显示 contact、message 摘要、risk、confirmation status。
- Evidence：显示 readiness、draft、submit、observation、failure_kind。

状态至少覆盖：

- created
- preparing/drafting
- waiting_for_user
- rejected/no-send
- running/sending
- completed
- failed
- unknown result

## 12. 错误分类

必须保留现有 WeChat runtime 的结构化失败信息。

建议映射：

| Phase | Failure kind | UI meaning |
| --- | --- | --- |
| readiness | missing_accessibility | macOS 权限未就绪 |
| contact_resolution | contact_not_found | 未找到联系人 |
| draft | input_focus_failed | 无法定位输入框 |
| confirmation | rejected | 用户拒绝，未发送 |
| submit | submit_not_verified | 已尝试提交但无法确认结果 |
| observe | post_send_observe_failed | 发送后观察失败 |

UI 文案必须区分“没有发送”、“发送失败”、“发送结果未知”。

## 13. 后端文件影响范围

预期新增或修改：

- `src/taskweavn/server/runtime_input_router.py`
- `src/taskweavn/server/runtime_input_models.py`
- `src/taskweavn/server/runtime_input_wechat.py` 或等价 resolver 模块
- `src/taskweavn/execution_plane/embedded_service.py` 仅在 handoff 边界缺字段时修改
- `tests/.../test_runtime_input_wechat_send.py`
- `tests/.../test_runtime_input_router_execution_handoff.py`

不应修改：

- WeChat runtime 的实际发送逻辑，除非发现 contract 缺口。
- MainPage 视觉结构。
- macOS computer-use package 的底层能力。

## 14. 前端影响范围

第一版前端尽量不做视觉重构。

可能需要：

- ContextInputBar submit 后支持 execution handoff response。
- pending/created task feedback。
- confirmation card 与当前 input priority 保持一致。
- result/error/evidence 链接保持可读。

不做：

- 新建 WeChat 专用一级入口。
- 新建联系人选择器。
- 新建批量发送 UI。

## 15. 测试计划

### Unit tests

- 接受模式 slot extraction。
- 中文/英文冒号。
- 确认提示短语剥离。
- 缺失 contact。
- 缺失 message。
- 多联系人拒绝。
- 模糊输入拒绝。

### Router tests

- clear input -> execution handoff。
- missing slot -> clarification。
- unsupported input -> non-mutating fallback。
- active confirmation response 不被 WeChat intent 抢占。
- workspace-scoped HTTP runtime-input route -> Execution Plane TaskRequest。

### Integration tests with fake runtime

- route -> task created。已补。
- route -> waiting_for_user。已补。
- reject -> no-send result。已补。
- confirm -> send-once result。已补。
- replay same command -> no duplicate execution。已补。
- idempotency conflict -> no send。

### Controlled local smoke

顺序必须是：

0. `npm run electron:smoke:runtime-input-wechat`
   - 只验证 UI input -> Runtime Input Router 的产品路径；
   - 不启用真实 computer-use；
   - 预期结果是 missing-message clarification 和 capability-disabled
     safety feedback；
   - 该 smoke 不证明真实微信发送。
1. reject/no-send smoke to `文件传输助手`
2. confirm/send-once smoke to `文件传输助手`

confirm smoke 必须使用 fresh idempotency key，并显式记录 evidence output。

2026-06-24 验收记录：

- preflight output:
  - `sidecarOk=true`;
  - `computerUseStatus=ok`;
  - `packageReadinessStatus=ready`;
  - `accessibilityTrusted=true`。
- confirm/send-once output:
  - `finalStatus=done`;
  - `resultKind=wechat_send_result`;
  - `evidenceCount=7`;
  - `terminalReplayStatus=done`;
  - `terminalReplaySameExecution=true`。
- terminal evidence:
  - readiness；
  - open/focus；
  - contact resolution；
  - draft；
  - confirmation request；
  - send observation with `keyboard_return`；
  - result summary。

## 16. 验收标准

- 用户可在 Main Page 输入明确微信发送请求。
- 系统能创建正确的 Execution Plane task。
- 缺失信息时不产生外部副作用。
- 发送前一定出现用户确认。
- 拒绝确认不会发送。
- 确认后只发送一次。
- 结果、错误和证据能在 Main Page 中被看到。
- 设计不依赖 Figma，不要求新增高保真 UI。

## 17. 开放问题

1. 第一版是否只允许 `文件传输助手`？
   - 推荐：测试和 smoke 阶段只允许 `文件传输助手`；产品开关允许扩展显式联系人。
2. WeChat send task 是否应该进入 Plan？
   - 推荐：作为 execution task 进入当前 session 的 activity/detail；是否纳入正式 Plan 后续再定。
3. 缺失 slot 是否使用 ASK？
   - 推荐：先用 Runtime Input Router clarification，ASK 稳定后再合并。
4. 用户重复提交同一段文本是否发送两次？
   - 推荐：主动重复提交视为新 intent；同一个 command replay 必须幂等。

## 18. 下一步

当前 UI-origin natural-language WeChat send path 已完成本地闭环验证。
后续工作应进入更高层的产品化问题，而不是继续扩展本 slice：

- 是否把首版联系人范围限制在 `文件传输助手` 之外；
- 是否为 WeChat usage 沉淀系统 skill；
- 是否开放 network Task API / remote ExecutionEnv；
- 是否把 pending clarification 升级为 durable ASK。
