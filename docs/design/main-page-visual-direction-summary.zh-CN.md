# Main Page 视觉方向一页式摘要

> 状态：视觉方向已锁定，页面实现尚未达标
> 日期：2026-06-04
> 范围：Plato Main Page 的视觉风格、信息层级、删减原则和优先级。
> 非目标：不修改前端代码，不写 Figma，不改 API，不迁移旧 Figma。

## 1. 最终方向

Plato Main Page 的视觉方向定为：

```text
Modern Classical Workbench
现代理性工作台
```

这不是古典装饰风，也不是 AI 炫技风。它的核心气质是：

- 冷静；
- 清晰；
- 结构化；
- 可控；
- 可追踪；
- 面向真实工作。

一句话判断：

```text
让用户一眼看清任务结构、下一步动作和结果可信度。
```

## 2. 页面第一原则

Main Page 不是聊天页，不是 Todo，不是 IDE，也不是营销页。

它是一个 Task-first 控制台：

```text
用户表达目标
  -> Plato 生成 TaskTree
  -> 用户审阅、补充、确认
  -> 系统执行
  -> 用户查看结果、文件变更和审计
```

因此视觉主角必须是 TaskTree，而不是消息流。

## 3. 信息层级

接受的页面层级是：

1. 当前 TaskTree / 被选中的 TaskNode
2. 当前必须处理的动作：发布、确认、重试、刷新、输入
3. 执行后的结果和文件变更
4. 消息流中的过程证据
5. 审计和日志细节

这意味着：

- MessageStream 只能辅助，不能和 TaskTree 平级抢注意力。
- DetailPanel 只解释当前对象或当前动作。
- Result、File Change、Audit 应该是一条验收路径，而不是三个互相竞争的面板。
- 每个状态只保留一个主解释，不要每个区域都解释一遍。

## 4. 各区域职责

| 区域 | 应该负责 | 不应该负责 |
|---|---|---|
| TopBar | 产品标识、项目、Workflow、Session、主状态 | 开发态状态选择器、产品教育文案 |
| Sidebar | Workflow / Session 导航 | 任务状态、审计信息、说明文案 |
| TaskTree | 任务结构、层级、选中、状态 | 长说明、日志、审计细节 |
| MessageStream | 过程证据、最近更新 | 主操作、重复状态说明 |
| DetailPanel | 当前对象、下一步动作、确认、结果、文件摘要 | 泛泛的 State note |
| InputDock | 输入作用域、命令模式、禁用原因 | 长帮助文案、和状态冲突的 placeholder |
| Audit Entry | 追溯入口 | 默认展开的审计详情 |

如果一条信息不属于所在区域，就移动、隐藏或删除。

## 5. 明确不要的方向

不要走这些方向：

- 聊天机器人首页；
- Todo / Task Manager；
- IDE / Terminal；
- SaaS marketing dashboard；
- Cyber / neon / magical AI；
- 希腊柱子、大理石、哲学装饰主题；
- 强玻璃拟态；
- 大圆角玩具感；
- 卡片套卡片。

Plato 可以有品牌气质，但工作台必须直接、克制、可用。

## 6. 视觉风格规则

保留：

- 低噪声浅色背景；
- 细边框；
- 轻阴影；
- 8px 以内圆角；
- 紧凑但可读的字体；
- 蓝色作为主路径；
- 金色作为等待/注意；
- 绿色作为完成；
- 红色只用于真实失败或风险；
- 米白/浅灰作为安静表面。

避免：

- 大面积渐变；
- 装饰性背景；
- 高饱和 AI 色；
- 过多阴影；
- 页面区块全部浮成卡片；
- 解释性文字过多。

## 7. 当前必须优先删减的内容

P0，先处理：

1. 隐藏生产界面里的状态选择器。
2. 文件变更摘要里默认不显示 `Owner TaskNode: task-...` 这类 raw id。
3. 解决 1280px 桌面宽度下的主要内容裁切/横向溢出。

P1，再处理：

1. 删除 S1/S3 里重复的 `State note`。
2. 降低 MessageStream 的视觉权重。
3. TopBar 里弱化或删除 `Task-first Intelligent Workbench` 副标题。
4. Confirmation 状态里减少重复说明，只保留动作、影响和选项。
5. File Change 面板减少密度，把 lineage / owner 信息放到展开或 Audit。

## 8. 关键交互判断

输入框必须让用户知道“我输入的话会作用到哪里”。

正确方向：

```text
Applies to: selected task / Visual direction
```

或者：

```text
Scope: task tree
```

错误方向：

- 已完成任务还提示用户继续编辑；
- 选中 TaskNode 后输入框仍像全局输入；
- Confirmation 状态里输入框和确认按钮互相抢主操作；
- read-only 状态只禁用，不解释原因。

## 9. 状态设计判断

| 状态 | 主视觉 | 应删/降级 |
|---|---|---|
| S1 Empty | 输入入口 + 空 TaskTree | Message 空态和 DetailPanel 重复说明 |
| S3 Draft Ready | TaskTree + Publish | 重复的 State note |
| S7 Confirmation | 右侧确认卡 | MessageStream 的视觉竞争和重复说明 |
| S8 Completed | Result summary | 重复的 result-ready message |
| S9 File Changes | 文件路径 + change type | raw TaskNode id 和过密 metadata |

先把这些状态理顺，再做细节美化。

## 10. 验收标准

未来 Figma 或前端调整只有满足这些条件，才算符合方向：

- TaskTree 在有任务时始终是主对象；
- 用户下一步动作一眼可见；
- TopBar 没有开发态状态选择器；
- MessageStream 明显降级为证据流；
- DetailPanel 不再重复泛泛说明；
- InputDock 的作用域和权限状态一致；
- Result / File Change / Audit 是连续验收路径；
- 默认视图不暴露 raw id、日志、审计证据；
- 1280px 桌面宽度不裁切主要内容；
- 整体感觉冷静、清晰、可操作，而不是热闹或炫技。

## 11. 当前结论

视觉方向已经明确：

```text
现代理性工作台，TaskTree 为主，消息为证据，详情为行动，审计为信任。
```

当前页面结构方向是对的，但还没有达到视觉简化验收标准。

下一步不应该先调颜色、阴影、圆角，而应该先做信息删减和层级重排：

```text
先删重复
  -> 再降级消息流
  -> 再解决宽度裁切
  -> 最后做视觉 polish
```
