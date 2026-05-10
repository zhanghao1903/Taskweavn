# TaskWeavn Planning Workflow

> 本文档定义“项目计划会话”的工作方式。这个会话只产出和维护 `docs/`
> 下的计划、问题、设计与验收文档；具体实现、修复和实验在其他会话完成。

---

## 1. 会话职责

本会话是项目总览与任务分流层，目标是把模糊想法整理成可执行文档。

不直接做：

- 修改 `src/`、`tests/` 等实现文件
- 修复 bug
- 实现 feature
- 大规模重构

直接做：

- 讨论问题边界、目标和优先级
- 产出计划文档
- 更新任务状态
- 记录验收标准、风险和后续决策
- 将任务切分成可交给其他实现会话执行的粒度

---

## 2. 三类任务

| 类型 | 目录 | 命名建议 | 用途 |
|---|---|---|---|
| 问题修复 | `docs/issues/` | `ISSUE-<num>-<slug>.md` | 记录 bug、复现、影响面、修复建议、验收 |
| 新特性支持 | `docs/plans/` | `<feature-slug>.md` | 记录功能目标、接口、执行切片、测试和验收 |
| 项目计划 | `docs/plans/` 或 `docs/architecture/` | `<topic>.md` | 记录阶段规划、架构演进、跨模块决策 |

如果任务偏“架构原则 / 长期设计”，放入 `docs/architecture/`。
如果任务偏“近期可执行工作包”，放入 `docs/plans/`。

---

## 3. 文档最小结构

每个任务文档至少包含：

```md
# 标题

## 背景

为什么现在要做。

## 目标

明确成功后系统应该具备什么能力。

## 非目标

这次不做什么，避免范围膨胀。

## 当前状态

基于代码和现有文档观察到的事实。

## 方案

可交给实现会话执行的决策完整方案。

## 验收标准

测试、命令、用户行为或文档检查。

## 状态

- Status: planned | in_progress | done | blocked | superseded
- Owner/Session: 可选
- Last Updated: YYYY-MM-DD
```

问题修复类额外包含：

- 复现步骤
- 期望行为
- 实际行为
- 可能根因
- 回归测试建议

---

## 4. 状态流转

| 状态 | 含义 |
|---|---|
| `planned` | 已整理成可执行计划，等待实现 |
| `in_progress` | 已有实现会话正在处理 |
| `done` | 实现完成，验收通过，文档已更新 |
| `blocked` | 缺少信息、依赖或决策 |
| `superseded` | 被新的计划替代，保留历史 |

任务完成后，回到本会话更新对应文档：

1. 将 `Status` 改为 `done`
2. 补充实现分支 / commit / PR 信息
3. 记录实际验收结果
4. 如果实现偏离原计划，补充“实际变更”
5. 如果产生后续任务，追加到“Follow-ups”

---

## 5. 计划粒度

一个计划应该能被另一个会话直接执行，不需要再做关键设计决策。

好的粒度：

- 能在一个分支内完成
- 有清晰验收标准
- 涉及模块边界明确
- 能独立测试
- 完成后能更新对应文档状态

过大的计划需要拆分，例如：

- `session lifecycle` 可以拆成 derived status、CLI session commands、resume behavior
- `observability` 可以拆成 event schema、log channels、query CLI、docs
- `RAG` 可以拆成 indexing、retrieval API、loop injection、evaluation set

---

## 6. 本会话工作约定

当用户提出一个想法时，本会话默认流程：

1. 先查现有 `docs/` 和相关代码，确认当前事实
2. 判断任务类型：问题修复 / 新特性 / 项目计划
3. 讨论目标、范围、约束和优先级
4. 产出或更新 `docs/` 下的计划文件
5. 不直接实现，除非用户明确切换到实现会话

如果用户说“这个完成了”，本会话默认做：

1. 找到对应文档
2. 更新状态和验收记录
3. 记录实际 commit / 分支 / 偏差
4. 如有必要，新建 follow-up 文档

---

## 7. 推荐索引

当前项目建议长期维护三类索引：

- `docs/issues/`：bug 和缺陷记录
- `docs/plans/`：近期 feature / improvement 工作包
- `docs/architecture/`：跨阶段架构设计和长期边界

后续可以增加：

- `docs/roadmap.md`：阶段级总路线
- `docs/decisions/ADR-<num>-<slug>.md`：重要架构决策记录
- `docs/releases/`：阶段完成记录和变更摘要
