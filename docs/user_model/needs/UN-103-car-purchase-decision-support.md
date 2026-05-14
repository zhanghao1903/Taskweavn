# UN-103 — 买车信息收集与候选对比建议

## 1) Metadata

- Need ID: `UN-103`
- Title: 购车约束收集与候选解释型推荐
- Status: `proposed`
- Owner: TBD
- Last Updated: 2026-05-14

## 2) User context

- User segment/persona: U3
- Scenario(s): `../scenarios/SC-103-car-purchase-decision-support.md`
- Trigger condition: 用户在高信息负载下需要快速形成可解释候选清单

## 3) Problem statement

- User problem: 车型信息分散、约束多、对比复杂且易遗漏。
- Why it matters: 涉及真实消费决策，错误成本较高。
- Current workaround: 多平台手工检索 + 主观比较表。

## 4) Decision

- Decision: `do`
- Decision rationale: 可作为“轻决策助手”纳入 Task-first；但须强约束风险和免责声明。

## 5) Current vs future handling

- Current approach (now): 无专属流程，通用问答难以稳定输出可审计对比。
- Future approach (planned): 先做约束收集任务节点（预算/用途/能源偏好/空间/路况）-> 候选比较 -> 推荐理由与不确定项。

## 6) Prioritization

- Impact: `medium`
- Urgency: `low`
- Confidence: `medium`
- Cost: `medium`
- Risk: `high`
- Priority summary: 有价值但风险高于前两场景，建议后置验证。

## 7) Evidence

- Evidence type: `interview`
- Evidence strength: `medium`
- Last validated at: 2026-05-11
- Source references: `docs/discussion/2026-05-11-product-positioning-and-boundaries.md`（10.3）

## 8) Architecture mapping

- Related architecture docs/sections: `docs/architecture/authoring-domain.md`, `docs/architecture/interaction-layer.md`
- Architecture impact: `none`
- Breaking change risk: `no`

## 9) Plan/feature mapping

- Related plan docs: TBD
- Related feature packages: 信息抓取/比对工具能力、结果解释与风险提示
- Milestone target: TBD

## 10) Implementation mapping

- Related implementation items (PR/commit/module): TBD
- Tracking issues/tasks: TBD

## 11) Definition of done

- Acceptance criteria: 可产出候选车型清单、每项理由/取舍、不确定项与信息更新时间。
- Success metrics: 决策前信息整理时间下降，用户主观信心提升。
- Guardrails: 不做自动下单/金融建议；不把不确定信息表述为确定事实。
- Rollback condition: 幻觉率高或高风险误导不可控。
