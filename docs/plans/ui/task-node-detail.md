# Task Node Detail

> Status: planned  
> Last Updated: 2026-05-10  
> 关联接口：`ui-api-interfaces.md`

---

## 1. 目标

定义选中 Task Node 后的详情面板。Task Node Detail 是用户查看、补充、确认和追踪单个任务的主区域。

---

## 2. 信息结构

建议分区：

- Task 摘要：标题、intent、状态、父节点、子节点
- 约束：用户补充的偏好、非目标、限制
- 当前权限：可编辑 / 可追加信息 / 只读
- 确认动作：当前 pending 和历史 resolved
- 消息视图：该 Task 相关消息
- 文件变更：直接变更 + 可选递归汇总
- 总结：结果、失败原因、后续建议

---

## 3. 状态与权限

| 状态 | Detail 行为 |
|---|---|
| pending | 可编辑 intent、约束、结构、状态 |
| running | 可追加信息和处理确认，不直接改历史字段 |
| done | 只读查看结果、消息、文件变更 |
| failed | 只读查看失败，可创建 retry/fix Task |

---

## 4. API 需求

引用 `ui-api-interfaces.md`：

- `getTaskNode`
- `updateTaskNode`
- `appendTaskMessage`
- `listTaskMessages`
- `listPendingConfirmations`
- `getTaskFileChanges`
- `getTaskSummary`
- `retryTask`

第一版可简化为单面板，但必须明确区分：

- 直接归属于该 Task 的信息
- 从子任务递归汇总的信息

---

## 5. 验收标准

- 选中 Task 后可以看到完整详情。
- pending Task 可编辑；done Task 只读。
- running Task 可以追加信息。
- 文件变更能区分直接变更和子任务汇总。

