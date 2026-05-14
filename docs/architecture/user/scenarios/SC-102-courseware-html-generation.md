# SC-102 — 教学目标到 HTML 课件草案

## 1) Metadata

- Scenario ID: `SC-102`
- Title: 课件制作任务化生成（HTML/Markdown 优先）
- Related segments: U2, U3
- Related needs: `../needs/UN-102-courseware-html-generation.md`
- Last Updated: 2026-05-14

## 2) Situation

- Context: 教师/内容创作者需要快速完成课件初稿并可反复调整。
- Trigger: 用户输入教学目标、受众年级、时长、风格要求。
- Constraints: 时间有限、内容结构复杂、需要可预览可迭代。

## 3) Job to be done

When 我需要快速准备教学内容, I want to 自动生成可编辑课件草案, so that 我能把时间集中在教学质量优化。

## 4) Desired outcomes

- Functional outcome: 自动生成任务树并输出 HTML/Markdown 课件草案。
- Quality outcome: 内容结构清晰、可按节点持续改写。
- Time-to-value outcome: 缩短首稿生成时间。

## 5) Current pain and failure points

- 手工制作链路长，改动成本高。
- 材料组织与练习设计分散。
- 多轮迭代缺少稳定结构。

## 6) Product response

- Should we support this scenario now? `yes`
- Current support path: 通用任务能力可覆盖基础流程。
- Future support path: 课件专属能力包（大纲/内容页/图示建议/练习题）。

## 7) Architecture implications

- Domain boundary touched: 主要在既有 Task-first 边界内。
- Data/model implications: 课件节点输入（目标/受众/难度）与输出（HTML/MD）。
- Interaction implications: 节点级教学风格与难度约束编辑。
- Observability/replay implications: 版本差异可追踪与回放。

## 8) Validation

- Validation method: 与人工制作流程做 AB 对照。
- Success signal: 首稿速度与可编辑性显著提升。
- Risk signal: 生成质量不稳定导致返工增多。
