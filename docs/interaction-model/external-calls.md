# External Calls Registry

> Status: active fact registry
>
> Last Updated: 2026-05-21
>
> Scope: UI 交互产生的所有外部调用集中登记。页面文档只能引用这里登记过的调用。

## 1. 调用边界

Plato 前端的默认通信边界是：

```text
React UI
  -> frontend API adapter
  -> UI Gateway / local sidecar
  -> backend domain / stores / bus
```

前端不直接调用：

- LLM provider；
- SQLite / 本地数据库；
- 用户 workspace 文件系统；
- TaskBus / MessageBus 内部对象；
- Python domain object。

这些能力必须由 backend gateway 暴露为 Query / Command / Event contract。

## 2. Source Documents

| Source | Usage |
|---|---|
| [Plato UI API Contract](../product/plato-ui-api-contract.md) | Query / Command / Event 的语义来源。 |
| [Main Page Frontend Runtime Integration Plan](../plans/feature/main-page-frontend-runtime-integration.md) | 当前前端集成阶段的实现约束。 |
| [UI And Backend Communication](../architecture/ui-backend-communication.md) | UI 与后端通信架构边界。 |

## 3. HTTP Query Calls

| Call ID | Method / Path | Returns | Used By | Notes |
|---|---|---|---|---|
| `EXT-Q-001` | `GET /api/v1/projects` | `ProjectSummary[]` | Main Page sidebar / future project switcher | 项目导航查询。Main Page MVP 可先由 snapshot 承载。 |
| `EXT-Q-002` | `GET /api/v1/projects/{projectId}/workflows` | `WorkflowSummary[]` | Main Page sidebar | 查询 Project 下的 Workflow。 |
| `EXT-Q-003` | `GET /api/v1/workflows/{workflowId}/sessions` | `SessionSummary[]` | Main Page sidebar | 查询 Workflow 下的 Sessions。 |
| `EXT-Q-004` | `GET /api/v1/sessions/{sessionId}/snapshot` | `MainPageSnapshot` | Main Page runtime | Main Page 初始化、resync、未知事件后的事实重载。 |
| `EXT-Q-005` | `GET /api/v1/sessions/{sessionId}/messages` | `SessionMessageView[]` | Session Message Stream | 查询会话消息，可按 `taskNodeId` 过滤形成 Task 投影。 |
| `EXT-Q-006` | `GET /api/v1/sessions/{sessionId}/task-tree` | `TaskTreeView` | TaskTree panel | 查询 TaskTree 视图。通常由 snapshot 包含。 |
| `EXT-Q-007` | `GET /api/v1/sessions/{sessionId}/tasks/{taskNodeId}` | `TaskNodeDetailView` | Detail Panel | 查询单个 TaskNode 详情。 |
| `EXT-Q-008` | `GET /api/v1/sessions/{sessionId}/confirmations/pending` | `ConfirmationActionView[]` | Detail Panel / confirmation cards | 查询待确认动作。通常由 snapshot 包含。 |
| `EXT-Q-009` | `GET /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/file-changes?recursive=true` | `FileChangeSummaryView` | File Change Summary | 父节点必须包含所有子节点文件变更汇总。 |
| `EXT-Q-010` | `GET /api/v1/sessions/{sessionId}/result` | `ResultCardView` | Result panel | 查询会话结果卡。 |

## 4. HTTP Command Calls

| Call ID | Method / Path | Payload | Used By | Notes |
|---|---|---|---|---|
| `EXT-C-001` | `POST /api/v1/sessions` | `CreateSessionPayload` | Main Page new session | 创建 Session。Workflow / Project 归属由 payload 或默认上下文提供。 |
| `EXT-C-002` | `POST /api/v1/sessions/{sessionId}/input` | `SubmitSessionInputPayload` | Context Input | 会话级自然语言输入或补充。 |
| `EXT-C-003` | `POST /api/v1/sessions/{sessionId}/task-tree/generate` | `GenerateTaskTreePayload` | Empty / New Session submit | 从自然语言目标生成 Draft TaskTree。 |
| `EXT-C-004` | `PATCH /api/v1/sessions/{sessionId}/tasks/{taskNodeId}` | `PatchTaskNodePayload` | TaskNode detail editor | 结构化修改 TaskNode。已完成节点默认不可用。 |
| `EXT-C-005` | `POST /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/input` | `SubmitTaskInputPayload` | Task-scoped input | 对选中 TaskNode 追加自然语言补充、约束或指导。 |
| `EXT-C-006` | `POST /api/v1/sessions/{sessionId}/task-tree/publish` | `PublishTaskTreePayload` | TaskTree publish action | 发布 Draft TaskTree 到任务总线。 |
| `EXT-C-007` | `POST /api/v1/sessions/{sessionId}/confirmations/{confirmationId}/respond` | `ResolveConfirmationPayload` | Confirmation card | 用户确认、修改、跳过等动作。 |
| `EXT-C-008` | `POST /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/cancel` | `CancelTaskPayload` | TaskNode controls | 取消未完成或运行中 TaskNode。MVP 可禁用。 |
| `EXT-C-009` | `POST /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/retry` | `RetryTaskPayload` | TaskNode controls | 重试失败 TaskNode。MVP 可禁用。 |

## 5. Event Calls

| Call ID | Type | Path | Used By | Notes |
|---|---|---|---|---|
| `EXT-E-001` | SSE / EventSource | `GET /api/v1/sessions/{sessionId}/events?cursor=...` | Main Page runtime | 后端到 UI 的实时事实变化通知。客户端应以 invalidation / refetch 为默认策略。 |

### 5.1 Canonical UI Events

| Event Type | Default UI Handling |
|---|---|
| `session.status_changed` | 刷新 snapshot 或 top status。 |
| `session.resync_required` | 重新查询 `EXT-Q-004`。 |
| `task.tree.changed` | 重新查询 snapshot 或 TaskTree。 |
| `task.node.changed` | 重新查询 snapshot 或 TaskNode detail。 |
| `message.appended` | 不假设 payload 是完整消息卡；重新查询 snapshot 或 messages。 |
| `confirmation.created` | 重新查询 snapshot 或 pending confirmations。 |
| `confirmation.resolved` | 清理 pending command，重新查询 snapshot。 |
| `result.updated` | 重新查询 result 或 snapshot。 |
| `file_changes.updated` | 重新查询 file changes 或 snapshot。 |
| `audit.summary_updated` | Main Page 可刷新 audit summary；完整内容属于 Audit Page。 |
| `command.completed` | 清理 pending command，按 refresh hint 更新。 |
| `command.failed` | 清理 pending command，显示错误并按 refresh hint 更新。 |

## 6. Browser / Navigation Calls

| Call ID | Type | Target | Used By | Notes |
|---|---|---|---|---|
| `EXT-N-001` | Internal route | Audit Page route, TBD | Top Bar / Result / File Change Summary | 进入审计页面。当前如果 Audit Page 未实现，入口必须禁用或显示不可用状态。 |
| `EXT-N-002` | Internal route | Settings Page route, TBD | Top Bar settings | 进入设置页面。当前如果 Settings Page 未实现，入口必须禁用或显示不可用状态。 |
| `EXT-N-003` | External link | User-provided links, TBD | Result card / docs links | 打开外部 URL 前需要在 UI 中明显标识外部跳转。 |

## 7. Disallowed Direct Calls

| Category | Rule |
|---|---|
| LLM provider | 前端不得直接调用 OpenAI、DeepSeek、OpenRouter、Anthropic 等 provider。 |
| Local DB | 前端不得直接读写 SQLite。 |
| Workspace FS | 前端不得直接读写 Session Workspace 文件。 |
| System bus internals | 前端不得直接访问 TaskBus、MessageBus、EventStream、MessageStream 内部对象。 |
| Shell / process | 前端不得直接执行 shell 或启动本地进程。 |

如果未来确实需要这些能力，必须先新增 backend gateway API，再更新本文件。

