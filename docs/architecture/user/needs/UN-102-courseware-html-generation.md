# UN-102 — 教师课件生成（HTML 优先）

## 1) Metadata

- Need ID: `UN-102`
- Title: 教学目标到课件草案的任务化生成（HTML/Markdown）
- Status: `proposed`
- Owner: TBD
- Last Updated: 2026-05-14

## 2) User context

- User segment/persona: U2、U3
- Scenario(s): `../scenarios/SC-102-courseware-html-generation.md`
- Trigger condition: 用户需要在短时间内生成可迭代课件初稿

## 3) Problem statement

- User problem: 课件制作步骤多、反复改稿成本高。
- Why it matters: 影响备课效率与内容一致性。
- Current workaround: 手工拼装文档/PPT，改动链路长、复用弱。

## 4) Decision

- Decision: `do`
- Decision rationale: 明确多步骤流程，且 HTML 路径与现有文件工作流一致。

## 5) Current vs future handling

- Current approach (now): 通用任务编排可支持，但无课件专属能力包。
- Future approach (planned): 教学目标 -> 课件任务树（大纲/内容页/图示建议/练习题），产出 HTML/Markdown 并支持后续导出。

## 6) Prioritization

- Impact: `high`
- Urgency: `medium`
- Confidence: `medium`
- Cost: `medium`
- Risk: `low`
- Priority summary: 与代码/文件流高度兼容，易于 MVP 验证。

## 7) Evidence

- Evidence type: `interview`
- Evidence strength: `medium`
- Last validated at: 2026-05-11
- Source references: `docs/discussion/2026-05-11-product-positioning-and-boundaries.md`（10.2）

## 8) Architecture mapping

- Related architecture docs/sections: `docs/architecture/task.md`, `docs/architecture/task-domain-ui-model-separation.md`
- Architecture impact: `none`
- Breaking change risk: `no`

## 9) Plan/feature mapping

- Related plan docs: TBD
- Related feature packages: Tooling 扩展（课件生成、结构化结果包装）
- Milestone target: TBD

## 10) Implementation mapping

- Related implementation items (PR/commit/module): TBD
- Tracking issues/tasks: TBD

## 11) Definition of done

- Acceptance criteria: 可从教学目标生成可编辑课件任务树并产出可预览 HTML/Markdown。
- Success metrics: 备课初稿耗时下降、迭代轮次下降。
- Guardrails: 不承诺“一键最终稿”；不先做 LMS 深度对接。
- Rollback condition: 产出不可编辑或不稳定导致人工成本上升。
