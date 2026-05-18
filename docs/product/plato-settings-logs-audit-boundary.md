# Plato Settings, Logs, And Audit Boundary

> Status: product boundary draft
> Last Updated: 2026-05-17
> Scope: 重新考量用户配置、配置变更历史、日志查看与 Audit Page 的产品边界。本文用于给后续 Settings、Diagnostics / Logs、Audit Page 设计预留入口和信息关系，不要求本期实现完整页面。
> Related: [Audit Page PRD](plato-audit-page-prd.md), [Audit Page UX Flow](plato-audit-page-ux-flow.md), [Centralized Runtime Configuration](../plans/feature/centralized-runtime-configuration.md), [Configurable Logging System](../plans/feature/configurable-logging-system.md), [UN-104](../user_model/needs/UN-104-config-personality-visualization.md), [UN-105](../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md)

---

## 1. 核心判断

用户配置决定 Plato 的产品性格：

- 交互多寡；
- 审计强度；
- 日志详细程度；
- autonomy / confirmation 策略；
- LLM provider、model、thinking、retry；
- 工具权限、风险阈值、预算；
- result presentation 和 UI 密度。

因此，配置不是审计页的附属能力。配置应该是独立的 Settings / Controls 产品面；Audit Page 只负责解释“当时是什么配置，以及配置何时改变过”。

日志也不应该成为 Audit Page 主体。日志是技术用户和测试人员的调试工具；Audit Page 是用户可理解的证据链。两者可以互相链接，但不能混成一个页面。

---

## 2. 页面职责分工

| Surface | 主职责 | 用户问题 | 是否本期实现 |
|---|---|---|---|
| Global / Workspace Settings | 配置默认行为 | 我希望 Plato 默认如何工作？ | 预留 |
| Session Controls / Session Settings | 配置当前 Session 行为 | 这次会话要多谨慎、多详细、多自动？ | 预留轻入口 |
| Task Advanced Panel | 配置某个 Task 的特殊策略 | 这个 Task 是否需要强审计或更严格工具限制？ | 预留 |
| Audit Page | 查看证据链和配置变更历史 | 当时为什么这样做，什么配置生效？ | 当前审计设计预留 |
| Diagnostics / Logs | 查看调试日志 | 技术上到底发生了什么？ | 预留，不进本期主体 |

---

## 3. 用户在哪里配置

建议三层 UI 入口。

### 3.1 Global / Workspace Settings

适合长期默认值：

- 默认 LLM provider / model。
- 默认 autonomy preset。
- 默认 audit strength。
- 默认 logging profile。
- 默认 result presentation。
- 默认 tool / budget policy。
- UI density、主题和可视化偏好。

用户心智：

```text
以后我在这个工作区里，系统默认按这个性格工作。
```

### 3.2 Session Controls / Session Settings

适合当前会话的行为：

- 本 Session 的交互频率。
- 本 Session 的审计强度。
- 本 Session 的日志 profile。
- 本 Session 的预算上限。
- 本 Session 的结果展示方式。

推荐以 profile / preset 为主，不直接暴露完整 schema：

| Domain | 低门槛入口 |
|---|---|
| Interaction | Quiet / Balanced / Careful / Manual |
| Audit | Minimal / Standard / Detailed |
| Logging | Quiet / Normal / Debug LLM / Debug Tools / Full Debug |
| Result | Compact / Rich cards / Raw first |

用户心智：

```text
这次我希望系统更快，或更谨慎，或记录更多调试信息。
```

### 3.3 Task Advanced Panel

适合局部例外：

- 这个 Task 强制审计。
- 这个 Task 禁止某些工具。
- 这个 Task 必须确认高风险动作。
- 这个 Task 使用更详细日志。
- 这个 Task 的结果必须包装成卡片。

第一版不建议把 Task 配置做成大表单。可以先显示“Advanced”入口和当前有效策略摘要。

用户心智：

```text
这个任务比较特殊，我要单独提高约束。
```

---

## 4. 配置变更历史怎么看

配置变更历史应该有两个查看面。

### 4.1 Settings 中的完整历史

Settings / Controls 应提供完整配置历史：

- global / workspace / session / task scope；
- domain；
- actor；
- reason；
- accepted / rejected；
- validation errors；
- effective time；
- previous / new hash；
- diff summary；
- mutability：live / next_action / next_llm_call / next_task / next_session / static。

这是配置系统自己的管理面。

### 4.2 Audit Page 中的相关历史

Audit Page 只展示与当前 Session / Task 相关的配置变更：

- 当时有效配置摘要；
- 影响该 Task / Action 的配置变化；
- 例如 autonomy threshold、audit strength、logging profile、tool policy、LLM provider；
- rejected config patch 可以作为 system record 出现；
- secret 和敏感值必须脱敏。

Audit Page 不提供配置编辑，只提供解释和跳转。

推荐 record kind：

```text
config_change
effective_config_snapshot
config_validation_rejected
```

---

## 5. 配置与审计的关系

配置会解释系统行为。

Audit Page 应能回答：

- 为什么这个 Action 当时需要确认？
- 为什么这个 Task 被强审计？
- 为什么日志这次特别详细？
- 为什么 LLM provider / model 是这个？
- 为什么某个工具被允许或禁止？

但 Audit Page 不应该变成配置编辑器。

正确关系：

```text
Settings owns configuration editing.
ConfigStore owns configuration facts.
Audit Page shows relevant configuration evidence.
Diagnostics / Logs show technical traces.
```

---

## 6. 日志入口放哪里

日志应该是独立的 Diagnostics / Logs 视图，而不是 Audit Page 的一个大 tab。

推荐入口：

1. Session Header 的 advanced / diagnostics 入口。
2. Settings 的 Logging 区域。
3. Audit record detail 中的 `View related logs` 深链。
4. Failed Task / inconclusive verdict 的辅助入口。

默认 Main Page 不应把日志入口做成主操作。技术社区早期用户需要日志，但普通用户不应该被日志打断。

---

## 7. 日志如何呈现

日志展示应从 session manifest 开始，而不是让用户猜文件路径。

### 7.1 默认视图

默认给技术用户一个 pretty timeline：

```text
12:03:11 INFO  llm.request    task=T3 model=deepseek-chat tokens≈1200
12:03:14 INFO  tool.result    task=T3 tool=write_file success=true duration=31ms
12:03:15 WARN  gate.decision  task=T3 risk=0.72 requires_user=true
```

### 7.2 筛选

第一版 Logs 视图应预留：

- level：TRACE / DEBUG / INFO / WARNING / ERROR；
- category：llm、tool、action、observation、audit、risk、config、bus、agent；
- scope：session、task、agent、tool；
- time range；
- text search；
- payload mode：summary / expanded JSON / raw JSONL。

### 7.3 展开层级

| 层级 | 内容 | 默认 |
|---|---|---|
| Pretty | 人类可读短行 | 默认 |
| Expanded JSON | 单条结构化事件 | 按需展开 |
| Raw JSONL path | 文件路径 / manifest 引用 | 高级入口 |

日志 full payload 只在配置允许且日志实际记录了 full payload 时可见。UI 必须提醒敏感数据风险。

---

## 8. Audit Page 需要预留什么

Audit Page 本期不实现完整配置页和日志页，但应预留：

1. Record kind：`config_change`。
2. Detail 区域的 `Effective configuration` 摘要位。
3. Detail 区域的 `View related logs` 深链位。
4. System / Config filter 的扩展空间。
5. Overview 中的 `Audit detail level` 或 `Logging profile` 小型摘要位。

这些预留只需要保证布局和信息架构不排斥未来能力，不要求 AP-003 生成完整 Settings 或 Logs 页面。

---

## 9. 当前产品决策

当前建议：

1. **配置编辑不放 Audit Page。** 配置属于 Settings / Session Controls / Task Advanced。
2. **配置变更历史可以出现在 Audit Page。** 只展示当前 Session / Task 相关变更，用于解释行为。
3. **日志查看不放 Audit Page 主体。** 日志属于独立 Diagnostics / Logs 视图。
4. **Audit Page 可以深链到日志。** 从某条 record 进入相关日志筛选视图。
5. **日志不是事实源。** EventStream / MessageStream / ConfigStore 是产品事实源；logs 是调试和诊断辅助。
6. **早期技术用户要被照顾。** 通过 Session Header / Settings 提供 Diagnostics 入口，并让 Logs 视图足够可读。
7. **本期只预留入口。** 审计页当前仍以 evidence chain 为主，不扩张成配置中心或日志控制台。

---

## 10. 后续页面建议

后续可以独立推进两个页面或面板：

### 10.1 Settings / Controls

建议走完整页面流程：

```text
Settings PRD
  -> Settings UX Flow
  -> Figma Settings v0.1
  -> Mock config API
  -> Config API contract
```

### 10.2 Diagnostics / Logs

建议走完整页面流程：

```text
Diagnostics Logs PRD
  -> Logs UX Flow
  -> Figma Logs v0.1
  -> Mock log manifest and JSONL fixtures
  -> Logs API / archive contract
```

Audit Page 只负责保留入口和上下文关系。
