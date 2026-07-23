# Interaction Layer 架构事实

> Status: current implementation fact document
>
> Calibrated: 2026-07-10
>
> Original historical document:
> [interaction-layer.original.md](archive/original/interaction-layer.original.md)
>
> Calibration record:
> [fix-log/interaction-layer.md](fix-log/interaction-layer.md)

## 1. 文档目的

本文描述当前仓库中已经存在并被实际装配的用户交互机制。它回答以下问题：

- 缺少用户信息时，执行 Agent 如何创建 ASK 并暂停 Published Task；
- 已知动作需要授权时，confirmation 如何持久化、展示和响应；
- `AgentMessage`、`MessageStream` 和 `MessageBus` 分别承担什么职责；
- 可选的 `AutonomyGate` 在哪里实际启用，哪些运行路径没有启用；
- Main Page、Runtime Input Router、Activity 和 Session 状态如何读取这些事实；
- 当前持久化、并发、幂等、恢复和续跑边界是什么。

本文不把历史 Phase 计划、候选 API 或未来跨进程实现写成当前能力。代码注释中的未来描述只有在存在调用点和测试时才作为现状。

## 2. 当前结论

当前系统没有一个统一的“交互对象”或统一状态机。至少有四个语义不同的机制：

| 机制 | 用户意图 | 后端事实权威 | 是否改变 Published Task 生命周期 | 当前主要入口 |
| --- | --- | --- | --- | --- |
| Authoring ASK | 在 TaskTree 生成前澄清规划意图 | RawTask / authoring store | 否 | Authoring ASK Work Area、批量回答命令 |
| Execution ASK | 执行缺少用户拥有的信息 | `AskStore`，并由 `TaskBus` 记录等待关联 | 是，`running -> waiting_for_user` | `ask_user` 工具、ASK answer/defer/cancel 命令 |
| Confirmation | 已知动作需要用户授权 | pending actionable `AgentMessage`；`TaskBus` 记录等待关联 | 是，`running -> waiting_for_user` | `request_confirmation` 工具、confirmation respond 命令 |
| Optional autonomy gate | 普通工具动作按风险或不确定性自动询问 | actionable/response `AgentMessage`；运行中的内存 pending 队列 | 不使用 Published Task 等待关联 | 通用 CLI `taskweavn run --autonomy ...` |

这四者可以共享 UI 基础控件，但不能共享后端权威语义：

- Authoring ASK 不属于 execution `AskStore`，也不暂停 `TaskBus`；
- Execution ASK 不是普通 `AgentMessage` 行，`AskStore` 才拥有 ASK 状态；
- confirmation 没有独立 Confirmation 表，其事实是 actionable/response 消息；
- autonomy gate 是 AgentLoop 的可选执行策略，不是 Main Page 默认执行路径。

## 3. 权威数据与持久化位置

Main Page workspace runtime 使用 `WorkspaceLayout` 解析以下路径：

| 事实 | 当前存储 | 写入者 / 权威 |
| --- | --- | --- |
| informational/actionable/response 消息 | `<workspace>/.plato/messages.sqlite` | `MessageBus.publish()` 支持的写路径；`SqliteMessageStream` 持久化 |
| Execution ASK 请求与回答 | `<workspace>/.plato/asks.sqlite` | `AskStore` / `SqliteAskStore` |
| Published Task 与等待关联 | `<workspace>/.plato/tasks.sqlite` | `TaskBus` / `SqliteTaskBus` |
| Authoring ASK、RawTask、Draft TaskTree | `<workspace>/.plato/authoring.sqlite` | authoring domain stores |
| AgentLoop action/observation 事件 | `<workspace>/.plato/sessions/<session-id>/events.sqlite` | per-session `SqliteEventStream` |
| UI command 响应幂等 | `<workspace>/.plato/ui_commands.sqlite` | UI transport idempotency store |
| UI event replay | `<workspace>/.plato/ui_events.sqlite` | sidecar UI event store |

`Session Activity` 是从消息、ASK、confirmation、Plan、Task、result 和 file summary 等事实投影出的读模型，不是新的领域事实库。Runtime Input 活动也会通过 `MessageBus` 写入 informational 消息，再进入 Activity 投影。

## 4. AgentMessage 与 MessageStream

### 4.1 AgentMessage 模型

`AgentMessage` 是 frozen、`extra="forbid"` 的 Pydantic 模型。消息类型只有三种：

- `informational`：通知或用户输入记录；
- `actionable`：等待回应的交互提示；
- `response`：对 actionable 的回应。

公共身份字段包括：

- `message_id`；
- `session_id`；
- 可选 `task_id`；
- `agent_id`；
- 可选 `parent_message_id`；
- `created_at`。

与 actionable 相关的字段包括：

- `action_options`；
- `requires_response`；
- `timeout_seconds`；
- `risk_assessment`；
- `related_action_id`。

与 response 相关的字段包括：

- `response_source`；
- `response_value`。

当前模型只为 `risk_assessment` 提供了类型转换校验，没有按 `message_type` 强制以下业务约束：

- actionable 必须 `requires_response=true`；
- response 必须在模型构造时带 parent；
- response value 必须属于 `action_options`；
- informational 不能携带 actionable/response 字段。

这些约束的一部分在存储或命令服务中实现，剩余部分只是生产者约定。

### 4.2 MessageStream 读接口

`MessageStream` 提供：

- `get(message_id)`；
- 按 session、task、agent 列表读取；
- `pending_actionable(session_id, task_id=...)`；
- `response_for(message_id)`；
- `thread(message_id)`；
- `len(stream)`。

列表查询按 `(created_at ASC, insertion id ASC)` 排序。因此相同时间戳的消息仍有确定总序。

`pending_actionable` 的当前定义是：

1. 同一 session 中 `message_type='actionable'`；
2. 可选地按 `task_id` 收紧；
3. 不存在以该消息为 parent 的 response 行。

它不检查 `requires_response`。因此任何未被 response 回答的 actionable 都会被视为 pending，并可进入 confirmation 和 Session 状态投影。

### 4.3 SQLite 写入约束

`SqliteMessageStream._insert()` 当前验证：

- `message_id` 全表唯一；
- response 必须带 `parent_message_id`；
- parent 必须存在；
- parent 必须是 actionable。

当前没有验证：

- response 与 parent 的 `session_id`、`task_id` 一致；
- 每个 actionable 最多只有一个 response；
- response value 属于 parent 的 options。

数据库也没有 `UNIQUE(parent_message_id)` 约束。因此不同写入者可以为同一 actionable 插入多条 response。`response_for()` 以 `(created_at, insertion id)` 最早的一条作为规范回答，后续 response 仍保留在表中。

## 5. MessageBus

### 5.1 当前实现

`MessageBus` Protocol 定义：

- `publish(message)`；
- `subscribe(session_id, types=...)`；
- `wait_for_response(message_id, timeout)`；
- `stream` 只读视图。

仓库中当前唯一实现是 `InProcessMessageBus`。不存在已实现的 `SqliteMessageBus` 或 Redis bus。

`InProcessMessageBus` 使用一个 `threading.Condition` 协调：

1. `publish()` 在 condition 锁内先调用 stream `_insert()`；
2. 再把消息放入匹配订阅者的 deque；
3. 最后 `notify_all()` 唤醒等待者。

因此本进程内的等待者在收到通知前可以从 SQLite 读到已提交消息。

### 5.2 等待与订阅语义

`wait_for_response`：

- `timeout=None`：无限等待，除非 bus 被关闭；
- `timeout=0`：非阻塞查询；
- 正数：等待到 deadline；
- bus 关闭且没有 response：返回 `None`。

订阅只收到订阅建立后的 future publish。读取历史必须先走 `MessageStream`，再附着 live subscription。

订阅 deque 当前无上限，没有 backpressure 或 drop policy。bus 关闭会结束订阅并唤醒 response 等待者。

“MessageBus 是单写者”是受支持 API 和代码约定，不是 Python 级不可绕过能力；`SqliteMessageStream._insert()` 仍可被直接调用。

## 6. Execution ASK

### 6.1 领域对象

Execution ASK 的事实权威是 `AskStore`，不是 MessageStream。

`AskRequest` 主要包含：

- `ask_id`、`session_id`、可选 `task_id`、`agent_id`；
- 主问题 `question` 与原因 `reason`；
- 可选的 `questions` 子问题集合；
- 建议选项；
- `answer_type`：`free_text`、`single_choice`、`multi_choice`、`boolean`；
- free-text 策略；
- `blocking`；
- 状态和各终态时间戳。

ASK 状态为：

- `pending`；
- `answered`；
- `deferred`；
- `cancelled`；
- `expired`。

blocking ASK 必须有 `task_id`。Product 当前固定 `attachments_supported=false`，`AskAnswer` 也拒绝非空 attachments。

一个 `AskRequest` 可以包含多个子问题，但仍由一个 `AskAnswer` 关闭；这不等于多个并行 execution ASK 组成的 group。

### 6.2 创建与暂停流程

Main Page Default Agent 在同时具有 `ask_store`、`task_bus` 和 `task_id` 时注册 `AskUserTool`。

```text
AgentLoop tool call: ask_user
  -> AskUserTool creates AskRequest in AskStore
  -> TaskBus.wait_for_user(..., ask_id)
  -> Task status becomes waiting_for_user
  -> tool returns AskUserObservation(status=waiting_for_user)
  -> AgentLoop returns stop_reason=waiting_for_user
```

`TaskBus.wait_for_user` 只允许 `running` Task 进入等待状态。

ASK 创建和 Task 状态更新属于两个数据库，没有跨库事务。如果 ASK 创建成功而 TaskBus 更新失败，ASK 行不会自动回滚。

### 6.3 回答、defer 与 cancel

`DefaultTaskAskCommandService` 的顺序是：

1. 先调用 `AskStore` 持久化命令结果；
2. 只有首次 `accepted` 才改变 Task 生命周期；
3. answer 尝试把匹配的 waiting Task 恢复为 `pending`；
4. defer/cancel 尝试把匹配的 waiting Task 标记为 `failed`；
5. idempotent replay 不重复执行 Task 生命周期变化。

回答会验证：

- session、ASK、task 目标一致；
- ASK 仍为 `pending`；
- option id 存在；
- answer type、选项数量和 free-text 策略匹配。

SQLite store 在一个数据库事务内写 ASK 状态、唯一 answer 行和 ASK command idempotency 结果。幂等键作用域是 `(session_id, idempotency_key)`，结果分为 `accepted`、`replayed`、`rejected`。

ASK Store 与 TaskBus 之间仍不是单事务。ASK 已回答但 Task resume 失败时，回答事实保持有效；命令结果会带 resume 失败或跳过说明。

### 6.4 续跑与恢复

HTTP execution ASK answer 路径在命令 accepted 后调用 `ExecutionTriggerGateway.request_dispatch(..., reason="ask_answer_resume")`。dispatch 失败不会回滚已经接受的 ASK answer。

下一次 Main Page AgentLoop 通过 `AskContextSource` 读取当前 Task 的 pending/answered ASK 事实；answered ASK 的回答会进入新运行的 Context Manager 输入。

snapshot 读取前还会 best-effort 调用 `DefaultAskRecoveryService`：

- 对已 answered、blocking、具有 task_id 的 execution ASK；
- 若 Task 仍在等待该 ASK，则先恢复为 pending；
- 若 Task 已为 pending，则可以请求 execution dispatch；
- 恢复异常不会让 snapshot 读取失败。

这是一种 ASK 专用的补偿路径，不是 ASK Store 与 TaskBus 的原子提交。

## 7. Confirmation

### 7.1 当前权威模型

当前没有独立 `Confirmation` 数据表或 store。一个 confirmation 由以下事实组成：

- pending actionable `AgentMessage` 是 confirmation 请求；
- response `AgentMessage` 是回答；
- Published Task 的 `waiting_for_confirmation_id` 关联当前等待对象。

Task projection 会把给定 Task 的所有 pending actionable 消息转换为 `ConfirmationActionView`，并不要求消息具有独立 confirmation discriminator。

### 7.2 创建与暂停流程

Main Page Default Agent 在具有 `message_bus`、`task_bus` 和 `task_id` 时注册 `RequestConfirmationTool`。

```text
AgentLoop tool call: request_confirmation
  -> RequestConfirmationTool publishes actionable AgentMessage
  -> TaskBus.wait_for_confirmation(..., confirmation_id=message_id)
  -> Task status becomes waiting_for_user
  -> tool returns RequestConfirmationObservation(status=waiting_for_user)
  -> AgentLoop returns stop_reason=waiting_for_user
```

默认 options 为 `confirm`、`reject`。允许 session approval 时可以增加 `approve_session`，但当前类型契约明确说明：它只记录该值，不会自动绕过未来 confirmation。

消息写入和 TaskBus 状态更新属于两个数据库。如果 actionable 已发布而 TaskBus 更新失败，该 actionable 不会自动回滚。

### 7.3 回答与恢复 Task

`DefaultTaskCommandService.resolve_confirmation()` 当前检查：

- message bus 已配置；
- confirmation id 存在；
- parent 属于当前 session；
- parent 是 actionable；
- 尚无 canonical response；
- value 非空。

随后它先发布 response 消息，再尝试把匹配 `waiting_for_confirmation_id` 的 Published Task 恢复为 `pending`。

当前命令不校验 value 是否属于 `action_options`，也不把 `reject` 解释为拒绝执行。任何非空值都可以关闭 confirmation 并恢复 Task。`approve_session` 也没有形成后续授权策略。

UI transport 的 confirmation respond 路由本身没有调用 execution dispatch helper。与 ASK answer 路径不同，confirmation 被恢复为 pending 后仍需要后续 dispatcher trigger/tick 才会重新执行。

当前 Context Manager 有 `AskContextSource`，但没有 MessageStream/confirmation response source。因此 response 的 `response_value` 不会作为结构化 confirmation 答案直接进入下一次 Main Page AgentLoop 上下文。不能把“已恢复 Task”解释为当前实现已经向 Agent 注入了所选授权值。

当前也没有与 `DefaultAskRecoveryService` 对等的 confirmation snapshot recovery。response 已写入但 Task resume 失败时，没有专门的 confirmation 补偿器。

## 8. Main Page 显式交互与 CLI Autonomy 的边界

### 8.1 Main Page 默认路径

Main Page `AgentLoop` 装配：

- 注册 `ask_user` 和 `request_confirmation` 工具；
- 不传 `gate`、`wait_coordinator` 或 AgentLoop interaction `bus` 字段；
- 通过工具显式创建 ASK/confirmation；
- 通过 blocking observation 结束当前 run；
- 由 TaskBus、UI command 和 execution dispatcher 组织后续 run。

因此 Main Page 不是“每个普通工具动作都自动经过 AutonomyGate”的运行模式。

### 8.2 通用 CLI 可选路径

通用 CLI `taskweavn run` 只有在传入 `--autonomy <preset>` 时才装配：

- `SqliteMessageStream`；
- `InProcessMessageBus`；
- `RiskAssessor`；
- `AutonomyGate`；
- `WaitCoordinator`；
- 读取 stdin response 的线程。

该路径默认使用显式 `--messages-db`，否则使用 `<log-dir>/messages.sqlite`；它不自动等同于 Main Page 的 workspace `.plato/messages.sqlite`。

### 8.3 AutonomyGate 决策

`AutonomyGate` 是纯决策组件，不发布消息也不阻塞。它返回：

- `PROCEED`；
- `EMIT`。

trigger 语义：

| trigger | 当前行为 |
| --- | --- |
| `never` | 总是 proceed |
| `always` | 总是 emit actionable |
| `on_risk` | `assessment.final >= risk_threshold` 时 emit |
| `on_uncertainty` | confidence 低于阈值时 emit |

没有 `ConfidenceProvider` 时 confidence 固定为 `1.0`。CLI 当前构造 gate 时没有传 provider，因此 `collaborative` 的 `on_uncertainty` 预设不会触发询问。

风险模型保证：

- score 在 `[0, 1]`；
- dynamic 不低于 action class baseline；
- final 为 baseline 与 dynamic 的最大值；
- `BaselineOnlyAssessor`、`LLMRiskAssessor`、`CompositeAssessor` 已实现；
- LLM assessor 失败时回退到 baseline，不中断 loop。

### 8.4 WaitCoordinator

`WaitCoordinator` 只处理已经发布的 actionable。

`sync`：

- 收到 response：返回 `GOT_RESPONSE`；
- timeout action 为 `wait`：继续无限等待；
- `skip`：不执行 action；
- `proceed_default`：选择第一个 option；
- `proceed_confident`：当前也选择第一个 option，并没有 confidence-based 选择。

`async`：

- 立即返回 `PENDING`；
- AgentLoop 把原 action 放入内存 `_pending_decisions`；
- 后续 step 使用 `wait_for_response(timeout=0)` 轮询；
- 非拒绝回复到达后才执行原 action；
- run 结束后仍未解决的 pending entry 从内存丢弃，actionable 消息仍保留在 SQLite。

timeout 自动 proceed/skip 时，coordinator 可以发布 informational notice，但不会写 response 行。因此原 actionable 仍满足 `pending_actionable` 查询，可能继续被投影为待用户处理。

AgentLoop 把以下 response value 视为拒绝 token：`no`、`n`、`deny`、`reject`、`skip`、`cancel`、`abort`。其他值，包括空值，走 proceed。

## 9. Task 与 Session 状态

### 9.1 Published Task

Published Task 执行状态包括：

- `pending`；
- `running`；
- `waiting_for_user`；
- `done`；
- `failed`。

当状态为 `waiting_for_user` 时，`TaskDomain` 强制恰好存在一个活动关联：

- `waiting_for_ask_id`；或
- `waiting_for_confirmation_id`。

非等待状态不能保留上述关联或 `waiting_for_user_since`。

ASK answer 和 confirmation response 的正常 resume 都把 Task 变回 `pending`，不是直接回到 `running`。后续 execution dispatcher 再 claim 并运行。

### 9.2 Core Session 派生函数

`core.session_status.derive_session_status()` 的规则是：

1. stored `archived` 优先；
2. MessageStream 有 pending actionable -> `awaiting_user`；
3. EventStream 最后一个事件是 `AgentFinishObservation` -> `finished`；
4. 否则 `active`。

当前生产代码没有调用这个 core helper；它的直接调用点在测试中。

### 9.3 Main Page Session 投影

Main Page snapshot 使用独立的 `_derive_session_status()`，它依次考虑：

- active execution ASK；
- pending authoring ASK；
- pending confirmations；
- TaskTree 中 waiting/running/completed/failed 状态；
- stored Session 状态；
- 是否已有 messages。

UI 状态词使用 `waiting_user`，与 Task 的 `waiting_for_user`、core Session 的 `awaiting_user` 不同。跨层比较必须显式映射，不能直接比较字符串。

## 10. UI、HTTP、Runtime Input 与 Activity

### 10.1 Query 与 command 面

与当前交互层直接相关的 HTTP 路由包括：

| Method | Route | 作用 |
| --- | --- | --- |
| GET | `/api/v1/sessions/{sessionId}/snapshot` | 读取 messages、pending confirmations、planning/pending/active ASK 等聚合状态 |
| GET | `/api/v1/sessions/{sessionId}/activity` | 读取 Session Activity 投影 |
| GET | `/api/v1/sessions/{sessionId}/asks` | execution ASK 列表 |
| GET | `/api/v1/sessions/{sessionId}/asks/{askId}` | execution ASK 详情 |
| POST | `/api/v1/sessions/{sessionId}/asks/{askId}/answer` | 回答 execution ASK，并在 accepted 后请求 dispatch |
| POST | `/api/v1/sessions/{sessionId}/asks/{askId}/defer` | defer execution ASK |
| POST | `/api/v1/sessions/{sessionId}/asks/{askId}/cancel` | cancel execution ASK |
| POST | `/api/v1/sessions/{sessionId}/confirmations/{confirmationId}/respond` | 写 confirmation response 并尝试恢复 Task |
| POST | `/api/v1/sessions/{sessionId}/authoring/raw-tasks/{rawTaskId}/asks/answers` | 批量回答 Authoring ASK |
| POST | `/api/v1/sessions/{sessionId}/runtime-input/route` | 根据当前交互上下文路由统一输入 |

Runtime Input Router 先查 active execution ASK，再查 active confirmation：

- 有 active ASK 时，输入被路由为 ASK answer；
- 无 ASK 但有 active confirmation 时，输入被解析为 confirmation response，无法确定时返回 clarification；
- 没有活动交互时才继续 stop/retry/inquiry/guidance/change 等分类。

### 10.2 Frontend

当前前端已经存在：

- `AuthoringAskWorkArea`；
- `ExecutionAskDetailPanel`；
- `ConfirmationDetailPanel`；
- domain-neutral `ChoiceGroup`；
- Main Page controller 中对应的本地 draft、pending、error 和 refetch 行为。

前端不把 command accepted 当作最终领域事实。命令完成后仍通过 snapshot/refetch 收敛 ASK、confirmation 和 Task 状态。

### 10.3 Activity 与 UI events

Activity projection 会组合：

- AgentMessage；
- pending/active ASK；
- confirmation；
- Plan/Task/result/file summary；
- Runtime Input 写入的活动消息。

Activity 与 Audit 是不同读模型；用户交互 Activity 不能替代 action/observation 审计。

后端 `UiEventType` 和 helper 声明了 `ask.created/answered/deferred/cancelled/expired`，但当前生产代码没有调用这些 ASK event helper，前端 `UiEventType` 也不包含 ASK event 类型。因此 ASK 的当前可靠收敛路径是 command response 加 snapshot/refetch，不应声明为完整的 ASK live-event 流。

## 11. 并发、幂等与恢复边界

| 场景 | 当前保证 | 当前限制 |
| --- | --- | --- |
| 同一 message id 重复 publish | SQLite unique 拒绝 | 不等于同一 actionable 只能有一个 response |
| 同一 confirmation 的两个不同 response | `response_for` 选择最早一条 | pre-check 与 insert 非同一唯一约束，竞争时可以保留多条 response |
| ASK 重复命令 | `(session_id, idempotency_key)` replay | 不带幂等键的重复命令按 ASK 当前状态拒绝 |
| UI command 重放 | sidecar 有 workspace UI command response idempotency store | 只覆盖经过该 transport 且复用命令标识的调用 |
| ASK create + Task wait | 每个 store 自身持久 | 无跨库事务，可能留下 pending ASK |
| confirmation create + Task wait | message 与 Task 各自持久 | 无跨库事务，可能留下 pending actionable |
| ASK answer + Task resume | ASK 先持久；snapshot recovery 可补偿 | 不是原子提交；dispatch 也可能失败 |
| confirmation response + Task resume | response 先持久；匹配时恢复 Task | 没有 confirmation 专用恢复器；route 不自动 dispatch |
| 进程重启 | messages、ASK、Task facts 保留 | Condition、subscription queue、CLI async pending queue 不保留 |
| 多进程等待 | SQLite 行可被其他进程看到 | `InProcessMessageBus` 不会被其他进程 publish 唤醒 |

## 12. 当前已知限制

1. 只有 `InProcessMessageBus`；跨进程 SQLite polling bus 和 Redis bus 未实现。
2. AgentMessage 缺少按 message type 的完整模型校验。
3. MessageStream 不限制一个 actionable 只能有一个 response。
4. `pending_actionable` 不检查 `requires_response`。
5. Task projection 将所有 pending actionable 映射为 confirmation。
6. confirmation value 不受 action options 约束；`reject` 也会恢复 Task。
7. `approve_session` 不会形成后续免确认策略。
8. confirmation respond 路由不会像 ASK answer 一样请求 execution dispatch。
9. confirmation response value 不是当前 Context Manager source。
10. confirmation 没有 ASK recovery 对等补偿器。
11. ASK/message 与 Task 生命周期变化没有跨库事务。
12. `on_uncertainty` 在无 ConfidenceProvider 时不会触发。
13. `proceed_confident` 当前与 first-option default 相同。
14. timeout 自决只写 informational notice，原 actionable 仍 pending。
15. async autonomy pending action 只存在于当前 AgentLoop run 的内存。
16. Main Page 默认 AgentLoop 不装配 AutonomyGate。
17. Execution ASK attachment 当前不支持。
18. ASK UI event helper 已定义，但生产 emit 与前端事件类型尚未闭合。

## 13. 代码事实索引

核心消息与 autonomy：

- `src/taskweavn/interaction/message.py`
- `src/taskweavn/interaction/sqlite_message_stream.py`
- `src/taskweavn/interaction/bus.py`
- `src/taskweavn/interaction/autonomy.py`
- `src/taskweavn/interaction/gate.py`
- `src/taskweavn/interaction/risk.py`
- `src/taskweavn/interaction/wait.py`

ASK 与 confirmation：

- `src/taskweavn/interaction/ask.py`
- `src/taskweavn/interaction/sqlite_ask_store.py`
- `src/taskweavn/tools/ask.py`
- `src/taskweavn/tools/confirmation.py`
- `src/taskweavn/types/ask.py`
- `src/taskweavn/types/confirmation.py`
- `src/taskweavn/task/ask_service.py`
- `src/taskweavn/task/commands.py`
- `src/taskweavn/task/models.py`
- `src/taskweavn/task/sqlite_bus.py`

AgentLoop 与装配：

- `src/taskweavn/core/loop.py`
- `src/taskweavn/cli/main.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/main_page_agent.py`
- `src/taskweavn/server/ask_recovery.py`

UI contract 与前端：

- `src/taskweavn/server/ui_http.py`
- `src/taskweavn/server/ui_http_routes.py`
- `src/taskweavn/server/ui_http_commands.py`
- `src/taskweavn/server/runtime_input_router.py`
- `src/taskweavn/server/ui_contract/command_gateway.py`
- `src/taskweavn/server/ui_contract/query_snapshot_helpers.py`
- `src/taskweavn/server/ui_contract/session_activity_projection.py`
- `src/taskweavn/server/ui_contract/events.py`
- `frontend/src/pages/main-page/interaction/AuthoringAskWorkArea.tsx`
- `frontend/src/pages/main-page/interaction/ExecutionAskDetailPanel.tsx`
- `frontend/src/pages/main-page/interaction/ConfirmationDetailPanel.tsx`

## 14. 验证原则

修改本架构事实时，至少覆盖：

- AgentMessage 与 SQLite round trip、pending/response 语义；
- MessageBus publish/subscribe/wait/close；
- autonomy gate、risk assessor、WaitCoordinator、AgentLoop interaction；
- ASK store、Task ASK service、TaskBus waiting 生命周期与 recovery；
- confirmation tool/command、Main Page sidecar 真实装配；
- query/command/runtime-input/activity 投影；
- 前端 Authoring ASK、Execution ASK、Confirmation 和 controller 收敛行为。

本次具体命令与结果记录在
[fix-log/interaction-layer.md](fix-log/interaction-layer.md)。
