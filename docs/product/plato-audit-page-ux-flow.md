# Plato Audit Page UX Flow

> Status: draft
> Last Updated: 2026-05-17
> Scope: Audit Page 的 UX 交互规格。本文把 [Audit Page PRD](plato-audit-page-prd.md) 转换为可用于 Figma 设计、设计评审和后续 UI 实现的交互说明。
> Related: [Core Product Principles](core-product-principles.md), [Workflow, Session, And Task UX Model](workflow-session-task-ux-model.md), [Plato Audit Page PRD](plato-audit-page-prd.md), [Settings, Logs, And Audit Boundary](plato-settings-logs-audit-boundary.md), [Audit Page 项目实施计划](../plans/ui/audit-page-project-implementation-plan.md)

---

## 1. 目标

Audit Page UX 的目标是让用户在不阅读底层日志的情况下理解系统行为。

第一版交互应支持：

```text
从 Main Page 进入
  -> 确认审计范围
  -> 查看审计概览
  -> 浏览关键证据
  -> 筛选某类记录
  -> 打开记录详情
  -> 理解证据和不确定性
  -> 返回 Main Page 原上下文
```

页面必须服务 Trust Plane，不服务执行控制。用户可以查看、筛选、理解和返回，但不在 Audit Page 里修改、确认、发布、重试或继续执行 Task。

---

## 2. UX 原则

1. **先结论，再证据**：默认先展示概览和关键风险，再让用户进入完整记录。
2. **以 Session / Task 为范围**：用户不应看到数据库表、event stream、log file 作为主导航。
3. **以用户问题组织信息**：我确认了什么、系统做了什么、文件为什么变、风险怎么处理、结果从哪里来。
4. **细节按需展开**：raw payload、trace detail、provider detail 默认不展示。
5. **不伪造完整性**：partial、failed、inconclusive、hidden evidence 必须明确表达。
6. **只读审计**：审计页不承载执行动作；需要行动时返回 Main Page 的相关 Task。
7. **保持冷静**：风险和警告要清楚，但不能制造恐慌或过度确定。

---

## 3. 页面入口与退出

### 3.1 Task 入口

入口位置：

- Main Page 的 TaskNode detail。
- Done / Failed Task 的 result 或 file change 区域。
- Task card 的 audit affordance。

触发条件：

- Task 已有 result、file change、confirmation、event、risk 或 audit verdict 任一事实。
- 如果暂时没有完整审计事实，也允许进入 partial audit 状态。

进入后默认 scope：

```text
Audit scope = Task
Selected task = 入口 Task
Default filter = All
Default selected record = none
```

### 3.2 Session 入口

入口位置：

- Main Page 的 Session Header。
- Session summary 或 completed state。
- 全局 audit affordance。

进入后默认 scope：

```text
Audit scope = Session
Selected task = none
Default filter = All
Default selected record = most important issue if any, else none
```

重要性排序建议：

1. failed / warning / inconclusive audit verdict。
2. unresolved or high-risk confirmation history。
3. failed action / observation。
4. file change。
5. result summary。
6. normal message / system record。

### 3.3 返回 Main Page

页面必须提供明确返回路径：

- 从 Task audit 返回原 Task。
- 从 Session audit 返回原 Session。
- 从 record detail 中返回对应 Task。

返回后应尽量保持 Main Page 原上下文：

```text
session_id preserved
selected_task_ref preserved if available
task detail panel opened if user entered from task
```

禁止：

- 在 Audit Page 中直接处理 confirmation。
- 在 Audit Page 中直接 retry / cancel / publish / edit Task。
- 用浏览器后退作为唯一返回方式。

---

## 4. 信息架构

第一版建议使用稳定的工作台式结构：

```text
┌────────────────────────────────────────────────────┐
│ Audit Header: scope, session/task title, return     │
├────────────────────────────────────────────────────┤
│ Audit Overview: summary counts, risk/verdict state  │
├───────────────┬────────────────────────────────────┤
│ Filter Rail   │ Evidence Timeline / Record List     │
│ or Filter Bar │ + selected record detail drawer      │
└───────────────┴────────────────────────────────────┘
```

### 4.1 Audit Header

必须展示：

- 当前页面名称：Audit。
- 当前 scope：Session 或 Task。
- Session 名称或 Task 标题。
- Task 状态或 Session 状态。
- 返回 Main Page 的入口。

不展示：

- 原始 `session_id` / `task_id` 作为主视觉。
- provider、event stream、database 路径作为标题。

### 4.2 Audit Overview

作用：让用户快速知道这次审计有没有重点。

建议展示：

- 审计状态：complete / running / partial / failed。
- verdict summary：passed / warning / failed / inconclusive。
- 关键计数：confirmations、risks、file changes、actions、results。
- 最值得关注的问题摘要。

第一版不需要复杂图表。

### 4.3 Filter Area

第一版 filter：

| Filter | 含义 |
|---|---|
| All | 全部审计记录 |
| Confirmations | 用户确认历史 |
| Actions | 系统关键动作 |
| Risks | 风险、警告、audit verdict |
| Files | 文件变更 |
| Results | 结果和产物 |
| System | 系统状态、partial、failed、hidden evidence |
| Config | 预留；与当前 scope 相关的配置变更和 effective config snapshot |

交互规则：

- 切换 filter 不改变 scope。
- 切换 filter 后清空 selected record，除非当前 record 仍属于新 filter。
- filter 应显示数量，但数量为 0 时仍可点击并显示空态。
- 第一版不要求全文搜索。

### 4.4 Evidence Timeline / Record List

记录列表是页面主体。

每条 record 至少展示：

- 时间。
- kind：confirmation、action、observation、risk、file、result、system、config。
- actor：user、agent、tool、system。
- 用户可读摘要。
- severity 或 verdict 状态。
- 关联对象：Task、file、result、action、confirmation。
- 是否 partial / hidden / inconclusive。

排序：

- 默认时间升序，支持用户理解过程。
- Session audit 可以在 overview 中突出重点，但 record list 仍保持时间顺序。

### 4.5 Record Detail

记录详情可以是右侧 drawer、下方 detail panel 或单独 detail view。第一版推荐 drawer，因为用户能保留时间线上下文。

详情必须回答：

- 发生了什么？
- 为什么重要？
- 证据来自哪里？
- 与哪个 Task / file / result / confirmation 相关？
- 是否完整、是否隐藏了部分证据、是否 inconclusive？

详情不默认展示 raw payload。

---

## 5. 核心状态

### 5.1 Loading

用户目标：

- 知道正在加载审计事实。

页面反馈：

- Header 可先显示 Session / Task 上下文。
- Overview 和 record list 使用轻量 loading state。

禁止：

- 显示空白页面。
- 让用户误以为没有审计记录。

### 5.2 Empty

触发：

- 当前 scope 没有任何可展示审计记录。

页面反馈：

- 明确说明该 Task / Session 暂无审计记录。
- 如果 Task 仍是 draft 或尚未执行，说明原因。
- 提供返回 Main Page。

禁止：

- 说“审计通过”。
- 伪造 passed verdict。

### 5.3 Running / Generating

触发：

- Task 或 Session 仍在执行，审计记录还在产生。

页面反馈：

- Overview 标记 `Audit still updating`。
- 已有 records 正常展示。
- 新记录出现时保持用户当前筛选和 selected record。

禁止：

- 把当前记录当作最终完整结论。

### 5.4 Partial

触发：

- 只有部分事实源可用。
- 某些 evidence 因策略隐藏。
- 历史 Session 没有完整 EventStream。

页面反馈：

- Overview 显示 partial 状态。
- 相关 record 标注 partial 或 hidden。
- Detail 中说明缺失原因。

禁止：

- 在 partial 情况下显示 complete。

### 5.5 Failed To Load

触发：

- 审计事实查询失败。
- ViewModel / Projection 构建失败。

页面反馈：

- Header 保留上下文。
- Overview 显示 audit data unavailable。
- 提供 retry load。
- 提供返回 Main Page。

禁止：

- 影响 Main Page 的 Task 状态。
- 隐式重跑 Task。

### 5.6 Inconclusive

触发：

- AuditAgent 或审计规则无法判断。
- 证据不足以支持 passed / failed。

页面反馈：

- 使用明确的 inconclusive 状态。
- 说明原因，例如证据不足、执行结果缺失、观察结果不可验证。
- 给出可追踪的 evidence refs。

禁止：

- 把 inconclusive 当作 warning 或 passed。

---

## 6. 核心流程

### 6.1 Flow A: 从 Task 查看审计

```text
Main Page TaskNode
  -> click Audit
  -> Task Audit Page
  -> read overview
  -> open record
  -> return to Task
```

用户目标：

- 理解这个 Task 的执行过程和结果可信度。

页面初始状态：

- scope = Task。
- Header 显示 Task 标题、状态、所属 Session。
- Overview 显示该 Task 的 verdict / risks / confirmations / file changes。
- Record list 显示该 Task 的 records。

可用动作：

- 切换 filter。
- 选择 record。
- 打开 evidence detail。
- 跳转到相关 file / result 引用。
- 返回 Main Page 原 Task。

禁止动作：

- 修改 Task。
- 处理 confirmation。
- retry Task。

退出标准：

- 用户能说出该 Task 做了什么、有没有风险、结果和文件变更来自哪里。

### 6.2 Flow B: 从 Session 查看审计

```text
Main Page Session Header
  -> click Audit
  -> Session Audit Page
  -> read overview
  -> select important record or task
  -> drill into Task audit if needed
```

用户目标：

- 复盘整个 Session，判断是否有需要关注的问题。

页面初始状态：

- scope = Session。
- Overview 显示整体审计状态和关键数量。
- Record list 展示跨 Task 的关键记录。

可用动作：

- 切换 filter。
- 选择 record。
- 从 record 进入相关 Task audit。
- 返回 Main Page Session。

禁止动作：

- 在 Session audit 中直接修改某个 Task。
- 把 Session 概览当成所有 Task 的最终质量结论。

退出标准：

- 用户能判断整个 Session 是否有风险、失败、inconclusive 或值得复盘的文件变更。

### 6.3 Flow C: 复盘确认动作

```text
Audit Page
  -> filter Confirmations
  -> select confirmation record
  -> inspect prompt, options, user choice, result
```

用户目标：

- 确认某个风险动作是否经过用户授权。

详情必须展示：

- prompt。
- options。
- default option。
- user choice。
- resolved time。
- related Task。
- related action / result if available。

可用动作：

- 跳转到相关 Task。
- 查看后续 action / observation。

禁止动作：

- 修改历史确认结果。
- 重新处理 confirmation。

退出标准：

- 用户能回答“我当时是否确认过，以及确认了什么”。

### 6.4 Flow D: 追踪文件变更

```text
Audit Page
  -> filter Files
  -> select file change
  -> inspect source Task/action/result
```

用户目标：

- 理解某个文件为什么被改。

详情必须展示：

- path。
- change type。
- summary。
- related Task。
- related action / observation if available。
- related result if available。

第一版不要求完整 diff viewer。

可用动作：

- 返回相关 Task。
- 查看 result reference。

禁止动作：

- 在 Audit Page 中直接 revert、accept 或 edit file。

退出标准：

- 用户能把文件变化归因到具体 Task 或 action。

### 6.5 Flow E: 查看风险与审计 verdict

```text
Audit Page
  -> filter Risks
  -> select risk or verdict
  -> inspect rationale and concerns
```

用户目标：

- 判断系统对某个动作或结果的审计结论。

详情必须展示：

- verdict：passed / warning / failed / inconclusive。
- rationale。
- concerns。
- intent_met if available。
- scope_respected if available。
- audited action / observation if available。

可用动作：

- 查看关联 action / observation。
- 返回相关 Task。

禁止动作：

- 将 warning 自动升级为 failed。
- 将 inconclusive 显示为 passed。

退出标准：

- 用户能理解 verdict 的含义和限制。

### 6.6 Flow F: 返回主流程

```text
Audit Page
  -> click Return to Task / Return to Session
  -> Main Page
  -> original context restored
```

用户目标：

- 审计后继续控制任务。

返回规则：

- 从 Task audit 返回时，Main Page 选中原 Task。
- 从 Session audit 返回时，Main Page 保留原 Session。
- 从 record detail 进入 Task audit 后返回，应优先返回该 Task。

禁止：

- 丢失 Session 上下文。
- 返回到无关默认页面。

---

## 7. Record Detail 规格

### 7.1 通用 detail 结构

每类 record detail 建议包含：

1. 标题：用户可读摘要。
2. 状态：severity / verdict / completion state。
3. Context：Session、Task、actor、time。
4. Explanation：发生了什么，为什么重要。
5. Evidence：关联 confirmation、action、observation、file、result。
6. Disclosure note：是否隐藏、脱敏、partial、inconclusive。
7. Configuration context：预留；当时有效配置摘要或相关配置变更。
8. Diagnostics link：预留；查看相关日志的深链。
9. Navigation：返回列表、查看相关 Task。

### 7.2 Disclosure 层级

第一版只定义三层披露：

| 层级 | 展示内容 | 默认 |
|---|---|---|
| Summary | 用户可读摘要和关键字段 | 默认展开 |
| Evidence refs | 关联对象、id、时间、来源 | 默认可见 |
| Sanitized detail | 脱敏后的字段片段 | 默认折叠或暂不提供 |

不提供：

- raw prompt。
- raw response。
- raw tool args。
- secret-bearing environment。

### 7.3 配置与日志预留

Record detail 应预留两个未来能力，但不在本期展开完整页面：

| 预留位 | 用途 | 本期行为 |
|---|---|---|
| Effective configuration | 展示影响该 record 的配置摘要，例如 audit strength、autonomy、logging profile、tool policy | 可留为空或展示 disabled placeholder |
| View related logs | 跳转到独立 Diagnostics / Logs 视图，并带上 session、task、action、category 过滤条件 | 可显示为不可用或隐藏 |

规则：

- 配置编辑不在 Audit Page 中发生。
- 完整日志 timeline 不嵌入 Audit Page。
- 如果未来 record 有 `config_change` kind，应进入 Config filter。
- 如果 future log deep link 不可用，不影响审计主路径。

---

## 8. Figma 最低画面

Figma v0.1 至少需要以下 frames：

1. Task audit default：有 overview、filter、record list。
2. Task audit with selected record detail。
3. Session audit overview。
4. Confirmations filter。
5. Files filter。
6. Risks / verdicts filter。
7. Empty audit state。
8. Running / partial audit state。
9. Failed to load state。
10. Inconclusive verdict detail。
11. Return to Main Page context。
12. Record detail with reserved configuration / related logs affordances。

每个 frame 必须体现：

- 当前 scope。
- 返回入口。
- 记录数量或空态。
- 至少一条用户可读 record。
- 不把 raw payload 当作主内容。

---

## 9. 文案样例

推荐文案：

| 场景 | 文案方向 |
|---|---|
| 页面标题 | Audit |
| Task scope | Auditing task: `<task title>` |
| Session scope | Auditing session: `<session title>` |
| partial | Some evidence is not available yet. |
| inconclusive | Audit could not reach a conclusion from available evidence. |
| hidden evidence | Some details are hidden by the disclosure policy. |
| file source | This file change is linked to `<task title>`. |
| return | Return to task |

中文 UI 可以翻译为：

- 审计。
- 正在审计任务：`<任务标题>`。
- 正在审计会话：`<会话标题>`。
- 部分证据暂不可用。
- 当前证据不足以形成审计结论。
- 部分细节已按披露策略隐藏。
- 此文件变更来自 `<任务标题>`。
- 返回任务。

---

## 10. 设计评审 Checklist

进入 UI 代码前，设计评审必须确认：

- 用户能一眼看出当前是 Session audit 还是 Task audit。
- 用户能找到确认记录、风险、文件变更、结果、verdict。
- 用户能打开 record detail 并理解证据来源。
- partial、failed、inconclusive 不会被误解成 passed。
- 页面没有默认展示 raw LLM/tool/provider payload。
- 配置编辑和完整日志查看没有被塞进 Audit Page 主体。
- 页面没有承载执行动作。
- 返回 Main Page 的路径明确。
- 视觉气质冷静、结构化、可信，不像日志控制台。

---

## 11. 第一版验收标准

UX Flow 通过后，应满足：

1. Figma 可以根据本文生成 Audit Page v0.1。
2. 每个关键状态都有用户目标、页面反馈、可用动作、禁止动作。
3. PRD 中的 P0 功能需求都有对应交互。
4. 页面边界保持只读审计，不与 Main Page 控制职责混淆。
5. 安全披露和不确定性表达有明确规则。

---

## 12. 下一步

基于本 UX Flow，进入 AP-003：

```text
Figma Audit Page v0.1
```

设计稿应先覆盖最低 frame，不追求完整视觉细节。第一轮评审重点是信息层级、审计心智模型、scope 识别、record detail 和不确定性表达。
