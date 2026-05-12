# TaskWeavn Configuration Guide

> Status: current
> Last Updated: 2026-05-12
> Audience: users running TaskWeavn locally

---

## 1. 当前配置模型

TaskWeavn 当前还没有统一的 `config.yaml`。现在可用的配置入口分为两类：

- **环境变量**：主要用于 LLM provider、audit、thought persistence。
- **CLI 参数**：主要用于单次运行的 workspace、autonomy、message db、日志目录等。

后续的统一配置系统会把这些配置收敛到“全局配置 -> 项目配置 -> session 配置 -> task 配置”的层级模型里。在那之前，本文件是用户侧配置入口的权威说明。

---

## 2. 最小配置

默认 provider 是 `litellm`。最小运行方式：

```bash
export LLM_API_KEY="your-api-key"
export LLM_MODEL="anthropic/claude-sonnet-4-5-20250929"

uv run taskweavn run \
  --task "inspect this folder and summarize it" \
  --workspace ./workspace
```

如果你要使用 `LLM_PROVIDER=deepseek` 或 `LLM_PROVIDER=openrouter`，不要在 CLI 里传 `--model`。当前 CLI 的逻辑是：

```text
--model 未设置 -> LLMClient.from_env() -> 读取 LLM_PROVIDER 等环境变量
--model 已设置 -> LLMClient(model=...) -> 使用默认 LiteLLM provider 构造路径
```

因此 provider 切换应通过环境变量完成。

---

## 3. LLM Provider 配置

### 3.1 通用变量

| 变量 | 可选值 / 示例 | 默认值 | 说明 |
|---|---|---:|---|
| `LLM_PROVIDER` | `litellm` / `deepseek` / `openrouter` | `litellm` | 选择 provider。 |
| `LLM_MODEL` | `deepseek-chat`、`anthropic/...` | CLI 默认模型 | 当前主循环模型。 |
| `LLM_API_KEY` | `sk-...` | 无 | 通用 API key。具体 provider key 优先级更高。 |

### 3.2 LiteLLM provider

LiteLLM 是默认兼容 provider，适合继续使用原有模型配置。

```bash
export LLM_PROVIDER=litellm
export LLM_API_KEY="your-api-key"
export LLM_MODEL="anthropic/claude-sonnet-4-5-20250929"
```

### 3.3 DeepSeek provider

DeepSeek provider 使用 OpenAI-compatible SDK 路径，适合验证 DeepSeek 官方 provider、自动重试和 thinking metadata。

普通 ReAct / tool-call 路径建议先用：

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export LLM_MODEL=deepseek-chat
```

可选变量：

| 变量 | 示例 | 默认值 | 说明 |
|---|---|---:|---|
| `DEEPSEEK_API_KEY` | `sk-...` | 无 | DeepSeek 专用 key，优先于 `LLM_API_KEY`。 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | `https://api.deepseek.com` | DeepSeek API base URL。 |
| `LLM_THINKING_ENABLED` | `true` / `false` | 未设置 | 是否开启 thinking。 |
| `LLM_THINKING_EFFORT` | `high` / `max` | `high` | thinking effort。 |

Thinking 示例：

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export LLM_MODEL=deepseek-v4-pro
export LLM_THINKING_ENABLED=true
export LLM_THINKING_EFFORT=high
```

注意：

- `deepseek-chat`：当前实现按“支持 tool calls，不支持 thinking”处理。
- `deepseek-reasoner`：当前实现按“不支持 tool calls，支持 thinking”处理，不适合现有 ReAct 工具执行主路径。
- `deepseek-v4-pro`：当前实现按“支持 tool calls + thinking + reasoning_content input”处理。

如果你只是做用户测试，优先使用 `deepseek-chat`，它最贴近当前工具调用路径。

### 3.4 OpenRouter provider

OpenRouter provider 的重点是 provider routing：固定上游 provider 或 provider 顺序，减少同一模型被随机路由导致的缓存和行为波动。

```bash
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY="your-openrouter-api-key"
export LLM_MODEL="openrouter/model-name"
```

Routing 变量：

| 变量 | 示例 | 默认值 | 说明 |
|---|---|---:|---|
| `OPENROUTER_PROVIDER_ORDER` | `Anthropic,OpenAI` | 空 | provider 优先顺序。 |
| `OPENROUTER_PROVIDER_ONLY` | `Anthropic` | 空 | 只允许这些 provider。 |
| `OPENROUTER_PROVIDER_IGNORE` | `SomeProvider` | 空 | 排除这些 provider。 |
| `OPENROUTER_ALLOW_FALLBACKS` | `false` | `false` | 是否允许 fallback。 |
| `OPENROUTER_REQUIRE_PARAMETERS` | `true` | `true` | 是否要求 provider 支持请求参数。 |
| `OPENROUTER_DATA_COLLECTION` | `deny` / `allow` | 未设置 | 上游数据使用偏好。 |
| `OPENROUTER_ZDR` | `true` / `false` | 未设置 | zero data retention 偏好。 |

固定 provider 示例：

```bash
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY="your-openrouter-api-key"
export LLM_MODEL="openrouter/model-name"
export OPENROUTER_PROVIDER_ONLY="Anthropic"
export OPENROUTER_ALLOW_FALLBACKS=false
export OPENROUTER_REQUIRE_PARAMETERS=true
```

---

## 4. CLI 运行参数

核心参数：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--task` / `-t` | 必填 | 用户任务。 |
| `--workspace` / `-w` | `./workspace` | 工作区根目录。 |
| `--model` / `-m` | `None` | 直接指定模型。注意：设置后不会读取 `LLM_PROVIDER`。 |
| `--max-steps` | `20` | 最大 ReAct 迭代次数。 |
| `--log-dir` | `./logs` | JSONL 日志目录。 |

示例：

```bash
uv run taskweavn run \
  --task "read docs/roadmap.md and summarize the next server-side plan" \
  --workspace . \
  --max-steps 8 \
  --log-dir ./logs
```

---

## 5. Autonomy / 用户确认配置

交互层默认关闭。开启后，系统会创建 MessageStream、MessageBus、AutonomyGate 和 WaitCoordinator。

```bash
uv run taskweavn run \
  --task "make a small documentation-only change" \
  --workspace . \
  --autonomy risk_gated \
  --risk-assessor baseline \
  --messages-db ./logs/messages.sqlite
```

| 参数 | 可选值 | 默认值 | 说明 |
|---|---|---:|---|
| `--autonomy` | `full_auto` / `risk_gated` / `careful` / `collaborative` / `manual` | 未设置 | 未设置时不启用 gate，所有工具调用直接执行。 |
| `--risk-assessor` | `baseline` / `llm` / `composite` | `baseline` | autonomy gate 的风险评估器。 |
| `--session-id` | 任意字符串 | 随机 uuid hex | MessageStream / EventStream 关联用的 session id。 |
| `--messages-db` | SQLite 路径 | `<log-dir>/messages.sqlite` | MessageStream 存储位置。 |

Autonomy presets：

| Preset | 行为 |
|---|---|
| `full_auto` | 不询问用户，不阻塞。 |
| `risk_gated` | 风险值 `>= 0.5` 时询问，等待最多 300 秒。 |
| `careful` | 风险值 `>= 0.3` 时询问，等待最多 600 秒。 |
| `collaborative` | 低置信度时询问，默认无限等待。 |
| `manual` | 每个 Action 前都询问，默认无限等待。 |

Risk assessors：

| Assessor | 行为 |
|---|---|
| `baseline` | 只使用 Action class 的静态 `baseline_risk`。 |
| `llm` | 使用主循环 LLM 动态评估风险。 |
| `composite` | baseline + LLM 组合，保留静态风险下限。 |

---

## 6. Audit 配置

AuditAgent 默认关闭。它用于对 `CodeAction` 做同步审计，审计失败不会 crash 主循环。

环境变量：

| 变量 | 示例 | 默认值 | 说明 |
|---|---|---:|---|
| `AUDIT_ENABLED` | `true` | `false` | 是否开启审计。 |
| `AUDIT_MODEL` | `anthropic/...` | 未设置 | 审计模型。 |
| `AUDIT_API_KEY` | `sk-...` | 未设置 | 审计模型 key。 |

CLI 参数：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--audit` / `--no-audit` | `--no-audit` | 显式开启/关闭审计。 |
| `--audit-model` | 未设置 | 覆盖审计模型。 |

示例：

```bash
export AUDIT_ENABLED=true
export AUDIT_MODEL="anthropic/claude-haiku-..."

uv run taskweavn run \
  --task "make a tiny code change and run tests" \
  --workspace .
```

---

## 7. ThoughtStore 配置

ThoughtStore 默认关闭。开启后，系统可以把 LLM 推理阶段写入 SQLite。

环境变量：

| 变量 | 可选值 / 示例 | 默认值 | 说明 |
|---|---|---:|---|
| `THOUGHTS_ENABLED` | `true` / `false` | `false` | 是否开启。 |
| `THOUGHTS_BACKEND` | `null` / `sqlite` | `null` | 存储后端。 |
| `THOUGHTS_DB_PATH` | `./logs/thoughts.sqlite` | 未设置 | SQLite 文件路径。 |
| `THOUGHTS_PHASES` | `plan,reason,reflect` | 未设置 | 只保存指定阶段；未设置表示全部。 |

CLI 参数：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--thoughts` / `--no-thoughts` | `--no-thoughts` | 开启/关闭 thought persistence。 |
| `--thoughts-db` | `<log-dir>/thoughts.sqlite` | SQLite 文件路径。 |
| `--thoughts-phases` | 未设置 | 逗号分隔的阶段 allow-list。 |

示例：

```bash
uv run taskweavn run \
  --task "inspect docs and propose a plan" \
  --workspace . \
  --thoughts \
  --thoughts-db ./logs/thoughts.sqlite
```

---

## 8. 日志配置

当前日志系统由 CLI 的 `--log-dir` 开启，写入四个 JSONL 文件：

| 文件 | 内容 |
|---|---|
| `<log-dir>/tool.log` | Runtime dispatch、工具结果、耗时。 |
| `<log-dir>/action.log` | EventStream 中的 Action。 |
| `<log-dir>/observation.log` | EventStream 中的 Observation。 |
| `<log-dir>/llm.log` | LLM request / response / retry。 |

示例：

```bash
uv run taskweavn run \
  --task "summarize this project" \
  --workspace . \
  --log-dir ./logs
```

更细粒度的日志级别、全局/session 继承、热更新和归档规则属于下一阶段的可配置日志系统。

---

## 9. 推荐配置组合

### 9.1 DeepSeek 普通用户测试

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export LLM_MODEL=deepseek-chat

uv run taskweavn run \
  --task "read docs/roadmap.md and summarize the next implementation step" \
  --workspace . \
  --max-steps 8
```

### 9.2 DeepSeek + 风险确认

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export LLM_MODEL=deepseek-chat

uv run taskweavn run \
  --task "append a short note to docs/plans/feature/configurable-logging-system.md" \
  --workspace . \
  --autonomy risk_gated \
  --risk-assessor baseline \
  --messages-db ./logs/messages.sqlite
```

### 9.3 OpenRouter 固定 provider

```bash
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY="your-openrouter-api-key"
export LLM_MODEL="openrouter/model-name"
export OPENROUTER_PROVIDER_ONLY="Anthropic"
export OPENROUTER_ALLOW_FALLBACKS=false

uv run taskweavn run \
  --task "inspect this project and list the top three risks" \
  --workspace .
```

---

## 10. 常见问题

### 为什么我设置了 `LLM_PROVIDER=deepseek`，但看起来没有生效？

检查是否传了 `--model`。当前 CLI 中，传 `--model` 会绕过 `LLMClient.from_env()`，因此不会读取 `LLM_PROVIDER`。

推荐：

```bash
export LLM_PROVIDER=deepseek
export LLM_MODEL=deepseek-chat
uv run taskweavn run --task "..." --workspace .
```

不要这样：

```bash
uv run taskweavn run --task "..." --workspace . --model deepseek-chat
```

### `deepseek-reasoner` 能不能跑工具调用？

当前实现中不能。`deepseek-reasoner` 被标记为 thinking-only、无 tool-call capability。现有 AgentLoop 是 ReAct 工具执行路径，因此用户测试应优先用 `deepseek-chat`。

### 配置文件在哪里？

目前还没有统一配置文件。当前生效入口是环境变量 + CLI 参数。统一 `config.yaml` 是后续配置系统计划的一部分。
