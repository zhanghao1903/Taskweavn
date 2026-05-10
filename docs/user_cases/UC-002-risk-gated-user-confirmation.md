# UC-002 风险门禁与用户确认

## 基本信息

| 字段 | 内容 |
|---|---|
| 编号 | UC-002 |
| 标题 | 风险门禁与用户确认 |
| 难度 | 适中 |
| 目标能力 | AutonomyGate、MessageBus、WaitCoordinator、CLI actionable/response |

## 描述

验证 `--autonomy risk_gated` 下，agent 在遇到高风险动作时会向用户发出 actionable 消息；用户回复 `yes` 后继续执行，回复 `no` 后跳过对应动作并尽量完成任务。该用例重点观察用户交互链路是否自然、消息是否持久化、拒绝路径是否稳定。

## 测试命令

```bash
taskweavn run \
  --task "帮我创建一个个人主页项目。需要 index.html、styles.css、README.md。页面包含姓名占位、简介、项目列表、联系方式。完成后可以用 shell 命令列出文件确认。" \
  --workspace ./workspace/user-test-medium \
  --max-steps 15 \
  --autonomy risk_gated \
  --risk-assessor baseline \
  --messages-db ./logs/user-test-medium-messages.sqlite
```

## 测试要求

- 已配置 `LLM_API_KEY` 和可用的 `LLM_MODEL`。
- 测试前建议清空或隔离 `./workspace/user-test-medium`。
- 需要在终端中观察 `[ask]` / `[fyi]` 输出。
- 不要求 Docker。
- 该用例至少需要一次人工回复。

## 测试动作 list

1. 执行测试命令。
2. 当出现 `[ask]` 时：
   - 如果请求写文件或运行普通检查命令，回复 `yes`。
   - 如果请求明显不必要或破坏性动作，回复 `no`。
3. 观察回复后 agent 是否继续执行。
4. 等待任务结束。
5. 检查 workspace 下是否包含：
   - `index.html`
   - `styles.css`
   - `README.md`
6. 检查 `./logs/user-test-medium-messages.sqlite` 是否生成。
7. 记录至少一条 actionable → response 的交互内容。

## 测试预期

- `write_file` 相关动作能顺利完成。
- `run_command` 或其他高风险动作触发用户确认。
- 用户回复 `yes` 后，对应动作继续执行。
- 用户回复 `no` 后，loop 不崩溃；应产生可理解的跳过行为，并继续尝试完成任务。
- `messages.sqlite` 中能查询到用户可见消息和回复。
- final answer 能说明完成内容；如果有动作被拒绝，应说明被跳过内容。

## 测试结果

> 由测试执行者填写。

- 测试日期：
- 当前分支 / commit：
- 使用模型：
- 实际用户回复记录：
- 命令是否成功退出：
- 生成文件：
- `messages.sqlite` 是否生成：
- 截图 / 日志链接：
- 观察到的问题：

## 测试总结

> 由测试执行者填写。

- 是否通过：
- 主要结论：
- 交互体验是否清楚：
- 需要修复或优化的点：
