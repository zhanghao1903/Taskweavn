# Main Page Runtime Reducer And Local Pending Submit 技术方案

> Status: draft for implementation
>
> Last Updated: 2026-06-26
>
> Owner: Frontend / Product / Backend UI Contract
>
> Branch: `codex/main-page-runtime-pending-submit`
>
> Related:
> [Plato Conversation And Direct Task UX Flow](../../product/plato-conversation-and-direct-task-ux-flow.md),
> [Plato Runtime Input Model](../../product/plato-runtime-input-model.md),
> [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md),
> [Router-first Main Page Input](router-first-main-input-durable-activity-technical-design.zh-CN.md),
> [Runtime Input Router Contract](runtime-input-router-contract-technical-design.md),
> [Main Page Frontend Runtime Integration](main-page-frontend-runtime-integration.md)

---

## 1. 目标

本切片是 Main Page 交互运行时重构的第一刀，目标是解决用户提交输入后“像卡住”
的问题，同时不破坏后端 canonical snapshot 作为事实权威的边界。

第一版要达到：

1. 用户点击发送后，Conversation 在前端本地立即出现用户输入。
2. 后端处理期间，Conversation 出现一个本地 pending 状态，表达 Plato 正在理解请求。
3. submit button 维持现有 pending affordance。
4. 后端 response / snapshot 回来后，本地 pending item 与 durable message/activity
   去重并收敛。
5. rejected / failed 路径不吞掉用户输入，给出可恢复状态。
6. 新增行为进入 runtime reducer / hook，不继续扩大 `useMainPageController.ts`。

本切片只处理 **local pending submit foundation**。它不试图一次性完成完整 event patch、
focus/scroll runtime 或 token streaming。

---

## 2. 当前状态

Main Page controller 拆分链已合入 main，当前边界为：

- `useMainPageController.ts`：组合层，约 576 行；
- `useMainPageInputRuntimeState.ts`：维护 input draft、runtime activity items、
  active runtime input mode；
- `useMainPageRuntimeInputMutation.ts`：负责 Runtime Input Router mutation；
- `useMainPageCommandMutations.ts`：组合 runtime/input/plan/task/interaction command
  mutation hooks；
- `MainPageWorkbench.tsx`：将 `runtimeActivityItems` 转成 transient messages，与
  snapshot messages 合并展示。

现有 Runtime Input 成功路径：

```text
submit
  -> routeRuntimeInput mutation
  -> onSuccess answered/dispatched
  -> prepend runtime user activity + runtime result activity
  -> clear input
  -> refetch snapshot
```

问题：

- 本地 user activity 只在 mutation 成功后出现；
- 后端处理时间长时，Conversation 没有即时反馈；
- local transient item 只有 activity 形态，缺少 command lifecycle；
- local item 与 snapshot durable message/activity 的关系不明确；
- failed/rejected 路径依赖 input error，没有 conversation-level 状态；
- `runtimeActivityItems` 是 array state，不适合表达 submit started、accepted、
  failed、reconciled 等状态。

---

## 3. 非目标

- 不修改后端 API contract。
- 不要求 `message.appended` event 携带 full `SessionMessageView`。
- 不实现 SSE event patch reducer。
- 不实现 focus/scroll runtime。
- 不实现 token-level streaming。
- 不改变 ASK/confirmation 显式 command 按钮行为。
- 不重写 `MainPageWorkbench` 的整体布局。
- 不改 archived plan、Audit、file changes 等 detail panel 行为。

---

## 4. 用户体验目标

### 4.1 成功路径

```text
User submits: "课件是否已经完成了？"

Immediately:
  You
    课件是否已经完成了？

  Plato
    Understanding your request...

After Router response / durable facts:
  Router interpretation / answer / task dispatch appears.
  Local pending items are removed or marked reconciled.
```

### 4.2 失败路径

```text
User submits request
  -> local user input remains visible
  -> pending item becomes failed
  -> input error/recovery remains available
  -> user can retry without retyping when feasible
```

### 4.3 Rejected path

如果后端明确 rejected：

```text
local user input remains
local pending status becomes rejected
conversation shows user-readable reason
draft can be restored or retry action offered
```

---

## 5. Runtime State 设计

本切片新增一个窄 runtime reducer。它先只管理 local pending conversation items 和
pending command lifecycle，不接管所有 Main Page state。

建议文件：

```text
frontend/src/pages/main-page/runtime/
  mainPagePendingRuntime.ts
  mainPagePendingRuntime.test.ts
```

### 5.1 State

```ts
type MainPagePendingRuntimeState = {
  sessionId: string | null;
  workspaceId: string | null;
  items: LocalConversationItem[];
  pendingCommands: Record<string, PendingRuntimeCommand>;
};
```

### 5.2 LocalConversationItem

```ts
type LocalConversationItem =
  | {
      id: string;
      kind: "local_user_input";
      commandId: string;
      sessionId: string;
      taskNodeId: string | null;
      body: string;
      createdAt: string;
      status: "pending" | "accepted" | "reconciled" | "failed" | "rejected";
    }
  | {
      id: string;
      kind: "local_understanding";
      commandId: string;
      sessionId: string;
      taskNodeId: string | null;
      body: string;
      createdAt: string;
      status: "pending" | "accepted" | "reconciled" | "failed" | "rejected";
      recoveryActions: ProductRecoveryAction[];
    };
```

第一版只需要两类 local item：

- `local_user_input`：用户刚提交的文本；
- `local_understanding`：Plato 正在理解/路由请求。

它们不是 durable facts，不写入 backend。它们只用于用户感知和 pending lifecycle。

### 5.3 PendingRuntimeCommand

```ts
type PendingRuntimeCommand = {
  commandId: string;
  kind: "runtime_input";
  sessionId: string;
  workspaceId: string | null;
  taskNodeId: string | null;
  submittedBody: string;
  submittedAt: string;
  status:
    | "local_pending"
    | "submitted"
    | "accepted"
    | "reconciled"
    | "failed"
    | "rejected";
  failureMessage: string | null;
  recoveryActions: ProductRecoveryAction[];
};
```

### 5.4 Reset boundary

这些状态必须在以下条件清空：

- active session 改变；
- active workspace 改变；
- snapshot identity 表明用户切换到另一个 session；
- user manually refreshes session and no pending command belongs to that session。

不要因为普通 snapshot refetch 就清空 pending；否则后端慢时会闪烁。

---

## 6. Reducer Actions

```ts
type MainPagePendingRuntimeAction =
  | {
      type: "runtime_input.submit_started";
      commandId: string;
      sessionId: string;
      workspaceId: string | null;
      taskNodeId: string | null;
      body: string;
      createdAt: string;
    }
  | {
      type: "runtime_input.command_accepted";
      commandId: string;
    }
  | {
      type: "runtime_input.command_rejected";
      commandId: string;
      message: string;
      recoveryActions: ProductRecoveryAction[];
    }
  | {
      type: "runtime_input.command_failed";
      commandId: string;
      message: string;
      recoveryActions: ProductRecoveryAction[];
    }
  | {
      type: "snapshot.hydrated";
      sessionId: string;
      workspaceId: string | null;
      messages: SessionMessageView[];
      activities: SessionActivityItemView[];
      generatedAt: string;
    }
  | {
      type: "runtime.reset_scope";
      sessionId: string | null;
      workspaceId: string | null;
    };
```

第一版不需要单独 `pendingTimedOut`，但 reducer 应预留 status 以便后续加 timeout。

---

## 7. Submit Flow

### 7.1 Controller flow

`handleInputSubmit` 当前已经在 controller 中选择 runtime router 或 legacy input
mutation。第一版需要在网络请求发出前派发 `submit_started`。为了让 request
selection/scope 只在一个边界内计算，本实现由 controller 生成 `commandId`，再由
`runtimeInputMutation.onMutate` 基于同一个 request builder 派发 `submit_started`：

```text
handleInputSubmit
  -> content = inputDraft.trim()
  -> commandId = generated once
  -> runtimeInputMutation.mutate({ commandId, content, ... })
  -> onMutate builds the same route request
  -> pendingRuntime.dispatch(submit_started)
  -> mutationFn sends routeRuntimeInput request
```

关键点：

- `commandId` 必须从 controller 生成并传入 mutation；
- `buildRuntimeInputRouteRequest` 使用同一个 commandId；
- 不要在 mutation 内部重新生成另一个 commandId；
- draft 清空应发生在 local item 已创建之后；
- `onMutate` 必须只做本地 pending lifecycle，不发网络请求。

### 7.2 Mutation success

Runtime route response 处理规则：

| Response | Pending runtime 更新 | Draft | Snapshot |
|---|---|---|---|
| `commandResponse` accepted | `command_accepted` | clear | 按 refresh hint/refetch |
| `commandResponse` rejected | `command_rejected` | keep or restore | optional |
| `outcome=answered/dispatched` | `command_accepted` | clear | current behavior refetch |
| `needs_clarification/unsupported/rejected` | `command_rejected` | keep | no required refetch |
| network/error | `command_failed` | keep | no required refetch |

现有 `runtimeActivityItems` 成功追加逻辑可保留，但本切片应逐步把它变成
pending runtime projection 的输出，避免两个 local transient sources 分叉。

---

## 8. Projection To Conversation

现有 `MainPageWorkbench` 做法：

```text
runtimeActivityItems -> messageFromActivityItem -> mergeMessages(snapshot messages)
```

本切片建议新增 projection：

```ts
function messagesFromPendingRuntime(
  state: MainPagePendingRuntimeState,
): SessionMessageView[];
```

生成规则：

### 8.1 local user input message

```ts
{
  id: `local:${commandId}:user`,
  sessionId,
  taskNodeId,
  kind: "informational",
  title: "Input",
  body,
  createdAt,
  relatedCommandId: commandId,
  conversationRender: {
    protocolVersion: "plato.conversation.render.v1",
    renderKind: "text",
    text: { title: "You", body },
  },
}
```

### 8.2 local understanding message

```ts
{
  id: `local:${commandId}:understanding`,
  sessionId,
  taskNodeId,
  kind: status === "failed" || status === "rejected" ? "error" : "informational",
  title: "Plato",
  body: bodyForStatus(status),
  createdAt,
  relatedCommandId: commandId,
  conversationRender: {
    protocolVersion: "plato.conversation.render.v1",
    renderKind: "text",
    text: { title: "Plato", body: bodyForStatus(status) },
  },
}
```

Recommended body copy:

| Status | Body |
|---|---|
| pending/submitted | `Understanding your request...` |
| accepted | `Plato accepted the request and is waiting for updates...` |
| failed | failure message |
| rejected | rejected message |

第一版可以只显示 pending / failed / rejected；accepted 状态可以继续显示
`Understanding your request...`，减少 copy churn。

---

## 9. Reconciliation

当 snapshot hydrated 时，本地 pending items 需要与 durable messages/activity 去重。

### 9.1 Strong match

优先匹配：

- durable message `relatedCommandId === commandId`；
- durable activity `sourceId === commandId`；
- route result `activity.sourceId === commandId`；
- command response emitted message ids 中出现 durable message。

### 9.2 Weak match

如果后端缺少 command id，允许弱匹配：

```text
same session
same normalized body
durable occurred within local submittedAt +/- 5 minutes
durable kind is user_input / answer / router_interpretation
```

弱匹配只用于移除 `local_user_input`；不要用弱匹配删除 failed/rejected 状态，避免丢
错误。

### 9.3 Removal policy

- 如果 durable user input 已出现，删除 local user input；
- 如果 durable Router trace / answer / question card 已出现，删除 local understanding；
- 如果 command failed/rejected，保留 failure item，直到用户重试、编辑输入或切换
  session；
- 如果 snapshot 没有任何 durable match，不删除 pending item。

---

## 10. Integration Points

### 10.1 `useMainPageInputRuntimeState`

扩展或替换为：

```text
input draft state
active runtime input mode
pending runtime reducer state
projection helpers
```

建议第一版仍保留 hook 名称，内部新增 `useReducer`，减少外部调用面变化。

### 10.2 `useMainPageRuntimeInputMutation`

需要改动：

- 接收 `commandId`；
- mutation context 带 `commandId`；
- `buildRuntimeInputRouteRequest` 使用传入 commandId；
- onSuccess/onError 派发 accepted/rejected/failed；
- 不在成功后才创建 local user activity。

### 10.3 `MainPageWorkbench`

需要改动：

- 接收 `pendingRuntimeMessages` 或继续接收统一后的 `runtimeActivityItems`；
- conversation merge 顺序稳定；
- local pending items 按 createdAt 排序；
- durable message 到达后去重。

第一版推荐最小改动：

```text
controller exposes runtimeActivityItems as today
useMainPageInputRuntimeState projects pending runtime into same shape
MainPageWorkbench remains mostly unchanged
```

也就是说，第一 PR 可以不改 Workbench 的 props，只改变 upstream projection。

### 10.4 Tests

新增 reducer tests，不要只测 React hook。

---

## 11. Implementation Slices

### Slice A: Reducer only

- 新增 `mainPagePendingRuntime.ts`；
- 定义 state/action/projection；
- unit tests 覆盖 submit/accepted/rejected/failed/reset/reconcile；
- 不接入 UI。

### Slice B: Hook integration

- `useMainPageInputRuntimeState` 使用 reducer；
- 对外仍返回 `runtimeActivityItems`；
- `runtimeActivityItems` 包含 pending user + understanding projection；
- session/workspace 切换清空 pending。

### Slice C: Mutation command id threading

- `handleInputSubmit` 创建 commandId；
- `RuntimeInputMutationContext` 接收 commandId；
- request 使用同一个 commandId；
- submit started 在 mutation `onMutate` 中发生，必须早于网络 request；
- success/error 更新 reducer。

### Slice D: Reconciliation

- snapshot hydrated 时调用 reducer；
- durable message/activity 到达后移除 matching local items；
- 保留 failed/rejected item。

### Slice E: Component acceptance tests

- 用户提交后立即出现 input bubble；
- 后端 pending promise 未 resolve 时仍显示 understanding；
- resolve 后 snapshot durable message 去重；
- rejected 时保留 error item 和 draft/recovery。

---

## 12. Test Plan

### 12.1 Unit tests

File:

```text
frontend/src/pages/main-page/runtime/mainPagePendingRuntime.test.ts
```

Cases:

1. `submit_started` creates user input + understanding items.
2. `command_accepted` marks pending command accepted.
3. `command_rejected` marks understanding item rejected and stores recovery.
4. `command_failed` marks understanding item failed.
5. `snapshot.hydrated` removes local user item when durable related command id exists.
6. `snapshot.hydrated` removes understanding item when durable answer/router trace exists.
7. `runtime.reset_scope` clears old session pending state.
8. Weak body/time match removes local user input only.

### 12.2 Hook / component tests

Existing likely targets:

```text
frontend/src/pages/main-page/useMainPageController.test.tsx
frontend/src/pages/main-page/MainPageWorkbench.test.tsx
```

Add focused cases:

- runtime input mutation promise blocked: local input and understanding item are visible;
- route response answered: pending local items reconcile with returned runtime activity or snapshot;
- route response rejected: input error visible and local failed/rejected item visible;
- legacy adapter without `routeRuntimeInput`: no new pending runtime behavior.

### 12.3 Manual / Electron acceptance

After implementation:

```text
npm run electron:dev
```

Validate:

1. 在已有 session 里输入一个 read-only question；
2. 点击发送后立刻看到自己的输入；
3. 后端回答前看到 Understanding 状态；
4. 回答出现后没有重复用户输入；
5. 网络/LLM error 时不会让用户觉得点击无效。

---

## 13. Acceptance Criteria

1. Runtime input submit 后，local user input item 在 mutation resolve 前出现。
2. Runtime input submit 后，local understanding item 在 mutation resolve 前出现。
3. `commandId` 在 submit、request、pending runtime、reconciliation 中保持一致。
4. route success 后保留现有 backend refetch behavior，但本地 UI 不等待 refetch 才反馈。
5. rejected/failed 路径保留用户可见错误，不吞掉输入。
6. snapshot hydration 能删除已被 durable facts 覆盖的 local pending items。
7. session/workspace 切换不会泄漏旧 session pending items。
8. 新增实现不把大段状态逻辑加回 `useMainPageController.ts`。
9. Reducer 有独立 unit tests。

---

## 14. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| local item 和 durable item 重复 | Conversation 变脏 | commandId strong match + body/time weak fallback |
| 后端未持久化 user input | local item 长时间存在 | accepted 后保留 pending 状态，后续 timeout slice 再处理 |
| mutation 失败后 draft 被清空 | 用户丢输入 | failed/rejected 不清 draft；或恢复 draft |
| Workbench merge 顺序不稳定 | timeline 跳动 | local item ids stable，createdAt 使用 submit timestamp |
| reducer 过早接管全部 Main Page state | scope 膨胀 | 第一版只管理 pending runtime |
| snapshot refetch 仍很多 | 性能收益有限 | 本切片目标是响应性；event patch 是后续 slice |

---

## 15. Open Questions

1. local understanding item 文案是否用英文 `Understanding your request...`，还是接入
   existing ui-text bilingual copy？
2. routeResult.activity 已返回时，是否立即作为 durable-like item 插入，还是等 snapshot？
3. rejected 后是否自动把 draft 恢复为 submitted body？
4. pending timeout 默认多久：15s、30s，还是等 event layer 再决定？
5. local user input 是否应该在 Activity overlay 中出现，还是只在 Conversation 层出现？

第一版建议：

- 使用已有英文 copy，后续统一本地化；
- routeResult.activity 可继续走现有 `runtimeActivityItems`；
- rejected/failed 保留 draft；
- 不做 timeout；
- local pending 同时通过现有 transient message 机制进入 Conversation，不单独进入
  Activity overlay。

---

## 16. Decision

本实现分支应先完成 **reducer foundation + local pending submit**，保持现有 snapshot
refetch 作为最终收敛路径。不要在同一个 PR 中做 event patch、focus/scroll 或 backend
contract 扩展。

实现完成后，再进入下一切片：

```text
Conversation render protocol hardening
  -> Focus / scroll runtime
  -> Event patch reducer
  -> Snapshot refetch reduction
```
