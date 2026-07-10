# Architecture 文档索引与事实维护规则

> Status: fact-calibrated active index
>
> Last verified: 2026-07-10
>
> Active documents: 24
>
> Original index: [README.original.md](README.original.md)
>
> Calibration record: [fix-log/README.md](fix-log/README.md)

本目录记录 Plato / TaskWeavn 的当前架构事实、明确标注的兼容边界，以及少量仍有
价值但尚未实现的 future design。顶层非 `*.original.md` 文档是当前阅读
入口；`*.original.md` 和 `fix-log/` 是校准证据，不是另一套现行
架构。

---

## 1. 事实权威与冲突处理

### 1.1 各类文档的职责

| 来源 | 负责回答 | 使用规则 |
|---|---|---|
| 当前源码与可执行测试 | 系统现在实际做什么 | 实现事实的最高依据 |
| 本目录 active architecture 文档 | 当前边界、owner、协议、存储、限制如何解释 | 应与源码/测试一致；发现偏差必须修复 |
| Product docs | 用户需要什么、产品语义是什么 | 不能单独证明已经实现 |
| Engineering contracts / plans | 准备如何实现、接口目标是什么 | 先看 status，再核对代码 |
| ADRs | 哪个长期决策已被接受 | `accepted` 不等于 `implemented` |
| Release/evidence docs | 哪个 slice 被声明为已交付及其证据 | 仍需与当前代码核对，避免后续回归 |
| `*.original.md` | 校准前文档是什么样 | 仅做历史比对 |
| `fix-log/*.md` | 为什么改、查了什么、如何验证 | 校准 provenance，不替代 active 文档 |

### 1.2 冲突优先级

判断“当前实现事实”时采用：

~~~text
current source + executable tests
  > fact-calibrated active architecture
  > implemented contract/release evidence
  > product direction
  > accepted but not implemented ADR
  > original/historical architecture
~~~

这不是说 Product 或 ADR 不重要，而是它们回答的问题不同。架构文档必须显式区分：

- current implementation；
- compatibility path；
- accepted direction；
- future proposal；
- absent capability。

---

## 2. 校准文件结构

每篇 active architecture 文档都有三联文件：

~~~text
docs/architecture/<name>.md
docs/architecture/<name>.original.md
docs/architecture/fix-log/<name>.md
~~~

| 文件 | 作用 | 可否作为当前事实 |
|---|---|---|
| `<name>.md` | 事实校准后的当前文档 | 是 |
| `<name>.original.md` | 开始校准时的 byte-for-byte 原文 | 否 |
| `fix-log/<name>.md` | 原文哈希、证据、逐项修复、验证记录 | 作为 provenance 使用 |

当前目录共有：

~~~text
24 active documents
24 preserved originals
24 fix logs
~~~

`original` 文件不得随 active 文档一起“同步更新”。它的价值就是保持校准
前状态不变。若未来再次校准 active 文档，应在现有 fix log 追加新的核验批次，而
不是覆盖 original。

---

## 3. 建议阅读路径

### 3.1 最小架构定向

开始任何跨模块技术设计前，至少阅读：

1. [overview.md](overview.md)：当前系统拓扑与主要边界；
2. [session.md](session.md)：workspace、Session、runtime、存储与状态边界；
3. [reference.md](reference.md)：当前 substrate 与实际装配；
4. 与任务直接相关的主题文档；
5. 对应 fix log 中的已知限制和验证记录。

不要求每个小改动机械阅读全部 24 篇。阅读范围应随 blast radius 扩展。

### 3.2 按工作类型阅读

| 工作类型 | 推荐顺序 |
|---|---|
| Published Task / execution lifecycle | [task.md](task.md) -> [bus.md](bus.md) -> [agent.md](agent.md) -> [context-manager.md](context-manager.md) |
| RawTask / Plan / authoring | [authoring-domain.md](authoring-domain.md) -> [authoring-command-protocol.md](authoring-command-protocol.md) -> [collaborator-agent-task-authoring.md](collaborator-agent-task-authoring.md) |
| Runtime Input / guidance / ASK / confirmation | [contract-revision-and-execution-loops.md](contract-revision-and-execution-loops.md) -> [interaction-layer.md](interaction-layer.md) -> [session.md](session.md) |
| Main Page / frontend / sidecar API | [task-domain-ui-model-separation.md](task-domain-ui-model-separation.md) -> [ui-backend-communication.md](ui-backend-communication.md) -> [session.md](session.md) |
| Tool / workspace / web / computer-use | [tool-capability-layer.md](tool-capability-layer.md) -> [workspace-communication-protocol.md](workspace-communication-protocol.md) -> [agent.md](agent.md) |
| LLM / retry / provider / usage | [llm-provider-reliability.md](llm-provider-reliability.md) -> [context-manager.md](context-manager.md) -> [configurable-logging-system.md](configurable-logging-system.md) |
| Embedded Execution Plane / local task types | [taskbus-service-multi-execution-env.md](taskbus-service-multi-execution-env.md) -> [task.md](task.md) -> [bus.md](bus.md) |
| Future scheduling / remote execution | [bus-v2.md](bus-v2.md) -> [taskbus-service-multi-execution-env.md](taskbus-service-multi-execution-env.md); 两者都必须结合 current TaskBus 文档阅读 |
| Multi-Agent claims or routing | [multi-agent-collaboration.md](multi-agent-collaboration.md) or [multi-agent-collaboration_en.md](multi-agent-collaboration_en.md) -> [agent.md](agent.md) -> [bus.md](bus.md) |
| 架构风险、发布门禁、优先级 | [review.md](review.md) -> 对应主题文档 -> release/evidence docs |

---

## 4. 完整文档目录

### 4.1 System map、Session 与评审

| Active document | 当前角色 | Original | Fix log |
|---|---|---|---|
| [README.md](README.md) | 本索引、权威规则和校准结构 | [original](README.original.md) | [log](fix-log/README.md) |
| [overview.md](overview.md) | Product 1.1 local runtime、fixed-route execution 和 embedded Execution Plane 的高层图 | [original](overview.original.md) | [log](fix-log/overview.md) |
| [reference.md](reference.md) | 当前 core/runtime/store/Main Page/CLI substrate 与装配参考；不是历史材料 | [original](reference.original.md) | [log](fix-log/reference.md) |
| [session.md](session.md) | workspace-local Session identity、registry、store scope、status、runtime、recovery 和 multi-workspace 边界 | [original](session.original.md) | [log](fix-log/session.md) |
| [review.md](review.md) | 当前架构风险与评价快照；事实和评分依据分开 | [original](review.original.md) | [log](fix-log/review.md) |

### 4.2 Task、Agent、TaskBus 与 Execution Plane

| Active document | 当前角色 | Original | Fix log |
|---|---|---|---|
| [task.md](task.md) | Published `TaskDomain` 数据、状态机、ASK/confirmation、retry/interrupt 和 Execution Plane 映射 | [original](task.original.md) | [log](fix-log/task.md) |
| [bus.md](bus.md) | 当前 TaskBus API、SQLite/in-memory authority、claim 与 fixed-route serial boundary | [original](bus.original.md) | [log](fix-log/bus.md) |
| [agent.md](agent.md) | Agent template/runtime/run 分层、Default Agent、role-specific LLM 与未实现 dynamic assignment | [original](agent.original.md) | [log](fix-log/agent.md) |
| [taskbus-service-multi-execution-env.md](taskbus-service-multi-execution-env.md) | 已实现 embedded Task API/Execution Plane/local runtime handlers，加上明确标注的 multi-env future direction | [original](taskbus-service-multi-execution-env.original.md) | [log](fix-log/taskbus-service-multi-execution-env.md) |
| [bus-v2.md](bus-v2.md) | **future design reference / not current runtime**；调度、并发、IO scope、lease 的后续备忘 | [original](bus-v2.original.md) | [log](fix-log/bus-v2.md) |

### 4.3 Authoring 与 Contract Revision

| Active document | 当前角色 | Original | Fix log |
|---|---|---|---|
| [authoring-domain.md](authoring-domain.md) | RawTask、authoring ASK、DraftTaskTree、durable Plan/PlanTaskNode 和 publish compatibility | [original](authoring-domain.original.md) | [log](fix-log/authoring-domain.md) |
| [authoring-command-protocol.md](authoring-command-protocol.md) | 当前 authoring command、version/idempotency 与 durable Plan publish 边界 | [original](authoring-command-protocol.original.md) | [log](fix-log/authoring-command-protocol.md) |
| [collaborator-agent-task-authoring.md](collaborator-agent-task-authoring.md) | command-backed Collaborator authoring、workspace-informed read 和 Plan proposal 路径 | [original](collaborator-agent-task-authoring.original.md) | [log](fix-log/collaborator-agent-task-authoring.md) |
| [contract-revision-and-execution-loops.md](contract-revision-and-execution-loops.md) | Runtime Input Router、read-only inquiry、guidance/ASK/confirmation/task mutation 与 execution handoff | [original](contract-revision-and-execution-loops.original.md) | [log](fix-log/contract-revision-and-execution-loops.md) |

### 4.4 Interaction、UI contract 与 transport

| Active document | 当前角色 | Original | Fix log |
|---|---|---|---|
| [interaction-layer.md](interaction-layer.md) | MessageStream/MessageBus、execution ASK、confirmation、AutonomyGate 实际装配、Activity 和 recovery | [original](interaction-layer.original.md) | [log](fix-log/interaction-layer.md) |
| [task-domain-ui-model-separation.md](task-domain-ui-model-separation.md) | backend domain facts、server ViewModels、frontend local state 与 Plan migration projection | [original](task-domain-ui-model-separation.original.md) | [log](fix-log/task-domain-ui-model-separation.md) |
| [ui-backend-communication.md](ui-backend-communication.md) | Query/Command/Event、HTTP routes、SSE、workspace + Session identity、auth 与 failure boundary | [original](ui-backend-communication.original.md) | [log](fix-log/ui-backend-communication.md) |

### 4.5 Context、Tool 与 Workspace

| Active document | 当前角色 | Original | Fix log |
|---|---|---|---|
| [context-manager.md](context-manager.md) | fixed-route Task execution 的 deterministic message context、snapshot/trace、cache-aware rendering 和 current limits | [original](context-manager.original.md) | [log](fix-log/context-manager.md) |
| [tool-capability-layer.md](tool-capability-layer.md) | concrete Tool runtime、capability catalog/policy、precision tools、web/computer-use 和 skill governance | [original](tool-capability-layer.original.md) | [log](fix-log/tool-capability-layer.md) |
| [workspace-communication-protocol.md](workspace-communication-protocol.md) | 已实现 inspection/precision/evidence/path policy，以及明确标注的 unified protocol future direction | [original](workspace-communication-protocol.original.md) | [log](fix-log/workspace-communication-protocol.md) |

### 4.6 LLM 与 Observability

| Active document | 当前角色 | Original | Fix log |
|---|---|---|---|
| [llm-provider-reliability.md](llm-provider-reliability.md) | LLM contracts、provider wiring、retry/timeout/errors、role profiles、usage/logging 和 2026-07-10 外部协议核验 | [original](llm-provider-reliability.original.md) | [log](fix-log/llm-provider-reliability.md) |
| [configurable-logging-system.md](configurable-logging-system.md) | process-local structured logging、rules/sinks、session archive、redaction、runtime config 和 diagnostics | [original](configurable-logging-system.original.md) | [log](fix-log/configurable-logging-system.md) |

### 4.7 Multi-Agent 事实边界

| Active document | 当前角色 | Original | Fix log |
|---|---|---|---|
| [multi-agent-collaboration.md](multi-agent-collaboration.md) | 中文现状：当前不是 multi-Agent graph runtime；说明真实角色、claim、协作媒介和 accepted extension | [original](multi-agent-collaboration.original.md) | [log](fix-log/multi-agent-collaboration.md) |
| [multi-agent-collaboration_en.md](multi-agent-collaboration_en.md) | 英文独立校准版本；与中文文档同主题但不是机械逐句翻译 | [original](multi-agent-collaboration_en.original.md) | [log](fix-log/multi-agent-collaboration_en.md) |

---

## 5. 当前架构主题图

### 5.1 主执行路径

~~~text
Main Page input
  -> Runtime Input Router
       -> read-only inquiry
       -> contract revision command
       -> authoring
       -> execution work
  -> RawTask / DraftTaskTree / Plan
  -> Published TaskDomain
  -> TaskBus
  -> FixedRouteExecutionDispatcher
  -> Resident Default Agent adapter
  -> task-scoped AgentLoop
  -> TaskBus result / wait / failure
  -> Session snapshot / Activity / Audit
~~~

### 5.2 Embedded Execution Plane

~~~text
TaskRequest
  -> EmbeddedTaskApiService
       -> ordinary type -> TaskBus + fixed-route dispatcher
       -> selected local type -> EmbeddedTaskRuntimeHandler
  -> ExecutionPlaneStore / status / evidence
~~~

当前有 embedded service boundary，但没有 remote worker registration、distributed
lease/heartbeat、external service auth 或 separated TaskBus service。

### 5.3 Identity 与 storage

~~~text
public identity = workspaceId + sessionId

workspace root
  -> shared project files
  -> workspace-level SQLite stores with scoped rows
  -> .plato/sessions/<sessionId>/
       -> events.sqlite
       -> context.sqlite
       -> logs/
~~~

Session 当前不是独立 filesystem fork，也不拥有一个独立 sidecar runtime。

---

## 6. 阅读注意事项

### 6.1 “Active document”不等于“全文都是 current”

例如：

- `bus-v2.md` 是 active 的 future design reference，全文明确 not current；
- `workspace-communication-protocol.md` 同时记录 implemented slices 和 future
  unified protocol；
- `taskbus-service-multi-execution-env.md` 同时记录 embedded facts 和 future
  multi-env service；
- `agent.md`、`task.md`、`bus.md` 有 future sections，但
  current/non-current 已明确分栏。

active 的含义是“它对当前架构判断仍有有效作用”，不是“其中每个提案都已实现”。

### 6.2 名字不是实现证据

类名、Protocol、DTO、ADR title 或旧 Phase 注释只能证明 substrate 或设计存在。
判断产品路径是否成立，还必须检查：

- production assembly；
- caller；
- durable store；
- route/transport；
- frontend consumer；
- executable tests。

### 6.3 Review 不是第二套事实权威

`review.md` 的风险、分数和优先级是有依据的评价快照。其事实部分应回链
当前代码和主题文档；评分本身不是系统行为。

### 6.4 双语协作文档

中文和英文 multi-Agent 文档分别核验。它们应保持结论一致，但允许按语言重组
结构。修改其中一篇时必须检查另一篇是否仍表达同一 current/future boundary。

---

## 7. 与其他文档目录的关系

| 目录 | 关系 |
|---|---|
| [Product](../product/) | 产品语义、目标体验和 acceptance intent |
| [Engineering](../engineering/) | API/runtime contracts；必须检查 implemented status |
| [Plans](../plans/) | 具体 delivery slice；不能替代 architecture current-state update |
| [Decisions](../decisions/) | durable decisions 和 rejected alternatives；接受不等于落地 |
| [Releases](../releases/) | shipped claim 与 release evidence |
| [Gaps](../gaps/) | 未满足能力和风险登记 |
| [Design](../design/) | UI/UX/design-system/Figma governance |

技术计划应同时引用：

1. Product/contract 输入；
2. 本目录相关 current architecture；
3. 必要 ADR；
4. 目标测试与 release evidence。

---

## 8. 文档维护流程

更新 architecture 时遵守：

1. **一次一篇。** 先界定文档主题和事实 owner。
2. **先核验，后改写。** 查相关代码、调用点、schema、前端、测试、contract、
   release 和 ADR status；不凭类名或旧文档猜测。
3. **保留 original。** 若 `<name>.original.md` 尚不存在，在首次校准前
   byte-for-byte 保存当前 active 文档，并记录 SHA。
4. **写 fix log。** 罗列证据、原陈述、判定、修复表达、测试和残余限制。
5. **分开 current/future。** 未实现能力必须使用明确否定语句或 future label。
6. **验证链接与差异。** 检查 original hash、active/original 差异、local links、
   Markdown fence、`git diff --check` 和工作树范围。
7. **按风险运行测试。** 文档中的实现陈述应由相关 tests 支撑；docs-only index
   变化不需要无关代码测试。
8. **最后更新本索引。** 新增、重命名、拆分或改变状态后，同步目录和阅读路径。

不得：

- 用 original 覆盖 active；
- 把 future example 改写成 shipped fact；
- 因文档落后而修改代码来“配合文档”；
- 未检查调用点就把 Protocol/DTO 称为 production path；
- 隐藏已知失败、未运行检查或 contract drift。

---

## 9. 当前校准状态

截至 2026-07-10：

- 24/24 active documents 已逐篇校准；
- 24/24 originals 已保留；
- 24/24 fix logs 已建立；
- 顶层 active 文档不再把 `reference`、`interaction-layer`、
  multi-Agent 文档或 `review` 误标为历史 substrate；
- embedded Execution Plane 被标为 current foundation，而 distributed multi-env
  execution 仍明确为 future；
- Session ownership 已按 product continuity、workspace runtime、store scope 和
  shared workspace root 分开；
- full-suite 当前已知基线和验证限制记录在
  [review fix log](fix-log/review.md)，本索引不把“完成校准”解释为“所有代码测试
  当前全绿”。

任何后续代码变更若使上述文档失真，应把对应 architecture update 作为同一交付的
必要部分。
