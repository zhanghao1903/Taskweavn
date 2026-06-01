# Plato Audit Page 项目实施计划

> Status: active implementation / real HTTP path and disclosure first pass ready
> Last Updated: 2026-06-01
> Scope: 重新推进 Plato / TaskWeavn Audit Page，从产品 PRD 到用户测试的完整交付链路。
> Reference: [Plato MVP 实施计划](../../product/plato-mvp-implementation-plan.md)
> Technical Design: [Audit Page Frontend Technical Design](audit-page-frontend-technical-design.md)
> Disclosure Design: [Audit Page Sanitized Payload Disclosure Technical Design](audit-page-sanitized-payload-disclosure-technical-design.md)
> Runtime Event Design: [Audit Page Runtime Event And Refetch Technical Design](audit-page-runtime-event-refetch-technical-design.md)
> Readiness Notes: [Audit Page AP-005 Readiness Notes](audit-page-readiness-notes.md)

---

## 1. 目标

本计划用于把 Audit Page 从已有产品原则和事件能力推进为可评审、可运行、可联调、可测试的第一版产品体验。

Audit Page 的产品定位是 Trust Plane。它不是主工作台，不承担日常推进任务的职责；它负责在用户需要追问、复盘、验证或排查时，让系统行为变得可解释、可追溯、可重建。

第一版目标是走通一条可信审计路径：

```text
用户从 Main Page 的 Task 或 Session 进入 Audit Page
  -> 看到本次 Session / Task 的审计概览
  -> 过滤关键事实：用户确认、Agent/Tool 行为、风险、文件变更、结果
  -> 进入某条审计记录详情
  -> 理解系统为什么这样做、证据来自哪里、与哪些结果相关
  -> 返回 Main Page 继续控制任务
```

Audit Page 应回答：

1. 为什么系统这样做？
2. 哪个 Agent、Tool、provider 或系统协议参与了？
3. 用户确认过什么？
4. 哪些文件在什么时候发生变化？
5. 哪些风险被识别、被确认或被规避？
6. 这个过程能否被追踪或重建？

---

## 2. 范围

### 2.1 本轮包含

- Audit Page 产品 PRD。
- Audit Page UX 交互规格。
- Figma 设计稿 / 可点击原型。
- 设计评审与微调记录。
- Audit Page 前端组件代码。
- Mock 数据和 mock scenario 联调。
- Audit Page 后端 API 合约收敛。
- UI 到真实后端审计事实源的通信。
- 第一轮用户测试。

### 2.2 本轮不包含

- 全量日志查询控制台。
- 开发者级 trace debugger。
- 任意事件 payload 的完整原文暴露。
- LLM request / response 原始内容的无边界展示。
- 完整回放执行引擎。
- 权限系统、团队审计审批流、合规报表导出。
- 复杂 diff viewer。
- Agent marketplace 或 provider 配置页。

Audit Page 第一版应是用户可理解的审计产品页面，而不是把 EventStream、MessageStream、logging 和 SQLite row 原样摊开。

---

## 3. 当前基线

### 3.1 已有产品与 UX 基础

- [Core Product Principles](../../product/core-product-principles.md)：定义 Main Page 是 Control Plane，Audit Page 是 Trust Plane。
- [Workflow, Session, And Task UX Model](../../product/workflow-session-task-ux-model.md)：定义 Audit Record 是 trust、replay、debugging surface。
- [Plato MVP 实施计划](../../product/plato-mvp-implementation-plan.md)：定义 PRD 到用户测试的推荐顺序；MVP 只要求 Audit 入口可见，完整审计页后续推进。
- [Plato Audit Page PRD](../../product/plato-audit-page-prd.md)：定义 Audit Page 第一版的用户目标、边界和信任问题。
- [Plato Audit Page UX Flow](../../product/plato-audit-page-ux-flow.md)：定义 Session / Task audit 的主要用户路径、状态和交互规则。
- [Settings, Logs, And Audit Boundary](../../product/plato-settings-logs-audit-boundary.md)：定义 Audit Page 与 Settings / Logs / Diagnostics 的边界。
- [UI Information Architecture](information-architecture.md)：定义主页面区域关系；Audit Page 应从 Task / Session 入口进入，而不是挤入主工作区。
- [UI API 接口归档](ui-api-interfaces.md)：已有 `getTaskTimeline`、`getTaskSnapshot` 等可回放时间线语义。
- [Observability Plan](../observability.md)：提供 trace、timeline、task tree、replay 等长期能力方向。
- [Audit Page Backend-To-Frontend Contract](../../engineering/audit-page-contract.md)：定义 Audit Page backend/frontend transport contract、mock scenarios 和实现状态。
- [Audit Page Frontend Technical Design](audit-page-frontend-technical-design.md)：定义基于 Figma v0.1 静态稿的路由、ViewModel、组件、状态、API、测试和实施切片。
- [Audit Page Sanitized Payload Disclosure Technical Design](audit-page-sanitized-payload-disclosure-technical-design.md)：定义 record/evidence detail 的安全 evidence disclosure、脱敏策略、API 行为和实施切片。
- [Audit Page Runtime Event And Refetch Technical Design](audit-page-runtime-event-refetch-technical-design.md)：定义 Audit Page runtime events、scope matching、cursor、refetch 策略和 AP-013 实施切片。

### 3.2 已有后端基础

- `EventStream`：记录执行期 Action / Observation 等事实，是审计和回放的骨架。
- `MessageStream`：记录用户可见的 Session communication，是产品叙事和确认历史的基础。
- `TaskInteractionTimelineService`：已能把 draft、message、confirmation、event、file、summary 串成只读时间线。
- `TaskProjectionService`：已能投影 Task card/detail、message、confirmation、file change、summary 等 UI-facing ViewModel。
- `AuditAgent`：已存在执行后审计能力，当前主要针对 `CodeAction`，产出 `AuditObservation` 和 verdict。
- `FileChangeStore` / `TaskSummaryStore`：为文件变更和结果摘要提供事实源。
- `src/taskweavn/server/ui_contract/view_models.py`、`snapshots.py`、`events.py` 已有 Audit Page additive backend contract models 和 audit event builders。

### 3.3 已有前端 contract / mock 基线

- `frontend/src/shared/api/types.ts` 已有 Audit Page snapshot、request、overview、filter、record、detail、evidence、permission、page-state 等类型。
- `frontend/src/shared/api/platoApi.ts` 已有 `getAuditSnapshot`、`listAuditRecords`、`getAuditRecordDetail`、`getEvidenceDetail`。
- `frontend/src/app/routes.ts` 已有 session/task audit route constants 和 builders。
- `frontend/src/entities/audit/model.ts` 已有 Audit Page contract helpers。
- `frontend/src/pages/audit-page/mockAuditScenarios.ts` 和 `mockAuditApi.ts` 已有 A1-A14 mock scenarios 与 mock API。
- `frontend/src/shared/api/apiUiMapping.ts` 已有 Audit Page API state 到 UI boundary 的映射。
- `frontend/src/app/platoRuntime.ts` 已能创建 mock/http audit API。
- 相关测试已覆盖 audit API types、routes、API client methods、mock scenarios/API、runtime creation、API-to-UI boundary mapping。

### 3.4 关键缺口

- Audit Page React route、page shell、overview/filter/timeline/detail、boundary states 已完成第一轮 mock-backed 实现。
- `frontend/src/app/App.tsx` 已挂载 Audit Page session/task routes。
- Main Page `View audit` 已在 Audit Page route 可用时启用，并导航到 mock-backed Audit Page；显式 fallback 仍可禁用入口。
- AP-005A-G 已完成第一轮实现和验证：路由、layout shell、overview/filter/timeline、record detail、A1-A14 boundary coverage、Main Page entry routing、visual/accessibility polish。
- 后端已实现 Audit Page HTTP routes、query gateway 和 projection-backed
  真实聚合第一版，并已开始接入 EventStream/log/config source references。
- `TaskInteractionTimeline` 的 event 展示仍偏底层，缺少用户可理解的审计摘要和分组。
- `AuditAgent` 当前是局部能力，不覆盖完整审计页需要的 Session / Task / confirmation / file / risk / result 关系。
- Sanitized payload disclosure 已完成第一版 contract tests、后端 request-time
  生成/注入和前端 detail panel 展示；仍需随更多 source 继续扩展策略。
- 已有 [runtime audit event/refetch 技术设计](audit-page-runtime-event-refetch-technical-design.md)，
  Audit Page route 已接入前端 runtime event router/hook 并用 mock
  subscription 覆盖 event-to-refetch 行为；前端已补充 live refresh/stale/
  disconnected 状态承载；后端 runtime source 尚未发出 audit-specific
  events。
- Audit Page 设计稿/原型状态本次未重新验证；下一轮设计对齐或高保真改版前应重新确认当前 canonical Figma/UX 是否足够。
- 小于当前支持最小宽度的移动端布局仍是后续 polish，不阻塞 mock walkthrough。

---

## 4. 实施原则

1. Audit Page 展示证据链，不展示无组织日志堆。
2. 默认以 Session 和 Task 为审计边界，而不是以数据库表或日志文件为边界。
3. 普通用户先看到摘要、风险、确认、文件和结果；高级细节按需展开。
4. 审计事实应来自 ViewModel / Projection，不让前端直接拼 SQLite row、EventStream payload 或日志文本。
5. Main Page 只保留审计入口和轻量摘要；完整证据进入 Audit Page。
6. 每条审计记录必须能说明来源、时间、关联对象和可信程度。
7. 原始 LLM、tool、provider payload 默认不直接展开；第一版使用摘要、字段白名单和安全引用。
8. 审计页只读；任何修复、重试、确认、继续执行动作都应回到 Main Page 或明确的 Task 操作入口。
9. Mock UI 先验证用户是否理解审计，再收敛 API 合约。
10. 审计体验要符合 Plato 的冷静、清晰、克制、可信方向。

---

## 5. 阶段计划

### Phase 0: 项目重基线

状态：已完成，并在 2026-05-30 按当前代码事实刷新。

目标：确认 Audit Page 当前产品、架构和代码事实，避免把审计页误做成日志页。

产出：

- 本实施计划。
- Audit Page 现状清单。
- Audit Page 本轮不做事项清单。
- 事实源映射草图：EventStream、MessageStream、TaskInteractionTimeline、AuditAgent、FileChangeStore、TaskSummaryStore。

验收标准：

- 团队确认本阶段只推进 Audit Page。
- Main Page 和 Audit Page 边界清楚。
- 审计页第一版的用户目标清楚。
- 后续每个阶段有明确文档或代码产物。

### Phase 1: 产品 PRD

状态：已有草案，可随 UI 实现继续迭代。

目标：定义 Audit Page 第一版到底解决什么信任问题。

产出：

```text
docs/product/plato-audit-page-prd.md
```

必须覆盖：

- 产品一句话定义。
- 目标用户与使用时机。
- 审计页和主页面的边界。
- Session-level audit 和 Task-level audit 的第一版范围。
- 用户要回答的问题。
- 第一版包含和不包含。
- 审计对象：confirmation、action、observation、audit verdict、file change、risk、result、message。
- 安全披露原则：摘要、脱敏、折叠、原始引用。
- 成功指标。

验收标准：

- 普通用户为什么进入审计页是清楚的。
- 审计页不是调试台、不是日志浏览器的边界清楚。
- PRD 可以直接进入 UX 规格阶段。

### Phase 2: UX 交互规格

状态：已有草案，可作为第一版 UI 实现输入；若 Figma 结果与实现偏差较大，应回写修订。

目标：把 PRD 转成可用于 Figma 生成和设计评审的交互规格。

产出：

```text
docs/product/plato-audit-page-ux-flow.md
```

必须覆盖：

- 从 Main Page 进入 Audit Page 的入口规则。
- Session audit overview。
- Task audit overview。
- Timeline / evidence list。
- 过滤与分组：All、Confirmations、Actions、Risks、Files、Results、System。
- 审计记录详情抽屉或详情页。
- 用户确认记录的前后文。
- 文件变更记录与 Task/result 的关联。
- `AuditObservation` / verdict 的展示方式。
- 空状态、无审计记录、审计仍在生成、审计失败或 inconclusive。
- 返回 Main Page 的上下文保持规则。

验收标准：

- 每个关键状态都有用户目标、系统反馈、可用动作、禁止动作。
- UX 规格不依赖用户理解 EventStream、MessageBus、SQLite、provider retry 等内部名词。
- Figma 设计可以直接按规格展开。

### Phase 3: Figma 设计稿 / 原型

状态：待确认。本次事实刷新未重新验证 canonical Figma 文件中的 Audit Page 设计状态。

目标：产出可评审的 Audit Page 第一版设计稿和关键状态原型。

建议产出：

- Figma Audit Page v0.1。
- 关键状态 frame。
- 从 Main Page `AuditEntryPoint` 进入 Audit Page 的简单点击原型。

最低 frame：

1. Session audit overview。
2. Task audit overview。
3. 审计时间线默认态。
4. 筛选为 confirmations。
5. 筛选为 file changes。
6. 筛选为 risks / audit verdicts。
7. 审计记录详情抽屉。
8. 无审计记录或审计仍在生成。
9. 审计 inconclusive / partial data。
10. 从详情返回 Main Page 的上下文态。

验收标准：

- 用户一眼能看出这是审计页，不是执行页。
- 用户能找到风险、确认、文件、结果和关键系统行为。
- 详情层级足够解释“为什么”，但不会默认压倒用户。
- 视觉符合 Plato 的冷静、清晰、可追溯、可信方向。

### Phase 4: 设计评审与微调

状态：待执行。AP-005 mock baseline 已可评审；后续应基于浏览器实现而不是只基于静态稿做轻量评审。

目标：在写代码前解决审计心智模型、信息层级和披露边界问题。

建议产出：

```text
docs/plans/ui/audit-page-design-review-notes.md
```

评审重点：

- 用户是否知道自己正在查看 Session 审计还是 Task 审计。
- 用户是否能用页面回答“为什么系统这样做”。
- 用户是否能定位自己确认过的事项。
- 用户是否能看清文件变更与 Task / result 的关系。
- 风险和 `AuditAgent` verdict 是否可理解、不过度制造确定性。
- 底层系统细节是否被放在合适层级。
- raw payload 是否有清楚的隐藏、脱敏或引用策略。
- 返回 Main Page 的路径是否明确。

验收标准：

- 所有 P0/P1 交互问题有处理结论。
- Figma 更新到 v0.2。
- UI 组件实现可以开始。

### Phase 5: UI 组件代码

状态：已完成第一轮 mock-backed baseline，可继续通过评审反馈微调。

目标：把设计稿落成可运行的 Audit Page 前端 shell。

技术方案：

```text
docs/plans/ui/audit-page-frontend-technical-design.md
```

建议产出：

```text
frontend/
```

建议沿用 [Frontend Framework Technical Design](frontend-framework-design.md) 的技术栈与 typed API 边界。

核心组件：

- `AuditPageShell`
- `AuditHeader`
- `AuditScopeSwitcher`
- `AuditOverviewPanel`
- `AuditTimeline`
- `AuditTimelineEntry`
- `AuditFilterBar`
- `AuditRecordDetail`
- `AuditEvidenceLink`
- `AuditConfirmationBlock`
- `AuditFileChangeBlock`
- `AuditRiskBlock`
- `AuditVerdictBadge`
- `AuditEmptyState`
- `ReturnToTaskLink`

验收标准：

- 页面可本地启动。
- Session scope 和 Task scope routes 已可渲染。
- 能过滤 confirmation、risk、file、result、system 等记录。
- 能打开审计记录详情。
- 组件通过 `AuditApi` / `PlatoApi` 边界加载 snapshot/detail/evidence，不直接在页面内拼 fixture。

### Phase 6: Mock 数据联调

状态：已完成第一轮联调；A1-A14 作为 AP-005E/AP-005G 验收 fixture。

目标：用 mock scenarios 走通第一版审计体验。

已具备：

```text
frontend/src/pages/audit-page/mockAuditScenarios.ts
frontend/src/pages/audit-page/mockAuditApi.ts
```

当前 mock scenarios 覆盖：

1. Empty / no audit records。
2. Loading。
3. Records ready。
4. Record selected。
5. Partial evidence。
6. Hidden evidence。
7. Warning verdict。
8. Failed verdict。
9. Inconclusive verdict。
10. Not available。
11. Permission denied。
12. Stale snapshot。
13. Query error。
14. Evidence load error。

验收标准：

- 不接真实后端也能完成完整审计 walkthrough。
- mock scenario 能驱动设计评审和用户测试彩排。
- 组件状态来自 API client，不来自页面内硬编码。
- mock 数据覆盖成功、风险、缺失、失败、inconclusive 五类情况。
- AP-005G 已完成桌面/平板浏览器 smoke 和 accessibility/focus polish。

### Phase 7: 后端 API 合约

状态：基础 contract 已完成，真实后端 route/gateway/aggregation 已完成第一版；
前端 runtime event-to-refetch baseline 已完成；后端 live event source/emission
仍待做。

目标：把 mock API 收敛为真实后端可实现的 Audit Page 合约。

已具备主 contract：

```text
docs/engineering/audit-page-contract.md
```

必须收敛：

- Query：
  - `getAuditEntryPoint(session_id, task_ref?)`
  - `getAuditOverview(session_id, scope)`
  - `listAuditRecords(session_id, scope, filters, cursor?)`
  - `getAuditRecord(session_id, audit_record_id)`
  - `getAuditTimeline(session_id, scope, filters)`
  - `getAuditEvidence(session_id, evidence_ref)`
- Event：
  - `audit.record.created`
  - `audit.record.updated`
  - `audit.summary.updated`
  - `audit.verdict.created`
  - `audit.evidence.available`

建议 ViewModel：

- `AuditEntryPointView`
- `AuditScope`
- `AuditOverviewView`
- `AuditRecordView`
- `AuditTimelineView`
- `AuditEvidenceRef`
- `AuditRecordDetailView`
- `AuditDisclosurePolicy`

验收标准：

- Mock API 和真实 API 使用同一套 TypeScript contracts。
- 后端返回审计 ViewModel，不返回裸 EventStream event 或 SQLite row。
- 每条 record 有稳定 id、时间、scope、source、kind、summary、severity、evidence refs。
- `TaskInteractionTimeline` 和 EventStream / MessageStream 的关系清楚。
- payload 披露策略写入合约。

### Phase 8: 真后端通信

状态：真实路径第一阶段已完成，并已开始后端 source hardening。前端 HTTP
client 方法已经存在；后端已补上 projection-backed audit routes/gateway，
可返回 session/task audit snapshot、records、record detail、evidence detail。
当前 gateway 还能在 source 存在时折叠 EventStream action/observation、
AuditObservation、session log archive、logging manifest config 记录。完整
timeline 和 runtime audit events 仍是后续增强；sanitized payload disclosure
已完成第一版 request-time implementation。

目标：把前端从 mock audit API 切到真实审计事实源。

建议顺序与当前状态：

1. Audit entry point 查询。已完成第一版。
2. Session audit overview 查询。已完成 projection-backed 第一版。
3. Task audit overview 查询。已完成 projection-backed 第一版。
4. Audit timeline 查询。待做，需要接入 `TaskInteractionTimelineService`。
5. Confirmation records 查询。已完成 projection-backed 第一版。
6. File change records 查询。已完成 projection-backed 第一版。
7. Result / summary evidence 查询。已完成 projection-backed 第一版。
8. `AuditObservation` / verdict 查询。已完成 EventStream-backed 第一版。
9. EventStream action / observation 摘要查询。已完成第一版。
10. Audit record detail 查询。已完成第一版。
11. Evidence refs 查询。已完成第一版。
12. Config/log references。已完成第一版：session log manifest 与 log archive
    file references。
13. Sanitized payload disclosure。已完成第一版 contract hardening、后端
    request-time 生成/注入和前端 detail/evidence 展示；更多 source 策略仍是
    follow-up。
14. Runtime audit event/refetch。AP-013A 技术设计已完成，AP-013B 前端
    event router/hook 与 mock subscription 测试已完成，AP-013C live
    refresh/stale/disconnected 状态承载已完成；live source 和 runtime
    emission 仍待做。

验收标准：

- UI 可以用真实后端完成 Session / Task 审计主路径。
- 页面刷新后能恢复相同审计状态。
- 审计详情能正确关联 confirmation、action、observation、file、summary。
- raw payload 默认不泄漏到 UI。
- mock mode 仍可保留用于设计、测试和演示。

### Phase 9: 用户测试

状态：待执行。应在 mock UI walkthrough 和至少一条真实后端路径之后进行。

目标：验证 Audit Page 是否真的增加信任，而不是增加认知负担。

建议产出：

```text
docs/user_cases/UC-007-audit-page-trust-flow.md
docs/user_cases/terminal_outputs/UC-007-audit-page-trust-flow.txt
```

测试任务：

1. 从一个完成的 Task 进入 Audit Page。
2. 找到用户曾经确认过的风险动作。
3. 找到某个文件为什么被修改。
4. 找到系统执行过的关键 action。
5. 判断 `AuditAgent` verdict 是通过、警告还是 inconclusive。
6. 判断结果摘要对应哪些事实。
7. 从 Audit Page 返回 Main Page 继续操作。

观察指标：

- 用户是否知道当前审计 scope。
- 用户是否能回答“为什么系统这么做”。
- 用户是否能找到自己的确认记录。
- 用户是否能找到文件变更来源。
- 用户是否误把审计页当成执行控制台。
- 用户是否觉得页面可信、克制、可追踪。
- 用户是否被底层术语困住。

验收标准：

- 至少完成一轮真实或半真实用户 walkthrough。
- 记录 P0/P1 体验问题。
- 形成下一轮修订清单。

---

## 6. 里程碑

| Milestone | 阶段范围 | 主要产物 | 可继续条件 |
|---|---|---|---|
| M0 | Phase 0 | 实施计划 | 已完成，2026-05-30 已刷新事实状态 |
| M1 | Phase 1-2 | PRD + UX Flow | 已有草案，可继续迭代 |
| M2 | Phase 3-4 | Figma v0.2 + review notes | 待确认；可基于 AP-005 mock baseline 做后续设计评审 |
| M3 | Phase 5-6 | Mock UI 可运行 | 已完成第一轮，进入评审/后端联调准备 |
| M4 | Phase 7-8 | API 合约 + 真实后端通信 | API contract 和 mock frontend 基线已具备；真实后端通信为下一步推荐 |
| M5 | Phase 9 | 用户测试记录 + 修订清单 | 待做 |

---

## 7. 推荐任务拆分

| ID | 任务 | 产出 | 依赖 |
|---|---|---|---|
| AP-001 | 写 Audit Page PRD | `docs/product/plato-audit-page-prd.md` | Done |
| AP-002 | 写 Audit Page UX Flow | `docs/product/plato-audit-page-ux-flow.md` | Done |
| AP-003 | 生成/确认 Figma v0.1 | Figma 文件 | Pending verification |
| AP-004 | 设计评审与 v0.2 微调 | review notes + Figma v0.2 | Pending |
| AP-005 | 搭建 Audit Page shell | `frontend/` audit route | Done through AP-005G; follow `audit-page-frontend-technical-design.md` |
| AP-006 | 实现审计核心组件 | Audit Page mock UI | Done as part of AP-005B-G baseline |
| AP-007 | 建立 typed mock audit API | mock scenarios | Done |
| AP-008 | Mock 联调审计主路径 | 可演示 audit flow | Done for A1-A14 smoke baseline; keep for regression |
| AP-009 | 收敛 Audit Page API 合约 | `docs/engineering/audit-page-contract.md` | Done as baseline; update as needed |
| AP-010 | 实现后端 audit projection adapter | server API boundary | Done first pass; richer timeline/audit-agent sources remain follow-up |
| AP-011 | 接入真实审计后端通信 | UI real mode | Done first pass; runtime audit events/refetch remain follow-up |
| AP-012 | Sanitized payload disclosure | contract tests + backend sanitizer + frontend detail rendering | Done first pass; broader source policy remains follow-up |
| AP-013 | Runtime audit event/refetch | event/refetch design + frontend subscription + live source/emission | AP-013A-C done; AP-013D-F pending |
| AP-014 | 第一轮用户测试 | UC-007 + findings | Ready after AP-013 or can run earlier with manual refresh caveat |

---

## 8. 风险与处理

| 风险 | 表现 | 处理 |
|---|---|---|
| 审计页变成日志页 | 用户看到大量 event kind 和 payload，不知道重点 | PRD 和 UX 阶段先定义用户问题和证据层级 |
| 过早暴露 raw payload | 泄漏敏感信息或制造噪音 | 默认摘要化、脱敏、折叠；合约中定义 disclosure policy |
| 审计和主页面职责混乱 | 用户在审计页尝试执行、确认、重试 | Audit Page 只读；操作回到 Main Page 或 Task 操作入口 |
| 只展示 `AuditAgent` verdict | 忽略 confirmation、file、result、message 等完整证据链 | 以 Session / Task audit record 聚合多事实源 |
| 只展示时间线，不展示结论 | 用户能看到发生了什么，但不知道是否可信 | 增加 overview、severity、verdict、concern、evidence refs |
| API 直接暴露 EventStream | 前端绑定内部事件 schema，后续难演进 | 后端提供 Audit ViewModel / Projection |
| 信息过度确定 | inconclusive 被看成通过，风险被淡化 | 明确 `passed/warning/failed/inconclusive` 等状态与解释文案 |
| 缺少可测试 mock | Figma 到真实后端之间没有体验验证 | Phase 6 必须先走通 mock scenarios |

---

## 9. 第一轮执行建议

下一步不再从 AP-001 开始。PRD、UX Flow、engineering contract、frontend
types/API/routes/mock scenarios 已经具备第一版基线。

当前推荐顺序：

```text
AP-005H readiness cleanup / status synchronization
  -> AP-010 后端 audit query gateway / projection adapter（第一版已完成）
  -> AP-011 前端 HTTP mode 真实审计路径联调（第一版已完成）
  -> AP-012 sanitized payload disclosure（第一版已完成）
  -> AP-013 runtime audit event/refetch（AP-013A-C 已完成，AP-013D-F 待实现）
  -> Phase 9 用户测试 / 或补强 timeline + AuditAgent audit evidence
```

Audit Page 的关键不是把所有系统细节都展示出来，而是把用户真正需要信任的证据组织好。第一版可以克制，但证据链不能乱。
