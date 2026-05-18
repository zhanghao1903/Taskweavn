# File Change Summary

> Status: planned  
> Last Updated: 2026-05-10  
> 关联接口：`ui-api-interfaces.md`

---

## 1. 目标

定义按 Task 聚合文件变更的 UI。TaskWeavn 不让用户从文件树反推任务，而是从 Task 进入文件证据。

---

## 2. 归属规则

- 文件修改的直接归属是产生修改的 Task。
- 父 Task 显示递归汇总：自身修改 + 所有子孙 Task 修改。
- 递归汇总是视图层聚合，不改变直接归属。
- 已完成父节点的文件汇总应可展开到具体子节点。

---

## 3. 展示结构

Task 文件区建议展示：

- 直接变更
- 子任务汇总变更
- 文件路径
- 操作类型：created / modified / deleted
- 简短摘要
- 可选 diff 入口

---

## 4. API 需求

引用 `ui-api-interfaces.md`：

- `getTaskFileChanges(session_id, task_id, recursive=false)`
- `getTaskFileChanges(session_id, task_id, recursive=true)`
- `subscribeSessionEvents`

第一版字段可简化，但必须保留：

- direct owner task
- path
- change type
- summary

---

## 5. 验收标准

- 子 Task 文件变更能在子节点详情中看到。
- 父 Task 能看到所有子孙 Task 的递归汇总。
- 父节点汇总能展开定位到具体子 Task。
- 已完成 Task 的文件变更只读。

