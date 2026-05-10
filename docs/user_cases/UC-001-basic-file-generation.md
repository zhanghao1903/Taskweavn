# UC-001 基础文件生成

## 基本信息

| 字段 | 内容 |
|---|---|
| 编号 | UC-001 |
| 标题 | 基础文件生成 |
| 难度 | 容易 |
| 目标能力 | ReAct loop、文件工具、EventStream、正常完成路径 |

## 描述

验证 agent 能完成一个简单、低风险、无用户交互的文件创建任务。该用例用于确认基础工具链稳定：LLM 能正确选择 `write_file`，runtime 能执行工具，EventStream 能记录 Action/Observation，loop 能用 `agent_finish` 正常结束。

## 测试命令

```bash
code-agent run \
  --task "在 workspace 里创建 README.md，内容包括项目名称、三条功能点、一个使用示例。" \
  --workspace ./workspace/user-test-easy \
  --max-steps 8
```

## 测试要求

- 已配置 `LLM_API_KEY` 和可用的 `LLM_MODEL`。
- 测试前建议清空或隔离 `./workspace/user-test-easy`。
- 不启用 `--autonomy`，该用例不测试用户交互。
- 不要求 Docker。

## 测试动作 list

1. 执行测试命令。
2. 观察 agent 是否调用文件写入工具。
3. 等待命令结束。
4. 检查 `./workspace/user-test-easy/README.md` 是否存在。
5. 阅读 `README.md`，确认内容是否包含项目名称、三条功能点和使用示例。
6. 记录终端 final answer 和生成文件内容摘要。

## 测试预期

- 命令正常退出。
- `README.md` 被创建在指定 workspace 下。
- 文件内容结构清楚，至少包含：
  - 项目名称
  - 三条功能点
  - 一个使用示例
- loop 通过 `agent_finish` 或无工具调用完成，不出现无意义循环。
- 不应出现路径逃逸或写到 workspace 外的行为。

## 测试结果

> 由测试执行者填写。

- 测试日期：
- 当前分支 / commit：
- 使用模型：
- 命令是否成功退出：
- 生成文件：
- 截图 / 日志链接：
- 观察到的问题：

## 测试总结

> 由测试执行者填写。

- 是否通过：
- 主要结论：
- 需要修复或优化的点：
