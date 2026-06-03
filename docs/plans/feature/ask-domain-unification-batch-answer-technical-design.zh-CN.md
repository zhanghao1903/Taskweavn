# ASK Domain Unification And Batch Answer 详细技术方案

> 状态: in progress
> 类型: Product 1.0 interaction UX/API alignment technical design
> Last Updated: 2026-06-04
> Feature Plan: [ASK Domain Unification And Batch Answer](ask-domain-unification-batch-answer.md)
> Related: [Message, ASK, And Confirmation Backend](message-ask-confirmation-backend.md), [ASK Lifecycle Contract](../../engineering/ask-lifecycle-contract.md), [Authoring Domain](../../architecture/authoring-domain.md), [Interaction Layer](../../architecture/interaction-layer.md)

---

## 1. 背景

当前系统有两种 ASK：

1. Authoring ASK：`RawTaskAsk`，用于 RawTask 阶段澄清用户意图、约束或权限前提。
2. Execution ASK：`AskRequest`，用于 PublishedTask 执行中缺少用户输入时暂停任务。

这两类 ASK 对用户都表现为“系统在问问题”，但它们的系统语义不同。Authoring
ASK 阻塞的是任务规划，Execution ASK 阻塞的是任务执行。两者不能合并成同一个
后端权威模型。

用户体验上，Authoring ASK 经常是成组出现的。用户看到后续问题后，可能会改变
对前面问题的回答。因此 Product 1.0 需要支持前端保存本地草稿，并一次性提交
多个 authoring answers。

---

## 2. 核心决策

### 2.1 统一 UI 表达，不统一权威数据源

前端可以复用同一套 ASK 组件，但 projection 必须携带 domain：

```python
AskDomain = Literal["authoring", "execution"]
AskScope = Literal["planning", "task"]
```

Authoring ASK 的权威数据源仍是 RawTask store。Execution ASK 的权威数据源仍是
durable AskStore。MessageStream 只能记录历史，不是 ASK 状态权威。

### 2.2 Authoring ASK 和 Execution ASK 的差异

| 维度 | Authoring ASK | Execution ASK |
|---|---|---|
| 发生阶段 | Task Tree 生成前 | PublishedTask 执行中 |
| 后端对象 | `RawTaskAsk` / `RawTaskAnswer` | `AskRequest` / `AskAnswer` |
| 权威数据源 | RawTask store | AskStore |
| 阻塞对象 | authoring pipeline | TaskBus lifecycle |
| 用户回答后 | 继续生成或调整 DraftTaskTree | `resume_after_user(...)` |
| UI 状态 | planning needs input | task waiting for input |
| TaskNode 状态 | 不变 | `waiting_user` |

### 2.3 批量提交优先用于 Authoring ASK

Product 1.0 最小实现优先支持 authoring batch answer：

```text
frontend local draft answers
  -> submit once
  -> backend validates all answers
  -> backend writes RawTaskAnswer objects atomically
  -> backend marks RawTask status by unresolved required asks
  -> frontend may trigger generate_task_tree(rawTaskId)
```

Execution ASK 暂时保持单 active blocking ASK。后续如果执行 Agent 需要一次提出
多个相关问题，再引入 `ask_group_id` 和 execution batch resume policy。

---

## 3. UI Projection 设计

长期目标是一个统一的 UI view model：

```python
class AskView:
    id: str
    domain: Literal["authoring", "execution"]
    scope: Literal["planning", "task"]
    session_id: str
    raw_task_id: str | None
    task_node_id: str | None
    question: str
    reason: str
    options: tuple[AskOptionView, ...]
    answer_type: Literal["free_text", "single_choice", "multi_choice", "boolean"]
    status: Literal["pending", "answered", "deferred", "cancelled", "expired"]
    group_id: str | None
```

Product 1.0 本 slice 不强制实现这个统一 projection。实现先保证后端 batch command
语义正确，避免把 UI redesign 和 domain hardening 混在一个风险较高的改动里。

---

## 4. Authoring Batch Answer API

建议 UI contract payload：

```python
class AnswerAuthoringAskItemPayload:
    ask_id: str
    value: str

class AnswerAuthoringAskBatchPayload:
    raw_task_id: str
    answers: tuple[AnswerAuthoringAskItemPayload, ...]
    continue_to_generate: bool = False
```

本 slice 的后端命令行为：

- `answers` 至少一个；
- 同一个 request 中 `ask_id` 不能重复；
- 所有 `ask_id` 必须属于同一个 RawTask；
- 如果任一 ASK 已被回答，则整个 batch 拒绝；
- 任一 answer value 为空，则整个 batch 拒绝；
- 写入使用一个 `MutateRawTaskCommand`，保持 all-or-nothing；
- command idempotency key 重放时返回相同结果；
- 成功后返回 refresh hints：`session.snapshot`, `session.messages`, `task.tree`。

### 4.1 状态更新

`AuthoringCommandService` 已通过 `_status_after_answers(...)` 决定 RawTask 后续状态：

```text
还有 required unanswered ask -> awaiting_user
没有 required unanswered ask -> assessing
```

这符合本 slice 的最小要求。后续自动继续生成 DraftTaskTree 可以由 UI 或更高层
orchestration 决定，不在 batch answer 写入函数中隐式执行。

### 4.2 用户消息

单个 batch 提交只发布一条用户消息，避免 MessageStream 被多条 answer message
刷屏。消息 context 需要包含：

```json
{
  "surface": "raw_task_ask",
  "operation": "answerRawTaskAskBatch",
  "raw_task_id": "...",
  "ask_ids": ["..."]
}
```

---

## 5. Execution Batch 预留

Execution batch answer 不在 C2 直接实现。原因：

- execution ASK 会触发 TaskBus `waiting_for_user -> pending`；
- 如果一个 task 同时等待多个 blocking ASK，resume 必须等整组全部 answered；
- 当前 runtime 是单 active blocking ASK，直接加 batch resume 容易制造假能力。

后续扩展时增加：

```python
AskRequest.ask_group_id: str | None
AskRequest.group_blocking_policy: Literal["all_required"]
```

并定义：

```text
answer batch accepted
  -> all blocking asks in group answered?
      yes -> resume task
      no  -> remain waiting_for_user
```

---

## 6. 实现计划

### C1 Docs Alignment

- 新增 feature plan。
- 新增本中文详细技术方案。
- 更新 feature plan README。

### C2 Authoring Batch Answer Backend

目标文件：

- `src/taskweavn/task/collaborator_api.py`
- `src/taskweavn/task/authoring_service.py`
- `src/taskweavn/server/ui_contract/commands.py`
- `src/taskweavn/server/ui_contract/command_gateway.py`
- `src/taskweavn/server/ui_contract/gateway_protocols.py`
- tests

实现点：

1. `CollaboratorApiAdapter.answer_raw_task_asks(...)`。
2. 单条 `answer_raw_task_ask(...)` 委托到 batch method，保持兼容。
3. `AuthoringCommandService` 拒绝已回答 RawTaskAsk 的新 answer。
4. batch payload 级别拒绝重复 ask id。
5. `DefaultUiCommandGateway.answer_authoring_ask_batch(...)`。

### C3 HTTP Entry

目标：

```text
POST /api/v1/sessions/{sessionId}/authoring/raw-tasks/{rawTaskId}/asks/answers
```

payload:

```json
{
  "answers": [
    {"askId": "ask-1", "value": "Developers"},
    {"askId": "ask-2", "value": "Portfolio and contact form"}
  ],
  "continueToGenerate": false
}
```

C3 可以在 C2 后单独做，避免本 slice 同时触碰 `ui_http.py` 过多。

---

## 7. 验收标准

- docs 明确两类 ASK 的差异。
- authoring batch answer 支持多个 answers 一次提交。
- batch 内 ask id 重复时拒绝。
- 已回答 RawTaskAsk 再次回答时拒绝。
- 单 answer 旧 API 仍可用。
- execution ASK 单 answer/defer/cancel 行为不变。
- targeted tests、ruff 通过。

