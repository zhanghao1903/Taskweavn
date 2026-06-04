# Message, ASK, and Confirmation Backend 详细技术方案

> 状态: done / accepted
> 类型: Product 1.0 interaction backend technical design
> Last Updated: 2026-06-05
> Decisions: [ADR-0014 Interaction Control Taxonomy For Product 1.0](../../decisions/ADR-0014-interaction-control-taxonomy-for-product-1-0.md)
> Feature Plan: [Message, ASK, And Confirmation Backend](message-ask-confirmation-backend.md)
> Related: [ASK Lifecycle Contract](../../engineering/ask-lifecycle-contract.md), [ASK User Interaction](../../interaction-model/ask-user-interaction.md), [Task](../../architecture/task.md), [TaskBus](../../architecture/bus.md), [Context Manager](../../architecture/context-manager.md)

---

## 1. 背景

Product 1.0 当前已经有三条相关但语义不同的交互路径：

1. Message：用户可见消息历史。
2. Confirmation：Agent 已知道要做什么，但需要用户授权。
3. ASK：Agent 缺少用户拥有的信息，需要用户输入后才能继续。

现状是 MessageStream 和 confirmation 最小链路已经存在：

```text
AgentMessage(actionable)
  -> MessageBus / MessageStream
  -> pending confirmation projection
  -> resolve_confirmation
  -> AgentMessage(response)
```

但执行期 ASK 还没有后端实现。Authoring 阶段已有 RawTask ASK，但它服务的是
任务澄清和 DraftTaskTree 生成，不是 PublishedTask 执行过程中的暂停/恢复。

本方案只覆盖后端 Product 1.0 minimal，不实现前端 ASK Dock。

---

## 2. 设计决策

### 2.1 三种机制分离

| 机制 | 后端语义 | 权威数据源 |
|---|---|---|
| Message | 用户可见历史、过程消息、被动记录。 | MessageStream |
| Confirmation | 对已知 action 的授权或拒绝。 | actionable message + response message |
| ASK | 对缺失用户信息的请求和回答。 | durable ASK store |

MessageStream 可以记录 ASK 历史，但不能成为 ASK 状态权威。

### 2.2 TaskBus 新增 `waiting_for_user`

执行期 blocking ASK 会暂停当前 PublishedTask。因此 TaskBus 状态需要扩展：

```python
TaskStatus = Literal[
    "pending",
    "running",
    "waiting_for_user",
    "done",
    "failed",
]
```

基本状态机：

```text
pending
  -> running
  -> waiting_for_user
  -> pending
  -> running
  -> done / failed
```

`waiting_for_user` 是 TaskDomain 事实，不是 UI projection。它表示 task 已经
执行到一个需要用户回答 ASK 的安全等待点。

### 2.3 ASK 单独 durable store

ASK 必须独立持久化：

- `AskRequest`
- `AskAnswer`
- command idempotency record

原因：

- ASK 有自己的状态机，不等同于 message thread；
- answer 成功后才能恢复执行；
- process restart 后 pending ASK 必须可恢复；
- Main Page snapshot 需要直接暴露 ASK facts；
- 后续 ASK Dock 不应该从普通 message 文本推断 active ASK。

### 2.4 Answer-before-resume

顺序必须固定：

```text
user submits answer
  -> backend validates ASK state
  -> backend persists AskAnswer
  -> backend marks AskRequest answered
  -> backend updates TaskBus waiting_for_user -> pending
  -> backend triggers dispatcher resume
```

前端只保证 answer command 写成功后再清理本地 pending state。后端负责保证
answer 写成功之后的行为正确。

### 2.5 幂等和重复回答

Product 1.0 规则：

- 同一个 idempotency key 重放，返回同一个 command result；
- ASK 已 answered 后，新的不同 command 试图再次回答，拒绝；
- confirmation 已 resolved 后，新的不同 command 试图再次 resolve，拒绝；
- 重复拒绝必须返回结构化 command rejection，前端据此 refresh。

---

## 3. 当前代码盘点

### 3.1 MessageStream

现有核心：

- `AgentMessage`
- `MessageBus`
- `SqliteMessageStream`
- `pending_actionable(...)`
- `response_for(...)`
- `thread(...)`

可以继续作为：

- message history；
- confirmation history；
- ASK passive history。

不建议扩展 `AgentMessage.message_type` 来表达 ASK 状态。ASK 状态进入
AskStore。

### 3.2 Confirmation

现有核心：

- `DefaultTaskCommandService.resolve_confirmation(...)`
- `TaskProjectionService._confirmations_for_ref(...)`
- `ConfirmationActionView`
- `POST /api/v1/sessions/{sessionId}/confirmations/{confirmationId}/respond`

当前 confirmation id 等于 actionable message id。Product 1.0 可以继续接受这
个实现，但 command 层要补充重复响应规则。

### 3.3 ASK

现有 execution ASK 缺失：

- 无 `AskRequest` / `AskAnswer` 执行期模型；
- 无 `AskStore`；
- 无 `/asks` query/command route；
- Main Page snapshot 无 `pending_asks` / `active_ask`；
- TaskBus 无 `waiting_for_user`；
- AgentLoop 无 `ask_user` yield/resume 协议。

Authoring 的 `answer_raw_task_ask(...)` 只能作为命令模式参考，不能直接复用为
执行期 ASK。

---

## 4. Domain Model

### 4.1 AskStatus

建议新增：

```python
AskStatus = Literal[
    "pending",
    "answered",
    "deferred",
    "cancelled",
    "expired",
]
```

`answering` 不进入后端 canonical status。它是前端 local command-in-flight
状态。

### 4.2 AskRequest

建议模型：

```python
class AskRequest(BaseModel):
    ask_id: str
    session_id: str
    task_id: str | None
    agent_id: str

    question: str
    reason: str
    suggested_options: tuple[AskOption, ...]
    answer_type: Literal["free_text", "single_choice", "multi_choice", "boolean"]
    allow_free_text: bool
    allow_no_option_with_text: bool
    blocking: bool
    attachments_supported: Literal[False] = False

    status: AskStatus
    answer_id: str | None = None
    resume_hint: str | None = None

    created_at: datetime
    answered_at: datetime | None = None
    deferred_at: datetime | None = None
    cancelled_at: datetime | None = None
    expired_at: datetime | None = None
```

Product 1.0 约束：

- blocking ASK 必须有 `task_id`；
- 一个 running task 同一时间最多一个 active blocking ASK；
- session-level ASK 可以进入 store，但默认 runtime path 先只创建 task-scoped
  blocking ASK；
- `attachments_supported` 固定为 `False`。

### 4.3 AskOption

```python
class AskOption(BaseModel):
    option_id: str
    label: str
    description: str | None = None
```

### 4.4 AskAnswer

```python
class AskAnswer(BaseModel):
    answer_id: str
    ask_id: str
    session_id: str
    task_id: str | None
    selected_option_ids: tuple[str, ...]
    text: str | None = None
    attachments: tuple[()] = ()
    answered_by: Literal["user"] = "user"
    idempotency_key: str | None = None
    created_at: datetime
```

校验规则：

- answer 必须至少有一个 option 或非空 text；
- `single_choice` 最多一个 option；
- `multi_choice` 可以多个 option；
- `free_text` 可以没有 option，但必须有 text；
- `boolean` 建议以 option 表达，Product 1.0 不引入独立 boolean 字段；
- option id 必须来自 AskRequest.suggested_options。

---

## 5. Store 设计

### 5.1 Protocol

建议新增 `src/taskweavn/interaction/ask.py` 或 `src/taskweavn/ask/` 模块。
Product 1.0 推荐先放在 `interaction` 下，因为 ASK 是交互控制域。

```python
class AskStore(Protocol):
    def create(self, request: AskRequest) -> AskRequest: ...
    def get(self, session_id: str, ask_id: str) -> AskRequest | None: ...
    def list_for_session(
        self,
        session_id: str,
        *,
        status: Iterable[AskStatus] | None = None,
        task_id: str | None = None,
    ) -> list[AskRequest]: ...
    def answer(
        self,
        session_id: str,
        ask_id: str,
        answer: AskAnswer,
        *,
        idempotency_key: str | None = None,
    ) -> AskCommandStoreResult: ...
    def defer(...): ...
    def cancel(...): ...
    def expire(...): ...
```

### 5.2 SQLite 表

建议两张主表，一张幂等表。

```sql
CREATE TABLE asks (
  ask_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  task_id TEXT,
  agent_id TEXT NOT NULL,
  question TEXT NOT NULL,
  reason TEXT NOT NULL,
  suggested_options_json TEXT NOT NULL,
  answer_type TEXT NOT NULL,
  allow_free_text INTEGER NOT NULL,
  allow_no_option_with_text INTEGER NOT NULL,
  blocking INTEGER NOT NULL,
  attachments_supported INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  answer_id TEXT,
  resume_hint TEXT,
  created_at TEXT NOT NULL,
  answered_at TEXT,
  deferred_at TEXT,
  cancelled_at TEXT,
  expired_at TEXT
);

CREATE TABLE ask_answers (
  answer_id TEXT PRIMARY KEY,
  ask_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  task_id TEXT,
  selected_option_ids_json TEXT NOT NULL,
  text TEXT,
  attachments_json TEXT NOT NULL,
  answered_by TEXT NOT NULL,
  idempotency_key TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(ask_id) REFERENCES asks(ask_id)
);

CREATE TABLE ask_command_idempotency (
  scope TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  command_kind TEXT NOT NULL,
  ask_id TEXT NOT NULL,
  response_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(scope, idempotency_key)
);
```

索引：

```sql
CREATE INDEX idx_asks_session_status_created
  ON asks(session_id, status, created_at);

CREATE INDEX idx_asks_session_task_status_created
  ON asks(session_id, task_id, status, created_at);

CREATE UNIQUE INDEX idx_ask_answers_one_answer
  ON ask_answers(ask_id);
```

`idx_ask_answers_one_answer` 是拒绝重复回答的数据库级保护。

### 5.3 事务边界

answer 必须在一个事务内完成：

1. 读取 ASK row；
2. 校验 status；
3. 校验 option/text；
4. 插入 AskAnswer；
5. 更新 asks.status = `answered`；
6. 写 idempotency record。

如果同一个 idempotency key 已存在，直接返回已记录 response。

如果 ASK 已 answered 且没有匹配 idempotency record，返回 duplicate-answer
rejection。

---

## 6. TaskBus 变更

### 6.1 TaskStatus

```python
TaskStatus = Literal["pending", "running", "waiting_for_user", "done", "failed"]
```

### 6.2 TaskDomain 字段

建议新增 active ASK linkage：

```python
waiting_for_ask_id: str | None = None
waiting_for_user_since: datetime | None = None
```

约束：

- `status == "waiting_for_user"` 时 `waiting_for_ask_id` 必须存在；
- `status != "waiting_for_user"` 时 active linkage 应为空，除非后续决定保留
  last answered ASK reference。Product 1.0 建议清空 active linkage，用 AskStore
  查历史。

### 6.3 TaskBus API

新增：

```python
def wait_for_user(
    self,
    session_id: str,
    task_id: str,
    *,
    ask_id: str,
) -> TaskDomain: ...

def resume_after_user(
    self,
    session_id: str,
    task_id: str,
    *,
    ask_id: str,
) -> TaskDomain: ...
```

状态规则：

```text
running + wait_for_user(ask_id)
  -> waiting_for_user
  -> waiting_for_ask_id = ask_id

waiting_for_user + resume_after_user(same ask_id)
  -> pending
  -> waiting_for_ask_id = null

waiting_for_user + fail(...)
  -> failed
```

`resume_after_user` 不直接执行任务，只把 Task 从等待态变为可继续执行状态。
Product 1.0 的 fixed-route executor 通过重新 claim 同一个 Task 身份继续推进，
因此 resume 目标状态是 `pending`。dispatcher resume 是下一层行为。

### 6.4 claim_next

`claim_next` 只 claim `pending`。

`waiting_for_user` 不应该被 claim，因为它不是新任务，而是已有 execution run 的
暂停点。

### 6.5 dispatcher 影响

当前 fixed-route dispatcher 只处理 pending task。加入 ASK 后有两种选择：

方案 A：answer 后 `waiting_for_user -> running`，然后直接触发 resident agent
继续同一个 task run。

方案 B：answer 后 `waiting_for_user -> pending`，让 fixed-route executor 重新
claim 同一个 task。

Product 1.0 采用方案 B，除非未来 AgentLoop runner 已能保存完整 continuation。

理由：

- 当前默认执行是 task-level run，不是长期挂起 coroutine；
- process restart 后更容易恢复；
- Context Manager 可以把 previous execution facts 和 AskAnswer 放进新 run；
- TaskBus claim 逻辑改动更小。

因此 Product 1.0 的实际 resume transition 是：

```python
def resume_after_user(...):
    waiting_for_user -> pending
```

如果后续实现真正 continuation，再把目标状态改为 `running`。当前文档和测试应以
`waiting_for_user -> pending -> running` 的同 Task 身份 redispatch 为验收。

---

## 7. ASK Runtime 协议

### 7.1 ask_user 工具输入

参考 ASK lifecycle contract：

```python
class AskUserToolInput(BaseModel):
    question: str
    reason: str
    suggested_options: tuple[AskOptionInput, ...] = ()
    answer_type: Literal["free_text", "single_choice", "multi_choice", "boolean"]
    allow_free_text: bool = True
    allow_no_option_with_text: bool = True
    blocking: bool = True
```

Product 1.0 只支持 `blocking=True` 的执行期 ASK。

### 7.2 ask_user 执行顺序

```text
AgentLoop tool call ask_user
  -> AskService.create_blocking_ask(...)
  -> AskStore.create(...)
  -> MessageBus.publish(ASK created informational history)
  -> TaskBus.wait_for_user(task_id, ask_id)
  -> AgentLoop yields with ask_pending result
  -> FixedRouteTaskExecutor returns waiting_for_user result
```

创建顺序建议：

1. 先写 AskStore；
2. 再写 TaskBus waiting state；
3. 再写 MessageStream history。

如果 MessageStream 写失败，不应回滚 ASK 事实。Message 是历史/展示，不是 ASK
权威。失败应进入日志/audit。

### 7.3 AgentLoop result

建议 resident agent run result 增加：

```python
status: Literal["ok", "failed", "waiting_for_user"]
ask_id: str | None
```

FixedRouteTaskExecutor 看到 waiting result 后不要调用 complete/fail。

### 7.4 Answer 后 resume

```text
answer command accepted
  -> AskStore.answer transaction committed
  -> TaskBus.resume_after_user(task_id, ask_id)
  -> MessageBus.publish(ASK answered history)
  -> ExecutionDispatcher.request_dispatch(session_id, reason="ask_answered")
```

如果 dispatcher trigger 失败，但 answer 已写成功：

- answer 仍然是成功事实；
- command response 应包含 warning/refresh hints；
- 后续手动 dispatch 或恢复流程可以继续。

不要因为 dispatcher trigger 失败回滚 AskAnswer。

---

## 8. Command / Query API

### 8.1 Payloads

```python
class AnswerAskPayload(UiContractModel):
    selected_option_ids: tuple[str, ...] = ()
    text: str | None = Field(default=None, min_length=1)
    attachments: tuple[()] = ()

class DeferAskPayload(UiContractModel):
    reason: str | None = Field(default=None, min_length=1)

class CancelAskPayload(UiContractModel):
    reason: str = Field(min_length=1)
```

`CommandRequest.command_id` 或 explicit idempotency key 作为幂等 key。应沿用现
有 command idempotency 约定。

### 8.2 Routes

```text
GET  /api/v1/sessions/{sessionId}/asks
GET  /api/v1/sessions/{sessionId}/asks/{askId}
POST /api/v1/sessions/{sessionId}/asks/{askId}/answer
POST /api/v1/sessions/{sessionId}/asks/{askId}/defer
POST /api/v1/sessions/{sessionId}/asks/{askId}/cancel
```

### 8.3 CommandResponse

answer accepted response should suggest:

```text
session.snapshot
session.messages
asks
task.tree
task.detail
```

affected scopes:

- asks;
- messages;
- task tree;
- task detail for owning task;
- audit if available.

---

## 9. Projection / ViewModel

### 9.1 AskRequestView

建议 backend UI contract 增加：

```python
class AskOptionView(UiContractModel):
    id: str
    label: str
    description: str | None = None

class AskRequestView(UiContractModel):
    id: str
    session_id: str
    task_node_id: str | None = None
    task_ref: TaskRef | None = None
    question: str
    reason: str
    suggested_options: tuple[AskOptionView, ...] = ()
    answer_type: Literal["free_text", "single_choice", "multi_choice", "boolean"]
    allow_free_text: bool
    allow_no_option_with_text: bool
    blocking: bool
    attachments_supported: Literal[False] = False
    status: Literal["pending", "answered", "deferred", "cancelled", "expired"]
    created_at: datetime
    answered_at: datetime | None = None
```

### 9.2 MainPageSnapshot

新增：

```python
pending_asks: tuple[AskRequestView, ...] = ()
active_ask: AskRequestView | None = None
```

active ASK 选择规则：

1. selected task 的 pending ASK；
2. current `waiting_for_user` task 的 pending ASK；
3. oldest blocking session-level pending ASK；
4. oldest non-blocking/deferred candidate。

Product 1.0 可以先只实现 1 和 2。

### 9.3 TaskCardView

如果 `TaskDomain.status == "waiting_for_user"`：

- execution/status 显示等待用户；
- 不等同于 pending confirmation；
- 不显示 `can_resolve_confirmation`；
- 可显示 `can_answer_ask` 或由 `active_ask` 驱动输入区。

具体前端 affordance 不在本 backend slice 实现。

---

## 10. Events

建议新增 UI events：

```text
ask.created
ask.answered
ask.deferred
ask.cancelled
ask.expired
```

Product 1.0 可以先发 invalidation event，不强制 payload 包含完整
`AskRequestView`。

Reducer 规则：

- event payload 完整时可 patch；
- payload 只有 id 时 refetch `/asks/{askId}` 或 session snapshot；
- malformed event 触发 resync，不做 optimistic final state。

---

## 11. Context Manager Integration

Context Manager 输入事实新增 ASK source：

```python
class AskContextFact(BaseModel):
    ask_id: str
    task_id: str | None
    status: AskStatus
    question: str
    selected_option_ids: tuple[str, ...] = ()
    answer_text: str | None = None
    blocking: bool
    created_at: datetime
    answered_at: datetime | None = None
```

渲染策略：

- pending ASK：告诉 Agent 当前任务正在等待用户，不要继续猜测；
- answered ASK：告诉 Agent 用户回答内容，并允许继续；
- cancelled/deferred/expired：告诉 Agent 按 backend policy 处理，不要假装有回答。

Cache-aware rendering 下，ASK answered 应作为 delta trigger：

```text
context delta: user answered ASK <ask_id>: ...
```

---

## 12. 语义修正

需要修正的已知问题：

- `session_status.py` 当前把 pending actionable 注释成 `ask_user` suspended。
  这应改成 pending confirmation/actionable，后续 ASK 应从 AskStore 推导
  awaiting-user 信号。
- 文档和测试里的 `ask1` 用作 confirmation fixture id 时，应逐步改名为
  `confirmation-1`，避免把 confirmation 与 ASK 混淆。
- `MessageType = actionable` 不应在说明中等同 ASK。它是 confirmation/actionable
  message。

---

## 13. Test Plan

### 13.1 Store tests

- create pending ASK；
- list by session/status/task；
- answer success；
- duplicate answer rejection；
- same idempotency key replay；
- defer/cancel/expire state transitions；
- SQLite restart persistence。

### 13.2 TaskBus tests

- `running -> waiting_for_user`；
- `waiting_for_user -> pending` resume path；
- `waiting_for_user -> failed`；
- claim ignores `waiting_for_user`；
- children remain blocked until parent `done`；
- retry clears active ASK linkage according to policy。

### 13.3 Command gateway / HTTP tests

- answer route parses payload；
- missing ASK returns not found；
- wrong session rejected；
- invalid option rejected；
- duplicate answer rejected；
- accepted response has affected scopes and suggested queries。

### 13.4 Projection tests

- snapshot includes `pending_asks`；
- active ASK chosen deterministically；
- task card status distinguishes `waiting_for_user` from pending confirmation；
- confirmation resolved projection remains unchanged。

### 13.5 Runtime integration tests

- Agent calls ask_user；
- AskRequest persisted；
- Task moves to `waiting_for_user`；
- answer persists AskAnswer；
- task re-enters executable state；
- dispatcher receives resume trigger；
- Context Manager includes answer fact before resumed LLM call。

---

## 14. Implementation Order

推荐顺序：

1. C2 confirmation backend hardening and terminology cleanup。
2. C3 ASK domain/store。
3. C4 TaskBus `waiting_for_user`。
4. C5 ASK commands/queries/snapshot。
5. C6 runtime `ask_user` and resume integration。
6. C7 tests/docs closure。

不建议先做 runtime `ask_user`。没有 durable store 和 TaskBus 等待态时，runtime
ASK 只能退化成 message prompt，无法保证 Product 1.0 闭环。

---

## 15. 验收标准

后端实现可验收的标准：

1. ASK 是 durable object，不依赖 MessageStream 推断状态。
2. blocking ASK 能让 PublishedTask 进入 `waiting_for_user`。
3. answer 写入成功后，后端保证 task 进入可恢复执行路径。
4. 重复 answer/confirmation resolve 被拒绝，幂等重放除外。
5. Main Page snapshot 能直接拿到 `pending_asks` 和 `active_ask`。
6. Context Manager resume input 包含用户回答事实。
7. confirmation 仍保持独立授权语义。
8. 相关注释、fixture、文档不再把 ASK 和 confirmation 混用。

---

## 16. 实现状态

当前后端 slice 已完成 Product 1.0 backend closure：

- C2 confirmation backend hardening and terminology cleanup：done。
- C3 ASK domain/store：done。
- C4 TaskBus `waiting_for_user`：done。
- C5 ASK commands/queries/snapshot：done。
- C6 runtime `ask_user` and resume integration：done。
- C7 tests/docs closure：done。

剩余工作转入单独的前端/交互 slice：Main Page ASK Dock、answer UI、
confirmation UI integration、event/refetch polish，以及最终 Product 1.0 QA。
