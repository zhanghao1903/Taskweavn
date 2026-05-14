# SC-104 — 核心配置变更后的 UI 个性反馈

## 1) Metadata

- Scenario ID: `SC-104`
- Title: 用户通过视觉反馈直觉理解系统个性
- Related segments: U1, U2, U3
- Related needs: `../needs/UN-104-config-personality-visualization.md`
- Last Updated: 2026-05-14

## 2) Situation

- Context: 系统提供大量配置参数，阈值会显著影响行为（积极度、审计强度、交互频率等）。
- Trigger: 用户在设置中调整核心配置并保存。
- Constraints: 不能牺牲可读性、无障碍和任务主流程清晰度。

## 3) Job to be done

When 我调整系统关键配置, I want to 在 UI 视觉上立即感知系统个性变化, so that 我能更直觉地判断“当前系统会如何表现”。

## 4) Desired outcomes

- Functional outcome: 核心配置可映射到主题模板/视觉 token 并即时生效。
- Quality outcome: 映射规则一致、可解释，不制造认知歧义。
- Time-to-value outcome: 用户在短时间内理解配置影响并完成偏好设定。

## 5) Current pain and failure points

- 配置影响“看不见”，只能靠行为推断。
- 复杂参数对新用户学习成本高。
- “系统个性”缺少统一表达层。

## 6) Product response

- Should we support this scenario now? `not-now`
- Current support path: 先保持功能正确性和稳定性，视觉表现保持基础统一。
- Future support path: 增加主题模板（色彩/提醒样式/组件密度），并建立配置到视觉 token 的映射表。

## 7) Architecture implications

- Domain boundary touched: 不改变核心执行架构，主要在 UI 表达层与配置读取层。
- Data/model implications: 增加配置可视化映射配置（theme profile）。
- Interaction implications: 配置变更后即时预览、可回退。
- Observability/replay implications: 记录主题变更事件，支持回放“当时系统个性”。

## 8) Validation

- Validation method: 可用性测试 + 主题 AB 测试。
- Success signal: 用户能正确描述配置影响，且主题使用率提升。
- Risk signal: 视觉暗示与实际行为不一致，导致错误预期。
