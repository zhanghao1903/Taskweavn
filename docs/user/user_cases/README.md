# 用户测试用例清单

> 本目录归档手工用户测试用例。每个用例一个 Markdown 文件，便于贴图、记录终端输出、补充观察结论。
>
> `测试结果` 与 `测试总结` 由测试执行者填写；其余部分为预设测试方案。

## 清单

| 编号 | 标题 | 难度 | 描述 | 文件 |
|---|---|---|---|---|
| UC-001 | 基础文件生成 | 容易 | 验证 agent 能在无用户介入的情况下完成简单文件创建任务，并用 `agent_finish` 正常收尾。 | [UC-001-basic-file-generation.md](UC-001-basic-file-generation.md) |
| UC-002 | 风险门禁与用户确认 | 适中 | 验证 `--autonomy risk_gated` 下，高风险动作会发出 actionable 消息，用户确认或拒绝后 loop 能继续。 | [UC-002-risk-gated-user-confirmation.md](UC-002-risk-gated-user-confirmation.md) |
| UC-003 | 长任务续作与动态风险评估 | 困难 | 验证同一 workspace/session 下的多轮项目构建、用户纠偏、拒绝恢复、消息聚合和 `--risk-assessor composite`。 | [UC-003-long-running-site-collaboration.md](UC-003-long-running-site-collaboration.md) |

## Artifacts

Supporting files are stored under `artifacts/`:

| Directory | Purpose |
|---|---|
| `artifacts/images/` | Screenshots referenced by test cases. |
| `artifacts/logs/` | Log files and SQLite message stores captured during test runs. |
| `artifacts/workspace/` | Generated workspaces or output projects from manual runs. |
| `inputs/` | Terminal input transcripts used for repeatable manual tests. |

## 记录约定

- 截图放在 `artifacts/images/` 下，建议命名为 `UC-编号-说明.png`，并在对应用例的 `测试结果` 中引用。
- 终端输出过长时，只贴关键片段，完整日志可另存为 `.txt` 并链接。
- 每次测试建议记录：
  - 运行日期
  - 当前分支 / commit
  - 使用模型
  - 是否启用 Docker / sandbox
  - 实际用户回复
  - 生成文件清单
  - 失败点或体验卡顿点
