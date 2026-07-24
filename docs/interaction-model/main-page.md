# Main Page Interaction Model

> Status: active baseline
>
> Last Updated: 2026-05-21
>
> Page: Plato Main Page
>
> Scope: Plato 1.0 用户控制面。记录 Main Page 上允许发生的用户交互、UI 状态变化和后端调用。
>
> Related UI specs: `docs/ux/ask-ui-spec.md`,
> `docs/ux/confirmation-ui-spec.md`.

## 1. Source of Truth

| Source | Role |
|---|---|
| [Plato Main Page UX Flow](../product/plato-main-page-ux-flow.md) | 页面对象、主路径、9 个状态画面、Detail Panel 动态语义。 |
| [Plato UI API Contract](../product/plato-ui-api-contract.md) | Query / Command / Event contract。 |
| [Main Page Frontend Runtime Integration Plan](../plans/feature/main-page-frontend-runtime-integration.md) | 当前从静态原型走向真实 sidecar runtime 的实现计划。 |
| [External Calls Registry](external-calls.md) | 本页可以触发的所有外部调用索引。 |

## 2. Page Mental Model

Main Page 面向用户展示的层级是：

```text
Project
  -> Workflow
      -> Session
          -> TaskTree / TaskNode
```

第一版写入边界以 `Session` 为主。`Task Message View` 不是第二条消息流，而是 `Session Message Stream` 按 Task 引用过滤后的投影。

## 3. Component Inventory

| Component | Responsibility | Local UI State | Backend Facts |
|---|---|---|---|
| Page Runtime | 装载 snapshot、连接事件流、处理 pending command。 | current session id, loading/error, pending commands | `MainPageSnapshot`, `UiEvent` |
| Top Bar | 展示产品、Project / Workflow / Session 状态、全局入口。 | none or menu open state | snapshot metadata |
| Workflow + Sessions Sidebar | 展示 Workflow 层级和该 Workflow 下 Sessions。 | selected workflow/session, collapsed group | project/workflow/session summaries |
| TaskTree Panel | 展示 TaskTree list 和 TaskNode 状态。 | selected task node, expanded/collapsed nodes | task tree, node status, permissions |
| Session Message Stream | 展示会话过程消息和确认入口摘要。 | selected message, filters | session messages, confirmations |
| Detail Panel | 当前焦点对象的 Context Inspector。 | active detail mode | workflow/session/task/result/file-change/confirmation facts |
| Context Input | 会话级或 Task 级自然语言输入。 | draft text, focused scope, submitting | session/task command responses |
| Event Handler | 后台接收后端事实变化。 | event cursor, reconnect state | SSE `UiEvent` |

## 4. Page Runtime

| ID | Status | User action / trigger | Availability | UI change | Backend / external call | Event / refresh | Notes |
|---|---|---|---|---|---|---|---|
| `MP-RUN-001` | `target` | 打开 Main Page。 | 有默认或 URL 指定 `sessionId`。 | 显示 loading skeleton；清空上一会话局部选择态。 | `EXT-Q-004` `GET /sessions/{sessionId}/snapshot`。 | 成功后用 snapshot 渲染页面，并以返回 cursor 连接事件流。 | Query key 必须以 `sessionId` 为主。 |
| `MP-RUN-002` | `target` | Snapshot 加载成功。 | `QueryResponse.ok=true`。 | 渲染 Project / Workflow / Session / TaskTree / Messages / Detail Panel。 | 无新增调用。 | 启动 `EXT-E-001`。 | Snapshot 是首屏事实源。 |
| `MP-RUN-003` | `target` | Snapshot 加载失败。 | `QueryResponse.ok=false` 或网络失败。 | 展示错误状态和重试入口；不展示过期 synthetic 成功状态。 | 重试时再次调用 `EXT-Q-004`。 | 成功后恢复。 | 错误文本来自 `ApiError`。 |
| `MP-RUN-004` | `target` | 连接 session event stream。 | Snapshot 带 cursor，HTTP runtime 开启。 | 页面不闪烁；显示轻量 realtime connected/pending 状态可选。 | `EXT-E-001` `GET /sessions/{sessionId}/events?cursor=...`。 | 收到事件后按第 11 节处理。 | SSE 断线时可自动重连或降级为手动刷新。 |
| `MP-RUN-005` | `target` | 用户切换 Session 或 URL `sessionId` 变化。 | 目标 session 存在。 | 重置 selected task、detail mode、input draft、pending command；进入新 session loading。 | `EXT-Q-004`。 | 重新连接 `EXT-E-001`。 | 不跨 Session 保留局部状态。 |

## 5. Top Bar

| ID | Status | User action / trigger | Availability | UI change | Backend / external call | Event / refresh | Notes |
|---|---|---|---|---|---|---|---|
| `MP-TOP-001` | `current` | 查看当前 Project / Workflow / Session 信息。 | Snapshot 已加载。 | 只读展示，不触发写入。 | 无。 | Snapshot 更新后刷新。 | 顶部只表达当前位置，不承担复杂编辑。 |
| `MP-TOP-002` | `planned` | 点击“查看审计”。 | Audit Page 已实现。 | 跳转 Audit Page；当前 session 上下文随 route 传递。 | `EXT-N-001`。 | Audit Page 自行加载审计数据。 | Audit 是信任页面，不是主控制面。 |
| `MP-TOP-003` | `disabled` | 点击“查看审计”。 | Audit Page 未实现。 | 按钮禁用或显示“暂未开放”。 | 无。 | 无。 | 禁止跳到空页面。 |
| `MP-TOP-004` | `planned` | 点击“设置”。 | Settings Page 已实现。 | 打开设置页或设置面板。 | `EXT-N-002`。 | 设置变更另有配置 contract。 | 当前 Main Page 不直接热更新配置。 |
| `MP-TOP-005` | `disabled` | 点击“设置”。 | Settings Page 未实现。 | 按钮禁用或显示“暂未开放”。 | 无。 | 无。 | 避免误导用户。 |

## 6. Workflow + Sessions Sidebar

| ID | Status | User action / trigger | Availability | UI change | Backend / external call | Event / refresh | Notes |
|---|---|---|---|---|---|---|---|
| `MP-SIDE-001` | `target` | 查看 Workflow 列表。 | Project 已加载。 | 左侧按 Workflow 分组展示。 | 可由 snapshot 承载；必要时 `EXT-Q-002`。 | Project / workflow 刷新后更新。 | Workflow 是 Session 模式，不是执行对象。 |
| `MP-SIDE-002` | `target` | 选择 Workflow。 | Workflow 存在。 | 展开该 Workflow 下 Sessions；可更新空状态说明。 | 必要时 `EXT-Q-003`。 | Session 列表刷新。 | 不自动创建 Session。 |
| `MP-SIDE-003` | `target` | 选择 Session。 | Session 存在且可访问。 | Main Page 切换到该 Session，清理局部选择态。 | `EXT-Q-004`；重建 `EXT-E-001`。 | 新 session events 驱动刷新。 | Session 是第一版通信边界。 |
| `MP-SIDE-004` | `planned` | 点击“新建 Session”。 | Workflow 已选中。 | 新建按钮进入 pending；成功后选中新 Session。 | `EXT-C-001`。 | `session.status_changed` 或 command result 后加载 snapshot。 | 如果后端尚未支持，应禁用。 |
| `MP-SIDE-005` | `disabled` | 删除 / 归档 Session。 | MVP Main Page。 | 不显示或禁用入口。 | 无。 | 无。 | 归档属于后续页面或设置能力。 |

## 7. TaskTree Panel

| ID | Status | User action / trigger | Availability | UI change | Backend / external call | Event / refresh | Notes |
|---|---|---|---|---|---|---|---|
| `MP-TREE-001` | `current` | 点击 TaskNode 卡片。 | TaskTree 已加载。 | 选中该节点；Detail Panel 切换为 TaskNode detail；Context Input 作用域变为该 Task。 | 可直接使用 snapshot；必要时 `EXT-Q-007`。 | `task.node.changed` 后刷新详情。 | TaskNode 是最小交互锚点。 |
| `MP-TREE-002` | `target` | 展开 / 收起父 TaskNode。 | 节点有子节点。 | 本地展开态变化。 | 无。 | Snapshot 不覆盖用户当前展开偏好，除非 session 切换。 | 纯 UI local state。 |
| `MP-TREE-003` | `current` | 点击“发布任务 / 开始执行”。 | TaskTree 为 draft/reviewing，用户有 publish 权限。 | 按钮进入 pending；禁止重复点击。 | `EXT-C-006`。 | `task.tree.changed` / `session.status_changed` / `command.failed`。 | Command accepted 不是最终事实。 |
| `MP-TREE-004` | `target` | 点击未开始 TaskNode 的编辑入口。 | 节点状态为 draft/queued，且有 edit 权限。 | Detail Panel 进入 task edit mode。 | 暂不调用；保存时 `EXT-C-004`。 | 保存后等事件或 refetch。 | 编辑入口不等于立即写入。 |
| `MP-TREE-005` | `target` | 点击已完成 TaskNode。 | 节点状态 completed。 | Detail Panel 只读展示 summary、result、file changes。 | 可按需 `EXT-Q-009`。 | `file_changes.updated` 后刷新。 | 已完成节点默认不可修改。 |
| `MP-TREE-006` | `target` | 点击运行中 TaskNode。 | 节点状态 running/executing。 | Detail Panel 展示过程信息；Context Input 切到追加指导。 | 无立即调用。 | 用户提交指导时 `EXT-C-005`。 | 运行中不做结构化 patch。 |
| `MP-TREE-007` | `planned` | 取消 TaskNode。 | 节点未完成，且有 cancel 权限。 | 显示二次确认或 pending。 | `EXT-C-008`。 | `task.node.changed` / `command.failed`。 | MVP 可不暴露。 |
| `MP-TREE-008` | `planned` | 重试失败 TaskNode。 | 节点 failed，且有 retry 权限。 | 节点进入 retry pending。 | `EXT-C-009`。 | `task.node.changed` / `command.failed`。 | MVP 可不暴露。 |

## 8. Session Message Stream

| ID | Status | User action / trigger | Availability | UI change | Backend / external call | Event / refresh | Notes |
|---|---|---|---|---|---|---|---|
| `MP-MSG-001` | `current` | 查看会话消息。 | Snapshot 已加载。 | 按 `createdAt ASC` 展示消息。 | Snapshot 或 `EXT-Q-005`。 | `message.appended` 后 refetch messages/snapshot。 | 后端消息流只有一条。 |
| `MP-MSG-002` | `target` | 点击消息卡。 | 消息有 task refs 或 confirmation refs。 | 选中消息；Detail Panel 定位相关 Task 或 Confirmation。 | 必要时 `EXT-Q-007` / `EXT-Q-008`。 | 相关事件后刷新。 | 消息是过程入口，不是主对象。 |
| `MP-MSG-003` | `target` | 点击 confirmation 消息中的操作入口。 | Confirmation pending。 | Detail Panel 切到确认卡；操作按钮可用。 | 无立即调用。 | 用户选择后 `EXT-C-007`。 | 确认动作必须挂具体 TaskNode。 |
| `MP-MSG-004` | `target` | 过滤到当前 Task 的消息。 | 已选中 TaskNode。 | 展示 Session Message Stream 的 task scoped projection。 | 可用 `EXT-Q-005?taskNodeId=...` 或本地过滤 snapshot。 | `message.appended` 后刷新。 | 不创建第二条 Task Message Stream。 |
| `MP-MSG-005` | `disabled` | 用户直接编辑历史消息。 | 所有状态。 | 不显示编辑入口。 | 无。 | 无。 | 历史消息是可追溯事实。 |
| `MP-MSG-006` | `target` | Authoring 或 Execution ASK 出现。 | Snapshot 投影包含结构化 ASK card。 | 在 Conversation 原时间位置展示问题、选项和回答控件。 | 无立即调用。 | ASK/RawTask 事件或 snapshot refetch。 | Conversation 是唯一主要 ASK 回答面。 |
| `MP-MSG-007` | `target` | 用户回答/延后/取消 ASK。 | ASK pending 且命令允许。 | 原卡片进入 pending，随后原位显示终态选择；不新增 Answer 卡片。 | Authoring batch 或 Execution ASK command。 | `ask.answered` / task/plan refresh。 | Activity/Audit 保留动作证据。 |

## 9. Detail Panel

| ID | Status | User action / trigger | Availability | UI change | Backend / external call | Event / refresh | Notes |
|---|---|---|---|---|---|---|---|
| `MP-DETAIL-001` | `target` | 会话开始前没有选中 Task。 | Empty / New Session。 | 展示 Workflow 信息、输入方式、交付物和默认策略。 | 无或 snapshot。 | Workflow 更新后刷新。 | Detail Panel 是 Context Inspector。 |
| `MP-DETAIL-002` | `target` | Session 正在理解或规划。 | Session status understanding/planning。 | 展示目标、系统当前动作、可补充说明。 | 无立即调用。 | `session.status_changed` / `task.tree.changed`。 | 输入提交走 Context Input。 |
| `MP-DETAIL-003` | `current` | 选中 TaskNode。 | `selectedTaskNodeId != null`。 | 展示 TaskNode 描述、状态、可操作项、相关文件/消息摘要。 | Snapshot 或 `EXT-Q-007`。 | `task.node.changed`。 | 操作受 permissions/status 控制。 |
| `MP-DETAIL-004` | `target` | 点击“编辑任务”。 | TaskNode draft/queued，且有 edit 权限。 | 显示结构化编辑控件。 | 保存时 `EXT-C-004`。 | `task.node.changed` / `task.tree.changed`。 | 自然语言补充走 `EXT-C-005`。 |
| `MP-DETAIL-005` | `target` | 点击“结果”。 | Session 或 Task 有 result。 | Detail Panel 展示 result card。 | Snapshot 或 `EXT-Q-010`。 | `result.updated`。 | Result 是信息流回答的结构化展示入口。 |
| `MP-DETAIL-006` | `target` | 点击“文件变更”。 | Task 有 file changes。 | 展示 File Change Summary。 | `EXT-Q-009` 或 snapshot。 | `file_changes.updated`。 | 父节点必须汇总所有子节点变更。 |
| `MP-DETAIL-007` | `disabled` | 修改已完成 TaskNode。 | completed。 | 编辑控件不可用；显示只读说明。 | 无。 | 无。 | 防止完成事实被静默改写。 |
| `MP-DETAIL-008` | `target` | 选中等待 ASK 的 TaskNode。 | Execution ASK pending。 | 展示任务上下文、等待状态和“定位到会话问题”；不重复 ASK 表单。 | 无。 | ASK/task 事件后刷新。 | 主操作位于 Conversation。 |

## 10. Confirmation Actions

Product 1.0 uses the selected TaskNode Detail Panel as the primary
confirmation operation surface. TaskTree badges and MessageStream confirmation
entries are navigation/history signals only; they should focus the owning
TaskNode and render `ConfirmationDetailPanel`, not duplicate the full
confirmation form.

| ID | Status | User action / trigger | Availability | UI change | Backend / external call | Event / refresh | Notes |
|---|---|---|---|---|---|---|---|
| `MP-CONF-001` | `target` | 点击“确认 / 执行 / Yes”。 | Confirmation pending。 | 按钮进入 pending；同一 confirmation 其他按钮禁用。 | `EXT-C-007`，payload 包含 selected option。 | `confirmation.resolved` / `task.node.changed` / `command.failed`。 | 不在前端直接把任务改成完成。 |
| `MP-CONF-002` | `target` | 点击“修改任务”。 | Confirmation pending，且支持 revise。 | Detail Panel 切到任务补充或编辑模式。 | 进入模式无调用；提交时 `EXT-C-004` 或 `EXT-C-005`。 | 修改后等待事件刷新。 | 用户补充应可追溯。 |
| `MP-CONF-003` | `target` | 点击“跳过 / No”。 | Confirmation pending，且支持 skip/reject。 | 按钮进入 pending；显示安全确认状态。 | `EXT-C-007`。 | `confirmation.resolved` / `task.node.changed` / `command.failed`。 | Rejection 不等于删除消息。 |
| `MP-CONF-004` | `disabled` | 对已 resolved confirmation 再次点击。 | Confirmation resolved。 | 操作按钮不可用；展示已处理结果。 | 无。 | 无。 | 防止重复提交。 |

## 11. Context Input

| ID | Status | User action / trigger | Availability | UI change | Backend / external call | Event / refresh | Notes |
|---|---|---|---|---|---|---|---|
| `MP-INPUT-001` | `current` | 在空会话输入目标并发送。 | Session 无 TaskTree 或处于 new/empty。 | 输入框清空；页面进入 understanding/planning pending。 | `EXT-C-003`。 | `task.tree.changed` / `session.status_changed` / `command.failed`。 | 这是自然语言到 Draft TaskTree 的主入口。 |
| `MP-INPUT-002` | `current` | 在会话作用域输入补充说明。 | 没有选中 TaskNode，Session 可接收输入。 | 输入框清空；消息流等待后端事实刷新。 | `EXT-C-002`。 | `message.appended` / `session.status_changed`。 | 不直接生成本地事实消息。 |
| `MP-INPUT-003` | `current` | 选中 TaskNode 后输入补充说明。 | TaskNode 未完成或可追加指导。 | 输入框清空；作用域显示当前 TaskNode；消息流等待后端事实刷新。 | `EXT-C-005`。 | `message.appended` / `task.node.changed`。 | 这是 Task-scoped workflow。 |
| `MP-INPUT-004` | `target` | 回答系统澄清问题。 | 当前有 clarification / actionable message。 | 输入框清空；问题进入 pending。 | 可走 `EXT-C-002` 或 `EXT-C-007`，取决于后端是否建模为 confirmation。 | `message.appended` / `confirmation.resolved`。 | 必须在消息中保留可追溯记录。 |
| `MP-INPUT-005` | `current` | 空输入点击发送。 | draft 为空或全空白。 | 发送按钮禁用；不显示错误。 | 无。 | 无。 | 防止无意义 command。 |
| `MP-INPUT-006` | `target` | Command 正在 pending 时继续输入。 | 允许并发输入或策略允许排队。 | 可继续编辑；发送按钮按策略禁用或允许排队。 | 如允许提交，走对应 Command。 | command events 后收敛。 | 策略必须由 snapshot permissions 表达。 |

## 12. Event Handling

| ID | Status | Trigger | UI change | Backend / external call | Notes |
|---|---|---|---|---|---|
| `MP-EVT-001` | `current` | `message.appended`。 | 不直接伪造完整消息卡；显示短 pending 可选。 | `EXT-Q-004` 或 `EXT-Q-005`。 | 事件 payload 是轻量字段。 |
| `MP-EVT-002` | `current` | `task.tree.changed`。 | TaskTree 区域保持布局，更新节点事实。 | `EXT-Q-004` 或 `EXT-Q-006`。 | 保留 selected task，除非节点不存在。 |
| `MP-EVT-003` | `current` | `task.node.changed`。 | 更新选中节点、卡片状态和 Detail Panel。 | `EXT-Q-004` 或 `EXT-Q-007`。 | 若影响父节点 file summary，等待 `file_changes.updated` 或 snapshot。 |
| `MP-EVT-004` | `current` | `confirmation.created`。 | Detail Panel / message stream 出现待确认入口。 | `EXT-Q-004` 或 `EXT-Q-008`。 | 不抢焦点，除非它阻塞当前任务。 |
| `MP-EVT-005` | `current` | `confirmation.resolved`。 | 清除 pending，按钮转为 resolved，只读展示结果。 | `EXT-Q-004`。 | 同时可能刷新 task status。 |
| `MP-EVT-006` | `current` | `result.updated`。 | Result 入口变为可用或更新内容。 | `EXT-Q-010` 或 `EXT-Q-004`。 | 如果 Detail Panel 正在 result mode，需要刷新。 |
| `MP-EVT-007` | `current` | `file_changes.updated`。 | File Change Summary badge/内容更新。 | `EXT-Q-009` 或 `EXT-Q-004`。 | 父节点汇总语义由后端保证。 |
| `MP-EVT-008` | `current` | `session.resync_required` 或未知事件。 | 保留基础 layout，显示轻量同步状态。 | `EXT-Q-004`。 | 默认 fail-safe：refetch snapshot。 |
| `MP-EVT-009` | `current` | `command.failed`。 | 清除 pending；展示错误；不提交本地成功状态。 | 按 refresh hint 查询。 | 错误来源必须可见但不打断整个页面。 |

## 13. Disabled / Not Allowed Interactions

| ID | Interaction | Reason | Required UI Behavior |
|---|---|---|---|
| `MP-NO-001` | HTTP runtime 下显示 fixture `StatePicker` 给普通用户。 | StatePicker 是开发/演示兼容层。 | 默认隐藏；仅 dev flag 开启。 |
| `MP-NO-002` | 前端根据 `message.appended.payload` 自造完整消息卡。 | 后端不承诺事件 payload 含完整 title/body。 | 事件触发 refetch 或 patch 已存在字段。 |
| `MP-NO-003` | 直接修改已完成 TaskNode。 | 完成状态是事实记录。 | 只读；需要未来显式 retry/reopen contract。 |
| `MP-NO-004` | 直接调用 LLM provider。 | 前端不拥有 provider 安全和审计边界。 | 必须通过后端 gateway。 |
| `MP-NO-005` | 直接读取 workspace 文件。 | Session Workspace 是后端执行边界。 | 通过 file change / result / future file preview API。 |
| `MP-NO-006` | 对同一 confirmation 重复提交响应。 | 会破坏确认动作幂等性。 | pending/resolved 时禁用重复按钮。 |

## 14. Maintenance Checklist

- [ ] 新增 Main Page 按钮前，新增或更新本文件交互条目。
- [ ] 新增 API 调用前，登记到 [external-calls.md](external-calls.md)。
- [ ] 页面实现从 fixture 转为 HTTP runtime 后，更新 `Status` 列。
- [ ] 事件 payload contract 改变后，同步更新第 12 节。
- [ ] TaskNode 状态机或 permissions 改变后，同步更新 TaskTree、Detail Panel、Context Input 三处。
- [ ] 新增 Audit / Settings 独立页面时，为对应 Page 新建交互模型文档。
