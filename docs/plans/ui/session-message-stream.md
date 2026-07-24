# Session Message Stream

> Status: planned  
> Last Updated: 2026-05-10  
> 关联接口：`ui-api-interfaces.md`

---

## 1. 目标

定义 Session 唯一消息流。它是整个会话的时间线和消息事实源，Task Message View 只是它的过滤视图。

---

## 2. 展示内容

Session Message Stream 包含：

- 用户全局输入
- 结构化 ASK 问题、选项、草稿提交状态和终态选择
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
- `appendSessionMessage`
- `subscribeSessionEvents`

第一版数据细节可简化，但每条消息应能表达：

- 所属 Session
- 可选所属 Task
- 类型
- 内容
- 时间
- 可选关联确认动作

ASK 是例外的结构化 Conversation 项：它的领域权威仍是 RawTask / AskStore，
但会话投影必须保留稳定卡片身份、原始问题、全部选项、已选项、自由文本和终态。
同一次 ASK 的回答不得追加第二张 Answer 会话卡片；回答动作继续进入 Activity /
Audit。

---

## 5. 验收标准

- 所有 Task 相关消息都能在 Session 流中回放。
- 选中 Task 后，能从同一消息源过滤出 Task 视图。
- 新消息到达时，Session 流实时更新。
- Authoring ASK 与 Execution ASK 都能在原时间线位置完成回答并回放终态。
- ASK 回答不会产生重复的独立 Answer 卡片。
