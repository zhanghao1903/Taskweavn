# Task-first UI 交互设计总述

> Status: planned  
> Last Updated: 2026-05-10  
> 类型：新特性支持 / 产品交互设计  
> 关联架构：`docs/architecture/overview.md`、`docs/architecture/task.md`、`docs/architecture/bus.md`

---

## 1. 背景

TaskWeavn 的核心理念是 **Task-first**：系统的主要交互对象不是文件、diff、命令行输出，也不是单纯的聊天消息，而是 `Task`。

传统代码助手 UI 往往围绕这些对象组织：

- chat message
- file tree
- diff
- terminal output
- tool call

TaskWeavn 需要不同的重心：

- 用户输入自然语言，但系统首先把它转成可观察、可确认、可修改的 `Task Tree List`
- 用户确认的不是抽象的“是否继续”，而是某个 `Task Node` 下面的具体选项
- 用户补充上下文时，可以明确指向某个 `Task Node`
- 文件修改、消息流、执行总结都归属于 Task，而不是反过来让用户从文件和日志里推断 Task

这意味着 UI 不是“带工具调用的聊天框”，而是“任务拓扑 + 任务消息流 + 任务详情”的协作界面。

---

## 2. 核心交互理念

### 2.1 Task 是用户心智的主对象

用户关心的是：

- 现在系统理解了哪些任务？
- 哪些任务会被执行？
- 哪些任务需要我确认？
- 哪些任务已经完成？
- 某个任务改了哪些文件？
- 某个任务的结论和后续建议是什么？

因此 UI 的主导航应围绕 Task，而不是文件。

文件、diff、日志和工具调用都是 Task 的证据层：

```text
Task Node
  ├─ 用户意图
  ├─ 执行状态
  ├─ 消息流
  ├─ 确认动作
  ├─ 文件修改清单
  └─ 总结 / 结果 / 后续建议
```

### 2.2 Chat 是输入方式，不是唯一界面

自然语言输入仍然重要，但它承担两种不同职责：

1. **全局输入**：用户描述目标，系统生成或调整 Task Tree List
2. **Task 局部输入**：用户选中某个 Task Node 后，对这个 Task 追加约束、补充信息或改变状态

这两种输入不能混在一起，否则用户会不清楚“我刚说的话是在改变整个计划，还是只是在补充一个节点”。

### 2.3 确认动作绑定 Task Node

需要用户确认时，确认动作必须出现在对应 Task Node 的上下文中。

用户看到的不是：

```text
Agent wants to run command. yes/no?
```

而是：

```text
Task: 检查项目结构
需要确认：是否允许运行 `ls -la` 来确认文件结构？
选项：允许 / 跳过 / 只查看计划
```

确认动作必须具备：

- 所属 Task Node
- 风险说明
- 可选项
- 默认行为
- 超时行为
- 结果记录

### 2.4 运行过程是可观察的，不是黑盒

用户应该实时看到：

- 哪个 Task 正在执行
- 当前 Agent 在做什么
- 是否需要确认
- 是否被用户补充信息影响
- 是否产生了文件修改
- 是否完成并给出总结

这要求 UI 同时支持：

- 单一 Session Message Stream
- 基于 `task_id` / `task_node_id` 过滤出的 Task 消息视图
- Task 状态变化流
- 文件变更摘要

系统设计上只有一个消息总线和一个会话消息流。Task 视图不是第二套消息流，
而是对同一条 Session Message Stream 的过滤、分组和上下文化展示。

### 2.5 已完成任务是只读事实，未开始任务是可编辑计划

Task Node 根据状态有不同交互权限：

| Task 状态 | 用户能力 | 原则 |
|---|---|---|
| 未开始 | 可编辑意图、状态、约束、顺序；可取消 | 计划仍可塑 |
| 进行中 | 可追加信息、回复确认、请求暂停/跳过 | 不强行打断执行，只影响后续决策 |
| 已完成 | 只读查看结果、文件、总结、消息流 | 历史不可改，变更通过新 Task 表达 |
| 失败 | 查看失败原因；可创建 retry/fix Task | 失败不是编辑旧节点，而是派生新节点 |

---

## 3. 两种核心工作流

### 3.1 工作流 A：全局 Task Tree 生成

用户在全局输入框输入自然语言目标：

```text
帮我创建一个个人网站，包含首页、项目列表和联系方式。
```

系统输出的是一个 Task Tree List：

```text
Task Tree List
├─ T1 分析目标和文件结构
├─ T2 创建首页 HTML
├─ T3 创建样式文件
├─ T4 填充项目列表和联系方式
└─ T5 自检并总结
```

用户可以：

- 接受整个 Task List
- 编辑某个节点
- 删除某个节点
- 添加新节点
- 调整顺序或状态
- 对某个节点进入局部会话

这个工作流的目标是形成“可执行计划”。

### 3.2 工作流 B：Task Node 局部会话

用户选中某个 Task Node 后，在对话框输入补充：

```text
T3 创建样式文件
用户补充：页面风格要极简，不要大面积渐变。
```

此时会话不再输出新的全局 Task Tree，而是在该 Task Node 下新增消息流，目标是完善这个 Task 或它的子任务：

```text
Task T3 Message Stream
├─ User: 页面风格要极简，不要大面积渐变
├─ Agent: 已记录约束：极简、低装饰、不使用大面积渐变
└─ Agent: 建议拆成两个子任务：布局样式 / 响应式样式
```

这个工作流的目标是“局部澄清与约束补充”，不是重建全局计划。

---

## 4. 主要设计区域

### 4.1 全局输入区

职责：

- 接收用户自然语言目标
- 创建新的 Task Tree List
- 对当前 Session 追加全局目标

关键点：

- 默认作用域是整个 Session
- 如果用户当前选中了 Task Node，输入框应明确切换为 Task 局部模式
- UI 必须清楚展示当前输入会影响“全局计划”还是“当前 Task”

### 4.2 Task Tree List / Task Topology 区

职责：

- 展示当前 Session 中所有 Task Tree
- 展示 Task 的父子关系、状态、执行顺序
- 作为用户导航主入口

当前阶段拓扑约束：

- Task 是 Tree 的列表，不是任意 DAG
- 每个 Task 只有一个 `parent_id`
- 多个 root Task 表示同一 Session 下的多个任务树

最小显示信息：

- Task 标题 / intent 摘要
- 状态
- 是否需要用户确认
- 是否有未读消息
- 是否产生文件修改

### 4.3 Task Node Detail 区

职责：

- 展示选中 Task 的完整信息
- 汇总该 Task 的执行证据

建议分区：

- Task 摘要
- 当前状态与权限
- 用户补充约束
- 确认动作
- 消息流
- 文件修改清单
- 执行总结
- 子任务列表

### 4.4 Task Message View 区

职责：

- 展示某个 Task 下的相关消息
- 支持用户追加自然语言信息
- 支持 Agent 对该 Task 的澄清、建议、进度通知

关键原则：

- 底层不新增第二套消息流
- 所有消息仍写入 Session Message Stream
- Task 视图通过 `task_id` / `task_node_id` 聚合同一会话消息
- 一个会话可以有很多 Task，因此 Task 消息视图必须是按需过滤，不应复制存储

消息类型：

- user note：用户补充
- agent progress：执行进度
- agent question：需要确认或澄清
- system event：状态变化
- result summary：结果摘要

### 4.5 Session Message Stream 区

职责：

- 展示整个会话的唯一消息流
- 给用户一个全局时间线

它不应替代 Task Tree，而是作为辅助视图。所有 Task 相关消息也直接进入这个流，
只是 UI 可以在 Task Node 被选中时过滤出相关子集：

- 哪些任务被创建
- 哪些任务开始 / 完成 / 失败
- 哪些确认动作被触发
- 用户在哪些时间点介入
- 某个 Task 下发生了哪些局部澄清和确认

### 4.6 Confirmation / Action 区

职责：

- 汇总所有当前需要用户处理的确认动作
- 允许用户逐个处理或批量处理

关键原则：

- 确认动作必须能跳回所属 Task Node
- 处理结果必须写回消息流
- 已处理确认不消失，只变成 resolved history

### 4.7 File Change Summary 区

职责：

- 让用户从 Task 视角查看文件变化
- 让父 Task 自动汇总所有子 Task 的文件变化

不是展示整个 workspace 的 diff，而是：

```text
Task T3 创建页面
  children:
    T3.1 创建样式文件
    T3.2 调整移动端布局

  recursive file changes:
  modified: styles.css
  created:  responsive.css
  modified: index.html
  summary:  汇总 T3 及所有子任务产生的文件变更
```

用户从 Task Node 进入文件细节，而不是从文件反推任务。

归属原则：

- 文件修改的直接归属是产生修改的子 Task
- 父 Task 展示递归汇总：自身修改 + 所有子孙 Task 修改
- 父节点汇总是视图层聚合，不改变子节点的归属
- 已完成父节点的文件汇总应可展开到具体子节点

---

## 5. 主要设计元素

| 元素 | 说明 |
|---|---|
| `Task Tree List` | 一个 Session 下的多个 root Task Tree |
| `Task Node` | UI 的核心对象，承载 intent/status/messages/files/result |
| `Task Node Badge` | 状态、风险、未读、待确认、文件变更等轻量标记 |
| `Session Message` | 唯一消息流中的消息，可选关联 Task |
| `Task Message View` | 从 Session Message Stream 按 Task 过滤出的局部视图 |
| `Confirmation Action` | 带选项、风险、默认行为的用户决策点 |
| `Task Detail Panel` | 选中 Task 后的详情面板 |
| `Task Topology View` | 展示父子关系和执行路径 |
| `File Change List` | 按 Task 聚合的文件修改清单 |
| `Task Summary` | 完成后由系统生成的结果摘要 |
| `Task Constraint` | 用户补充的约束、偏好、非目标 |

---

## 6. 主要交互点

### 6.1 从自然语言生成 Task Tree

输入：

- 用户的自然语言目标

输出：

- 一个或多个 root Task
- 每个 root Task 下的子任务树
- 每个 Task 的 intent / 状态 / 初始能力推断

交互要求：

- 生成结果必须先展示给用户
- 用户可以编辑后再执行
- 系统应清楚标识“计划态”和“执行态”

### 6.2 选择 Task Node

用户点击 Task Node 后：

- 右侧或主区域切换到 Task Detail
- 输入框作用域切换为该 Task
- 消息流展示该 Task 的局部消息
- 文件修改清单和总结聚焦该 Task

### 6.3 编辑未开始 Task

用户可修改：

- intent
- 约束
- 状态
- 是否取消
- 子任务结构

限制：

- 已完成 Task 不允许直接修改
- 修改已完成结果必须创建 follow-up Task

### 6.4 对进行中 Task 追加信息

用户可以：

- 补充需求
- 澄清偏好
- 回答确认
- 要求暂停 / 跳过 / 继续

系统行为：

- 不强制中断当前原子动作
- 信息写入 Session Message Stream，并关联当前 Task
- 下一次 Agent 推理时可见

### 6.5 处理确认动作

确认动作必须支持：

- 单选项确认
- 自然语言回复
- 跳过
- 默认动作说明

确认后：

- 状态从 pending → resolved
- 结果写入 Session Message Stream，并关联确认所属 Task
- Task Node Badge 更新

### 6.6 查看 Task 拓扑

用户可以查看：

- root Task 列表
- 每个 Task 的父子关系
- 当前执行路径
- 已完成 / 进行中 / 未开始 / 失败节点

当前版本只支持 Tree List，不支持 DAG。

### 6.7 查看 Task 的文件修改和总结

用户选中已完成 Task 后可以查看：

- 文件修改清单
- 每个文件的操作类型
- 任务总结
- 结果产物
- 后续建议

已完成 Task 只读。

---

## 7. 后续分述文件清单

建议将 UI 设计拆成以下分述文件：

| 文件 | 内容 |
|---|---|
| `docs/plans/ui/visual-reference.md` | 当前 UI 草图和原型截图索引，作为视觉方向参考 |
| `docs/plans/ui/ui-api-interfaces.md` | Task-first UI 公共接口归档：查询、命令、实时事件、视图模型和跨文档约定 |
| `docs/plans/ui/task-tree-view.md` | Task Tree List / Topology 的展示规则、节点状态、展开折叠、排序和导航 |
| `docs/plans/ui/task-node-detail.md` | Task Detail Panel 的信息结构：摘要、约束、消息、文件、总结、子任务 |
| `docs/plans/ui/task-message-view.md` | Task 消息视图：如何从 Session Message Stream 按 Task 过滤、聚合、展示 |
| `docs/plans/ui/session-message-stream.md` | Session 唯一消息流：时间线、过滤、Task 关联和全局回放 |
| `docs/plans/ui/confirmation-actions.md` | 用户确认动作：选项、风险、默认值、超时、批量处理 |
| `docs/plans/ui/task-editing-rules.md` | 不同状态下 Task Node 可编辑性：未开始、进行中、完成、失败 |
| `docs/plans/ui/file-change-summary.md` | 按 Task 聚合文件变更；父节点递归汇总子节点文件修改 |
| `docs/plans/ui/task-generation-flow.md` | 自然语言 → Task Tree List 的生成、预览、编辑、确认执行流程 |
| `docs/plans/ui/task-scoped-chat-flow.md` | 选中 Task 后的局部对话工作流，与全局对话的切换规则 |
| `docs/plans/ui/information-architecture.md` | 整体布局、主导航、区域关系、响应式层级 |

第一版先搭框架，字段细节和视觉细节后续补充。建议优先级：

1. `ui-api-interfaces.md`
2. `task-generation-flow.md`
3. `task-tree-view.md`
4. `task-node-detail.md`
5. `task-message-view.md`
6. `confirmation-actions.md`

---

## 8. 当前非目标

本总述不决定：

- 具体前端技术栈
- 具体视觉风格
- 像素级布局
- 数据库 schema
- 多 Agent 并发细节
- DAG 任务拓扑
- 文件 diff 的完整交互

这些内容进入后续分述或实现计划。

---

## 9. 验收标准

这份总述完成后，应满足：

- 能清楚解释 TaskWeavn UI 和 Codex / Claude 类 UI 的根本区别
- 能说明 Task、Message、File Change、Confirmation Action 的关系
- 能指导后续分述文档拆分
- 能作为 UI 原型和数据模型设计的上游输入

---

## 10. 状态

- Status: planned
- Owner/Session: planning session
- Last Updated: 2026-05-10
