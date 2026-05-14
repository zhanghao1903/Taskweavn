# SC-101 — 摄影师海量图片筛选

## 1) Metadata

- Scenario ID: `SC-101`
- Title: 拍摄后海量图片快速筛选与人工复核
- Related segments: U2
- Related needs: `../needs/UN-101-photo-curation-batch-screening.md`
- Last Updated: 2026-05-14

## 2) Situation

- Context: 一次拍摄后需要从大量图片中选出可交付候选。
- Trigger: 用户提交“筛图目标 + 质量偏好”。
- Constraints: 时间紧、主观美学差异大、需要可解释理由。

## 3) Job to be done

When 我有大量待筛图片, I want to 快速得到可解释候选集合, so that 我能高质量且按时交付。

## 4) Desired outcomes

- Functional outcome: 任务树化筛选流程 + 导出候选列表。
- Quality outcome: 保留结果与筛选标准一致。
- Time-to-value outcome: 明显缩短首轮筛选耗时。

## 5) Current pain and failure points

- 人工逐张筛选效率低。
- 选择标准难沉淀、难复用。
- 缺少可回放过程。

## 6) Product response

- Should we support this scenario now? `yes`
- Current support path: 通用任务编排（无专属能力包）。
- Future support path: 图像评分能力 + 阈值调参 + 人工复核节点。

## 7) Architecture implications

- Domain boundary touched: Authoring -> Task publish（既有边界内）。
- Data/model implications: 增加图像筛选任务节点输入输出结构。
- Interaction implications: 节点级阈值编辑与复核确认。
- Observability/replay implications: 保留评分依据与筛选历史。

## 8) Validation

- Validation method: 小规模真实数据集人工对照测试。
- Success signal: 耗时下降且候选质量可接受。
- Risk signal: 筛选理由不可解释或误筛率持续偏高。
