# Main Page Frontend Runtime Integration 技术设计

> Status: planned
> Last Updated: 2026-05-21
> Feature Plan: [Main Page Frontend Runtime Integration](main-page-frontend-runtime-integration.md)
> Parent Plan: [Main Page Real Backend Integration](main-page-real-backend-integration.md)

---

## 1. 背景与目标

当前 Main Page 的前后端链路已经有了骨架：

```text
taskweavn plato-dev
  -> MainPageSidecarApp
  -> PlatoUiHttpTransport
  -> UiQueryGateway / UiCommandGateway / UiEventSource
  -> createHttpPlatoApi
  -> createHttpMainPageAdapter
  -> MainPage
```

但 `MainPage` 自身仍然带着 prototype runtime：

- `stateId` 是 query key；
- `StatePicker` 总是显示；
- HTTP adapter 仍返回 mock metadata shape；
- 命令 accepted 后由本地 synthetic message 表示成功；
- event handler 只处理两个事件；
- `message.appended` 被当作完整消息 payload，但后端只保证 lightweight event。

本设计目标是把前端 runtime 改成真实后端驱动：

```text
SessionId
  -> MainPageSnapshot query
  -> local UI selection/detail/input state
  -> CommandResponse pending/refresh
  -> UiEvent invalidation/refetch
  -> refreshed MainPageSnapshot
```

第一版追求正确性和可验证性，不追求复杂 patch 性能。

---

## 2. 设计原则

### 2.1 Snapshot 是事实源

HTTP mode 下，以下对象只以 `MainPageSnapshot` 为事实源：

- `TaskTreeView`;
- `TaskNodeCardView`;
- `SessionMessageView`;
- `ConfirmationActionView`;
- `ResultCardView`;
- `FileChangeSummaryView`;
- `SessionSummary.status`。

本地 state 可以临时表达 pending/loading/error，但不能长期覆盖这些事实。

### 2.2 Event 默认是 invalidation

`UiEvent` 是事实变化通知，不是完整 ViewModel。

前端默认策略：

```text
event received
  -> compute affected scopes
  -> invalidate/refetch snapshot
```

只有事件 payload 明确包含完整 UI ViewModel 时，才允许局部 patch。

### 2.3 Mock runtime 和 HTTP runtime 并存但隔离

Mock runtime 继续服务：

- Figma 9 states review；
- product discussion；
- visual regression；
- component behavior tests。

HTTP runtime 服务：

- sidecar integration；
- command/event correctness；
- real user workflow smoke。

两者共享组件和 selectors，但不共享 runtime identity。

### 2.4 先保守，后优化

第一版可以频繁 refetch snapshot。性能压力现在不是主要问题。

等到事件 payload 和局部 query 稳定后，再考虑：

- messages-only query；
- task-node-only patch；
- result/file-change scoped query；
- event replay store。

---

## 3. 推荐文件结构

当前 `pages/main-page` 已经包含组件、fixtures、mock adapter、HTTP adapter、selectors。

建议第一阶段只做轻量拆分，不进行大迁移：

```text
frontend/src/pages/main-page/
  MainPage.tsx
  ContextInputPanel.tsx
  MainPageDetailPanel.tsx
  SessionMessagePanel.tsx
  TaskTreePanel.tsx
  mainPageSelectors.ts
  mainPageUiTypes.ts
  fixtures.ts
  mainPageStateCatalog.ts
  runtime/
    adapter.ts
    mockAdapter.ts
    httpAdapter.ts
    metadata.ts
    commandRefresh.ts
    eventRouter.ts
    runtimeConfig.ts
```

迁移顺序：

1. 新增 `runtime/adapter.ts`，复制稳定类型，不立刻删除旧 export；
2. 新增 `runtime/metadata.ts`，把 HTTP mode 的 metadata 从 snapshot 推导；
3. 新增 `runtime/eventRouter.ts`，先独立测试；
4. `MainPage.tsx` 切换到新 runtime types；
5. 最后清理 `mockPlatoApi.ts` 中的 adapter 类型。

---

## 4. 核心类型

### 4.1 MainPageRuntimeMode

```ts
type MainPageRuntimeMode = "mock" | "http";
```

### 4.2 MainPageRuntimeConfig

```ts
type MainPageRuntimeConfig = {
  mode: MainPageRuntimeMode;
  sessionId: string | null;
  showScenarioPicker: boolean;
};
```

规则：

- mock mode: `sessionId=null`, `showScenarioPicker=true`;
- http mode: `sessionId` required, `showScenarioPicker=false` by default；
- 可用未来 dev flag 打开 HTTP mode scenario picker，但不是普通用户路径。

### 4.3 MainPageSnapshotEnvelope

`MainPage` 当前需要 metadata + snapshot。建议保留 envelope，但 metadata 来源要变清楚：

```ts
type MainPageSnapshotEnvelope = {
  metadata: MainPageRuntimeMetadata;
  snapshot: MainPageSnapshot;
};
```

### 4.4 MainPageRuntimeMetadata

```ts
type MainPageRuntimeMetadata = {
  id: string;
  label: string;
  detail: MainPageDetail;
  initialSelectedTaskNodeId: TaskNodeId | null;
  inputScope: MainPageInputScope;
  topStatus: string;
  topStatusTone: BadgeTone;
};
```

`id` 在 mock mode 可以是 `stateId`。HTTP mode 建议使用：

```text
live:<sessionId>:<snapshot.cursor | generatedAt>
```

但不要把它放进 query key。

### 4.5 MainPageAdapter

第一版 adapter 可以先覆盖 Main Page 需要的命令：

```ts
type MainPageAdapter = {
  runtime: MainPageRuntimeConfig;
  loadSnapshot(input: LoadSnapshotInput): Promise<MainPageSnapshotEnvelope>;
  appendSessionInput(request: CommandRequest<AppendSessionInputPayload>): Promise<CommandResponse>;
  generateTaskTree(request: CommandRequest<GenerateTaskTreePayload>): Promise<CommandResponse>;
  updateTaskNode(sessionId: SessionId, taskNodeId: TaskNodeId, request: CommandRequest<UpdateTaskNodePayload>): Promise<CommandResponse>;
  appendTaskInput(sessionId: SessionId, taskNodeId: TaskNodeId, request: CommandRequest<AppendTaskInputPayload>): Promise<CommandResponse>;
  publishTaskTree(request: CommandRequest<PublishTaskTreePayload>): Promise<CommandResponse>;
  resolveConfirmation(sessionId: SessionId, confirmationId: ConfirmationId, request: CommandRequest<ResolveConfirmationPayload>): Promise<CommandResponse>;
  subscribeSessionEvents(sessionId: SessionId, cursor: EventCursor | null, onEvent: (event: UiEvent) => void): () => void;
};
```

`LoadSnapshotInput` 区分两个 runtime：

```ts
type LoadSnapshotInput =
  | { mode: "mock"; stateId: MainPageStateId }
  | { mode: "http"; sessionId: SessionId };
```

这样 `MainPage` 不再把 `stateId` 传给 HTTP adapter。

---

## 5. Snapshot Query 设计

### 5.1 Query key

```ts
function snapshotQueryKey(runtime: MainPageRuntimeConfig, stateId: MainPageStateId) {
  if (runtime.mode === "http") {
    return ["main-page", "snapshot", runtime.sessionId];
  }
  return ["main-page", "fixture", stateId];
}
```

### 5.2 Query fn

```ts
function snapshotQueryInput(runtime, stateId): LoadSnapshotInput {
  if (runtime.mode === "http") {
    return { mode: "http", sessionId: requireSessionId(runtime) };
  }
  return { mode: "mock", stateId };
}
```

### 5.3 Snapshot change reset

当前 `useEffect([snapshotData])` 会重置 selection、draft、local messages。

HTTP mode 更合理的 reset key：

```text
session.id + taskTree?.id + taskTree?.version
```

建议：

- session 改变：重置 selection/detail/input；
- taskTree id/version 改变：如果当前 selected task 不存在，重新选择默认 task；
- 普通 message append：不清空 input draft；
- command accepted：不清空 durable state，只清 pending。

---

## 6. Metadata 推导

### 6.1 默认选中 TaskNode

HTTP mode:

```text
pending confirmation task
  -> running / waiting_user task
  -> first draft task with canEdit
  -> first task
  -> null
```

### 6.2 Detail mode

优先级：

```text
active confirmation
  -> explicit local override(result/file_changes)
  -> selected task
  -> result
  -> file changes
  -> task tree/session
  -> workflow
```

注意：result/file changes 是否应该优先于 selected task 是产品问题。第一版保持当前行为：用户显式点 result/file changes 时尊重 override，否则 selected task 更具体。

### 6.3 Input scope

```text
no task tree -> session / generate task tree
selected draft task -> selected task / revision
selected running task -> selected task / guidance
selected done task -> read-only, unless follow-up mode
confirmation focus -> confirmation note or option
```

UI 文案仍可简化，但 command payload 必须按 scope 分流。

---

## 7. Command Runtime

### 7.1 Command ID

当前使用 `Date.now()`。第一版可以继续，但建议统一 helper：

```ts
function newCommandId(prefix: string): CommandId {
  return `${prefix}-${crypto.randomUUID?.() ?? Date.now()}`;
}
```

### 7.2 Command Pending State

```ts
type PendingCommand = {
  commandId: CommandId;
  kind:
    | "append_session_input"
    | "generate_task_tree"
    | "update_task_node"
    | "append_task_input"
    | "publish_task_tree"
    | "resolve_confirmation";
  taskNodeId?: TaskNodeId | null;
  startedAt: string;
  message: string;
};
```

Pending state 只用于 UI affordance：

- disable duplicate button；
- show "waiting for backend update"；
- allow retry if failed。

不要用 pending state 永久改变 TaskNode status。

### 7.3 CommandResponse handling

```text
CommandResponse.ok=false
  -> show ApiError
  -> clear pending

ok=true + result.status=accepted
  -> store pending command
  -> if refresh.waitForEvents: wait for event up to short timeout
  -> invalidate affected scopes or snapshot
  -> clear pending when event/refetch confirms or timeout refetch completes
```

第一版 timeout 可保守：

```text
accepted command
  -> refetch snapshot immediately
  -> event later may refetch again
```

这牺牲少量请求，换取简单可靠。

### 7.4 Scope to command mapping

| UI condition | Command |
|---|---|
| no TaskTree and user submits goal | `generateTaskTree` with `prompt` |
| session has TaskTree and no selected task | `appendSessionInput` with `global_guidance` |
| selected draft task and free-form guidance | `appendTaskInput` with `revision_request` or `guidance` |
| selected running/waiting task | `appendTaskInput` with `guidance` |
| structured field edit | `updateTaskNode` |
| draft tree publish | `publishTaskTree` |
| confirmation option chosen | `resolveConfirmation` |

`AppendSessionInputPayload.mode="generate_task_tree"` 当前存在于 contract，但第一版 UI 更推荐使用显式 `generateTaskTree` endpoint。若后端希望合并两者，需要同步 contract，而不是让前端猜。

---

## 8. Event Router

### 8.1 Router input/output

```ts
type EventRouterInput = {
  event: UiEvent;
  pendingCommands: Map<CommandId, PendingCommand>;
};

type EventRouterDecision =
  | { kind: "refetch_snapshot"; reason: string }
  | { kind: "append_complete_message"; message: SessionMessageView }
  | { kind: "command_failed"; commandId: CommandId | null; message: string; retryable: boolean }
  | { kind: "mark_limited_events"; reason: string }
  | { kind: "ignore"; reason: string };
```

第一版大多数事件返回 `refetch_snapshot`。

### 8.2 message.appended

后端当前事件：

```json
{
  "eventType": "message.appended",
  "messageIds": ["message-1"],
  "payload": {
    "message_type": "informational",
    "agent_id": "collaborator"
  }
}
```

这不是完整 `SessionMessageView`。

处理：

```text
if payload has title/body/kind:
  optionally append transient message
else:
  refetch snapshot
```

为了简单，第一版可以总是 refetch。

### 8.3 command.failed

```text
event.commandId exists
  -> clear matching pending
  -> show payload.message
  -> if retryable: keep retry affordance
```

### 8.4 resync_required loop guard

状态：

```ts
type ResyncGuard = {
  lastCursor: EventCursor | null;
  lastReason: string | null;
  count: number;
};
```

规则：

- same cursor + same reason 连续超过 1 次，不继续立即 refetch；
- 标记 event status 为 `limited`；
- 用户命令仍可触发 refetch；
- 下一次 snapshot cursor 改变后重置 guard。

UI label 可以从：

```text
Events live / Events offline / Resyncing
```

扩展为：

```text
Events live / Events limited / Events offline / Resyncing
```

---

## 9. MainPage 组件调整点

### 9.1 StatePicker

当前 always render。

目标：

```tsx
{adapter.runtime.showScenarioPicker && (
  <StatePicker stateId={stateId} onStateChange={handleStateChange} />
)}
```

### 9.2 Sidebar session buttons

当前 session button 无点击行为。第一版可暂不做完整 session switch，但如果 snapshot 返回多个 sessions：

- mock mode: inert 或 fixture behavior；
- http mode: disabled + tooltip/label 表明 session switching not implemented；
- 后续 session selector plan 再接入。

不要让用户以为可以切换但实际无效。

### 9.3 Local synthetic messages

当前：

- confirmation decision -> push `User decision captured`;
- input success -> push `Task guidance captured`。

目标：

- accepted 后显示 pending inline affordance；
- refetch 后如果 backend snapshot 包含对应 message，就显示真实 message；
- 如果 refetch 超时，可显示 transient pending/error，不写入 `messages` 数组。

### 9.4 Task status local override

当前 `task-visual-direction` 特判必须移除或限定为 fixture adapter 数据：

```text
status must come from snapshot.taskTree.nodes[].status
```

如果 mock scenario 需要确认后改变状态，可以让 mock adapter 返回变化后的 snapshot，或仅在 fixture test 中验证 local decision text，不改 task card durable status。

---

## 10. 测试设计

### 10.1 Adapter tests

- mock adapter loads each fixture state；
- HTTP adapter loads by session id, not state id；
- HTTP adapter exposes generate/update/publish commands；
- runtime config differs by mode。

### 10.2 MainPage tests

- mock mode shows StatePicker；
- HTTP mode hides StatePicker；
- HTTP mode query key uses session id；
- accepted session input invalidates/refetches snapshot；
- accepted confirmation does not permanently override TaskNode status；
- command rejection shows API error；
- event `task.tree.changed` triggers refetch；
- backend fixture `message.appended` triggers refetch, not fake message body；
- resync loop guard prevents repeated immediate refetch for same cursor/reason。

### 10.3 Contract fixture tests

Existing tests should expand from type-only validation to behavior:

- `main_page_snapshot.min.json` can render MainPage HTTP mode；
- `command_response.accepted.json` maps to pending/refetch decision；
- `ui_event.message_appended.json` maps to refetch decision。

### 10.4 Browser smoke

Manual:

```text
uv run taskweavn plato-dev --workspace ./plato-workspace --session-name Demo
```

Expected:

1. page opens without StatePicker;
2. top bar shows live session;
3. snapshot loads;
4. input submit sends command;
5. UI refetches from sidecar without local fake final state.

Automated Browser/Playwright smoke can be added after command semantics stabilize.

---

## 11. 迁移顺序

### Step 1: Runtime adapter extraction

Low risk. Moves types and helpers. No behavior change.

### Step 2: Runtime config and StatePicker gating

Small visible change. HTTP mode becomes less prototype-like.

### Step 3: Session-centric query key

Important behavior change. Keep tests tight.

### Step 4: Command refresh helper

Replace local synthetic truth with pending/refetch.

### Step 5: Event router

Move event handling out of `MainPage.tsx`; default to refetch.

### Step 6: Full command coverage

Add `generateTaskTree`, `updateTaskNode`, `publishTaskTree` through adapter and UI only where current snapshot permissions allow.

### Step 7: Smoke and docs

Validate with `taskweavn plato-dev`, then update parent plan and release record.

---

## 12. 与后端计划的边界

属于前端 runtime integration：

- query key；
- local UI state；
- command pending/error affordance；
- event router；
- adapter boundary；
- Main Page component wiring。

不属于本计划：

- adding durable `UiEventStore`;
- changing backend event payload richness;
- adding new backend command semantics;
- implementing TaskBus execution lifecycle;
- full session creation/selection product flow。

如果实施中发现后端 contract 无法表达必要 UI 行为，应更新 `plato-ui-api-contract.md` 并把后端改动拆为独立 backend slice。

---

## 13. Done Definition

本技术方案完成后的状态：

```text
Mock mode:
  fixture states remain available
  StatePicker visible
  product/visual review remains fast

HTTP mode:
  session id drives snapshot query
  StatePicker hidden
  commands submit to sidecar
  accepted commands refetch from backend facts
  events invalidate/refetch safely
  lightweight message events do not fabricate messages
```

这时 Main Page 才能被称为“真实 backend runtime 已接入”，而不仅是“能调用 HTTP API 的原型页面”。
