# Main Page 视觉方向与实施指导摘要

> 状态：视觉方向已锁定，作为后续 Figma/前端实施入口
> 日期：2026-06-05
> 范围：Plato Main Page 的视觉风格、信息层级、删减原则、Message/Activity 交互和优先级。
> 非目标：不修改前端代码，不写 Figma，不改 API，不迁移旧 Figma。

## 0. 文档角色

这份文档是后续实施的第一入口。

实施前先读本文件，再按需要查看支撑文档：

| 文档 | 角色 |
|---|---|
| `main-page-visual-direction-summary.zh-CN.md` | 中文实施指导入口，给产品、设计、前端对齐最终方向。 |
| `main-page-visual-direction-decision.md` | 英文正式决策记录：接受方向、拒绝方向、表面职责和验收门槛。 |
| `main-screen-states-visual-simplification-brief.md` | 设计规则细化：信息删减、布局、响应式和组件表面规则。 |
| `main-screen-states-recomposition-checklist.md` | 状态级验收清单：每个 S1-S13 状态应该显示、降级、隐藏什么。 |
| `main-screen-states-current-ui-review-2026-06-04.md` | 当前运行时证据：记录问题来源，不作为最新实施规格。 |
| `../decisions/ADR-0015-main-page-activity-overlay-message-history.md` | 正式 ADR：记录 Latest Activity、Activity Overlay、Result Reader 的长期决策。 |

不要把五份文档都当成同等实施手册。实施口径以本文件为准；如果细节不够，再进入对应支撑文档。

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
4. 最新动态和可回看的任务动态
5. 审计和日志细节

这意味着：

- MessageStream 不再作为主屏常驻栏，不能和 TaskTree 平级抢注意力。
- Workspace 只显示一条产品化后的最新动态，不显示原始长消息。
- 所有消息通过 `Activity Overlay / 任务动态层` 回看和过滤。
- DetailPanel 只解释当前对象或当前动作。
- Result、File Change、Audit 应该是一条验收路径，而不是三个互相竞争的面板。
- 每个状态只保留一个主解释，不要每个区域都解释一遍。

## 4. 各区域职责

| 区域 | 应该负责 | 不应该负责 |
|---|---|---|
| TopBar | 产品标识、项目、Workflow、Session、主状态 | 开发态状态选择器、产品教育文案 |
| Sidebar | Workflow / Session 导航 | 任务状态、审计信息、说明文案 |
| TaskTree | 任务结构、层级、选中、状态 | 长说明、日志、审计细节 |
| Latest Activity Strip | 最后一条重要动态，一行提示 | 原始消息、长内容、滚动列表 |
| Activity Overlay | 所有动态回看、过滤、长结果入口 | 常驻占位、半露出 DetailPanel |
| DetailPanel | 当前对象、下一步动作、确认、结果、文件摘要 | 泛泛的 State note |
| Result Reader | 长 Result Summary、结构化结果内容 | 普通进度、工具日志、确认动作 |
| InputDock | 输入作用域、命令模式、禁用原因 | 长帮助文案、和状态冲突的 placeholder |
| Audit Entry | 追溯入口 | 默认展开的审计详情 |

如果一条信息不属于所在区域，就移动、隐藏或删除。

## 5. Message / Activity 实施结论

这是 2026-06-05 收敛后的交互结论。

### 5.1 主屏默认态

主屏不再保留 `Session messages` / `MessageStream` 常驻列。

默认布局应是：

```text
+----------------------+-------------------------+
| TaskTree             | DetailPanel             |
|                      |                         |
+------------------------------------------------+
| InputDock                                      |
+------------------------------------------------+
```

在 Workspace 内保留一条轻量 `Latest Activity Strip`：

```text
刚刚 · 结果摘要已生成 · 发现 3 个问题 · 查看
```

规则：

- 只显示最后一条重要动态；
- 显示产品化状态，不显示原始 message body；
- 永远一行，不滚动，不展开成长文本；
- 右侧提供 `动态 4` 入口；
- 没有动态时可以隐藏，不需要显示空消息面板。

### 5.2 二级动态入口

点击 `动态 4` 或 latest activity 里的 `查看` 后，打开独立的
`Activity Overlay / 任务动态层`。

规则：

- overlay 覆盖在 DetailPanel 上层；
- 不复用 DetailPanel 组件；
- 不做 DetailPanel 半露出的稳定状态；
- TaskTree 可以保持可见，必要时弱化；
- 关闭 overlay 后回到原 DetailPanel，选中 Task 不变；
- overlay 是唯一滚动区域，主工作台不新增第二个常驻滚动栏。

推荐桌面尺寸：

| 环境 | Overlay 行为 |
|---|---|
| 普通桌面 | 覆盖 DetailPanel，宽度约 480-560px |
| 宽屏 / 长结果阅读 | 可加宽到 640-720px |
| 窄屏 / 移动 | 全屏 overlay |

### 5.3 动态过滤

`Activity Overlay` 至少支持这些过滤：

```text
当前任务 / 全部 / 结果 / 错误
```

可选扩展：

```text
需要确认 / 工具记录 / 审计
```

不要把工具调用和审计详情默认暴露到主屏；它们可以在动态里作为低权重记录，或继续进入 Audit。

### 5.4 长消息和 Result Summary

长 `Result Summary` 不应该在动态列表里直接展开。

正确处理：

```text
动态列表卡片
  -> 查看完整结果
  -> Result Artifact / Reader
```

Reader 可以在 Activity Overlay 内打开，也可以让 overlay 加宽进入阅读态。它的心智是“结果文档”，不是“第三级消息列表”。

长内容分流规则：

| 类型 | 主显示位置 |
|---|---|
| 普通进度 | Latest Activity + Activity Overlay |
| 需要用户确认 | DetailPanel |
| 错误/重试 | 相关控件附近内联显示 + Activity Overlay |
| Result Summary | Result Artifact / Reader |
| File Change | DetailPanel 的文件摘要 / 审计入口 |
| Raw tool/audit log | Audit，不进主屏 |

一句话：

```text
短消息做动态，长内容做结果，行动项进详情，原始证据进审计。
```

## 6. 明确不要的方向

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

## 7. 视觉风格规则

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

## 8. 当前必须优先删减的内容

P0，先处理：

1. 隐藏生产界面里的状态选择器。
2. 文件变更摘要里默认不显示 `Owner TaskNode: task-...` 这类 raw id。
3. 解决 1280px 桌面宽度下的主要内容裁切/横向溢出。
4. 移除主屏常驻 `Session messages` / `MessageStream` 栏，改为
   `Latest Activity Strip + Activity Overlay`。

P1，再处理：

1. 删除 S1/S3 里重复的 `State note`。
2. 完成 Activity Overlay 的过滤、关闭、长结果 Reader 规则。
3. TopBar 里弱化或删除 `Task-first Intelligent Workbench` 副标题。
4. Confirmation 状态里减少重复说明，只保留动作、影响和选项。
5. File Change 面板减少密度，把 lineage / owner 信息放到展开或 Audit。

## 9. 关键交互判断

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

## 10. 状态设计判断

| 状态 | 主视觉 | 应删/降级 |
|---|---|---|
| S1 Empty | 输入入口 + 空 TaskTree | Message 空态和 DetailPanel 重复说明 |
| S3 Draft Ready | TaskTree + Publish | 重复的 State note |
| S7 Confirmation | 右侧确认卡 | 动态只能作证据，确认必须进 DetailPanel |
| S8 Completed | Result summary | result-ready message 只进 Latest Activity / Activity Overlay |
| S9 File Changes | 文件路径 + change type | raw TaskNode id 和过密 metadata |

先把这些状态理顺，再做细节美化。

## 11. 验收标准

未来 Figma 或前端调整只有满足这些条件，才算符合方向：

- TaskTree 在有任务时始终是主对象；
- 用户下一步动作一眼可见；
- TopBar 没有开发态状态选择器；
- 主屏没有常驻 MessageStream / Session messages 栏；
- Workspace 只显示一行 Latest Activity；
- `动态` 入口能打开可过滤的 Activity Overlay；
- Activity Overlay 覆盖 DetailPanel，不把 DetailPanel 半露出作为稳定状态；
- 长 Result Summary 以 Result Artifact / Reader 形式打开；
- DetailPanel 不再重复泛泛说明；
- InputDock 的作用域和权限状态一致；
- Result / File Change / Audit 是连续验收路径；
- 默认视图不暴露 raw id、日志、审计证据；
- 1280px 桌面宽度不裁切主要内容；
- 整体感觉冷静、清晰、可操作，而不是热闹或炫技。

## 12. 当前结论

视觉方向已经明确：

```text
现代理性工作台，TaskTree 为主，详情为行动，动态为回看，结果为文档，审计为信任。
```

当前页面结构方向是对的，但还没有达到视觉简化验收标准。

下一步不应该先调颜色、阴影、圆角，而应该先做信息删减和层级重排：

```text
先删重复
  -> 再移除常驻 MessageStream
  -> 引入 Latest Activity + Activity Overlay
  -> 再解决宽度裁切
  -> 最后做视觉 polish
```
