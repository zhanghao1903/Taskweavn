# 前端 API Mock Happy Path 详细技术方案

> 状态: deferred
> 类型: Frontend API mock / Main-Audit happy path integration
> 最后更新: 2026-05-27
> 关联计划: [Frontend API Mock Happy Path](frontend-api-mock-happy-path.md)
> 上游输入: [Frontend Architecture Plan](../../frontend/frontend-architecture-plan.md), [API/UI Mapping](../../frontend/api-ui-mapping.md), [Event Reducer Contract](../../frontend/event-reducer-contract.md), [Audit Page Contract](../../engineering/audit-page-contract.md), [Canonical Status Model](../../product/canonical-status-model.md)

---

## 1. 背景

> 2026-05-27 决策更新：API mock 工作量偏大，先搁置。P7.1A Main Page
> Compatibility Wrap 可先推进，因为它只增加 route/runtime wrapper，不依赖完整
> interactive API mock。

P6.1-P6.8 已经建立了前端类型契约、Main/Audit mock scenario、API boundary hardening、runtime reducer foundation、mock runtime facade、compatibility adapter、MainPage event harness 覆盖。

继续扩大静态场景或事件 harness 测试，收益已经下降。下一步需要把 mock 从「状态陈列」推进为「API 形状的可交互后端替身」。

目标不是做完整 fake backend，而是做一条可重复、可测试、能驱动页面变化的 Main/Audit happy path session mock。

## 2. 设计目标

1. 前端通过现有 `PlatoApi` 调用 mock，不直接依赖 fixture state id。
2. Main Page 可以从 empty session 走到 draft TaskTree、publish、confirmation、completed、file changes。
3. Audit API 数据来自同一个 session mock state，不再与 Main session 生命周期割裂。
4. Command response 只代表 command accepted/rejected，不直接代表最终事实。
5. 最终 UI 事实来自下一次 `getSessionSnapshot` / `getAuditSnapshot`。
6. Event 可以作为 deterministic invalidation hint，但第一版不依赖真实 SSE 时序。
7. Mock 可用于 API unit tests 和 Main Page happy path integration test。
8. 不改 UI、不重构 MainPage、不替换真实 HTTP adapter。

## 3. 非目标

- 不模拟完整多 session、多 workflow、多 project。
- 不覆盖所有 negative path。
- 不实现真实 agent execution。
- 不实现真实 HTTP server。
- 不实现完整 SSE retention、cursor expiry、backfill。
- 不将 mock 写入生产 runtime 默认路径。
- 不在此阶段实现 Audit Page UI。

## 4. 当前代码基础

### 4.1 可复用边界

现有 `frontend/src/shared/api/platoApi.ts` 已定义统一 `PlatoApi`:

- session lifecycle: `listSessions`, `createSession`, `renameSession`, `deleteSession`
- Main query: `getSessionSnapshot`
- Main commands: `appendSessionInput`, `generateTaskTree`, `updateTaskNode`, `appendTaskInput`, `publishTaskTree`, `resolveConfirmation`
- Audit query: `getAuditSnapshot`, `listAuditRecords`, `getAuditRecordDetail`, `getEvidenceDetail`
- event: `subscribeSessionEvents`

现有 `frontend/src/pages/main-page/httpMainPageAdapter.ts` 已支持注入任意 `PlatoApi`:

```ts
createHttpMainPageAdapter({ api, sessionId, showStatePicker: false })
```

这意味着 P6.9 不需要改 MainPage 结构，只需要实现一个符合 `PlatoApi` 的 mock。

### 4.2 现有 mock 的限制

`frontend/src/pages/main-page/mockPlatoApi.ts` 当前更接近 fixture adapter:

- `getMainPageMockSnapshot(stateId)` 根据静态 state id 返回 snapshot。
- command mock 返回 accepted，但不维护 session 状态机。
- command 后 refetch 仍回到同一个 fixture，无法证明 API 驱动页面变化。

`frontend/src/pages/audit-page/mockAuditApi.ts` 当前独立于 Main session:

- Audit scenario 可独立查询。
- 不能证明 file change / result / audit record 与 Main happy path 同源。

## 5. 目标模块结构

建议新增测试/开发专用 API mock 模块:

```text
frontend/src/testing/api/
  happyPathPlatoApi.ts
  happyPathPlatoApi.test.ts
  happyPathSessionState.ts
```

说明:

- `testing/api` 表示它不是生产 API adapter。
- 如果后续需要在本地 dev runtime 中可视化使用，可以再通过显式 dev-only provider 暴露。
- 第一版不放到 `pages/main-page`，避免和历史 fixture adapter 继续耦合。

如果构建配置不方便从 `testing` 引入，也可以退一步放在:

```text
frontend/src/shared/api/happyPathMockPlatoApi.ts
```

但需要在文件头明确标注 dev/test-only。

## 6. 对外 API

建议导出:

```ts
export type HappyPathStep =
  | "empty"
  | "draft_ready"
  | "published_running"
  | "waiting_confirmation"
  | "completed_with_result";

export type HappyPathMockPlatoApiOptions = {
  now?: () => string;
  initialStep?: HappyPathStep;
  eventMode?: "none" | "sync";
};

export type HappyPathMockPlatoApi = PlatoApi & {
  getState(): HappyPathSessionState;
  drainEvents(): UiEvent[];
};

export function createHappyPathMockPlatoApi(
  options?: HappyPathMockPlatoApiOptions,
): HappyPathMockPlatoApi;
```

### 6.1 `eventMode`

第一版推荐默认:

```ts
eventMode: "none"
```

MainPage 现有行为已经会在 command accepted 后 refetch snapshot。P6.9/P6.10 可以先证明 command -> refetch -> new facts。之后再打开 `sync` 验证 deterministic event invalidation。

## 7. 内部状态模型

Mock 内部维护一个单 session state:

```ts
type HappyPathSessionState = {
  projectId: "project-personal-website";
  workflowId: "workflow-task-planning";
  sessionId: "session-happy-path";
  sessionName: "个人网站项目规划";
  step: HappyPathStep;
  version: number;
  cursorIndex: number;
  commandLog: HappyPathCommandLogEntry[];
  selectedTaskNodeId: TaskNodeId | null;
  confirmation: {
    id: ConfirmationId;
    status: "pending" | "resolved";
    resolvedValue: string | null;
  };
  audit: {
    recordsAvailable: boolean;
    selectedRecordId: AuditRecordId | null;
  };
};
```

`step` 是 mock 内部实现细节，不进入产品契约。对外返回的 snapshot 必须映射到 canonical status dimensions:

| Mock step | planning | task readiness | execution | confirmation | audit verdict |
|---|---|---|---|---|---|
| `empty` | `empty` | `unknown` / tree empty | `not_started` | none | `not_available` |
| `draft_ready` | `draft_ready` | draft/ready | `not_started` | none | `not_available` |
| `published_running` | `published` | published | `running` | none | `not_available` |
| `waiting_confirmation` | `published` | published | `running` | `pending` | `not_available` |
| `completed_with_result` | `published` | published | `done` | `resolved` | `warning` |

## 8. Query 行为

### 8.1 `listSessions`

返回一个 session:

- id: `session-happy-path`
- projectId: `project-personal-website`
- workflowId: `workflow-task-planning`
- name: `个人网站项目规划`
- status 根据 `step` 映射:
  - `empty` -> `new`
  - `draft_ready` -> `draft_ready`
  - `published_running` -> `running`
  - `waiting_confirmation` -> `waiting_user`
  - `completed_with_result` -> `completed`

### 8.2 `getSessionSnapshot`

根据当前 `step` 构造 `MainPageSnapshot`。

推荐第一版复用现有静态 fixture 作为 snapshot seed，以降低实现成本:

| Mock step | Seed fixture |
|---|---|
| `empty` | `s1-empty` |
| `draft_ready` | `s3-draft-ready` |
| `published_running` | `s6-running` |
| `waiting_confirmation` | `s7-confirmation` |
| `completed_with_result` | `s9-file-changes` 或 `s8-completed` + file summary |

复用方式:

1. 调用 `getMainPageMockSnapshot(seedStateId).snapshot`。
2. 复制 snapshot，替换:
   - `session.id`
   - `session.name`
   - `session.status`
   - `cursor`
   - `generatedAt`
   - `pendingConfirmations`
   - `auditSummary`
   - 必要时替换 result/fileChangeSummary。
3. 不暴露 seed state id 给页面。

这样第一版可以聚焦 API state machine，而不是重写大量 ViewModel fixture。

### 8.3 Audit queries

Audit 数据必须与同一个 `sessionId` 绑定。

| API | 行为 |
|---|---|
| `getAuditSnapshot` | `completed_with_result` 前返回 empty/not_available；完成后返回 records ready / warning verdict snapshot。 |
| `listAuditRecords` | 返回当前 Audit records。 |
| `getAuditRecordDetail` | 按 `recordId` 返回 detail；不存在返回 `not_found`。 |
| `getEvidenceDetail` | 按 `evidenceId` 返回 evidence detail；不存在返回 `not_found`。 |

第一版可以复用 `getAuditMockSnapshot("a7-warning-verdict")` 或 `getAuditMockSnapshot("a3-records-ready")` 作为完成态 seed，再统一替换 `subject.sessionId`、record refs、cursor。

## 9. Command 行为

### 9.1 Command response 规则

所有成功 command 返回:

```ts
{
  ok: true,
  result: {
    status: "accepted",
    commandId,
    message,
    affectedTaskRefs,
    objectRefs,
    affectedObjects,
    emittedMessageIds,
    publishedTaskIds,
    debugRefs: {},
  },
  error: null,
  refresh: {
    waitForEvents: eventMode === "sync",
    suggestedQueries: [...],
    affectedTaskRefs: [...],
    affectedScopes: [...],
  }
}
```

注意:

- `accepted` 不等于 `done`。
- Mock 可以在返回 accepted 前后同步推进内部 `step`，但测试断言必须通过后续 query 观察最终事实。
- 如果后续需要更真实的异步，可以把状态推进延迟到 event emit，但第一版不建议增加复杂度。

### 9.2 `appendSessionInput`

行为:

- 如果当前 `step = empty` 且 `payload.mode = generate_task_tree`，可以委托到 `generateTaskTree` 语义，推进到 `draft_ready`。
- 如果当前已有 task tree，则作为 session guidance 接受，但不改变 happy path terminal facts。

原因:

- 当前 MainPage 在 empty 且无 TaskTree 时会直接调用 `generateTaskTree`。
- 兼容 `appendSessionInput` 可以让未来输入模式测试不需要另起 mock。

### 9.3 `generateTaskTree`

前置条件:

- `sessionId` 必须匹配 `session-happy-path`。
- 当前 `step` 最好为 `empty`，但为测试幂等性可允许重复调用保持 `draft_ready`。

状态转移:

```text
empty -> draft_ready
```

事件候选:

- `task.tree.changed`
- `message.appended`

### 9.4 `publishTaskTree`

前置条件:

- 当前 `step = draft_ready`。
- `payload.taskTreeId` 匹配当前 snapshot 的 TaskTree id。

状态转移推荐:

```text
draft_ready -> waiting_confirmation
```

说明:

- P6 happy path 的主要目标之一是覆盖 confirmation lifecycle。
- 如果需要短暂 running 态，可在 integration test 中拆成:
  - `publishTaskTree` 后第一次 snapshot: `published_running`
  - 下一次 snapshot 或 sync event 后: `waiting_confirmation`
- 第一版为了稳定，建议 publish 后直接进入 `waiting_confirmation`，同时在 snapshot 内保留 running/executing 语义。

事件候选:

- `task.tree.changed`
- `confirmation.created`

### 9.5 `resolveConfirmation`

前置条件:

- 当前 `step = waiting_confirmation`。
- `confirmationId` 匹配当前 pending confirmation。
- `payload.value` 支持 `"confirm"` / `"skip"` / `"reject"`，第一版 happy path 使用 `"confirm"`。

状态转移:

```text
waiting_confirmation -> completed_with_result
```

完成后 snapshot 应包含:

- resolved confirmation facts 或无 pending confirmation。
- completed execution status。
- result summary。
- file change summary。
- Audit summary verdict `warning`。

事件候选:

- `confirmation.resolved`
- `result.updated`
- `file_changes.updated`
- `audit.summary_updated`

### 9.6 `updateTaskNode` / `appendTaskInput`

第一版处理策略:

- 返回 accepted。
- 记录 commandLog。
- 不改变主 happy path step，除非后续 P6.10 测试明确需要 task editing path。

这样可以覆盖 MainPage 现有按钮和输入边界，但不把 mock 扩展成完整任务编辑后端。

### 9.7 session lifecycle command

| API | 第一版行为 |
|---|---|
| `createSession` | 返回新的 session id 可以是当前固定 session；或如果已存在，返回 `session-happy-path`。不创建多 session。 |
| `renameSession` | 更新 `sessionName`。 |
| `deleteSession` | 返回 `nextSessionId: null`，但不作为 happy path 必测项。 |

如果 lifecycle 行为增加实现成本，P6.9 可以先用 explicit `command_rejected`，但需要在测试里说明 Main happy path 不依赖它。

## 10. Error 和 unsupported handling

Mock 不应 silently pass 不支持路径。

推荐工具函数:

```ts
function queryError<T>(
  code: ApiError["code"],
  message: string,
  retryable = false,
): QueryResponse<T>;

function commandRejected(
  commandId: CommandId,
  code: ApiError["code"],
  message: string,
  retryable = false,
): CommandResponse;
```

规则:

| 条件 | 响应 |
|---|---|
| sessionId 不匹配 | `not_found` |
| taskNodeId / recordId / evidenceId 不存在 | `not_found` |
| command 与当前 step 冲突 | `command_rejected` |
| expectedVersion 低于当前 version | `version_conflict` |
| permission 测试未启用但调用受限命令 | `permission_denied` 或 `command_rejected` |

## 11. Event 和 cursor 设计

第一版 cursor 只需要 deterministic:

```text
cursor-happy-0001
cursor-happy-0002
cursor-happy-0003
```

每次状态转移:

1. `version += 1`
2. `cursorIndex += 1`
3. 生成一个或多个 `UiEvent`
4. `getSessionSnapshot` / `getAuditSnapshot` 返回最新 cursor

`subscribeSessionEvents`:

- `eventMode = "none"`: 注册 listener，返回 unsubscribe，不主动 emit。
- `eventMode = "sync"`: command 转移后同步向当前 listener emit pending events。

不要在第一版使用 timers。定时器会增加 test flakiness。

## 12. Snapshot builder 设计

建议拆分:

```ts
function buildMainSnapshot(state: HappyPathSessionState): MainPageSnapshot;
function buildAuditSnapshot(state: HappyPathSessionState): AuditPageSnapshot;
function buildAuditRecords(state: HappyPathSessionState): AuditRecord[];
```

### 12.1 Main snapshot builder

输入:

- `HappyPathSessionState`
- `now()`

输出:

- contract-shaped `MainPageSnapshot`

实现策略:

1. 从 seed fixture 深拷贝。
2. 统一 session/project/workflow ids。
3. 统一 generatedAt/cursor。
4. 按 step 校正 status dimensions 相关字段。
5. 在完成态启用 result/fileChange/audit summary。

### 12.2 Audit snapshot builder

完成态前:

- Audit snapshot 可返回 empty / not_available。
- `records = []`
- overview verdict `not_available`

完成态后:

- `records` 至少包含:
  - confirmation resolved record
  - action/task execution record
  - file change summary record
  - warning verdict record
- selected record 默认使用 file change / warning record。
- evidence detail 不暴露 raw payload。

### 12.3 数据一致性

所有 builder 必须共享:

- `sessionId`
- `taskNodeId`
- `confirmationId`
- `resultId`
- `auditRecordId`
- `evidenceId`

不要在 Main 和 Audit 各自硬编码一套不相关 id。

## 13. P6.9 API 单元测试

建议测试:

1. `listSessions` returns the happy path session.
2. `getSessionSnapshot` returns empty snapshot initially.
3. `generateTaskTree` returns accepted and next snapshot has draft TaskTree.
4. `publishTaskTree` returns accepted and next snapshot has pending confirmation.
5. `resolveConfirmation` returns accepted and next snapshot has completed result/file changes.
6. `getAuditSnapshot` before completion is not available or empty.
7. `getAuditSnapshot` after completion has warning verdict and records.
8. `listAuditRecords` returns same records as snapshot.
9. `getAuditRecordDetail` returns detail for existing record.
10. `getEvidenceDetail` returns evidence detail for existing evidence.
11. Unknown session/record/evidence returns structured `not_found`.
12. Invalid command order returns structured `command_rejected`.

## 14. P6.10 Main Page happy path integration test

测试不再切换 state picker。

建议流程:

```ts
const api = createHappyPathMockPlatoApi();
const adapter = createHttpMainPageAdapter({
  api,
  sessionId: "session-happy-path",
  showStatePicker: false,
});

render(<MainPage adapter={adapter} />);
```

断言路径:

1. 初始加载:
   - 不显示 StatePicker。
   - 显示 empty TaskTree / goal input。
2. 输入目标并发送:
   - MainPage 调用 `generateTaskTree`。
   - command accepted 后 refetch。
   - 页面显示 draft TaskTree。
3. 发布 TaskTree:
   - 调用 `publishTaskTree`。
   - 页面显示 waiting confirmation。
4. 确认:
   - 调用 `resolveConfirmation`。
   - 页面显示 result/file changes/audit entry。
5. 直接查询 mock Audit API:
   - `getAuditSnapshot({ sessionId })` 返回完成态 Audit records。

如果 UI 文案短期不稳定，测试优先断言稳定结构:

- role/button names
- TaskTree title
- confirmation panel action
- file names
- audit link text

## 15. P6.11 Audit API happy path test

第一版不要求 Audit UI。

API-only 测试:

1. 通过 Main command path 推进到 `completed_with_result`。
2. 调用 `getAuditSnapshot`。
3. 调用 `listAuditRecords`。
4. 选择第一条 warning/file record 调 `getAuditRecordDetail`。
5. 选择 evidence ref 调 `getEvidenceDetail`。
6. 验证:
   - verdict 是 `warning`。
   - evidence visibility 不是 raw payload。
   - record 与 session/task/file change refs 对齐。

## 16. 切换入口策略

P6.9-P6.11 不改生产入口。

后续如果需要让本地页面可通过 mock 真正动起来，有两个安全入口:

### 16.1 test-only harness

只在测试里显式创建:

```ts
createHttpMainPageAdapter({ api: createHappyPathMockPlatoApi() })
```

这是 P6.9-P6.11 的默认策略。

### 16.2 dev-only runtime flag

后续可在 `frontend/src/app/platoRuntime.ts` 增加:

```ts
PLATO_RUNTIME=happy-path-mock
```

或 Vite env:

```text
VITE_PLATO_API_MODE=happy-path-mock
```

但必须满足:

- 默认仍是现有 runtime。
- mock mode 不进入生产 build 默认路径。
- docs 明确标记为 dev/test-only。

## 17. 实施阶段

### P6.9 Frontend API Mock Foundation

交付:

- `happyPathPlatoApi.ts`
- API unit tests
- 明确 unsupported/error behavior

验收:

- mock 实现 Main/Audit happy path 需要的 `PlatoApi` 方法。
- 所有状态转移通过 query 观察。
- 不改 UI。

### P6.10 Main Page API Mock Happy Path Test

交付:

- MainPage integration test。
- 使用 `createHttpMainPageAdapter({ api: mockApi })`。
- 不使用 fixture StatePicker。

验收:

- 测试从 empty 走到 completed/file changes。
- command accepted 与 final facts 分离。

### P6.11 Audit API Linkage Test

交付:

- API-only Audit happy path test。

验收:

- Audit data 来自同一 session。
- record/detail/evidence 可查询。
- hidden/raw payload 规则不被破坏。

### P6.12 Dev Mock Runtime Entry

可选。

交付:

- dev-only feature flag。
- 本地手动可跑 API mock path。

验收:

- 默认生产入口不变。
- 可手动启用 mock interactive runtime。

## 18. 工作量估算

| 阶段 | 工作量 | 说明 |
|---|---:|---|
| P6.9 | 0.5-1 天 | 状态机、snapshot builders、API tests。 |
| P6.10 | 0.5-1 天 | MainPage integration test 可能需要处理异步 refetch。 |
| P6.11 | 0.5 天 | Audit API-only 联动。 |
| P6.12 | 0.25-0.5 天 | 仅当需要本地手动体验 mock runtime。 |

总计: 2-3 天。

## 19. 风险与控制

| 风险 | 控制 |
|---|---|
| Mock 膨胀成第二后端 | 只实现一条 happy path，其他路径 structured reject。 |
| 与静态 fixture 重复 | 测试必须通过 API command 推进，不允许切 state id。 |
| Snapshot seed 造成隐藏耦合 | builder 统一覆盖 id/status/cursor/audit refs，并加 contract tests。 |
| Event 增加不稳定 | 第一版不依赖 timers，默认 eventMode none。 |
| Audit 仍与 Main 断裂 | Audit records 从同一个 `HappyPathSessionState` 派生。 |
| UI 文案变化导致测试脆弱 | Integration test 优先断言稳定 role、结构和关键数据。 |

## 20. 下一步推荐任务

```text
Use the product-workflow-gate skill first.

Task:
Implement P6.9 Frontend API Mock Foundation.

Context:
docs/plans/feature/frontend-api-mock-happy-path.md and
docs/plans/feature/frontend-api-mock-happy-path-technical-design.zh-CN.md define
the API mock plan. Build one in-memory PlatoApi mock for a single Main/Audit
happy path session.

Do not change MainPage UI.
Do not wire the mock into production runtime.
Do not add more static scenario tests.

Required work:
1. Create happyPathPlatoApi.ts.
2. Implement single-session Main/Audit happy path state transitions.
3. Add focused API tests for query/command/error behavior.
4. Keep unsupported paths explicit.

Output:
- files changed
- API methods implemented
- tests run
- remaining gaps
```
