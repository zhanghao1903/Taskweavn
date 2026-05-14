# SC-103 — 购车候选对比与解释型建议

## 1) Metadata

- Scenario ID: `SC-103`
- Title: 买车信息整理与候选比较
- Related segments: U3
- Related needs: `../needs/UN-103-car-purchase-decision-support.md`
- Last Updated: 2026-05-14

## 2) Situation

- Context: 用户在预算、用途、能源类型等多约束下做车型选择。
- Trigger: 用户提出“给我推荐车”但条件不完整或信息分散。
- Constraints: 数据时效性强、误导风险高、消费后果真实。

## 3) Job to be done

When 我需要做购车决策, I want to 得到可解释的候选清单和取舍分析, so that 我能更快完成高质量判断。

## 4) Desired outcomes

- Functional outcome: 形成约束收集 -> 候选对比 -> 推荐解释任务流。
- Quality outcome: 推荐理由透明，明确不确定项。
- Time-to-value outcome: 降低信息整理与比较时间。

## 5) Current pain and failure points

- 信息来源分散，手工对比成本高。
- 约束条件常遗漏，结论不稳。
- 很难说明推荐结论依据与边界。

## 6) Product response

- Should we support this scenario now? `not-now`
- Current support path: 通用问答 + 任务拆解，但缺少稳定信息治理。
- Future support path: 轻决策助手模式，必须附“信息更新时间 + 二次核验提示”。

## 7) Architecture implications

- Domain boundary touched: 既有边界可承载，核心是工具能力与治理规则。
- Data/model implications: 约束结构化输入与候选对比输出模型。
- Interaction implications: 澄清问题与候选取舍解释节点。
- Observability/replay implications: 推荐依据、数据时间戳、免责声明可回放。

## 8) Validation

- Validation method: 受控任务集 + 人工专家抽检。
- Success signal: 信息整理效率提升且误导投诉率可控。
- Risk signal: 幻觉性陈述、过度确定性表达、风险提示缺失。
