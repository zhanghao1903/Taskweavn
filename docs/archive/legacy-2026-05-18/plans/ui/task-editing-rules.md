# Task Editing Rules

> Status: planned  
> Last Updated: 2026-05-10  
> 关联接口：`ui-api-interfaces.md`

---

## 1. 目标

定义不同 Task 状态下用户可以做什么。该文档保护 Task 历史不可变，同时允许计划态灵活编辑。

---

## 2. 权限矩阵

| 状态 | 可编辑 intent | 可编辑结构 | 可追加消息 | 可处理确认 | 可取消 | 可 retry |
|---|---|---|---|---|---|---|
| pending | 是 | 是 | 是 | 不适用 | 是 | 否 |
| running | 否 | 否 | 是 | 是 | 待定 | 否 |
| done | 否 | 否 | 否 | 否 | 否 | 可创建 follow-up |
| failed | 否 | 否 | 否 | 否 | 否 | 是 |

---

## 3. 核心规则

- pending Task 是计划，可编辑。
- running Task 是执行事实，不直接改字段，只追加信息。
- done Task 是历史，只读。
- failed Task 不原地修复，通过 retry/fix Task 表达。

---

## 4. API 需求

引用 `ui-api-interfaces.md`：

- `updateTaskNode`
- `appendTaskMessage`
- `cancelTask`
- `retryTask`
- `getTaskNode`

接口层必须拒绝非法状态修改，不能只靠前端隐藏按钮。

---

## 5. 验收标准

- pending Task 可以被编辑。
- done Task 的编辑入口不可用。
- running Task 的用户输入进入消息流，而不是直接覆盖 intent。
- failed Task 可以创建 retry/fix Task。

