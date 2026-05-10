# ISSUE-001: LLM 请求失败时 AgentLoop 无 Action/Observation 记录

## 状态

Fixed locally

## 严重级别

High

## 背景

用户测试困难用例时，LLM 请求在第一轮失败：

```text
model: openrouter/deepseek/deepseek-v4-pro
error: litellm.APIError: APIError: OpenrouterException - Internal Server Error
```

由于失败发生在 `llm.chat(...)` 返回 tool calls 之前，当前程序直接失败退出，没有任何
`Action` 或 `Observation` 落到 `EventStream`。

## 复现用例

运行长任务用户测试，例如：

```bash
code-agent run \
  --task "帮我从零搭建一个个人网站项目。要求：1. 首页有 hero、about、projects、contact 四个区域；2. 使用独立 CSS；3. README 说明如何预览；4. 创建一个简单的 TODO.md 记录后续优化；5. 完成后检查目录结构和关键文件内容。" \
  --workspace ./workspace/user-test-hard \
  --max-steps 30 \
  --autonomy careful \
  --risk-assessor composite
```

当上游 LLM API 返回 5xx / 连接失败 / provider 内部错误时复现。

## 当前行为

- `AgentLoop.run(...)` 失败退出。
- 没有 `Action` 记录。
- 没有 `Observation` 记录。
- `EventStream` 无法解释本次 run 为什么中断。
- Session / MessageStream 后续也无法可靠展示"失败发生在 LLM 请求阶段"。

## 期望行为

LLM 请求失败也应该被表示为一条可回放、可审计的事件。

建议新增内置控制流事件：

- `LLMRequestFailedAction` 或更通用的 `AgentErrorAction`
- `LLMRequestFailedObservation` 或 `AgentErrorObservation`

最小可接受版本：

- 在 `llm.chat(...)` 抛错时捕获异常。
- 生成一条失败 observation，包含：
  - `error_type`
  - `message`
  - `model`
  - `phase = "llm_chat"`
  - `step`
  - `task_id`
- 追加到 `EventStream`。
- `LoopResult` 返回 `finished=False`，`stop_reason="llm_error"`。

## 设计约束

- 不应该把 provider 的 5xx 伪装成 agent 逻辑失败。
- 不应该让 Runtime 承担 LLM 错误，因为错误发生在 Action 产生之前。
- 事件需要能被 `SqliteEventStream` 序列化/反序列化。
- 对 MessageStream 可选：如果 interaction layer 已启用，可以额外发一条 informational message 给用户。

## 影响面

- `src/code_agent/core/loop.py`
- `src/code_agent/types/common.py`
- `tests/test_loop.py`
- 可能涉及 `LoopResult.stop_reason` 的 literal/文档更新

## 验收标准

- 新增测试：LLMClient.chat 抛异常时，loop 不崩溃。
- `EventStream` 至少包含一条失败 observation。
- `LoopResult.finished is False`。
- `LoopResult.stop_reason == "llm_error"`。
- SQLite EventStream round-trip 正常。
- 现有 3.6 interaction/gating 行为不回退。

## 备注

这是用户测试暴露出的真实问题。它不属于工具执行失败（Runtime 已经能转为
`ErrorObservation`），而是 ReAct loop 在 Action 生成前的失败路径缺少事件化表达。

## 修复记录

- 新增 `AgentErrorObservation` 表示 loop 层、Action 生成前的失败。
- `AgentLoop._run_inner` 捕获 `llm.chat(...)` 异常：
  - 追加 `AgentErrorObservation(error_type="llm_error", phase="llm_chat", ...)`
    到 `EventStream`
  - 返回 `LoopResult(finished=False, stop_reason="llm_error")`
  - interaction layer 启用时，额外发布一条 informational message 到 `MessageStream`
- 新增测试覆盖：
  - LLM 抛错时 loop 不崩溃
  - EventStream 存在失败 observation
  - `SqliteEventStream` 可 round-trip `AgentErrorObservation`
