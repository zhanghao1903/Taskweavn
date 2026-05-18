# Task-scoped Chat Flow

> Status: planned  
> Last Updated: 2026-05-10  
> 关联接口：`ui-api-interfaces.md`

---

## 1. 目标

定义选中 Task Node 后的局部对话工作流。该工作流用于完善当前 Task，而不是生成新的全局 Task Tree。

---

## 2. 进入条件

用户选中一个 Task Node 后：

- 输入框进入 Task scoped 模式
- Task Detail 显示该 Task 相关上下文
- 发送消息默认调用 `appendTaskMessage`

---

## 3. 与全局输入的区别

| 模式 | 输入作用域 | 默认结果 |
|---|---|---|
| global | Session | 生成或调整 Task Tree List |
| task_scoped | 当前 Task | 追加约束、澄清、确认或局部子任务建议 |

UI 必须明确展示当前模式，避免用户误以为局部补充会改变全局计划。

---

## 4. API 需求

引用 `ui-api-interfaces.md`：

- `appendTaskMessage`
- `listTaskMessages`
- `getTaskNode`
- `updateTaskNode`

第一版可将 Agent 对局部消息的响应简化为普通消息，但需要保留未来扩展：

- 局部生成子任务建议
- 局部确认动作
- 局部约束更新

---

## 5. 验收标准

- 选中 Task 后输入框明确显示 Task scoped 状态。
- 发送消息后，该消息关联当前 Task。
- Task scoped 消息不会触发全局 Task Tree 重建。
- 用户可一键返回 global 模式。

