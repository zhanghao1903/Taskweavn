# Task Message View

> Status: planned
> Last Updated: 2026-05-11
> 关联接口：`ui-api-interfaces.md`

---

## 1. 目标

定义 Task 局部消息视图。Task Message View 不是第二套消息流，而是对 Session Message Stream 按 Task 聚合后的局部视图。

---

## 2. 核心原则

- 底层只有 Session Message Stream。
- 每条消息可以关联 `task_id`。
- 选中 Task Node 后，UI 展示该 Task 相关消息。
- 父 Task 视图可选择包含子任务消息，但默认先展示自身直接消息。

---

## 3. 消息类型

Task 视图中至少展示：

- 用户补充
- Agent 进度
- 系统状态事件
- 确认动作
- 确认结果
- 结果总结

---

## 4. 交互

- 用户在 Task 作用域输入自然语言，调用 `appendTaskMessage`。
- 处理确认动作后，resolved 结果仍留在消息视图中。
- 用户可从消息跳转到相关文件变更或确认动作。

---

## 5. API 需求

引用 `ui-api-interfaces.md`：

- `listTaskMessages`
- `getInteractionMessages`
- `listSessionMessages`
- `appendTaskMessage`
- `appendUserMessage`
- `resolveConfirmation`
- `respondToActionable`
- `subscribeSessionEvents`
- `subscribeInteractionEvents`

第一版最低要求：

- 支持按 Task 过滤消息
- 支持 Task 子树消息聚合的未来扩展
- 支持 resolved confirmation 的历史展示
- 支持 actionable message 直接渲染为确认卡，并通过 response message 记录用户选择

---

## 6. 验收标准

- 同一 Session Message Stream 中的消息能被 Task 过滤展示。
- Task 局部输入不会触发全局 Task Tree 生成。
- 确认动作处理后，结果能在 Task 视图和 Session 流中看到。
- 选中 Task 时，当前可见消息面板可以替代隐藏的 Global timeline，完成交互闭环。
