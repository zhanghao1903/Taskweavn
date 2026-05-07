# codeAgent

> [English](README.md)

一个具备**强类型 Action / Observation**、**EventStream 驱动的 ReAct 循环**和**可插拔 Runtime** 的代码智能体——基于 OpenHands SDK 构建 LLM 适配层。路线图涵盖四个阶段：ReAct 基础 → CodeAction 审计 → RAG 记忆 → 多 Agent 编排。

## 当前状态

**Phase 2 完成** — CodeAction schema、沙箱执行器、AuditAgent 和 SqliteThoughtStore 均已就绪。

| 阶段 | 范围 | 状态 |
| ---- | ---- | ---- |
| 1 | Action/Observation 类型、EventStream、Runtime、ReAct 循环 | ✅ 完成 |
| 2 | `CodeAction`（沙箱执行）+ AuditAgent + SqliteThoughtStore | ✅ 完成 |
| 3 | RAG 记忆 + SQLite EventStream + 预算控制器 | 计划中 |
| 4 | 多 Agent 编排（planner / executor / auditor） | 计划中 |

## 项目亮点

### 消息流替代阻塞式打断

传统 human-in-the-loop 系统在等待用户响应时会暂停执行，由系统主导节奏。codeAgent 将其替换为**消息流模型**：agent 向共享消息流发送消息，用户可以随时回应，也可以不回应。没有响应时 agent 如何处理，由每个 agent 独立配置的**自主度等级**决定，而非硬编码在系统中。

自主度最高时，消息流退化为只读执行日志；自主度最低时，每个决策都等待用户确认。任务质量与打断频率之间的权衡是用户设置，不是架构约束，选择权完全在用户。

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
export LLM_API_KEY=sk-ant-...            # 任意 litellm 支持的 provider key
export LLM_MODEL=anthropic/claude-sonnet-4-5-20250929  # 可选，覆盖默认模型

uv run code-agent run \
    --task "write a hello.py that prints hi, then run it" \
    --workspace ./workspace \
    --max-steps 10
```

Agent 将每个 Action 和 Observation 写入内存 `EventStream`，在以下任一情况停止：显式的 `agent_finish` 工具调用、LLM 轮次中无 `tool_calls`，或达到 `--max-steps`。

## 编程调用

```python
from code_agent.core.loop import AgentLoop
from code_agent.llm.client import LLMClient
from code_agent.runtime.local import LocalRuntime
from code_agent.tools.fs import ReadFileTool, WriteFileTool, ListDirTool
from code_agent.tools.shell import RunCommandTool
from code_agent.tools.workspace import Workspace

ws = Workspace("./workspace")
runtime = LocalRuntime()
tools = [ReadFileTool(ws), WriteFileTool(ws), ListDirTool(ws), RunCommandTool(ws)]
for t in tools:
    t.register(runtime)

loop = AgentLoop(llm=LLMClient.from_env(), runtime=runtime, tools=tools)
result = loop.run("create README.md describing this folder")
print(result.final_answer)
```

## 项目结构

```
src/code_agent/
├── types/          # BaseEvent / BaseAction / BaseObservation + registry
├── core/           # EventStream, ReAct AgentLoop
├── memory/         # ThoughtStore（旁路存储，可选接入）
├── llm/            # LLMClient (openhands-sdk + litellm), tool-schema helpers
├── runtime/        # Runtime Protocol + LocalRuntime
├── tools/          # Workspace, Tool base, ReadFile/WriteFile/ListDir/RunCommand
├── orchestration/  # 多 Agent Protocol（Phase 4 占位）
└── cli/            # Typer 入口点（`code-agent`）
```

## 文档

| 文档 | 中文 | English |
| ---- | ---- | ------- |
| 项目计划 | [agent_project_plan.md](docs/agent_project_plan.md) | [agent_project_plan_en.md](docs/agent_project_plan_en.md) |
| 多 Agent 协作架构 | [multi_agent_collaboration_architecture.md](docs/multi_agent_collaboration_architecture.md) | [multi_agent_collaboration_architecture_en.md](docs/multi_agent_collaboration_architecture_en.md) |

## 开发

```bash
uv run pytest          # 运行测试套件
uv run ruff check .    # 代码检查
uv run mypy src tests  # 严格类型检查
```

提交前三项检查均须通过。

## License

MIT
