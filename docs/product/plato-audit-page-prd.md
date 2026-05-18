# Plato Audit Page PRD

> Status: draft
> Last Updated: 2026-05-17
> Scope: Audit Page 的产品需求定义。本文回答“为什么做、为谁做、第一版做什么、不做什么、如何判断成功”，不规定具体页面布局、组件 API、Figma frame 或后端 transport 合约。
> Related: [Core Product Principles](core-product-principles.md), [Workflow, Session, And Task UX Model](workflow-session-task-ux-model.md), [Settings, Logs, And Audit Boundary](plato-settings-logs-audit-boundary.md), [Plato Audit Page 项目实施计划](../plans/ui/audit-page-project-implementation-plan.md), [UN-105](../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md)

---

## 1. 产品一句话定义

Audit Page 是 Plato 的 Trust Plane。

它把一次 Session 或一个 TaskNode 的关键事实组织成用户可理解的证据链，帮助用户追问系统为什么这样做、谁参与了、用户确认过什么、哪些文件改变了、风险如何被处理，以及过程能否被追踪或重建。

---

## 2. 背景与问题

Plato 的主体验是 Task-first：

```text
Workflow -> Session -> TaskTree -> TaskNode -> Result -> Audit
```

Main Page 负责控制和推进工作。它应该让用户知道任务是什么、状态如何、哪里需要确认、结果在哪里。Main Page 不应该展示所有底层事件、工具参数、provider 细节或 trace payload。

但当系统执行真实工作后，用户会自然产生信任问题：

- 这个结果是怎么来的？
- 系统为什么修改了这个文件？
- 我当时是否确认过这个风险动作？
- 哪个 Agent、Tool 或 provider 参与了？
- 有哪些风险被发现但没有完全解决？
- 如果结果不对，我能否回看过程并定位原因？

如果没有 Audit Page，Plato 会在两个方向之间摇摆：

1. Main Page 过度暴露底层细节，变得嘈杂难用。
2. Main Page 保持简洁，但用户无法建立过程信任。

Audit Page 的价值是把底层可追溯能力产品化，让主页面保持清晰，同时让用户在需要时能深入检查。

---

## 3. 目标用户与使用时机

### 3.1 目标用户

| 用户 | 需求 |
|---|---|
| 普通任务用户 | 想确认系统做了什么、为什么这么做、结果是否可信。 |
| 高风险操作用户 | 需要回看自己是否授权了文件修改、外部调用、删除、覆盖等动作。 |
| 项目负责人 | 需要复盘一次 Session 的执行过程、失败原因和风险处理。 |
| 高阶用户 / 开发者 | 需要定位 Agent、Tool、provider 或任务拆解上的问题，但不想直接读日志。 |

### 3.2 典型使用时机

- 一个 Task 完成后，用户想检查结果来源。
- 文件发生变化后，用户想知道变化由哪个 Task 和动作引起。
- 系统要求过确认，用户想回看确认内容和自己的选择。
- Task 失败或结果不符合预期，用户想复盘过程。
- 系统给出 `warning` 或 `inconclusive` 审计判断，用户想查看原因。
- 用户需要判断系统能力边界和可信度。

---

## 4. 产品目标

### 4.1 第一版目标

第一版 Audit Page 要完成三件事：

1. **让用户看见证据链**：把 confirmation、action、observation、file change、risk、result、audit verdict 组织到 Session / Task 范围下。
2. **让用户理解关键行为**：用产品语言解释“发生了什么”和“为什么重要”，而不是展示原始事件名。
3. **让用户可回到主流程**：审计页只读；需要继续操作、重试或修复时，清楚回到 Main Page 的对应 Task。

### 4.2 非目标

第一版不追求：

- 完整日志检索系统。
- 开发者 trace debugger。
- 全量 EventStream payload 展示。
- 全量 LLM request / response 原文查看。
- 真正的时间旅行式执行回放。
- 合规报告导出。
- 多用户审批和权限审计。
- 复杂文件 diff viewer。
- 完整 Settings / configuration editor。
- 完整 Diagnostics / Logs viewer。

---

## 5. 页面边界

### 5.1 与 Main Page 的边界

| 关注点 | Main Page | Audit Page |
|---|---|---|
| 任务状态 | 主信息 | 作为证据上下文 |
| 用户确认 | 当前可操作动作 | 历史记录和证据 |
| 文件变更 | 摘要和验收入口 | 完整来源追踪 |
| Agent / Tool 使用 | 简化为责任或能力 | 展示关键参与链路 |
| 风险 | 用户可读警告 | 风险识别、处理和结论 |
| 日志 / 事件 | 默认隐藏 | 通过产品化记录按需检查 |

原则：

- Main Page 是 Control Plane，回答“现在该做什么”。
- Audit Page 是 Trust Plane，回答“之前发生了什么，为什么可信”。
- Audit Page 默认只读，不在页面内直接执行、确认、发布、重试或修改 Task。

### 5.2 与 Observability / Debugging 的边界

Audit Page 可以使用 observability 事实，但不是 observability 控制台。

| 能力 | Audit Page 第一版 | Debug / Observability 后续 |
|---|---|---|
| 用户可读时间线 | 包含 | 包含 |
| 关键 action / observation 摘要 | 包含 | 包含 |
| 原始 event payload | 默认不展示 | 可展示 |
| provider retry / latency detail | 默认不展示 | 可展示 |
| trace graph / span tree | 不包含 | 可包含 |
| metrics panel | 不包含 | 可包含 |
| replay control | 不包含 | 可包含 |

### 5.3 与 Settings / Logs 的边界

配置编辑不属于 Audit Page。用户应在 Settings、Session Controls 或 Task Advanced Panel 中配置系统行为。Audit Page 只展示与当前 Session / Task 相关的配置变更历史、当时有效配置摘要，以及跳转到配置管理面的入口。

日志查看不属于 Audit Page 主体。日志应进入独立的 Diagnostics / Logs 视图。Audit Page 可以在 record detail 中提供 `View related logs` 深链，但不把完整日志 timeline 嵌入审计页。

| 关注点 | 所属页面 | Audit Page 角色 |
|---|---|---|
| 配置编辑 | Settings / Session Controls / Task Advanced | 只读展示相关配置证据 |
| 配置变更历史 | Settings history + Audit relevant records | 展示当前 Session / Task 相关变更 |
| 日志 profile 切换 | Settings / Session Controls | 展示当时 logging profile |
| 原始日志查看 | Diagnostics / Logs | 提供相关日志深链 |
| 日志事实源 | Logging archive | 不作为审计事实源 |

---

## 6. 第一版审计范围

### 6.1 Scope

第一版支持两种审计范围：

| Scope | 用户含义 | 第一版能力 |
|---|---|---|
| Session audit | 查看一次 Workflow run 的整体过程 | 概览、关键记录、风险、确认、文件变更汇总 |
| Task audit | 查看一个 TaskNode 的过程 | Task 级时间线、确认、action、observation、文件、结果、verdict |

Task audit 是第一版最重要的粒度，因为 TaskNode 是 Plato 的最小交互锚点。

### 6.2 第一版审计对象

| 对象 | 用户问题 | 第一版展示方式 |
|---|---|---|
| Confirmation | 我确认过什么？ | prompt、选项、用户选择、时间、关联 Task |
| Action | 系统做了什么？ | 用户可读摘要、actor、时间、关联 observation |
| Observation | 动作结果是什么？ | 成功/失败、摘要、关键输出引用 |
| Audit Verdict | 审计怎么看这次动作？ | passed / warning / failed / inconclusive，加 rationale 和 concerns |
| Risk | 哪些风险被识别？ | 风险摘要、严重度、处理状态、是否用户确认 |
| File Change | 哪些文件变了？ | path、change type、摘要、来源 Task / action |
| Result | 结果是什么？ | 结果摘要、产物引用、关联证据 |
| Message | 用户或系统说了什么关键话？ | 只展示与审计相关的关键消息 |
| Config Change | 当时什么配置生效或发生变化？ | 预留；scope、domain、diff summary、actor、reason、effective time |

### 6.3 Draft / Published 边界

第一版优先审计 published Task 的执行过程。

Draft 阶段只保留轻量 lineage：

- RawTask / DraftTaskTree 如何进入 published Task。
- 用户是否编辑或发布了 TaskTree。
- Draft 和 published Task 的映射。

完整 draft authoring 审计不是第一版重点。

---

## 7. 核心用户路径

### 7.1 从 Task 进入审计

```text
用户在 Main Page 看到完成或失败的 Task
  -> 点击 Audit 入口
  -> 进入 Task audit
  -> 查看概览和关键记录
  -> 打开某条记录详情
  -> 理解证据
  -> 返回原 Task
```

成功体验：

- 用户知道自己正在审计哪个 Task。
- 用户能看到这个 Task 的关键事件和结果。
- 用户能找到文件变更和确认记录。

### 7.2 从 Session 进入审计

```text
用户在 Main Page 或 Session Header 进入 Audit
  -> 看到 Session audit overview
  -> 查看风险、确认、文件变更和异常记录
  -> 选择一个 Task 或 record 深入
```

成功体验：

- 用户能快速判断整个 Session 是否有值得关注的审计点。
- 用户能从 Session 概览钻取到 Task。

### 7.3 复盘风险动作

```text
用户筛选 Risks / Confirmations
  -> 找到风险动作
  -> 查看风险说明、确认 prompt、用户选择、后续 action 和结果
```

成功体验：

- 用户能回答“这个风险动作是否经过授权”。
- 用户能看到系统如何处理风险。

### 7.4 追踪文件变更

```text
用户筛选 File Changes
  -> 选择某个文件
  -> 查看关联 Task、action、summary 和 result
```

成功体验：

- 用户能回答“这个文件为什么被改”。
- 用户能从文件变化回到对应 Task。

---

## 8. 功能需求

| ID | 需求 | 优先级 |
|---|---|---|
| AP-PRD-001 | Audit Page 必须支持从 Main Page 的 Session 或 Task 入口进入。 | P0 |
| AP-PRD-002 | 页面必须清楚展示当前审计 scope：Session 或 Task。 | P0 |
| AP-PRD-003 | Task audit 必须展示关键时间线或证据列表。 | P0 |
| AP-PRD-004 | 页面必须展示用户确认历史，包括 prompt、选项、用户选择、时间和关联 Task。 | P0 |
| AP-PRD-005 | 页面必须展示文件变更摘要，并能关联到 Task 或 action。 | P0 |
| AP-PRD-006 | 页面必须展示结果摘要或产物引用，并说明关联的 Task。 | P0 |
| AP-PRD-007 | 页面必须展示风险和审计 verdict 的状态、原因和 concerns。 | P0 |
| AP-PRD-008 | 页面必须支持按 All、Confirmations、Actions、Risks、Files、Results、System 过滤。 | P1 |
| AP-PRD-009 | 每条审计记录必须有稳定时间、来源、类型、摘要、关联对象和可信状态。 | P0 |
| AP-PRD-010 | 审计记录详情必须能展示更完整的解释和 evidence references。 | P1 |
| AP-PRD-011 | 页面必须支持 empty、partial、loading、failed、inconclusive 状态。 | P0 |
| AP-PRD-012 | 页面必须提供返回 Main Page 原 Session / Task 的路径。 | P0 |
| AP-PRD-013 | 页面默认不展示 raw LLM/tool/provider payload。 | P0 |
| AP-PRD-014 | 页面必须对不可展示或不完整的数据给出清楚解释。 | P1 |
| AP-PRD-015 | Session audit 必须汇总关键数量：确认、风险、文件变更、失败或 inconclusive 记录。 | P1 |
| AP-PRD-016 | 页面应预留配置变更记录类型，用于展示与当前 Session / Task 相关的 config change。 | P2 |
| AP-PRD-017 | 审计记录详情应预留 `View related logs` 深链位，跳转到独立 Diagnostics / Logs 视图。 | P2 |

---

## 9. 披露与安全原则

Audit Page 应增加信任，但不能通过无边界披露制造新风险。

### 9.1 默认展示

默认可以展示：

- 用户可读摘要。
- 时间。
- 关联 Session / Task。
- actor 类型：user、agent、tool、system。
- confirmation prompt 和用户选择。
- 文件路径和变更类型。
- 风险摘要和处理状态。
- `AuditAgent` verdict、rationale、concerns。
- 结果摘要和产物引用。

### 9.2 默认不展示

默认不直接展示：

- 完整 LLM prompt。
- 完整 LLM response。
- tool call 原始参数。
- provider API response。
- token、secret、credential、环境变量。
- 内部 stack trace。
- 大型 payload 或二进制内容。

### 9.3 需要表达的不确定性

Audit Page 不应伪造确定性。

必须明确表达：

- 审计数据仍在生成。
- 只拿到 partial data。
- 审计结果 inconclusive。
- 某些证据因安全策略被隐藏。
- 某些旧任务没有完整审计事实。

---

## 10. 内容与文案原则

Audit Page 文案应：

- 使用用户能理解的语言。
- 优先说“发生了什么”和“为什么重要”。
- 避免让 event kind、message bus、SQLite row、provider retry 等内部术语成为主文案。
- 对风险保持克制，不夸大也不淡化。
- 对 `inconclusive` 保持明确，不把未知包装成通过。

推荐语气：

```text
清楚、克制、具体、可追溯。
```

不推荐语气：

```text
神秘、夸张、过度保证、开发者日志式。
```

---

## 11. 成功指标

### 11.1 用户理解指标

- 用户能说出当前审计的是 Session 还是 Task。
- 用户能找到自己确认过的风险动作。
- 用户能解释某个文件为什么被修改。
- 用户能说出某条 audit verdict 的含义。
- 用户不会把 Audit Page 当作执行控制台。

### 11.2 信任指标

- 用户在完成任务后更愿意接受结果或继续下一步。
- 用户能更快定位失败或异常原因。
- 用户对系统能力边界的判断更清楚。
- 用户不会因为底层术语或日志噪声感到失控。

### 11.3 产品质量指标

- P0 审计记录在 mock scenario 中完整覆盖。
- Task audit 主路径可以在真实或半真实数据下走通。
- `inconclusive`、partial、failed 状态都有明确展示。
- Main Page 不需要承担完整审计展示。

---

## 12. 第一版验收标准

第一版 Audit Page 可以认为达标，当：

1. 用户能从 Main Page 的 Task 或 Session 进入 Audit Page。
2. 用户能清楚看到当前审计 scope。
3. 用户能查看 Task 或 Session 的审计概览。
4. 用户能查看关键证据列表或时间线。
5. 用户能找到 confirmation、risk、file change、result、audit verdict。
6. 用户能打开一条审计记录详情。
7. 页面能表达 empty、partial、failed、inconclusive。
8. 页面默认不泄漏 raw LLM/tool/provider payload。
9. 用户能返回 Main Page 原上下文。
10. 至少一轮用户 walkthrough 能验证审计页增加信任而不是增加困惑。

---

## 13. 依赖

### 13.1 产品依赖

- Main Page 必须提供明确的 Audit 入口。
- Task / Session / Result / File Change Summary 的用户心智模型保持稳定。
- UX Flow 需要进一步定义进入、筛选、详情、返回等交互细节。
- Settings / Controls 后续需要承担配置编辑和完整配置历史。
- Diagnostics / Logs 后续需要承担日志归档查看和筛选。

### 13.2 技术依赖

- `EventStream` 提供执行期 Action / Observation。
- `MessageStream` 提供用户确认和关键 communication。
- `TaskInteractionTimelineService` 提供可回放时间线基础。
- `TaskProjectionService` 提供 Task / file / summary UI 投影。
- `AuditAgent` 提供部分 action 的 audit verdict。
- 后续 `ConfigStore` / `ConfigChange` 提供配置变更历史和 effective config snapshot。
- 后续 Diagnostics / Logs 视图从 session log manifest 读取日志归档。
- 后续需要 Audit Page 专用 ViewModel / Projection，不应让前端直接拼底层事件。

---

## 14. 风险与取舍

| 风险 | 表现 | 取舍 |
|---|---|---|
| 审计页变成日志页 | 用户看到大量底层事件，无法判断重点 | 第一版只展示产品化审计记录和证据摘要 |
| 信息过少 | 用户看不到足够证据，仍不信任 | 记录详情提供 evidence refs 和解释 |
| 信息过多 | 用户被 trace、payload、provider 细节淹没 | 默认摘要化，细节按需展开 |
| 过度确定 | 系统把未知说成已验证 | 明确展示 inconclusive 和 partial |
| 与 Main Page 职责混淆 | 用户在审计页尝试继续执行或修改 Task | 审计页只读，操作回主页面 |
| 后端事实源不完整 | 某些旧 Task 或失败路径缺少记录 | 明确显示数据缺失，不伪造完整性 |

---

## 15. 待定问题

1. 第一版是否需要 Session audit 和 Task audit 同时完整支持，还是先以 Task audit 为主？
2. 是否允许高级用户展开部分 sanitized payload？
3. `AuditAgent` verdict 状态应采用哪些用户可见标签？
4. 风险 severity 是否用固定等级，还是先用 warning / critical 的简化模型？
5. 文件变更是否需要第一版集成 diff viewer，还是只展示 path + summary + source？
6. 审计页是否需要长期保存用户的筛选状态？
7. 对没有完整 EventStream 的历史 Session，是否显示兼容模式？

---

## 16. 下一步

基于本 PRD，下一阶段进入 AP-002：

```text
docs/product/plato-audit-page-ux-flow.md
```

UX Flow 需要把本文中的产品目标转换成具体交互规格：

- 入口与返回。
- Session audit overview。
- Task audit overview。
- 时间线 / 证据列表。
- 筛选与分组。
- 审计记录详情。
- 空状态、partial、failed、inconclusive。
- 安全披露和折叠规则。
