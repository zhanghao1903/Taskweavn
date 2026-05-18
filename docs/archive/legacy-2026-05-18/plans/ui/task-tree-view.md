# Task Tree View

> Status: planned  
> Last Updated: 2026-05-10  
> 关联接口：`ui-api-interfaces.md`

---

## 1. 目标

定义 Task Tree List / Topology 的展示规则。Task Tree 是用户理解系统当前计划和执行状态的主界面。

---

## 2. 展示对象

Task Tree View 展示一个 Session 下的多个 root Task Tree：

```text
Session
├─ Root Task A
│  ├─ A.1
│  └─ A.2
└─ Root Task B
   └─ B.1
```

当前版本只支持 Tree List，不支持 DAG。

---

## 3. 节点信息

每个 Task Node 最少展示：

- 标题 / intent 摘要
- 状态：pending / running / done / failed
- 待确认 badge
- 未读消息 badge
- 文件变更 badge
- 子任务数量

---

## 4. 交互

- 点击节点：选中并打开 Task Node Detail。
- 展开/折叠：控制子树可见性。
- 状态过滤：显示全部 / 待确认 / 运行中 / 已失败。
- 搜索：按标题或 intent 搜索 Task。
- 跳转：从确认动作、消息、文件变更跳回所属 Task。

---

## 5. API 需求

引用 `ui-api-interfaces.md`：

- `listTaskTrees`
- `getTaskNode`
- `listPendingConfirmations`
- `getTaskFileChanges`
- `subscribeSessionEvents`

第一版需要支持按事件增量刷新：

- `task.created`
- `task.updated`
- `task.status_changed`
- `confirmation.created`
- `confirmation.resolved`
- `file_change.recorded`

---

## 6. 验收标准

- 能展示多个 root Task Tree。
- 节点状态变化后，UI 能实时更新。
- 待确认 Task 有明显标记。
- 点击节点后，详情区展示同一个 Task。

