# UN-105 — 系统可评估性与能力边界透明化

## 1) Metadata

- Need ID: `UN-105`
- Title: 让用户快速判断“能做什么 / 不能做什么 / 高效与低效任务”
- Status: `proposed`
- Owner: TBD
- Last Updated: 2026-05-14

## 2) User context

- User segment/persona: U1、U2、U3
- Scenario(s): `../scenarios/SC-105-system-evaluability-and-capability-disclosure.md`
- Trigger condition: 用户准备把任务交给系统前，需要判断任务匹配度与预期效率

## 3) Problem statement

- User problem: 系统即便强大也不可能高效覆盖所有任务，但用户缺少快速评估依据。
- Why it matters: 影响信任、任务分配效率与失败成本控制。
- Current workaround: 试错式使用（先提任务再看结果），成本高且不可预测。

## 4) Decision

- Decision: `do`
- Decision rationale: 属于平台级体验与治理能力，补齐“计划/执行”之外的“评估线”。

## 5) Current vs future handling

- Current approach (now): 仅有计划线与执行线；缺少明确 eval 评估线与能力边界披露。
- Future approach (planned): 建立评估线（pre-task fit + in-task confidence + post-task quality），输出可解释评估数据。

## 6) Prioritization

- Impact: `high`
- Urgency: `medium`
- Confidence: `medium`
- Cost: `medium`
- Risk: `medium`
- Priority summary: 对用户决策效率与系统信任建设价值高，建议进入中近期规划。

## 7) Evidence

- Evidence type: `interview`
- Evidence strength: `medium`
- Last validated at: 2026-05-14
- Source references: 当前会话补充需求

## 8) Architecture mapping

- Related capability docs: `docs/capabilities/task-authoring/`, `docs/capabilities/audit-trust/`, `docs/capabilities/diagnostic-bundle/`
- Architecture impact: `cross-module`
- Breaking change risk: `no`

## 9) Plan/feature mapping

- Related plan docs: future feature packages under `docs/plans/features/`; legacy observability/cost sources live under `docs/archive/legacy-2026-05-18/plans/`
- Related feature packages: 能力评估器、任务匹配评分、结果可信度信号、评估数据 API
- Milestone target: TBD

## 10) Implementation mapping

- Related implementation items (PR/commit/module): TBD
- Tracking issues/tasks: TBD

## 11) Definition of done

- Acceptance criteria: 用户在提交任务前可看到任务匹配度与预期效率提示；任务后可看到质量与可信度摘要。
- Success metrics: 无效任务提交率下降、用户二次尝试成功率上升、满意度提升。
- Guardrails: 不以“伪精确分数”误导用户；明确置信区间与数据来源。
- Rollback condition: 评估数据与真实执行表现持续偏离，造成错误决策。
