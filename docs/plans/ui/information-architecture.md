# UI Information Architecture

> Status: planned  
> Last Updated: 2026-05-10  
> 关联接口：`ui-api-interfaces.md`

---

## 1. 目标

定义 Task-first UI 的主要区域关系。第一版只描述信息架构，不规定具体前端技术栈和像素布局。

---

## 2. 建议区域

```text
┌────────────────────────────────────────────────────┐
│ Header / Session Controls                           │
├───────────────┬────────────────────┬───────────────┤
│ Task Tree     │ Task Detail         │ Session Stream│
│ / Topology    │ + Task Message View │ / Confirmations│
├───────────────┴────────────────────┴───────────────┤
│ Global or Task-scoped Input                         │
└────────────────────────────────────────────────────┘
```

---

## 3. 区域职责

| 区域 | 职责 |
|---|---|
| Header / Session Controls | 当前 Session、运行状态、自主度、全局操作 |
| Task Tree / Topology | 主导航，展示 Task Tree List |
| Task Detail | 选中 Task 的详情、文件、总结、权限 |
| Task Message View | 从 Session Stream 过滤出的 Task 相关消息 |
| Session Stream | 全局时间线和消息事实源 |
| Confirmation Area | 当前待处理确认动作 |
| Input Area | global 或 task_scoped 输入 |

---

## 4. API 需求

引用 `ui-api-interfaces.md`：

- `getSessionOverview`
- `listTaskTrees`
- `getTaskNode`
- `listSessionMessages`
- `listPendingConfirmations`
- `subscribeSessionEvents`

布局层必须能响应实时事件，而不是只依赖手动刷新。

---

## 5. 验收标准

- 用户能一眼看到 Task Tree、当前选中 Task、全局消息。
- 选中 Task 后，详情和消息视图同步切换。
- 待确认动作不会淹没在普通消息中。
- 输入框当前作用域明确可见。

