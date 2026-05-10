# Confirmation Actions

> Status: planned  
> Last Updated: 2026-05-10  
> 关联接口：`ui-api-interfaces.md`

---

## 1. 目标

定义用户确认动作的 UI 行为。确认动作是 Task 执行过程中需要用户介入的决策点，必须归属于具体 Task Node。

---

## 2. 确认动作内容

每个确认动作至少展示：

- 所属 Task
- 请求说明
- 风险等级或原因
- 可选项
- 默认行为
- 超时行为
- 当前状态：pending / resolved / expired

---

## 3. 交互

- 用户可以从 Task Node Detail 处理确认。
- 用户可以从全局 Confirmation 区处理确认。
- 处理后结果写入 Session Message Stream。
- 已处理确认保留为 resolved history，不从界面消失。

---

## 4. API 需求

引用 `ui-api-interfaces.md`：

- `listPendingConfirmations`
- `resolveConfirmation`
- `listTaskMessages`
- `listSessionMessages`
- `subscribeSessionEvents`

第一版选项形式可以简单：

- `value: string`
- `label: string`
- `is_default: bool`

---

## 5. 验收标准

- 用户能看到所有待确认动作。
- 用户能跳回确认所属 Task。
- 用户处理确认后，Task Badge 和消息流同步更新。
- resolved confirmation 可追溯。

