# UN-104 — 配置驱动的系统个性可视化（UI 主题映射）

## 1) Metadata

- Need ID: `UN-104`
- Title: 核心配置变化在 UI 视觉上体现系统个性
- Status: `proposed`
- Owner: TBD
- Last Updated: 2026-05-14

## 2) User context

- User segment/persona: U1、U2、U3
- Scenario(s): `../scenarios/SC-104-config-personality-visualization.md`
- Trigger condition: 用户调整系统核心配置（如积极度、审计强度、交互频率）

## 3) Problem statement

- User problem: 配置参数改变后，系统行为变化不够“可感知”，用户难形成“系统个性”直觉。
- Why it matters: 影响可理解性、可控感与使用愉悦度，尤其在长期协作会话中。
- Current workaround: 用户只能从行为细节间接感知，缺少统一视觉反馈。

## 4) Decision

- Decision: `do`
- Decision rationale: 属于体验优化用例，不影响系统可运行性，但能显著提升“配置-行为”心智映射。

## 5) Current vs future handling

- Current approach (now): 配置主要影响后端行为与日志策略，UI 缺少个性表达层。
- Future approach (planned): 提供多主题模板（颜色、强调强度、组件密度/提醒样式），并把核心配置映射到视觉 token。

## 6) Prioritization

- Impact: `medium`
- Urgency: `low`
- Confidence: `medium`
- Cost: `medium`
- Risk: `low`
- Priority summary: 非阻断能力，建议在主链路稳定后作为体验增强项推进。

## 7) Evidence

- Evidence type: `interview`
- Evidence strength: `medium`
- Last validated at: 2026-05-14
- Source references: 当前会话补充需求

## 8) Architecture mapping

- Related capability docs: `docs/capabilities/settings-and-first-run/`, `docs/capabilities/configuration-control-plane/`
- Architecture impact: `none`
- Breaking change risk: `no`

## 9) Plan/feature mapping

- Related plan docs: future feature package under `docs/plans/features/`; legacy visual sources live under `docs/archive/legacy-2026-05-18/plans/ui/`
- Related feature packages: UI 主题系统、配置到视觉 token 映射、主题预设管理
- Milestone target: TBD

## 10) Implementation mapping

- Related implementation items (PR/commit/module): TBD
- Tracking issues/tasks: TBD

## 11) Definition of done

- Acceptance criteria: 用户修改核心配置后，UI 在主题/视觉表达上有一致、可解释的变化。
- Success metrics: 配置理解度提升、用户主观可控感提升、主题切换使用率提升。
- Guardrails: 不用视觉效果替代关键行为说明；无障碍对比度和可读性必须达标。
- Rollback condition: 视觉映射造成误解、可读性下降或操作负担上升。
