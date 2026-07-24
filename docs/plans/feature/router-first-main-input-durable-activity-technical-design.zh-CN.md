# Router-first Main Page Input, Conversation Protocol, And Durable Activity 技术方案

> Status: planned for implementation branch
>
> Last Updated: 2026-06-19
>
> Owner: Product / Frontend / Backend UI Gateway
>
> Related:
> [Runtime Input Router Contract](runtime-input-router-contract.md),
> [Runtime Input Router Technical Design](runtime-input-router-contract-technical-design.md),
> [Runtime Input And Contract Revision Program](runtime-input-and-contract-revision-program.md),
> [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md),
> [Contract Revision Command Skills](contract-revision-command-skills.md),
> [Product 1.1 Open Work](../../product/plato-1-1-open-work.md)

---

## 1. 目标

本切片关闭 Product 1.1 P0 中三个紧邻缺口：

1. Main Page 底部自然语言输入默认进入 Runtime Input Router，而不是在前端先分流到旧的 `generateTaskTree` / `appendSessionInput` / `appendTaskInput` 命令。
2. Conversation 区域展示 Router 的用户可见判断过程，包括它识别了什么意图、作用在哪个 scope、是否会产生副作用、为什么继续/拒绝/追问。
3. Router 对每次输入的解释、追问、回答和结果写入 durable Conversation / Activity，使用户刷新、重启 Electron、打开 Activity/Audit 时仍能看到“Plato 如何理解了我的输入，以及产生了什么后果”。

“Router 的思考过程”在本方案中定义为用户可见的 Router trace /
interpretation summary，不是隐藏 chain-of-thought，不包含 raw prompt、provider
payload、工具原始输入输出、SQLite 行、绝对路径或 secrets。

本切片不实现 LLM 模糊意图分类，不扩展 Agent protocol，不直接执行 workspace
写入。

---

## 2. 当前状态

已有能力：

- `RuntimeInputRouteRequest` / `RuntimeInputRouteResult` API、HTTP route、frontend API client 已存在。
- `DefaultRuntimeInputRouter` 已支持：
  - active ASK answer；
  - active confirmation response；
  - selected-task stop / retry；
  - read-only inquiry question；
  - command-backed `record_guidance`；
  - command-backed `create_execution_task`；
  - unsupported / clarification structured outcome。
- `MessageBusRuntimeInputActivityPublisher` 已能持久化 read-only answer。
- `MessageBusContractRevisionActivityPublisher` 已能持久化 accepted Contract Revision command Activity。
- Main Page controller 已有 `runtimeInputMutation`，但目前仅在 `shouldRouteReadOnlyQuestion(content)` 为 true 时使用 Router，并且请求强制 `mode: "ask"`。

缺口：

- 普通目标输入、新计划输入、任务指导输入仍默认走旧命令路径。
- Router unsupported / clarification / rejected / selected-task stop-retry 等结果没有统一 durable Activity 写入。
- Activity projection 依赖部分 reserved title 推断 runtime activity kind，缺少通用 Router Activity context 投影。
- Conversation 当前更像消息/Activity 的展示结果，缺少后端显式告诉前端“渲染纯文本、Router trace、问题卡片、选项卡片”的协议。
- Router 发起的 clarification / follow-up question 还没有以 conversation card 的方式持久化；用户回答也没有作为 conversation 内容与该问题稳定关联。

---

## 3. 产品语义

Main Page 输入不再是“聊天框 + 若干隐式命令分支”，而是 Runtime Input Router 的入口：

```text
用户输入
  -> durable conversation user message
  -> Router 判断意图与 scope
  -> durable conversation Router trace
  -> 下游能力执行 / 拒绝 / 发起问题卡片
  -> durable Activity 摘要和 Audit/diagnostic refs
  -> UI 显示 conversation / activity / notice / refresh
```

用户可理解的结果类型：

| Router outcome | 用户含义 | 是否允许改变状态 |
|---|---|---|
| answered | 只读回答 | 否 |
| dispatched | 已派发到受控命令或执行任务 | 仅允许 product contract state，通过命令 |
| needs_clarification | 需要用户补充信息 | 否 |
| unsupported | 当前无法安全处理 | 否 |
| rejected | 下游命令拒绝 | 不应产生部分状态 |

### 3.1 Conversation 与 Activity 的边界

| Surface | 作用 | 内容粒度 |
|---|---|---|
| Conversation | 用户按时间阅读交互过程。 | 用户输入、Router trace、问题卡片、用户回答、结果说明。 |
| Activity | 用户快速理解发生了什么，并跳转到证据。 | 一条输入对应的解释摘要、scope、side-effect、refs。 |
| Audit | 用户验证系统是否可信。 | 证据、命令、诊断、配置、日志引用。 |

Conversation 不是 raw chat transcript。它是 typed conversation content。每个可见项都必须带有 render 协议或可安全降级为纯文本。

结构化 ASK 是 Conversation 的主要交互项：问题、选项、草稿、提交和终态都
属于同一个稳定卡片。ASK 的回答动作可以另行投影为 Activity / Audit，但不再
追加独立 Conversation Answer 卡片。普通 Read-only Inquiry Answer 不受此规则
影响。

### 3.2 Router Trace 显示内容

每次 Router 处理输入后，conversation 中应追加一条 Router trace。Trace 至少包含：

- `intent`：question / guidance / ask_answer / confirmation_response /
  execution_request / command / clarification / unsupported；
- `scope`：session / plan / task；
- `confidence`：high / medium / low；
- `sideEffect`：no_effect / context_effect / state_effect / resume_effect /
  authorization_effect / evidence_effect；
- `dispatchTarget`：read_only_inquiry / record_guidance / resolve_ask /
  resolve_confirmation / execution_handoff / existing_command /
  clarification / unsupported；
- `explanation`：一句用户可读解释；
- `outcomeStatus`：answered / dispatched / needs_clarification /
  unsupported / rejected。

Trace 不展示隐藏推理链；它展示 Router contract 中已经可审计的判断摘要。

### 3.3 Router 提问卡片

当 Router 需要追问或需要用户选择时，不应只在 input error 中显示文本。后端必须持久化一个 conversation card，让前端按协议渲染：

- clarification question；
- active ASK mirror card；
- confirmation response card；
- future multi-question card。

卡片可以有 free-text input、single/multi-choice options、boolean options、required
questions、submit/defer/cancel affordance。前端不能仅通过 title/body 文案猜测卡片类型。

---

## 4. Frontend 设计

### 4.1 Router-first submit

`useMainPageController.handleInputSubmit` 改为：

1. 如果 `adapter.routeRuntimeInput` 存在，默认调用 Router。
2. 如果 Router 不存在，保留旧命令路径作为 mock/兼容 fallback。
3. 明确 UI 按钮路径保持原样：
   - ASK detail 面板的 Answer/Defer/Cancel 仍调用显式 ASK command；
   - Confirmation detail 面板按钮仍调用显式 confirmation command；
   - Task action 按钮仍调用显式 stop/retry command。

### 4.2 旧 input mode 到 Router mode 的映射

| MainPageInputCommandMode | Router mode | 说明 |
|---|---|---|
| `generate_task_tree` | `change` | 用户在空会话描述目标，应创建可执行 contract work，而不是前端直接进入旧 authoring path。 |
| `append_plan_input` | `guide` | 用户对当前 plan 提供指导，应记录为 typed guidance。 |
| `append_task_input` | `guide` | 用户对选中 task 提供指导，应记录为 task-scoped guidance。 |
| `append_session_input` | `guide` | 用户对 session 提供全局指导。 |

问题类输入仍可使用 `mode=auto` 或 `mode=ask`，但第一版不在前端靠问题启发式决定是否走 Router。所有默认输入先进入 Router；Router 内部负责优先处理 active ASK/confirmation、命令、问题、指导、执行请求。

### 4.3 前端反馈

Router response 处理规则：

- `outcome.status in answered/dispatched`：清空输入，显示 `outcome.userMessage` 或 inquiry answer notice。
- `needs_clarification/unsupported/rejected`：显示 input error 与 recovery actions，不清空用户输入。
- 若 response 带 `activity`，立即插入 runtime activity strip；同时后端 durable Activity 支持 reload 后重放。
- 若 response 带 command response 且需要 refetch，触发 snapshot refetch。
- 对 `dispatched` 的 command-backed guidance / execution handoff，即使没有 `commandResponse`，也应 refetch snapshot，因为 Plan/Activity 可能变化。

### 4.4 Conversation render 协议

前端 conversation 区域必须兼容后端显式协议，而不是从文本内容推断 UI。

第一版新增可选 render payload：

```ts
type ConversationRenderView = {
  protocolVersion: "plato.conversation.render.v1";
  renderKind: "text" | "router_trace" | "question_card";
  text?: {
    title?: string | null;
    body: string;
  };
  routerTrace?: {
    intent: RuntimeInputIntent;
    scopeKind: RuntimeInputScopeKind;
    confidence: RuntimeInputConfidence;
    sideEffect: SessionActivitySideEffect;
    dispatchTarget: RuntimeInputDispatchTarget;
    explanation: string;
    outcomeStatus: RuntimeInputOutcomeStatus;
  } | null;
  questionCard?: {
    cardId: string;
    cardKind: "clarification" | "ask" | "confirmation";
    status: "pending" | "answered" | "cancelled" | "expired";
    title: string;
    body?: string | null;
    questions?: Array<{
      id: string;
      label: string;
      inputHint?: string | null;
      required: boolean;
    }>;
    options?: Array<{
      id: string;
      label: string;
      description?: string | null;
    }>;
    answerMode: "runtime_input" | "ask_command" | "confirmation_command";
    targetRef?: SessionActivityRefView | null;
  } | null;
};
```

兼容规则：

- `renderKind=text`：按普通 conversation 文本展示。
- `renderKind=router_trace`：展示为 Router 判断摘要，可以折叠/展开。
- `renderKind=question_card`：展示输入项和选项；只有 `status=pending` 才允许提交。
- 不认识的 `protocolVersion` 或 `renderKind`：降级为 text，不渲染可交互控件。
- 没有 render payload 的 legacy message：继续按当前 message title/body 展示。

### 4.5 Conversation 中的提问与回答

Router 发起提问时，Conversation 中至少出现三类 durable item：

1. 用户原始输入；
2. Router trace；
3. 问题卡片。

用户回答结构化 ASK 后：

1. 原问题卡片原位显示已选项或自由文本；
2. Router/command 处理结果进入 Activity / Audit；
3. ASK 专用用户输入和 `ask_answered` 摘要不新增 Conversation 卡片；
4. 普通 clarification 和 Read-only Inquiry 仍可按各自协议追加文本结果。

用户刷新后必须能看到完整问答上下文，而不是只看到最新状态或错误 toast。

---

## 5. Backend 设计

### 5.1 通用 Runtime Activity Publisher

扩展 `RuntimeInputActivityPublisher`：

```python
class RuntimeInputActivityPublisher(Protocol):
    def publish_router_activity(
        self,
        request: RuntimeInputRouteRequest,
        activity: SessionActivityItemView,
    ) -> None: ...
```

保留 `publish_read_only_answer` 作为兼容 wrapper，内部可转调 `publish_router_activity`。

### 5.2 MessageStream 写入格式

`MessageBusRuntimeInputActivityPublisher.publish_router_activity` 写入
informational `AgentMessage`，作为 Activity projection 的 durable source：

- `message_id = f"runtime-input-{activity.kind}-{request.command_id}"`
- `session_id = request.session_id`
- `task_id = activity.task_node_id`
- `agent_id = "router"`
- `message_type = "informational"`
- `content = activity.body`
- `related_action_id = activity.source_id`
- `context` 至少包含：
  - `title`
  - `activity_related_refs`
  - `runtime_input_activity_kind`
  - `runtime_input_side_effect`
  - `runtime_input_decision_id`
  - `runtime_input_outcome_status`
  - `runtime_input_scope_kind`
  - `runtime_input_plan_id`
  - `runtime_input_task_node_id`

重复发布同一个 `command_id + kind` 必须 idempotent，遇到 duplicate message id 只吞掉重复错误。

### 5.2.1 Conversation Message 写入格式

新增 Router Conversation publisher seam，或扩展 Runtime Activity publisher，让同一个 Router result 可以写入 conversation content：

```python
class RuntimeConversationPublisher(Protocol):
    def publish_user_input(
        self,
        request: RuntimeInputRouteRequest,
    ) -> None: ...

    def publish_router_trace(
        self,
        request: RuntimeInputRouteRequest,
        decision: RuntimeInputRouteDecision,
        outcome: RuntimeInputOutcome,
    ) -> None: ...

    def publish_question_card(
        self,
        request: RuntimeInputRouteRequest,
        card: ConversationQuestionCard,
    ) -> None: ...

    def publish_user_answer(
        self,
        request: RuntimeInputRouteRequest,
        answer_text: str,
        target_card_id: str,
    ) -> None: ...
```

第一版可以复用 `AgentMessage.context` 承载 `conversation_render`：

- `message_type="informational"`；
- `agent_id="user"` 用于用户输入/回答；
- `agent_id="router"` 用于 Router trace 和问题卡片；
- `context["conversation_render"]` 写入 `ConversationRenderView` 的 JSON 形态；
- `related_action_id` 绑定 `request.command_id` 或 question card id；
- `parent_message_id` 可在回答时指向问题卡片消息，形成稳定问答线程。

### 5.2.2 持久化规则

每次 Router route 至少持久化：

1. user input message；
2. router trace message；
3. activity summary message。

如果 outcome 是 `needs_clarification` 或 Router/command 需要用户选择，再持久化 question card。

如果用户回答 ASK/confirmation/clarification，回答也必须作为 conversation 内容持久化，并通过 `parent_message_id` 或 `targetRef` 与原问题卡片关联。

### 5.3 Router 发布策略

在 `DefaultRuntimeInputRouter._result(...)` 中统一发布 durable Activity：

- 如果 `activity_publisher is None`：只返回 projection activity，保持测试/兼容可用。
- 如果该 route 已由 `ContractRevisionCommandService` 的 activity publisher 写入 accepted command Activity，则不要重复写同一 accepted command Activity。
- 以下 route 必须由 Runtime Activity Publisher 写入：
  - unsupported；
  - needs_clarification；
  - rejected；
  - read-only answer；
  - existing command route stop/retry；
  - 没有 ContractRevision publisher 的 fallback ASK/confirmation route。

第一版可以通过一个显式参数控制 `_result(..., publish_activity=True/False)`，避免对 Contract Revision accepted commands 双写。

### 5.4 Activity Projection

`DefaultSessionActivityProjectionService` 应优先使用 `SessionMessageView` 的 safe fields。

如果 `SessionMessageView` 已暴露 `activity_related_refs` 和 `related_command_id`，但没有直接暴露 context 中的 `runtime_input_activity_kind`，则第一版可继续通过 title fallback 识别常见 runtime activity；同时需要补齐 reserved title：

- `Runtime input routed`
- `Runtime input needs clarification`
- `Runtime input unsupported`
- `Runtime command routed`
- `Guidance recorded`
- `ASK answered`
- `Confirmation resolved`
- `Execution work created`

若需要更稳妥的投影，应在 `SessionMessageView` 增加安全字段读取 `runtime_input_activity_kind`，但这会触及 API contract，需同步 fixture 与 frontend type。第一版优先避免扩大 contract。

### 5.5 Conversation Projection

前端需要一个明确的 Conversation projection source。第一版有两种可选路径：

1. 在现有 `SessionMessageView` 上新增可选 `conversationRender` 字段；
2. 新增 `SessionConversationItemView` / `SessionConversationTimelineResult`。

本切片建议选择 **路径 1**，因为 Main Page 已有 message projection 和 message card
UI，可以最小化路由和查询改动。

安全规则：

- projection 只暴露 `conversation_render` 白名单字段；
- 不透传完整 `AgentMessage.context`；
- question card 的 options/questions 由后端结构化给出；
- 前端未知 render payload 必须 text fallback；
- 已回答/过期/取消卡片不可提交。

---

## 6. 兼容策略

- Mock adapter 若未实现 `routeRuntimeInput`，继续使用旧 `inputMutation` fallback。
- HTTP adapter 已有 `routeRuntimeInput`，真实 app 默认进入 Router。
- 旧 `generateTaskTree` API 保留，不在本切片删除。
- 明确按钮行为不迁移，避免在一个分支里同时改可见按钮语义和默认输入语义。

---

## 7. 验收标准

1. 在 HTTP/Main Page 环境，底部输入默认调用 `/runtime-input/route`。
2. 空会话目标输入以 Router `mode=change` 创建 execution task handoff，不直接调用旧 `generateTaskTree`。
3. 选中 Task 后输入指导以 Router `mode=guide` 记录 task-scoped guidance。
4. 普通问题仍走 read-only inquiry，并返回 `no_effect` answer。
5. Conversation 区域显示 Router trace，至少包含 intent、scope、side-effect、dispatch target、explanation、outcome。
6. Router 发起 clarification/ASK/confirmation 时，conversation 区域显示结构化问题卡片和选项/输入控件。
7. 用户提问、Router 追问、用户回答、Router 结果均持久化为 conversation 内容，刷新后仍可见。
8. Unsupported / clarification outcome reload 后可在 Session Activity 中看到。
9. Accepted guidance / execution handoff / ASK answer / confirmation response 不重复写 Activity。
10. 没有 Router 的 mock/fallback 环境仍可提交旧命令。
11. Targeted frontend/backend tests 通过。

---

## 8. 测试计划

Backend:

```bash
uv run pytest tests/test_runtime_input_router.py tests/test_read_only_inquiry.py
```

Frontend:

```bash
npm --prefix frontend test -- src/pages/main-page/useMainPageController.test.tsx src/pages/main-page/httpMainPageAdapter.test.ts
npm --prefix frontend run lint -- src/pages/main-page/useMainPageController.ts
```

Contract / safety:

```bash
git diff --check
```

If this branch changes shared API contract fields, also run:

```bash
npm --prefix frontend test -- src/shared/api/backendContractFixtures.test.ts
```

---

## 9. 实施顺序

1. Backend: extend Runtime Activity publisher with generic durable write.
2. Backend: add Conversation render protocol projection, either as optional
   `SessionMessageView.conversationRender` or a dedicated Conversation item.
3. Backend: make Router publish durable user input, Router trace, question card
   when needed, and Activity summary.
4. Backend: add tests for persisted Router trace, question card, user answer,
   unsupported/clarification reloadable Activity, and no duplicate accepted
   command Activity.
5. Frontend: render `conversationRender` with text fallback, Router trace card,
   and question card controls.
6. Frontend: make `handleInputSubmit` Router-first when `routeRuntimeInput` exists.
7. Frontend: map MainPage input mode to Router mode/scope and update tests.
8. Docs: update RIR plan status from planned to in-progress for RIR-5/RIR-6.
9. Run targeted tests and decide whether Electron smoke is needed before PR.

---

## 10. 风险与假设

- 风险：将 `generate_task_tree` 映射到 Router `change` 会改变空会话目标输入的第一步体验。该风险是本切片目标的一部分，但需要 Electron 验证。
- 风险：Activity projection 继续依赖 title fallback，不如显式 context 字段稳定。为了避免扩大 API contract，第一版先接受该折中。
- 风险：Conversation render protocol 会扩大前后端 contract。必须用可选字段和 fallback 渲染降低兼容风险。
- 风险：Router trace 如果写得太像内部推理，会误导用户或泄露隐藏上下文。Trace 必须限制为 contract-level summary。
- 假设：Contract Revision commands 已在 `main` 可用，Router-first submit 不需要重新实现 command substrate。
- 假设：用户仍可通过显式按钮处理 ASK/confirmation；默认输入只是新增同一 surface 的自然语言入口。
