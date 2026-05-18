# ISSUE-003: LLMRiskAssessor 调用缺少独立标识、日志和超时保护

## 状态

Open

## 严重级别

High

## 背景

用户测试 `user-test-cli-001` 时出现“几分钟无反应”。排查
`docs/user_cases/logs/sessions/user-test-cli-001` 后，最长阻塞基本定位到
`LLMRiskAssessor` 的一次 LLM 风险评估调用。

关键日志：

- `llm.jsonl` line 249：20:59:23 发起 `llm.request`
- `llm.jsonl` line 250：21:09:26 收到 `llm.response`
- 间隔：`602.397s`，约 10 分钟

关键上下文：

- 这次请求 `messages=2`
- `tools=0`
- 发生在主 LLM 已生成 `write_file` 之后、`gate.decision` 之前
- 随后 `gate.jsonl` line 71 显示：
  - `risk.assessor = "llm"`
  - `action = WriteFileAction`

判断：这次最长无响应不是工具执行、不是用户确认等待，而是
`LLMRiskAssessor` 的 LLM 风险评估调用卡住约 10 分钟。

## 其他观察

- `20:16:32 -> 20:50:57` 有一个 `2064s` gap，但这是第一个 task 结束、
  第二个 task 开始之间的空档，不像系统内部阻塞。
- 主 LLM 调用有几次较慢：`67s`、`61s`、`59s`、`54s`、`47s`，都是
  `tools=6` 的正常 agent 思考调用。
- 用户确认等待最大约 `77s`，对应 `gate.decision -> wait.got_response`，
  属于正常用户确认流。
- 工具执行最长 `12.1s`，是 `pip install -e ".[dev]"`。
- 没看到 `llm.retry` 事件；相关 response 里 `retry_count=0`。
- 没看到 `response_timeout`、tool timeout、sandbox execute 卡住。

## 当前行为

- Risk assessor 的 LLM 请求在 `llm.jsonl` 中看起来像普通 LLM 请求。
- 缺少稳定字段标识这次请求的业务目的，例如：
  - `request_purpose = "risk_assessment"`
  - `action_kind`
  - `action_event_id`
  - `risk_assessor`
- 缺少独立的 risk 日志事件：
  - `risk.request`
  - `risk.response`
  - `risk.failed`
- `LLMRiskAssessor` 虽然能在异常时 fallback baseline，但如果底层 LLM 调用长时间不返回，
  主流程会同步卡住。
- 没有独立短超时策略，风险评估调用可以拖住整个 AgentLoop。

## 期望行为

### 1. 给风险评估 LLM 请求加独立标识

`LLMRiskAssessor` 调用 LLM 时，metadata 至少包含：

```json
{
  "request_purpose": "risk_assessment",
  "risk_assessor": "llm",
  "action_kind": "WriteFileAction",
  "action_event_id": "<event_id>",
  "session_id": "<session_id>",
  "task_id": "<task_id>"
}
```

这样在 `llm.jsonl` 中可以直接区分：

- 主 agent 思考请求
- risk assessment 请求
- audit 请求
- 后续 RAG / summarization 请求

### 2. 增加 risk 专属日志事件

建议输出到 `risk.jsonl` 或现有结构化 logging channel：

```text
risk.request
risk.response
risk.failed
```

字段建议：

- `assessor`
- `action_kind`
- `action_event_id`
- `baseline`
- `dynamic`
- `final`
- `duration_ms`
- `fallback_used`
- `failure_type`
- `failure_message`
- `llm_provider_request_id`

### 3. 给 LLMRiskAssessor 独立短超时

风险评估不能无限拖住主流程。建议：

- `LLMRiskAssessor(timeout_seconds=...)`
- 默认值建议 `15s` 或 `30s`
- 超时后 fallback 到 baseline
- rationale 记录：`risk assessment timed out; falling back to baseline`

如果底层 provider 暂时不支持 timeout，可以先在 provider/request 层加配置字段并透传。

### 4. CLI / 配置暴露

建议增加配置：

```bash
--risk-timeout-seconds 15
```

或环境变量：

```bash
RISK_TIMEOUT_SECONDS=15
```

## 设计约束

- Risk assessor failure / timeout 不应让 AgentLoop 失败。
- fallback 到 baseline 必须保留 `dynamic >= baseline` 单调不变量。
- 主 LLM 请求和 risk LLM 请求必须能从日志中一眼区分。
- 不能依赖用户从 `tools=0/messages=2` 这种间接信号倒推这是风险评估。
- 默认超时应偏短，因为风险评估是频繁路径。

## 影响面

- `src/taskweavn/interaction/risk.py`
- `src/taskweavn/llm/client.py`
- `src/taskweavn/llm/contracts.py`
- `src/taskweavn/llm/providers/*`
- `src/taskweavn/llm/logging.py`
- `src/taskweavn/cli/main.py`
- observability 配置 / sink
- tests:
  - `tests/test_interaction_risk_llm.py`
  - logging 相关测试
  - CLI 配置测试

## 验收标准

- 风险评估 LLM 请求日志中包含 `request_purpose="risk_assessment"`。
- 日志能显示 action kind / action id，足以定位是哪一个 Action 的风险评估。
- 新增 `risk.request/risk.response/risk.failed` 或等价结构化事件。
- risk assessor 超时会 fallback baseline，不阻塞主流程超过配置阈值。
- 超时 fallback 有测试覆盖。
- 正常 LLMRiskAssessor 成功路径仍保持 `dynamic >= baseline`。
- CLI 或 env 可配置 risk timeout。

## 备注

这是用户测试暴露出的真实“无反应”问题。用户感知上像 CLI 卡死，但根因是同步风险评估
LLM 请求长时间未返回。需要把 risk assessor 从“隐形 LLM 调用”提升为可观测、可限时、
可 fallback 的独立子流程。
