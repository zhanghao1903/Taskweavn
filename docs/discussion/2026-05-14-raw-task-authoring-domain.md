# Discussion: RawTask、可行性判断与 Authoring Domain

> 日期：2026-05-14
> 类型：讨论稿（暂不升级为实施计划）
> 状态：exploratory

---

## 1. 背景

TaskWeavn 的核心交互是：

```text
用户输入自然语言
  -> 协作者理解和拆解
  -> 生成 Task Tree
  -> 用户确认
  -> 发布到 TaskBus
```

但这里有一个尚未想清楚的问题：

> 系统如何识别用户的任务能否完成，或者问题能否解决？

如果完全交给 Collaborator Agent 判断，协作者承担的责任会过重：

- 理解用户意图；
- 判断可行性；
- 判断缺失信息；
- 决定问什么；
- 生成 Task Tree；
- 维护用户交互状态。

如果前置一个专门的 Feasibility Agent，也有别扭之处：

- 可行性不是简单 yes/no；
- 判断会依赖能力、权限、风险、上下文、用户补充信息；
- 一个固定前置 Agent 容易变成新的“门卫”，交互体验僵硬。

本讨论暂不形成 plan，只沉淀当前共识。

---

## 2. 当前倾向

更自然的方式不是让系统直接生成完整 Task Tree，而是：

```text
UserMessage
  -> RawTask
  -> feasibility / clarification / enrichment
  -> DraftTaskTree
  -> PublishedTask
```

也就是说，用户输入后先生成一个 **RawTask**。

RawTask 是用户意图的前置容器。它还不是可执行任务，也不一定能被拆成 Task Tree。它可以处于：

- 信息不足；
- 需要澄清；
- 部分可行；
- 需要权限；
- 不支持；
- 可以规划。

ASK 动作应该挂载在 RawTask 上，而不是只挂在 Session 上。

---

## 3. RawTask 的意义

RawTask 可以承担“从聊天输入到任务系统”的过渡态。

它解决几个问题：

1. 用户输入后，系统立刻有一个可展示对象，而不是空聊天流。
2. 可行性判断有载体，不是协作者的一句主观判断。
3. ASK / answer 有明确归属对象。
4. 用户补充信息可以 patch RawTask。
5. DraftTaskTree 的生成有可追溯来源。
6. Replay 可以重现从模糊意图到任务树的过程。

RawTask 示例字段：

```python
class RawTask:
    id: str
    session_id: str
    source_message_id: str
    user_input: str
    status: Literal[
        "created",
        "assessing",
        "awaiting_user",
        "ready_to_plan",
        "converted",
        "rejected",
        "cancelled",
    ]
    intent_summary: str | None
    feasibility: FeasibilityReport | None
    missing_inputs: list[Question]
    constraints: list[str]
    assumptions: list[str]
```

RawTaskAsk 示例：

```python
class RawTaskAsk:
    raw_task_id: str
    question: str
    options: list[AnswerOption]
    required: bool
    reason: str
```

---

## 4. 可行性判断不是 yes/no

当前倾向是做结构化 feasibility assessment，而不是单一裁判 Agent。

可行性判断应该输出：

```python
class FeasibilityReport:
    status: Literal[
        "ready",
        "needs_clarification",
        "needs_user_permission",
        "partially_feasible",
        "not_supported",
        "unsafe",
    ]
    confidence: float
    reasons: list[str]
    missing_inputs: list[Question]
    required_capabilities: list[str]
    required_permissions: list[str]
    suggested_next_action: Literal[
        "generate_task_tree",
        "ask_user",
        "offer_alternatives",
        "decline",
    ]
```

它回答的不是：

```text
能不能做？
```

而是：

```text
做到什么程度？
缺什么？
风险在哪？
下一步该问用户、生成 Task Tree、给替代方案，还是拒绝？
```

---

## 5. RawTask 要不要进 TaskBus？

这是讨论中的关键问题。

如果 RawTask 进入当前 TaskBus，会出现几个问题：

- RawTask 还没有稳定的 `required_capability`；
- RawTask 不应该被普通执行 Agent 领取；
- RawTask 的状态不是 `pending / running / done / failed`；
- 固定路由给 Collaborator Agent 本质上需要 route-to-agent 策略；
- 当前 TaskBus 还没有 task kind routing / fixed agent routing。

所以当前倾向是：

> RawTask 不进入 Execution TaskBus。

但这不等于 RawTask 不进入系统。

RawTask 应该进入 Authoring Domain，被消息、事件、日志、配置、UI、Replay 观察和管理。

---

## 6. Authoring Domain 与 Execution Domain

讨论中形成的主要共识：

```text
TaskWeavn 至少有两个任务域：

1. Authoring Domain：任务如何被产生
2. Execution Domain：任务如何被执行
```

### 6.1 Authoring Domain

职责：

> 把模糊输入变成可发布的 Task Tree。

对象：

- `UserMessage`
- `RawTask`
- `RawTaskAsk`
- `RawTaskAnswer`
- `FeasibilityReport`
- `DraftTaskTree`
- `DraftTaskNode`
- `TaskPatch`
- `CollaboratorProposal`

生命周期示例：

```text
created
assessing
awaiting_user
ready_to_plan
drafting
ready_to_publish
cancelled
rejected
```

主要参与者：

- 用户；
- Collaborator Agent；
- feasibility assessor；
- UI；
- MessageStream / EventStream / Config / Logging。

### 6.2 Execution Domain

职责：

> 把已确认的 Task 执行并产出结果。

对象：

- `PublishedTask`
- `TaskClaim`
- `TaskResult`
- `TaskFailure`
- `PipelineTask`
- `ResultPackagingTask`

生命周期示例：

```text
pending
running
blocked
done
failed
cancelled
```

主要参与者：

- TaskBus；
- Execution Agents；
- ResultPackagingAgent；
- Pipeline agents。

---

## 7. 边界原则

当前最重要的边界原则：

> Authoring objects do not enter Execution TaskBus.
> Only published execution tasks enter TaskBus.

换句话说：

```text
RawTask / DraftTaskTree / Clarification Ask
  -> Authoring Domain

PublishedTask / PipelineTask / ResultPackagingTask
  -> Execution TaskBus
```

两者通过 `TaskPublisher` 连接：

```text
RawTask
  -> DraftTaskTree
  -> user confirmation
  -> TaskPublisher
  -> Execution TaskBus
```

---

## 8. 为什么不强行统一进 TaskBus

把 RawTask 强行塞进 TaskBus，表面上少了一个 domain，实际上会污染 TaskBus：

- 需要支持 raw task；
- 需要支持 draft task；
- 需要支持 fixed route collaborator；
- 需要支持 non-executable lifecycle；
- 需要区分 authoring blocked 和 execution blocked；
- 需要防止 execution agent 领取不可执行对象。

这属于：

> 省一个概念，污染一个核心。

而引入 Authoring Domain 虽然增加概念，但它换来：

- 协作者责任减轻；
- ASK 有明确归属；
- UI 有 RawTask Card；
- feasibility 可解释；
- replay 更完整；
- TaskBus 保持干净。

这笔复杂度是有明确用户场景收益的。

---

## 9. 复杂度原则

讨论中形成的一条重要判断：

> 复杂度不是敌人，不受控的复杂度才是敌人。

系统复杂度、上下文、LLM 注意力、用户注意力都是有限资源。

因此，每增加一个系统层，应该满足：

1. 换来明确用户场景；
2. 减少另一个核心模块的污染；
3. 帮助切分上下文；
4. 能被 UI 和 replay 解释。

Authoring Domain 增加了概念复杂度，但保护了 Execution TaskBus，也让用户输入到 Task Tree 的过程可解释。

---

## 10. 仍未决定的问题

这些问题暂不进入 plan，等待更多用户场景：

1. Authoring Domain 是否需要自己的 `AuthoringBus`，还是只需要 store + events？
2. RawTask 是否需要持久化为独立表，还是作为 Message/Event 派生对象？
3. Feasibility Assessment 是否由 Collaborator 调用工具完成，还是作为独立 assessor service？
4. RawTaskAsk 是否复用现有 MessageStream actionable，还是定义 authoring-specific ask object？
5. DraftTaskTree 与 RawTask 的版本关系如何表达？
6. UI 上 RawTask Card 和 Task Node Card 是否共享 ViewModel？
7. 如果未来统一 WorkBus，Authoring / Execution 是否只是不同 domain 的 WorkItem？

---

## 11. 当前结论

当前暂定共识：

1. 用户输入后先生成 `RawTask`，不直接生成完整 Task Tree。
2. ASK 动作挂载在 RawTask 上。
3. Feasibility 是 RawTask 的结构化状态/报告，不是一个简单 yes/no 判断。
4. RawTask 不进入 Execution TaskBus。
5. Collaborator workflow 和 RawTask 都属于 Authoring Domain。
6. Execution TaskBus 只接收已发布、可执行的 Task。
7. `TaskPublisher` 是 Authoring Domain 到 Execution Domain 的边界。
8. 暂不做 plan，等更多用户场景后再决定是否正式建模。
