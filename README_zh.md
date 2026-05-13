# TaskWeavn

> [English](README.md)

TaskWeavn 是一个具备**强类型 Action / Observation**、**EventStream 驱动的
ReAct 循环**、**可插拔 Runtime** 和**用户协作交互层**的代码智能体——基于
OpenHands SDK 构建 LLM 适配层。

项目当前处于 Phase 3：把单轮 ReAct 基础扩展为具备持久会话、工作区隔离、消息流交互和自主度控制的 agent。

## 当前状态

**Phase 3 进行中** — 持久 workspace/session、SQLite EventStream/MessageStream、自主度预设、MessageBus、AgentLoop 交互层接入和 LLM 风险评估均已落地。当前继续收紧派生 `Session.status` 和用户可见 session 表面。

| 阶段 | 范围 | 状态 |
| ---- | ---- | ---- |
| 1 | Action/Observation 类型、EventStream、Runtime、ReAct 循环 | ✅ 完成 |
| 2 | `CodeAction`（沙箱执行）+ AuditAgent + SqliteThoughtStore | ✅ 完成 |
| 3 | 持久会话、MessageStream、自主度门控、用户交互、风险评估 | 🚧 进行中 |
| 4 | 多 Agent 编排（planner / executor / auditor） | 计划中 |

## 项目亮点

### 消息流替代阻塞式打断

传统 human-in-the-loop 系统在等待用户响应时会暂停执行，由系统主导节奏。TaskWeavn 将其替换为**消息流模型**：agent 向共享消息流发送消息，用户可以随时响应，也可以不响应。没有响应时 agent 如何处理，由每个 agent 独立配置的**自主度等级**决定，而非硬编码在系统中。

自主度最高时，消息流退化为只读执行日志；自主度最低时，高风险决策会等待用户确认。任务质量与打断频率之间的权衡是用户设置，不是架构约束。

### 量化风险与自主度

每个 `BaseAction` 都有 class-level `baseline_risk`。运行时评估器可以动态抬高风险，但不能低于这个静态下限。自主度门控会综合：

- Action 的静态风险下限；
- 可选的 LLM 动态风险评估；
- 用户配置的 autonomy preset；
- 同步等待或异步延迟响应策略。

最终结果是三选一：静默执行、通知用户后执行、或发布 actionable message 并根据预设等待/延后。

### 约束驱动的 LLM 编排

用户用自然语言描述需求，**Orchestration Designer**（编排设计 meta-agent）将意图转化为在 **ConstraintProfile** 约束下合法的 agent 协作图——输出天然合法，无需事后校验。约束 profile 本身是可版本化的，随成功率数据积累逐步松绑，让早期体验简单可靠，同时随时间扩展能力边界。

约束是一等公民，每条规则都记录了它守护的失败模式。松绑一条约束是有数据依据的工程决策，而不是直觉猜测。

> 完整设计：[docs/multi_agent_collaboration_architecture.md](docs/multi_agent_collaboration_architecture.md) · [docs/multi_agent_collaboration_architecture_en.md](docs/multi_agent_collaboration_architecture_en.md)

## 设计理念

- **Action / Observation 对称。** 流经 agent 的每个事件都是二者之一——Pydantic v2 冻结模型，带 `kind` 鉴别器，JSON 往返不丢失类型。单一 `EventStream` 是"发生了什么"的唯一真相来源，消费方（循环、审计、回放、持久化）读取同一 Protocol，与存储无关。
- **工具 = Action 类 + executor。** `Tool[ActionT, ObservationT]` 向 LLM 暴露 schema 并向 Runtime 注册自己。新增工具只需一个文件，循环层完全不感知。
- **Runtime 可替换。** 当前是 `LocalRuntime`（进程内），Phase 2.2 换成沙箱/Docker。`execute(action) -> observation` 合约不变，消费方零改动。
- **永不抛异常合约。** Runtime 捕获所有 executor 异常并返回 `ErrorObservation`，循环将其作为 tool message 反馈给 LLM——错误成为可恢复的信号，而非崩溃。
- **LLM 层依赖 `litellm`。** `LLMClient.chat()` 直接穿透 `litellm.completion`，Pydantic Action 无需继承 openhands 的 `Action` / `Observation` 层级即可生成 OpenAI 格式的 tool schema。

## 快速开始

需要 Python 3.12+ 和 [`uv`](https://github.com/astral-sh/uv)。

```bash
uv sync                                  # 安装依赖和开发工具
export LLM_PROVIDER=litellm              # litellm | deepseek | openrouter
export LLM_API_KEY=sk-ant-...            # provider API key
export LLM_MODEL=anthropic/claude-sonnet-4-5-20250929  # 可选，覆盖默认模型

uv run taskweavn run \
    --task "write a hello.py that prints hi, then run it" \
    --workspace ./workspace \
    --max-steps 10
```

Agent 将每个 Action 和 Observation 写入内存 `EventStream`，在以下任一情况停止：显式的 `agent_finish` 工具调用、LLM 轮次中无 `tool_calls`，或达到 `--max-steps`。

使用 DeepSeek：

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-...
export LLM_MODEL=deepseek-chat
```

通过环境变量切换 provider 时不要传 `--model`；当前 CLI 只有在
`--model` 未设置时才会通过 `LLMClient.from_env()` 读取 `LLM_PROVIDER`。
完整配置项见 [配置指南](docs/configuration.md)。

开启 Phase 3 交互层：

```bash
uv run taskweavn run \
    --task "inspect this project and propose a small safe improvement" \
    --workspace ./workspace \
    --autonomy risk_gated \
    --risk-assessor baseline \
    --messages-db ./logs/messages.sqlite
```

可用 autonomy preset：`full_auto`、`risk_gated`、`careful`、`collaborative`、`manual`。可用 risk assessor：`baseline`、`llm`、`composite`。

## 推荐本地测试命令

### 使用 DeepSeek 的基础任务

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-...
export LLM_MODEL=deepseek-chat

uv run taskweavn run \
    --task "write a hello.py that prints hi, then run it" \
    --workspace ./workspace \
    --max-steps 10
```

### 开启 autonomy 门控

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-...
export LLM_MODEL=deepseek-chat

uv run taskweavn run \
    --task "inspect this project and propose a small safe improvement" \
    --workspace ./workspace \
    --autonomy risk_gated \
    --risk-assessor baseline \
    --messages-db ./logs/messages.sqlite
```

### 日志输出位置

当设置 `--log-dir`（默认 `./logs`）时，CLI 运行会写入 session 归档目录：

```text
<log-dir>/
  global/config.jsonl
  sessions/<session-id>/
    manifest.json
    action.jsonl
    observation.jsonl
    tool.jsonl
    llm.jsonl
    bus.jsonl
    gate.jsonl
    wait.jsonl
    audit.jsonl
```

常用日志调试开关：

```bash
uv run taskweavn run \
    --task "inspect this project and summarize provider config" \
    --workspace ./workspace \
    --session-id debug-llm-run \
    --logging-profile debug-llm \
    --log-dir ./logs
```

可用 profile 包括 `normal`、`quiet`、`debug-llm`、`debug-tools`、`debug-bus`
和 `full-debug`。`manifest.json` 是 UI、测试人员和归档脚本定位日志的稳定入口。
旧的 `configure_logging()` API 仍支持 `tool.log` 这类 flat file，但
`taskweavn run` 使用 session archive。

此外，`--messages-db`（默认 `<log-dir>/messages.sqlite`）以 SQLite 存储交互层消息流，
`--thoughts-db`（默认 `<log-dir>/thoughts.sqlite`）在通过 `--thoughts` 开启 thought
持久化后存储 LLM 推理过程。

## 编程调用

```python
from taskweavn.core.loop import AgentLoop
from taskweavn.llm.client import LLMClient
from taskweavn.runtime.local import LocalRuntime
from taskweavn.tools.fs import ReadFileTool, WriteFileTool, ListDirTool
from taskweavn.tools.shell import RunCommandTool
from taskweavn.tools.workspace import Workspace

ws = Workspace("./workspace")
runtime = LocalRuntime()
tools = [ReadFileTool(ws), WriteFileTool(ws), ListDirTool(ws), RunCommandTool(ws)]
for t in tools:
    t.register(runtime)

loop = AgentLoop(llm=LLMClient.from_env(), runtime=runtime, tools=tools)
result = loop.run("create README.md describing this folder")
print(result.final_answer)
```

编程方式开启交互层时，需要成套接入 message stream、bus、gate 和 wait coordinator：

```python
from taskweavn.interaction import (
    AutonomyGate,
    BaselineOnlyAssessor,
    InProcessMessageBus,
    SqliteMessageStream,
    WaitCoordinator,
    get_preset,
)

behavior = get_preset("risk_gated")
stream = SqliteMessageStream("./workspace/.code-agent/messages.sqlite")
bus = InProcessMessageBus(stream)
gate = AutonomyGate(behavior, BaselineOnlyAssessor())

loop = AgentLoop(
    llm=LLMClient.from_env(),
    runtime=runtime,
    tools=tools,
    workspace_root=ws.root,
    session_id="demo-session",
    bus=bus,
    gate=gate,
    wait_coordinator=WaitCoordinator(bus, behavior),
)
```

## 项目结构

```
src/taskweavn/
├── types/          # BaseEvent / BaseAction / BaseObservation + registry
├── core/           # EventStream, SQLite EventStream, sessions, AgentLoop
├── interaction/    # Risk, autonomy, AgentMessage, MessageStream, MessageBus
├── memory/         # ThoughtStore（旁路存储，可选接入）
├── llm/            # LLMClient (openhands-sdk + litellm), tool schema helpers
├── runtime/        # Runtime Protocol + LocalRuntime
├── tools/          # Workspace, Tool base, fs/shell/code-action tools
├── audit/          # AuditAgent for CodeAction review
├── observability/  # Logging setup
├── orchestration/  # 多 Agent Protocol（Phase 4 占位）
└── cli/            # Typer 入口点（`taskweavn`）
```

## 文档

| 文档 | 中文 | English |
| ---- | ---- | ------- |
| 配置指南 | [configuration.md](docs/configuration.md) | - |
| 架构参考 | [architecture.md](docs/architecture.md) | - |
| 交互层技术设计 | [interaction_layer_design.md](docs/interaction_layer_design.md) | - |
| 项目计划 | [agent_project_plan.md](docs/agent_project_plan.md) | [agent_project_plan_en.md](docs/agent_project_plan_en.md) |
| 多 Agent 协作架构 | [multi_agent_collaboration_architecture.md](docs/multi_agent_collaboration_architecture.md) | [multi_agent_collaboration_architecture_en.md](docs/multi_agent_collaboration_architecture_en.md) |
| 用户测试用例 | [docs/user_cases](docs/user_cases) | - |

## 开发

```bash
uv run pytest          # 运行测试套件
uv run ruff check .    # 代码检查
uv run mypy src tests  # 严格类型检查
```

目标质量门禁是 tests、Ruff、mypy 全绿。当前 PR review follow-up：`uv run mypy src` 已通过，`uv run mypy src tests` 的剩余问题单独由 [issue #7](https://github.com/zhanghao1903/codeAgent/issues/7) 跟踪。

## License

MIT
