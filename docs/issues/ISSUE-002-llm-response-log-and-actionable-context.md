# ISSUE-002: LLM response 日志缺少正文，Actionable 提示缺少决策上下文

## 状态

Open

## 严重级别

Medium

## 背景

用户测试 CLI 交互时发现两个可观测性 / 交互体验问题：

1. LLM response 日志只记录 metadata，没有打印实际响应正文。
2. `AutonomyGate` 触发 `actionable` 时，CLI 的 `[ask]` 提示只显示 Action 类型和风险，不显示用户做决定所需的具体信息。

示例日志：

```json
{
  "category": "llm",
  "context": {
    "model": "deepseek-v4-pro",
    "provider": "deepseek",
    "provider_request_id": "f885f1d6-24a8-4226-896e-f9724044fc13",
    "session_id": "user-test-cli-001",
    "task_id": "77f7b1dc15d9441ba4d8d1cb836399b2",
    "workspace_root": "/Users/zhanghao/PycharmProjects/pythonProject/codeAgent/docs/user_cases/workspace/user-test-cli"
  },
  "data": {
    "content_length": 183,
    "has_reasoning_content": false,
    "model": "deepseek-v4-pro",
    "provider": "deepseek",
    "retry_count": 0,
    "tool_calls": []
  },
  "event": "response",
  "level": "INFO",
  "message": "response"
}
```

CLI 提示：

```text
[ask] OK to run RunCommandAction? (risk 0.50; risk 0.50 >= threshold 0.30) [yes, no]
> y
```

## 当前行为

### LLM response 日志

- 只记录：
  - `content_length`
  - `tool_calls`
  - token usage
  - provider/model metadata
- 不记录：
  - `response.content`
  - `reasoning_content`（如果允许暴露）
  - tool call arguments（至少 debug profile 下需要）

这导致用户测试失败时只能看到模型“回复过”，但无法知道回复了什么。

### Actionable ask

当前提示只显示：

- Action class name
- risk score
- gate reason
- yes/no options

但没有显示 Action payload，例如：

- `RunCommandAction.command`
- `RunCommandAction.cwd`
- `WriteFileAction.path`
- `CodeAction.intent`
- `CodeAction.tracking.files`

用户无法判断是否应该授权。

## 期望行为

### LLM response 日志

至少在 debug / full-debug profile 下记录：

- `content`
- `reasoning_content`（仅当配置允许）
- `tool_calls` 的 name + arguments 摘要

默认 profile 可以继续只记录 metadata，避免日志过大或泄露敏感内容。

建议字段：

```json
{
  "content": "...",
  "content_length": 183,
  "tool_calls": [
    {
      "id": "...",
      "name": "run_command",
      "arguments": "{\"command\": \"ls -la\"}"
    }
  ]
}
```

### Actionable ask

CLI `[ask]` 应展示面向用户的决策摘要，而不是只展示 class name。

示例：

```text
[ask] OK to run shell command?
      command: ls -la
      cwd: .
      risk: 0.50 (risk 0.50 >= threshold 0.30)
      options: yes, no
> 
```

对于不同 Action 应有不同摘要：

| Action | 最小提示字段 |
|---|---|
| `RunCommandAction` | `command`, `cwd`, `timeout_seconds` |
| `WriteFileAction` | `path`, `content` 摘要 / 字符数 |
| `ReadFileAction` | `path` |
| `CodeAction` | `intent`, `tracking.files`, `code` 摘要 |
| fallback | `action.to_dict()` 的安全摘要 |

## 设计约束

- 日志需要尊重 redaction / profile 配置。
- 默认日志不应无条件打印完整 prompt / response / tool arguments。
- CLI ask 应优先展示“用户做 yes/no 决策需要的信息”，不是完整 JSON dump。
- MessageStream 中的 `AgentMessage.context` 已经有 `action_kind` / `action_event_id`，可以扩展为包含 action 摘要字段。

## 影响面

- `src/taskweavn/llm/logging.py`
- `src/taskweavn/core/loop.py`
- `src/taskweavn/cli/main.py`
- 可能涉及 observability profile / redaction 配置
- `tests/test_cli.py`
- `tests/test_loop_interaction.py`
- logging 相关测试

## 验收标准

- debug/full-debug profile 下，LLM response 日志可看到正文或正文摘要。
- 默认 profile 不强制泄露完整 response。
- `[ask]` 对 `RunCommandAction` 至少展示 command/cwd/timeout。
- `[ask]` 对 `WriteFileAction` 至少展示 path 和 content 摘要。
- MessageStream 中 actionable 的 `content` 或 `context` 包含足够的 action 摘要。
- 新增用户测试覆盖 CLI ask 可读性。

## 备注

这是用户测试暴露出的产品体验问题：当前 agent 已经能判断“需要问用户”，但问法本身信息不足，导致用户无法做出可靠授权决策。
