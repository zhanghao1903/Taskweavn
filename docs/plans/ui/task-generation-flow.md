# Task Generation Flow

> Status: planned  
> Last Updated: 2026-05-10  
> 关联接口：`ui-api-interfaces.md`

---

## 1. 目标

定义“自然语言 → Task Tree List”的入口流程。用户输入自然语言目标后，系统先生成可编辑的任务计划，而不是立即执行。

---

## 2. 核心交互

1. 用户在全局输入区输入目标。
2. 系统调用 `generateTaskTree(session_id, prompt)` 生成 Task Tree 草案。
3. UI 展示 Task Tree List，所有节点处于计划态。
4. 用户可以编辑、删除、添加、调整节点。
5. 用户确认后调用 `acceptTaskTree(session_id, root_task_ids)`。
6. 用户选择开始执行时调用 `startTaskExecution(session_id, task_id)`。

---

## 3. 界面要求

- 生成结果必须清楚标记为“草案 / 未执行”。
- 每个 Task Node 至少展示标题、摘要、状态和是否可编辑。
- 用户可以进入任意 Task Node 的局部会话补充要求。
- 全局输入区和 Task 局部输入区必须视觉区分。

---

## 4. API 需求

引用 `ui-api-interfaces.md`：

- `generateTaskTree`
- `acceptTaskTree`
- `updateTaskNode`
- `listTaskTrees`
- `startTaskExecution`

第一版字段细节可简化，但必须支持：

- root Task 列表
- parent-child 关系
- Task intent
- Task status
- Task constraints

---

## 5. 验收标准

- 用户输入一句自然语言后，界面能展示 Task Tree List 草案。
- 用户不确认时，系统不开始执行。
- 用户编辑节点后，Task Tree 展示立即反映变化。
- 用户确认后，Task Tree 从计划态进入可执行态。

