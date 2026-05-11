# Session Message Stream

> Status: planned
> Last Updated: 2026-05-11
> 关联接口：`ui-api-interfaces.md`

---

## 1. 目标

定义 Session 唯一消息流。它是整个会话的时间线和消息事实源，Task Message View 只是它的过滤视图。

首版 UI 中，右侧 `Global timeline` 区域先隐藏。Session Message Stream 仍然是后端事实源，但可见 UI 先只展示当前交互消息流：未选 Task 时展示 session scope，选中 Task 时展示 task scope。

---

## 2. 展示内容

Session Message Stream 包含：

- 用户全局输入
- Task 创建 / 更新 / 状态变化事件
- Agent 进度消息
- 确认动作和结果
- 文件变更摘要事件
- Task 总结消息

---

## 3. 过滤能力

UI 至少支持：

- 按 Task 过滤
- 按消息类型过滤
- 只看待确认相关消息
- 只看系统事件
- 时间范围过滤

---

## 4. API 需求

引用 `ui-api-interfaces.md`：

- `listSessionMessages`
- `getInteractionMessages`
- `appendSessionMessage`
- `appendUserMessage`
- `respondToActionable`
- `listPendingActionables`
- `subscribeSessionEvents`
- `subscribeInteractionEvents`

第一版数据细节可简化，但每条消息应能表达：

- 所属 Session
- 可选所属 Task
- 类型
- 内容
- 时间
- 可选关联确认动作

后端消息类型应使用 `informational | actionable | response`，UI 通过 `authorRole` 和 projection 字段决定展示成普通消息、确认卡或回复结果。

---

## 5. 验收标准

- 所有 Task 相关消息都能在 Session 流中回放。
- 选中 Task 后，能从同一消息源过滤出 Task 视图。
- 新消息到达时，Session 流实时更新。
- Global timeline 隐藏时，当前交互消息流仍能完成发送、确认、回复和回放闭环。
