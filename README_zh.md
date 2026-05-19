# TaskWeavn

> 用户可见产品名：Plato
> English: [README.md](README.md)
> 文档入口：[docs/README.md](docs/README.md)

TaskWeavn 是 Plato 背后的本地任务智能体系统。它把用户的自然语言意图转换为以任务为中心的计划，让用户能够查看、修正和确认这些任务，再用可观察的消息、确认动作、文件变更、审计证据和诊断信息完成执行。

Plato 不应是一个套壳 CLI 聊天产品。它的产品方向是 Task-first：

```text
用户意图
  -> RawTask 与可行性判断
  -> Collaborator 生成 Task Tree List
  -> 用户编辑 / 确认 TaskNode
  -> TaskPublisher 发布任务
  -> TaskBus 分发执行
  -> UI 展示拓扑、消息、确认、文件、审计和结果
```

## 当前状态

TaskWeavn 已经不再是早期的单轮 ReAct agent。当前重点是把 server-core 基础能力打磨成本地桌面产品。

| 区域 | 状态 | 说明 |
|---|---:|---|
| 核心 agent 基础 | 完成 | 强类型 Action/Observation、EventStream、Runtime、ReAct loop、CLI。 |
| 沙箱 / 审计 / 记忆 | 完成 | CodeAction、Docker sandbox、AuditAgent、SQLite ThoughtStore。 |
| Interaction Layer | 完成到 Phase 3.8 | Session、workspace、risk/autonomy、message、bus、wait coordination、loop integration、LLM risk、派生 session status。 |
| LLM reliability | 完成 | Provider 抽象、自动重试、DeepSeek thinking、OpenRouter routing。 |
| Logging and observability | 完成 / 后续增强 | 结构化 JSONL 日志、session archives、profiles、运行时控制；集中化配置仍待完成。 |
| Task authoring | server-core 完成 | RawTask、可行性判断、DraftTaskTree、Collaborator authoring commands、publish boundary。 |
| Task publishing | server-core 部分完成 | TaskPublisher、SQLite TaskBus publish surface、SQLite publish control plane、API publish transport；执行生命周期仍待完成。 |
| Plato frontend baseline | 完成 / 待真实集成 | `frontend/src` 已有 Main Page scaffold、state catalog、typed mock/API adapter、shared API types、UI primitives。 |
| Plato productization | 进行中 | UI/backend contract、sidecar API、真实后端集成、settings、audit、diagnostics、packaging。 |

活跃规划从这些文档开始：

- [docs/README.md](docs/README.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/project/roadmap.md](docs/project/roadmap.md)
- [docs/gaps/README.md](docs/gaps/README.md)
- [docs/architecture/README.md](docs/architecture/README.md)

## 项目亮点

### Task-First UX

Task 是第一用户交互对象。Chat 是输入、澄清和解释，不是主要状态模型。用户应该可以选中 TaskNode，查看状态，追加指导，回答确认，查看相关消息，并检查文件变更。

### 强类型 Agent Core

Action 和 Observation 是带 `kind` 鉴别器的 frozen Pydantic model。Tool 向 LLM 暴露 Action schema。Runtime 执行后返回 Observation，executor 失败会变成 `ErrorObservation`，而不是让 loop 崩溃。

### Interaction Layer

TaskWeavn 使用一条 session message stream，并通过 task scope 做投影。交互层包括：

- `AgentMessage` 与 `SqliteMessageStream`；
- `InProcessMessageBus`；
- 量化风险与 autonomy presets；
- `AutonomyGate` 与 `WaitCoordinator`；
- 同步等待与异步延迟响应路径。

### Authoring And Publishing Separation

Authoring Domain 与 Execution TaskBus 分离：

- RawTask 和 DraftTaskTree 支持执行前的探索式规划。
- Collaborator authoring tools 根据用户输入持续修正 task tree。
- TaskPublisher 将用户确认后的 task tree 发布到 TaskBus。
- API、scheduler、pipeline、custom tree publisher 都走同一个 publish 边界。

## 快速开始：CLI Agent

需要 Python 3.12+ 和 [`uv`](https://github.com/astral-sh/uv)。

```bash
uv sync

export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-...
export LLM_MODEL=deepseek-chat

uv run taskweavn run \
  --task "write a hello.py that prints hi, then run it" \
  --workspace ./workspace \
  --max-steps 10
```

开启 interaction layer：

```bash
uv run taskweavn run \
  --task "inspect this project and propose a small safe improvement" \
  --workspace ./workspace \
  --autonomy risk_gated \
  --risk-assessor baseline \
  --messages-db ./logs/messages.sqlite
```

可用 autonomy presets：

```text
full_auto, risk_gated, careful, collaborative, manual
```

可用 risk assessors：

```text
baseline, llm, composite
```

完整配置见 [docs/configuration.md](docs/configuration.md)。

## 快速开始：Frontend Baseline

Plato 前端 baseline 位于 `frontend/`。

```bash
cd frontend
npm install
npm run dev
```

常用前端检查：

```bash
npm test
npm run lint
npm run build
```

当前前端是 Main Page baseline，包含 typed mock scenarios 和 HTTP adapter contract。真实后端 sidecar 集成仍是 gap，从 [docs/gaps/README.md](docs/gaps/README.md)、[docs/product/plato-ui-api-contract.md](docs/product/plato-ui-api-contract.md) 和 [docs/architecture/ui-backend-communication.md](docs/architecture/ui-backend-communication.md) 跟踪。

## 文档模型

当前文档模型保持轻量：

```text
Product intent + Architecture facts
  -> Roadmap priority
  -> Gap registry
  -> Plan package
  -> Implementation
  -> Release record
```

关键入口：

| 需求 | 入口 |
|---|---|
| 当前方向 | [docs/roadmap.md](docs/roadmap.md) |
| 执行队列 | [docs/project/roadmap.md](docs/project/roadmap.md) |
| gap 路由 | [docs/gaps/README.md](docs/gaps/README.md) |
| 架构事实 | [docs/architecture/README.md](docs/architecture/README.md) |
| 产品意图 | [docs/product/README.md](docs/product/README.md) |
| plans | [docs/plans/README.md](docs/plans/README.md) |
| decisions | [docs/decisions/README.md](docs/decisions/README.md) |
| releases | [docs/releases/README.md](docs/releases/README.md) |

## 项目结构

```text
src/taskweavn/
  audit/          AuditAgent 与 audit observations
  cli/            Typer CLI 入口
  core/           AgentLoop、EventStream、session、workspace layout
  interaction/    Risk、autonomy、message、bus、gate、wait coordination
  llm/            LLM client 与 provider implementations
  memory/         ThoughtStore 旁路存储
  observability/  结构化日志与 session archives
  orchestration/  多 agent 占位与协议边界
  runtime/        Runtime protocol 与 LocalRuntime
  server/         framework-neutral server / transport adapters
  task/           Task domain、authoring、publishing、pipeline、stores
  tools/          Workspace、Tool base、fs/shell/code-action tools
  types/          BaseEvent、BaseAction、BaseObservation、registries

frontend/
  src/            Plato Main Page baseline、API types、UI primitives

docs/
  README.md       文档入口
```

## 开发检查

后端：

```bash
uv run pytest
uv run ruff check .
uv run mypy src tests
```

前端：

```bash
cd frontend
npm test
npm run lint
npm run build
```

目标质量门禁：能力发生变化时，测试、lint、type checks 和相关产品文档一起更新。

## License

MIT
