# SC-105 — 任务前后可评估性与能力边界披露

## 1) Metadata

- Scenario ID: `SC-105`
- Title: 用户在任务前后判断系统匹配度与可信度
- Related segments: U1, U2, U3
- Related needs: `../needs/UN-105-system-evaluability-and-capability-disclosure.md`
- Last Updated: 2026-05-14

## 2) Situation

- Context: 用户希望在投入时间前判断任务是否适合系统，并在执行后判断结果可信度。
- Trigger: 用户输入任务目标或查看任务完成结果。
- Constraints: 评估数据要有解释性，且不能制造“过度确定性”错觉。

## 3) Job to be done

When 我考虑是否把任务交给系统, I want to 快速看到能力匹配和效率预期, so that 我能做出低风险且高收益的任务分配决策。

## 4) Desired outcomes

- Functional outcome: 提供任务前匹配评估、任务中进度/风险信号、任务后质量摘要。
- Quality outcome: 评估信号可解释、可追溯、与真实表现相关。
- Time-to-value outcome: 减少无效尝试和错误委托。

## 5) Current pain and failure points

- 用户只能试错，不知道“能否做/是否高效”。
- 结果好坏缺少标准化评估视图。
- 系统边界缺少主动披露，影响信任。

## 6) Product response

- Should we support this scenario now? `yes`
- Current support path: 通过计划与执行日志间接判断，评估信息分散。
- Future support path: 增加独立 eval 评估线，贯穿 pre-task / in-task / post-task。

## 7) Architecture implications

- Domain boundary touched: Authoring（任务适配判断）+ Execution（执行效率与质量信号）+ UI（评估展示）。
- Data/model implications: 新增 `eval signals`（匹配分、置信度、失败模式、历史表现）。
- Interaction implications: 任务创建前提示“建议执行/不建议执行/需补充信息”。
- Observability/replay implications: 评估结论与证据链可回放、可审计。

## 8) Validation

- Validation method: 离线回放评估 + 在线 A/B 测试。
- Success signal: 用户任务匹配决策准确度上升、失败率下降。
- Risk signal: 评估提示与真实表现偏差大，导致误导性委托。

## 9) Eval data design notes (for follow-up plan)

- Pre-task: 任务类型匹配度、前置条件完整度、预估成本/时延区间。
- In-task: 计划偏差、风险升级频率、重试/回退次数。
- Post-task: 结果质量信号、人工接管比例、可验证证据覆盖率。
- Trust vs richness: 先提供中等丰度、强解释的指标；逐步扩展高维信号，避免低可信高复杂面板。
