# Task 架构设计

> 多 Agent 协作架构的核心抽象 · v1.0 · 2026-05-08

---

## 1. 定义

**Task 是工作的最小单位，是本架构的一等公民。**

任何需要被 Agent 完成的事情都被表达为一个 Task。用户的请求是 Task，Agent 派生的子工作是 Task，审计、验证、综合也都是 Task。**整个系统的运转就是 Task 的生产、流转、消费。**

```
Task ≡ 一个明确的意图 + 完成它所需的能力声明 + 完成后的结果
```

---

## 2. 核心抽象

### 2.1 Task 不是函数调用，是工作描述

Task 描述"要做什么"，不描述"怎么做"。**怎么做**由 TaskBus 调度到匹配能力的 Agent 实例后决定。

```
Task        ─ "审计这段代码的安全性"     ← intent
              required_capability="audit"  ← who can do it
              ↓
TaskBus     ─ 匹配能力为 audit 的 Agent
              ↓
Agent 实例   ─ 执行，产出 result
```

这种解耦让 Task 可以被序列化、持久化、转发、replay——它是数据，不是控制流。

### 2.2 Task 是树的节点

任务通过 `parent_id` 形成单根树：

```
        Root Task (用户请求)
          ├── Subtask 1
          │     └── Subtask 1.1
          ├── Subtask 2
          └── Subtask 3
```

**树而非图**是核心约束。Fan-out / fan-in 由父任务作为同步点：父任务创建多个子任务并行执行，等待全部完成后再综合。

### 2.3 Task 三要素

```python
@dataclass(frozen=True)
class Task:
    # 身份
    id: TaskId
    parent_id: TaskId | None

    # 意图
    intent: str                       # 自然语言描述
    required_capability: str          # 单值，决定调度

    # 状态与产出
    status: TaskStatus                # 4 状态
    result: TaskResult | None         # 完成后填充
```

`intent` 给 Agent（人类可读），`required_capability` 给调度器（机器可读），`result` 给后续任务（结构化或自由文本）。

---

## 3. 核心属性

| 属性 | 类型 | 说明 |
|-----|------|-----|
| `id` | `TaskId` | 全局唯一，UUID 或递增 |
| `parent_id` | `TaskId \| None` | 父任务，None 表示根任务 |
| `intent` | `str` | 任务意图，自然语言 |
| `required_capability` | `str` | 必须有此 capability 的 Agent 才能领取 |
| `status` | `TaskStatus` | `pending` / `running` / `done` / `failed` |
| `result` | `TaskResult \| None` | 任务完成后的产物 |
| `created_at` | `datetime` | 创建时间 |
| `created_by` | `AgentId \| UserId` | 任务创建者 |
| `started_at` | `datetime \| None` | 进入 running 的时间 |
| `completed_at` | `datetime \| None` | 进入终态的时间 |
| `error` | `str \| None` | failed 状态时的失败原因 |

**所有属性 frozen，状态变更通过新建 Task 对象完成。** 这与 EventStream 的不可变事件模型一致。

---

## 4. 设计理念

### 4.1 Task 是数据，不是行为

Task 的所有信息都可以序列化为 JSON 持久化。这意味着：
- 任务可以跨进程转发
- 任务可以被 replay 用于调试
- 任务历史就是系统的完整审计日志
- Task ↔ Event 同构，可以共用持久化层

### 4.2 单根树形约束

```
为什么不用 DAG？

DAG 解锁的能力（leaf-to-leaf 横向依赖）在 LLM 驱动的任务分解里
出现频率极低。LLM 自顶向下分解任务，自然形成树。

代价：
  树调度器 ≈ 几十行代码
  DAG 调度器 ≈ 几百行 + 拓扑排序 + 环检测 + 就绪事件订阅 + 死锁处理

收益：90% 场景的简洁性远超 10% 场景的表达力损失。
```

剩下 10% 的场景通过 `artifact_refs`（未来扩展）以非破坏性方式补足。

### 4.3 状态机极简化

只有 4 个状态：

```
pending  ─→  running  ─→  done
                   ↘  failed
```

砍掉的中间态：
- ❌ `waiting`（等待依赖）→ pending 时由总线判断 parent 是否完成
- ❌ `assigned`（已分配未开始）→ 与 running 合并
- ❌ `blocked`（创建子任务后等待）→ 父任务继续 running，LLM 调用嵌套
- ❌ `cancelled` → 通过 failed + error reason 表达

### 4.4 任务发布权 = 协作能力

是否能发布任务取决于 Agent 是否挂载了 `CreateTaskTool`：

```
普通 Agent     ─ 工具集 = [read_file, write_file]
                  无法发布任务，是协作的"叶子节点"

协作 Agent     ─ 工具集 = [read_file, write_file, create_task]
                  可以发布子任务，触发其他 Agent 协作

Orchestrator  ─ 工具集 = [create_task, claim_result]
                  专门做编排，自己不直接执行业务工具
```

**协作能力被工具化**，与其他能力同等管理，不需要在 Agent 类型上特殊分类。

---

## 5. 任务状态机

```
            ┌─────────┐
            │ pending │  任务已发布到总线，等待被领取
            └────┬────┘
                 │ Agent 领取
                 ↓
            ┌─────────┐
            │ running │  正在被某个 Agent 实例执行
            └────┬────┘
           ┌─────┴─────┐
           ↓           ↓
       ┌──────┐    ┌────────┐
       │ done │    │ failed │
       └──────┘    └────────┘
        终态        终态
```

**关键状态转换规则：**

```
pending → running   总线分配给已实例化的 Agent
                    parent 必须是 done（否则任务停留在 pending）

running → done      Agent 返回 result，无异常
                    若任务有未完成的子任务，等子任务全部 done 才 done

running → failed    Agent 抛异常 / 子任务 failed / 显式标记失败
                    终态，不可恢复（重试 = 新建任务）
```

终态任务不可变，包括 result 不可修改。任何"修改"通过新建任务表达。

---

## 6. 生命周期

### 6.1 创建

任务由用户或 Agent 创建，必须指定 `intent` 和 `required_capability`：

```
用户创建（根任务）：
  Session.publish(Task(parent_id=None, intent="...", capability="..."))

Agent 创建（子任务）：
  CreateTaskTool 在工具调用层包装：
  Tool input → Task object → bus.publish(task)
```

创建即进入 `pending` 状态，进入总线队列。

### 6.2 等待与领取

任务在总线上等待，直到：
- `parent_id is None` 或 `parent.status == done`
- 有 Agent 实例申请了 `claim_next(capability=task.required_capability)`

匹配成功后，`status: pending → running`。

### 6.3 执行

Agent 实例执行任务：
- 读取 Workspace
- 调用 LLM 推理
- 调用工具（可能包括 CreateTaskTool 派生子任务）
- 写入 Workspace
- 返回 result

执行期间任务保持 `running`。如果创建了子任务，**任务依然 running**，等所有子任务终态后才转入终态。

### 6.4 完成

```
所有子任务 done + Agent 返回 result（成功）→ status: running → done
任何子任务 failed 且未被父任务捕获 → 父任务 status: running → failed
Agent 自身抛异常 → status: running → failed
```

完成时间 `completed_at` 写入，result（或 error）写入。

### 6.5 持久化与归档

任务终态后**永久存档**到 EventStream，作为审计和 replay 的依据。Workspace 里的产物保留到 Session 结束。

```
活跃任务  ──  内存 + TaskBus 队列
终态任务  ──  EventStream（append-only）+ 可选缓存
```

---

## 7. 与其他组件的关系

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   User      ──创建──>     Task                      │
│                            │                        │
│   Agent     ──创建──>     Task                      │
│                            │                        │
│                            ↓ publish                │
│                         TaskBus                     │
│                            │                        │
│                            ↓ claim                  │
│                          Agent                      │
│                            │                        │
│                            ↓ read/write             │
│                        Workspace                    │
│                            │                        │
│                            ↓ persist                │
│                       EventStream                   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

- **与 Session：** 每个 Task 隶属于一个 Session，使用 Session 的 Workspace
- **与 Agent：** Task 描述需求，Agent 实例提供能力，多对多映射
- **与 Bus：** Task 是 Bus 的载荷，Bus 是 Task 的传递媒介
- **与 ThoughtStore：** Task 执行过程中的推理可选写入 ThoughtStore，供后续任务检索

---

## 8. 未来发展点

### 8.1 v1.x：非破坏性扩展

**`artifact_refs` 字段**

```python
@dataclass(frozen=True)
class Task:
    # ...existing fields
    artifact_refs: list[TaskId] = field(default_factory=list)
```

- 调度器忽略此字段（不影响调度逻辑）
- Agent 在执行时通过此字段读取其他任务的产物
- 表达"我需要任务 X 的输出，但 X 不是我的 parent"
- 解决 90% 的"伪 DAG 需求"，零破坏性

### 8.2 v2.x：状态扩展

**`cancelled` 状态**

当用户主动取消会话或父任务时，未开始的子任务进入 `cancelled` 而非 `failed`，便于区分意图。

**`paused` 状态**

需要长时间等待外部输入（如人工审核）时的中间态。仅在确实出现此场景时引入。

### 8.3 v3.x：DAG 化（仅在数据支持下）

**真正的多依赖**

```python
@dataclass(frozen=True)
class Task:
    parent_id: TaskId | None              # 仍保留，表示创建关系
    depends_on: list[TaskId]              # 新增，表示调度依赖
```

调度器升级为拓扑排序 + 环检测。**只有当 `artifact_refs` 模式无法表达的需求被实证后才引入。**

### 8.4 v3.x：流式任务

**长生命周期任务（producer 风格）**

```python
class StreamingTask(Task):
    yields: AsyncIterator[Artifact]  # 持续产出而非单次返回
```

仅在生产者-消费者用例（如实时监控、流式数据处理）成为核心需求时引入。这会引发对"无状态 Agent"约束的根本挑战，需要慎重评估。

---

## 9. 设计决策小结

| 决策 | 选择 | 替代方案 | 选择理由 |
|------|------|---------|---------|
| 任务关系 | 单根树 | DAG | LLM 分解天然成树，DAG 复杂度收益不成比例 |
| 状态数 | 4 个 | 8+ 个 | 中间态可压缩到 running，少状态少 bug |
| 依赖表达 | 单值 parent_id | 多值 depends_on | 可演进为 artifact_refs，渐进引入 |
| 不变性 | frozen | mutable | 与 EventStream 一致，可 replay |
| 协作权 | 工具化（CreateTaskTool） | Agent 类型分类 | 与其他能力同构管理 |
| 失败处理 | 终态 + 重试 = 新任务 | 状态回退 | 任务历史完整，调试友好 |
