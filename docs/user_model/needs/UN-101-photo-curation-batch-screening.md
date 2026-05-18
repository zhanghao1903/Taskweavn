# UN-101 — 摄影师批量图片筛选与复核

## 1) Metadata

- Need ID: `UN-101`
- Title: 摄影师批量图片筛选与复核
- Status: `proposed`
- Owner: TBD
- Last Updated: 2026-05-14

## 2) User context

- User segment/persona: U2（Solo Builder / Small Team Developer）与扩展创作型用户
- Scenario(s): `../scenarios/SC-101-photo-curation-batch-screening.md`
- Trigger condition: 一次拍摄后需要从大量图片中快速筛选可交付候选

## 3) Problem statement

- User problem: 手工筛图耗时高、标准不一致、难以解释筛选依据。
- Why it matters: 直接影响交付速度与质量稳定性。
- Current workaround: 人工逐张筛选 + 临时打标，过程不可回放。

## 4) Decision

- Decision: `do`
- Decision rationale: 与 Task-first（批处理 + 人工确认节点 + 可回放）高度匹配。

## 5) Current vs future handling

- Current approach (now): 尚未产品化支持，仅有通用任务编排能力。
- Future approach (planned): 建立图片筛选任务树（导入 -> 评分 -> 风格筛选 -> 人工复核 -> 导出）与阈值调参节点。

## 6) Prioritization

- Impact: `high`
- Urgency: `medium`
- Confidence: `medium`
- Cost: `medium`
- Risk: `medium`
- Priority summary: 价值验证速度快，且不要求先改核心架构。

## 7) Evidence

- Evidence type: `interview`
- Evidence strength: `medium`
- Last validated at: 2026-05-11
- Source references: `docs/archive/legacy-2026-05-18/discussion/2026-05-11-product-positioning-and-boundaries.md`（10.1）

## 8) Architecture mapping

- Related capability docs: `docs/capabilities/task-authoring/`, `docs/capabilities/file-change-summary/`, `docs/capabilities/audit-trust/`
- Architecture impact: `none`
- Breaking change risk: `no`

## 9) Plan/feature mapping

- Related plan docs: TBD
- Related feature packages: Tooling 扩展（图像评分/筛选能力）
- Milestone target: TBD

## 10) Implementation mapping

- Related implementation items (PR/commit/module): TBD
- Tracking issues/tasks: TBD

## 11) Definition of done

- Acceptance criteria: 可从图片集生成可编辑任务树，并输出候选清单+理由摘要。
- Success metrics: 人工筛选时间下降、候选命中率提升。
- Guardrails: 不承诺“绝对美学判断”；不处理复杂版权/人脸合规决策。
- Rollback condition: 评分依据不可解释或误筛率过高。
