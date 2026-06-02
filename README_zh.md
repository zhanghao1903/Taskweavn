# TaskWeavn

> 用户可见产品名：Plato
> English: [README.md](README.md)
> 文档入口：[docs/README.md](docs/README.md)

TaskWeavn 是 Plato 背后的本地任务智能体运行时。它把用户意图转成以
Task 为中心的工作：先生成可检查的任务树，让用户审阅和修正，再发布到
TaskBus 执行，并把消息、确认动作、文件变更、结果和审计证据投影回 Main
Page。

当前产品方向是 Task-first，而不是 chat-first：

```text
用户意图
  -> RawTask 与可行性判断
  -> Collaborator 草拟 Task Tree List
  -> 用户编辑 / 确认 TaskNode
  -> TaskPublisher 发布任务
  -> TaskBus 管理执行生命周期
  -> FixedRouteTaskExecutor 调用常驻 Default Agent
  -> Main Page 投影状态、消息、结果和文件变更
```

## 当前状态

TaskWeavn 已经不再是早期单 ReAct loop 原型。当前 Product 1.0 主路径是：
本地 Plato Main Page 前端、本地 Python sidecar、持久化 authoring/execution
stores、固定路由执行，以及在每次 LLM 调用前做确定性、cache-aware
上下文组装的 Context Manager。

| 区域 | 状态 | 说明 |
|---|---:|---|
| Agent core | 完成 | 强类型 Action/Observation、EventStream、Runtime、ReAct loop、CLI。 |
| Interaction substrate | 完成 | Session/workspace 持久化、MessageStream、MessageBus、risk/autonomy、wait coordination、派生 session status。 |
| Reliability / observability | 完成 / 后续增强 | LLM provider 抽象、重试、DeepSeek thinking、OpenRouter routing、结构化 JSONL session 日志。 |
| Authoring Domain | 完成 | RawTask、可行性判断、DraftTaskTree、Authoring Commands、Collaborator authoring、publish boundary。 |
| Publishing / TaskBus | baseline 完成 | TaskPublisher、SQLite TaskBus、publish idempotency、claim/running/complete/fail/skip 生命周期。 |
| Main Page integration | baseline 完成 | 前端 runtime adapter、本地 sidecar HTTP/SSE shell、command/query/event contract、result/error/file projection。 |
| Fixed-route execution | baseline 完成 | Product 1.0 使用一个常驻 Default Agent 路由，不引入 Router / Agent Manager。 |
| Context Manager 1.0 | 验收通过 / cache-aware hardening 完成 | `llm.chat(...)` 前确定性组装、append-only 复用和低频 checkpoint。 |
| Manual retry | 进行中 | failed published Task 可原地回到 pending，并保留失败消息/结果摘要作为审计事实。 |
| Product 1.1+ | 规划中 | Router、Agent Manager、skills、MCP、多模态上下文、更完整结果包装和高级 pipeline。 |

当前规划从这些文档开始：

- [docs/roadmap.md](docs/roadmap.md)
- [docs/project/roadmap.md](docs/project/roadmap.md)
- [docs/gaps/README.md](docs/gaps/README.md)

## 环境要求

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv)
- Node.js 和 npm，用于 Plato 前端
- 一个 LLM provider key，用于 authoring / execution

常用 LLM 环境变量：

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-...
export LLM_MODEL=deepseek-chat
```

其他 provider 配置见 [docs/configuration.md](docs/configuration.md)。

## 安装

在仓库根目录运行：

```bash
uv sync
npm install --prefix frontend
```

`uv sync` 安装 Python package 和开发依赖。前端是独立的 Vite/React package，
位于 `frontend/`，因此需要单独安装 npm 依赖。

## 启动 Plato 本地产品

默认启动命令会同时启动 Python sidecar 和 Vite 前端：

```bash
uv run taskweavn plato-dev --workspace ./plato-workspace
```

默认地址：

```text
Frontend: http://127.0.0.1:5173
Sidecar:  http://127.0.0.1:52789
Health:   http://127.0.0.1:52789/api/v1/health
```

常用参数：

```bash
uv run taskweavn plato-dev \
  --workspace ./plato-workspace \
  --sidecar-port 52789 \
  --frontend-port 5173
```

可以用 `--model <model-id>` 临时覆盖 Collaborator authoring 使用的模型。
不传 `--model` 时，TaskWeavn 从环境变量读取 provider / model。

### 只启动 sidecar

```bash
uv run taskweavn plato-sidecar --workspace ./plato-workspace
```

然后以 HTTP 模式启动前端：

```bash
VITE_PLATO_API_MODE=http \
VITE_PLATO_API_BASE_URL=http://127.0.0.1:52789 \
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173
```

### 只启动 mock 前端

不需要真实后端时：

```bash
npm run dev --prefix frontend
```

未设置 `VITE_PLATO_API_MODE=http` 时，前端会使用 typed mock scenarios。

## 运行底层 CLI Agent

底层 CLI loop 仍可直接执行 workspace task：

```bash
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

## 日志

CLI 和 sidecar 相关路径会写结构化 session artifacts。CLI 默认日志目录是
`./logs`。

常用命令：

```bash
uv run taskweavn logging profiles
uv run taskweavn logging manifest --log-dir ./logs --session-id <session-id>
uv run taskweavn logging render ./logs/sessions/<session-id>/llm.jsonl --limit 50
```

session archive 结构：

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

## 开发检查

后端：

```bash
uv run pytest
uv run ruff check .
uv run mypy src tests
```

前端：

```bash
npm test --prefix frontend
npm run build --prefix frontend
```

常用 targeted checks：

```bash
uv run pytest tests/test_main_page_sidecar_app.py tests/test_ui_http_transport.py
npm test --prefix frontend -- useMainPageController platoApi httpMainPageAdapter
```

## 项目结构

```text
src/taskweavn/
  audit/          AuditAgent 与 audit observations
  cli/            Typer CLI 入口：taskweavn
  context/        Context Manager models、stores、source adapters、renderer
  core/           AgentLoop、EventStream、session、workspace layout
  interaction/    Risk、autonomy、message、bus、gate、wait coordination
  llm/            LLM client 与 provider implementations
  memory/         ThoughtStore 旁路存储
  observability/  结构化日志与 session archives
  runtime/        Runtime protocol 与 LocalRuntime
  server/         Plato sidecar、UI HTTP transport、contract gateways
  task/           Task domain、authoring、publishing、TaskBus、projection
  tools/          Workspace、Tool base、fs/shell/code-action tools
  types/          BaseEvent、BaseAction、BaseObservation、registries

frontend/
  src/            Plato Main Page、runtime adapters、API types、UI primitives

docs/
  README.md       文档入口
```

## 文档入口

| 需求 | 入口 |
|---|---|
| 当前方向 | [docs/roadmap.md](docs/roadmap.md) |
| 当前执行队列 | [docs/project/roadmap.md](docs/project/roadmap.md) |
| 已知 gaps | [docs/gaps/README.md](docs/gaps/README.md) |
| 架构事实 | [docs/architecture/README.md](docs/architecture/README.md) |
| 产品意图 | [docs/product/README.md](docs/product/README.md) |
| UI/API contract | [docs/product/plato-ui-api-contract.md](docs/product/plato-ui-api-contract.md) |
| 实施计划 | [docs/plans/README.md](docs/plans/README.md) |
| 架构决策 | [docs/decisions/README.md](docs/decisions/README.md) |
| 完成记录 | [docs/releases/README.md](docs/releases/README.md) |

## License

MIT
