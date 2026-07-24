# 会话内原位 ASK 渲染技术设计

> 状态：F2-F5 已实现，等待 PR 验收
>
> 分支：`codex/session-inline-ask-rendering`
>
> 最后更新：2026-07-24
>
> 需求：
> [会话内原位 ASK 渲染需求](session-inline-ask-rendering.zh-CN.md)

## 1. 目标

本设计把 Authoring ASK 和 Execution ASK 投影为 Conversation 中稳定的结构化
卡片，并让回答、延后、取消和终态在同一张卡片中更新。

必须同时满足：

1. Conversation 是 ASK 的唯一主要回答面。
2. Authoring 一批问题只生成一张组卡片。
3. Execution 一个 AskRequest 生成一张卡片。
4. ASK 回答不再生成独立 Conversation Answer 卡片。
5. Activity / Audit 继续保留回答动作和恢复证据。
6. 普通 Read-only Inquiry Answer 和普通用户消息不变。
7. 卡片从 RawTask / AskStore 持久事实恢复，不依赖前端缓存。

## 2. 当前边界

### 2.1 Authoring

```text
RawTaskStore
  RawTask
    RawTaskAsk[]
    RawTaskAnswer[]
```

当前 Main Page 把 pending RawTaskAsk 投影到 `AuthoringAskWorkArea`，回答后另写
一条 `AgentMessage(title="User answer")`。

### 2.2 Execution

```text
AskStore
  AskRequest
  AskAnswer
```

当前 Main Page 只把 pending AskRequest 放入 `activeAsk` /
`ExecutionAskDetailPanel`。`AskRequestView` 有 `answerId`，但没有完整 Answer
内容，因此历史卡片无法标记已选项。

### 2.3 Conversation

`ConversationRenderView` v1 已支持：

- `text`
- `router_trace`
- `question_card`

本特性采用 additive `ask_card`，保留旧 `question_card` 用于 Router clarification
和 Confirmation 兼容。

## 3. 目标组件与所有权

```text
Backend durable facts
  RawTaskStore -----------------------+
  AskStore ---------------------------+--> ConversationAskProjection
  MessageStream ----------------------+      -> SessionMessageView[]
                                              -> conversationVisibility

MainPageSnapshot.messages
  -> MainPageViewModel
  -> ConversationLayer
  -> SessionMessageCard
  -> ConversationAskCard
       -> authoring batch command
       -> execution answer/defer/cancel command
```

### Backend

| 模块 | 责任 |
|---|---|
| `conversation_ask_projection.py` | 把 Authoring / Execution 权威事实投影成稳定 Conversation ASK 卡片。 |
| `view_models.py` | 定义 additive ASK card 与 Answer view contract。 |
| `ask_projection.py` | 将 AskStore 的 AskAnswer 一并投影到 AskRequestView。 |
| `query_snapshot_helpers.py` | 合并普通消息与 ASK 卡片，不改变持久权威。 |
| `authoring_answer_projection.py` | 将 ASK 专用答案消息标记为 Activity-only。 |
| `runtime_input_activity.py` | Router 处理 ASK 回答时，用户输入和 ask_answered 摘要为 Activity-only。 |

### Frontend

| 模块 | 责任 |
|---|---|
| `ConversationAskCard.tsx` | ASK 卡片展示、草稿、验证、提交、失败与终态。 |
| `conversationAskInteraction.ts` | Authoring / Execution 命令适配器与 pending/error 状态。 |
| `SessionMessageCard.tsx` | 按 render protocol 委托 ASK 卡片，不承载领域命令逻辑。 |
| `ConversationLayer.tsx` | 向消息卡传递一个 ASK interaction adapter。 |
| `MainPageWorkbench.tsx` | 删除会话外主要 ASK 表单，只做薄接线。 |
| `MainPageDetailPanel.tsx` | Execution ASK 只显示等待状态与定位入口，不重复回答表单。 |

## 4. UI Contract

### 4.1 Answer View

Execution AskRequestView 增加：

```ts
type AskAnswerView = {
  id: string;
  selectedOptionIds: string[];
  text: string | null;
  createdAt: string;
};

type AskRequestView = {
  // existing fields...
  answer: AskAnswerView | null;
};
```

旧 `answerId` 保留，避免破坏现有消费者。

### 4.2 Conversation Visibility

```ts
type ConversationVisibility = "visible" | "activity_only";

type SessionMessageView = {
  // existing fields...
  conversationVisibility: ConversationVisibility;
};
```

`activity_only` 消息：

- 仍进入 Activity projection；
- 仍可进入 Audit / diagnostics；
- 不在主 Conversation 列表中渲染；
- 不参与 Conversation 可见计数与自动滚动定位。

### 4.3 ASK Card

```ts
type ConversationAskDomain = "authoring" | "execution";

type ConversationAskStatus =
  | "pending"
  | "answered"
  | "deferred"
  | "cancelled"
  | "expired"
  | "superseded";

type ConversationAskOptionView = {
  id: string;
  value: string;
  label: string;
  description: string | null;
  selected: boolean;
};

type ConversationAskQuestionView = {
  id: string;
  prompt: string;
  reason: string | null;
  required: boolean;
  answered: boolean;
  answerType: "free_text" | "single_choice" | "multi_choice" | "boolean";
  allowFreeText: boolean;
  options: ConversationAskOptionView[];
  answerText: string | null;
};

type ConversationAskCardView = {
  cardId: string;
  domain: ConversationAskDomain;
  status: ConversationAskStatus;
  title: string;
  body: string | null;
  rawTaskId: string | null;
  askId: string | null;
  taskNodeId: string | null;
  questions: ConversationAskQuestionView[];
  createdAt: string;
  resolvedAt: string | null;
  canAnswer: boolean;
  canDefer: boolean;
  canCancel: boolean;
  readonlyReason: string | null;
};
```

`ConversationRenderView` 增加：

```ts
renderKind: "text" | "router_trace" | "question_card" | "ask_card";
askCard?: ConversationAskCardView | null;
```

兼容行为：

- 旧客户端不认识 `ask_card` 时使用 message `body` 降级；
- 旧消息没有 `conversationVisibility` 时默认 `visible`；
- 旧 `question_card` 继续原样工作；
- 新客户端不从 title/body 推断 ASK。

## 5. 投影规则

### 5.1 Authoring ASK 组卡片

一条 RawTask 中所有 `RawTaskAsk` 组成一张卡片：

```text
cardId = "conversation-ask:authoring:" + rawTaskId
messageId = cardId
createdAt = min(ask.createdAt)
```

状态：

| 条件 | 状态 |
|---|---|
| 所有问题均有 RawTaskAnswer | `answered` |
| 存在未回答问题，且同一路径已有 TaskTree | `superseded` |
| 其他 | `pending` |

答案映射：

- Answer.value 匹配 option id/value/label 时，对应 option.selected=true；
- 未匹配选项时，将 Answer.value 投影为 `answerText`；
- 每个问题以 `answered` 明确表达是否已有持久答案；pending 组卡片中已回答问题只读，
  提交 payload 只包含尚未回答的问题；
- answered 卡片的 `resolvedAt` 为最后一个 Answer.createdAt；
- pending 卡片仅允许未回答问题编辑，已回答问题只读。

### 5.2 Execution ASK 卡片

每个 AskRequest 一张卡片：

```text
cardId = "conversation-ask:execution:" + askId
messageId = cardId
createdAt = ask.createdAt
```

- `AskRequest.status` 直接映射卡片状态；
- `AskAnswer.selectedOptionIds` 标记 option.selected；
- `AskAnswer.text` 显示为 `answerText`；
- `resolvedAt` 取 answered/deferred/cancelled/expired 对应时间；
- 只有 `pending` 可以回答；defer/cancel capability 仍受原命令边界约束。

### 5.3 排序与去重

- ASK 卡片按 ASK 创建时间进入 Conversation；
- 回答后不改变排序时间；
- message id / card id 稳定，因此 refetch 不产生第二张卡；
- 普通 MessageStream 消息与 synthetic ASK card 通过统一 id 去重；
- ASK 卡片由领域事实投影，不额外写入 MessageStream。

## 6. 命令与状态流

### 6.1 Authoring

```text
pending card
  -> local draft keyed by rawTaskId + askId
  -> Submit all answers
  -> answerAuthoringAskBatch
  -> submitting (frontend fact)
  -> accepted, refetch
  -> RawTaskAnswer facts
  -> same card answered
  -> Draft TaskTree generation continues
```

### 6.2 Execution

```text
pending card
  -> local draft keyed by askId
  -> answer / defer / cancel
  -> command pending
  -> accepted, refetch/event
  -> AskRequest + AskAnswer terminal facts
  -> same card terminal
  -> Task resumes or follows terminal policy
```

失败时：

- 草稿保留；
- 原卡显示错误；
- backend 未确认前不乐观显示 answered；
- stale/expired/permission 错误触发 refetch 并按权威状态关闭操作。

## 7. Conversation 与 Activity 去重

### Authoring

现有 `raw_task_ask` answer AgentMessage 继续持久化，但投影为：

```text
title = "ASK answered"
conversationVisibility = "activity_only"
```

其 body 保留用户可读答案摘要，供 Activity 使用。

### Runtime Input ASK Answer

当 Router decision intent 为 `ask_answer`：

- 用户输入 Message 标记为 `activity_only`；
- `ask_answered` Activity Message 标记为 `activity_only`；
- AskStore 卡片在 refetch 后原位显示选择；
- Read-only Inquiry 的问题/答案仍为 `visible`。

## 8. Conversation 外区域

- Authoring ASK 不再替换 Main Work Area。
- Conversation 始终可见。
- Execution ASK 不在 Detail Panel 重复完整表单。
- Top Bar、TaskTree、Detail Panel 可显示 waiting/needs-answer 状态。
- 状态入口点击后滚动并聚焦 Conversation 中对应 `[data-conversation-ask-id]`。
- Context Input 在存在 blocking ASK 时可以继续按现有策略禁用或路由为 ASK answer，
  但主结构化交互位于卡片。

## 9. 可访问性与响应式

- 卡片使用 `fieldset` / `legend` 或等价语义；
- 单选使用 radio 语义，多选使用 checkbox 语义；
- `aria-checked` / native checked 明确反映选择；
- submit error 使用可被读屏器感知的状态区域；
- submitting 时控件禁用但选择仍可读；
- resolved 选项显示文字/图标，不只依赖颜色；
- Esc 不关闭 blocking ASK；
- 手机单列，平板/桌面允许选项行布局，但不得横向溢出；
- 长问题、长选项和中英文文案必须换行。

## 10. 实施切片

### F2-1 契约修订

文件：

- `docs/engineering/ask-lifecycle-contract.md`
- `docs/interaction-model/ask-user-interaction.md`
- `docs/ux/ask-ui-spec.md`
- `docs/plans/ui/session-message-stream.md`
- `docs/frontend/ui-viewmodel-contract.md`

验收：所有 canonical docs 都以 Conversation 为 ASK 唯一主要回答面。

### F3-1 Backend contract 与纯投影

文件：

- `src/taskweavn/server/ui_contract/view_models.py`
- 新建 `src/taskweavn/server/ui_contract/conversation_ask_projection.py`
- `src/taskweavn/server/ui_contract/ask_projection.py`
- 对应 backend tests

验收：两类领域事实可确定性投影为稳定 card。

### F4-1 Snapshot 集成与去重

文件：

- `src/taskweavn/server/ui_contract/query_snapshot_helpers.py`
- `src/taskweavn/server/ui_contract/authoring_answer_projection.py`
- `src/taskweavn/server/ui_contract/mapping.py`
- `src/taskweavn/server/runtime_input_activity.py`
- 对应 gateway/router/activity tests

验收：snapshot 包含 ASK card，ASK Answer message 为 Activity-only。

### F4-2 Frontend adapter extraction

文件：

- 新建 `frontend/src/pages/main-page/conversation-ask/ConversationAskCard.tsx`
- 新建 `frontend/src/pages/main-page/conversation-ask/conversationAskInteraction.ts`
- 新建对应 CSS module 与 tests
- `frontend/src/pages/main-page/SessionMessageCard.tsx`
- `frontend/src/pages/main-page/ConversationLayer.tsx`

验收：ASK 草稿和命令适配不进入页面大组件。

### F4-3 Main Page 切换

文件：

- `frontend/src/pages/main-page/MainPageWorkbench.tsx`
- `frontend/src/pages/main-page/mainPageViewModel.ts`
- `frontend/src/pages/main-page/MainPageDetailPanel.tsx`
- 对应 Workbench/ViewModel/Detail tests

验收：Conversation 始终显示；旧 Authoring/Execution 主回答面移除。

### F5-1 验证与文档

- backend: projection/query/router/activity tests；
- frontend: component/viewmodel/workbench tests；
- `uv run ruff check`；
- `uv run mypy`（仓库支持范围）；
- frontend lint/typecheck/test/build；
- desktop viewport、tablet、mobile 视觉检查；
- Electron 或真实 sidecar reload/restart smoke；
- 更新 feature plan、README/changelog/release note。

## 11. 回滚

- 合同字段均 additive；
- 旧 question_card 和普通文本路径保留；
- 若新卡片渲染失败，客户端降级到 message body；
- 回滚前端时后端新增字段可被旧客户端忽略；
- 不修改 RawTask / AskStore 数据库 schema；
- 不删除 MessageStream / Activity / Audit 底层事实。

## 12. 风险

1. Authoring 与 Execution 的答案值语义不同，必须在投影层适配，不能在组件中猜。
2. MainPageWorkbench 与 API types 较大，必须保持薄接线。
3. Runtime Input ASK answer 可能同时产生多个 Message，必须只改变 Conversation
   可见性，不能误删 Activity。
4. 历史 RawTask 可能有不匹配当前 options 的答案，需要 answerText fallback。
5. Execution batch questions 只有一个 Answer.text；首版按卡片级文本保留，不能
   伪造逐问题结构化答案。

## 13. 实施与验证结果

### 已完成

- additive `ask_card`、`conversationVisibility` 与 `AskAnswerView` UI contract；
- Authoring RawTask 与 Execution AskStore 的确定性 Conversation 投影；
- ASK 专用答案消息保留为 Activity / Audit 证据并从 Conversation 隐藏；
- Conversation 内 Authoring 批量回答，以及 Execution answer/defer/cancel；
- Detail Panel 退化为状态和“在会话中查看”入口；
- 旧 Authoring Work Area 与 Execution Detail Panel 回答表单移除；
- Plan 打开时定位 Conversation ASK 会折叠 Plan，避免覆盖卡片；
- 响应式与可访问性交互测试。

### 评审整改闭环

- `FINDING-001`：问题投影新增 `answered`；部分已回答 Authoring 组中已完成问题
  保持只读，批量命令只提交未回答问题，并增加真实 Authoring 服务链路回归；
- `FINDING-002`：Execution answer/defer/cancel 的 pending、error 和 recovery 状态按
  `askId` 管理；任一命令执行中全局锁定其他 Execution ASK，避免重复命令；
- `FINDING-003`：pending 草稿提升到 Workbench 会话状态，以
  `sessionId/cardId/questionId` 隔离，切换会话后返回仍能恢复；
- `FINDING-004`：已选项显示 `✓ 已选择/Selected` 非颜色标记，并通过
  `aria-labelledby` 将 choice group 关联到原始问题，保留 `aria-pressed` 语义。

### 验证证据

- `uv run pytest -q`：1568 passed，10 skipped；
- changed backend scope `uv run ruff check`：通过；
- changed backend scope `uv run mypy`：通过；
- `npm test`：573 passed，6 skipped；
- `npm run build`：通过；
- `npm run lint`：0 error，保留 2 条既有 Fast Refresh warning；
- 浏览器桌面、768px 平板与 390px 手机视口：Authoring 与 Execution ASK 均在
  Conversation 内显示，问题标签关联正确，非颜色已选标记可见，无横向溢出，
  console 无 error。

仓库全量 `ruff check .` 与 `mypy src` 仍包含本特性范围外的既有历史问题；
相关文件未在本特性中修改，详见 PR 验证说明。
