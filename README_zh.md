# TaskWeavn

> 用户可见产品名：Plato
> English: [README.md](README.md)
> 文档总入口：[docs/README.md](docs/README.md)

TaskWeavn 是 Plato 背后的本地任务智能体系统。它的核心目标是：把用户的自然语言意图转换为以任务为中心的计划，让用户能够查看、修正、确认这些任务，再用可观察的消息、确认动作、文件变更、审计证据和诊断信息完成执行。

Plato 不是一个套壳 CLI 聊天产品。它的产品模型是：

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

项目已经不再是早期的单轮 ReAct agent。当前工作重点是 Plato 1.0 产品化：把已经完成的 server-core 基础能力，打磨成本地桌面产品。

| 区域 | 状态 | 说明 |
|---|---:|---|
| Phase 1 核心 agent | 完成 | 强类型 Action/Observation、EventStream、Runtime、ReAct loop、CLI。 |
| Phase 2 沙箱 / 审计 / 记忆 | 完成 | CodeAction、Docker sandbox、AuditAgent、SQLite ThoughtStore。 |
| Phase 3.1-3.8 Interaction Layer | 完成 | Session、workspace、risk/autonomy、message、bus、wait、loop integration、LLM risk、派生 session status。 |
| LLM provider reliability | 完成 | Provider 抽象、自动重试、DeepSeek thinking、OpenRouter routing。 |
| Configurable logging | 完成 | 结构化 JSONL 日志、session archive、profiles、运行时控制。 |
| Task authoring foundation | 完成 | RawTask、可行性判断、DraftTaskTree、Collaborator authoring commands。 |
| Task publishing foundation | 部分完成 / server-core 完成 | TaskPublisher、SQLite TaskBus publish surface、SQLite publish control plane、API publish transport。执行生命周期仍待完成。 |
| Plato frontend baseline | 完成 / 待真实集成 | `frontend/src` 已有 Main Page scaffold、state catalog、typed mock/API adapter、shared API types、UI primitives。 |
| Plato 1.0 productization | 进行中 | UI/backend contracts、sidecar API、真实后端集成、settings、audit、diagnostics、packaging。 |

实时路线图见 [docs/roadmap.md](docs/roadmap.md) 和 [docs/project/roadmap.md](docs/project/roadmap.md)。

## 产品与架构亮点

### Task-First UX

Task 是第一用户交互对象。Chat 是输入、澄清和解释，不是主要状态模型。用户应该可以选中 TaskNode，查看状态，追加指导，回答确认，查看相关消息，并检查文件变更。

### 强类型 Agent Core

Action 和 Observation 是带 `kind` 鉴别器的 frozen Pydantic model。Tool 向 LLM 暴露 Action schema，Runtime 执行后返回 Observation。Runtime 异常会变成 `ErrorObservation`，而不是让 loop 崩溃。

### Interaction Layer

TaskWeavn 使用一条 session message stream，并通过 task scope 做投影。交互层包括：

- `AgentMessage` 与 `SqliteMessageStream`；
- `InProcessMessageBus`；
- 量化风险与 autonomy presets；
- `AutonomyGate` 与 `WaitCoordinator`；
- 同步等待与异步延迟响应路径。

### Task Authoring And Publishing

Authoring domain 与 execution domain 分离：

- RawTask 和 DraftTaskTree 支持执行前的探索式规划。
- Collaborator authoring tools 根据用户输入持续修正 task tree。
- TaskPublisher 将用户确认后的 task tree 发布到 TaskBus。
- API、scheduler、pipeline、custom tree publisher 都走同一个 publish 边界。

### Plato 1.0 方向

Plato 1.0 面向本地单用户桌面助手。当前 P0 路径是：

1. UI/backend contract baseline。
2. Local sidecar API shell。
3. Main Page real backend integration。
4. Settings and first run。
5. Task execution lifecycle。
6. Message and confirmation integration。
7. File Change Summary。
8. Audit / Trust page。
9. Product error handling。
10. Diagnostic bundle。
11. Packaging and distribution。

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

配置规划见 [Settings and First Run](docs/capabilities/settings-and-first-run/) 和
[Configuration Control Plane](docs/capabilities/configuration-control-plane/)。
旧版 CLI 配置指南已归档到
[docs/archive/legacy-2026-05-18/root/configuration.md](docs/archive/legacy-2026-05-18/root/configuration.md)。

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

当前前端是 Main Page baseline，包含 typed mock scenarios 和 HTTP adapter contract。真实后端 sidecar 集成仍是 Plato 1.0 缺口，从 [docs/contracts/ui-backend/](docs/contracts/ui-backend/) 和 [docs/capabilities/main-page-real-backend/](docs/capabilities/main-page-real-backend/) 跟踪。

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
  README.md       文档总入口
```

## 文档

从 [docs/README.md](docs/README.md) 开始。主要活跃文档：

| 需求 | 入口 |
|---|---|
| 产品版本 | [Plato 1.0 Overview](docs/product/versions/1.0/overview.md) |
| 当前缺口 | [Plato 1.0 Gap Analysis](docs/product/versions/1.0/gap-analysis.md) |
| 能力地图 | [docs/capabilities/index.md](docs/capabilities/index.md) |
| 当前架构 | [docs/architecture/current.md](docs/architecture/current.md) |
| UI/backend contracts | [docs/contracts/ui-backend/](docs/contracts/ui-backend/) |
| 总路线图 | [docs/roadmap.md](docs/roadmap.md) |
| 项目执行计划 | [docs/project/roadmap.md](docs/project/roadmap.md) |
| 文档工作流 | [docs/project/docs-operating-model.md](docs/project/docs-operating-model.md) |
| 发布记录 | [docs/releases/](docs/releases/) |

历史文档保留在 `docs/archive/legacy-2026-05-18/`，不再作为新工作的活跃入口。

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
