# Agent LLM Config And Router LLM 技术设计

> Status: proposed / ready for implementation branch
>
> Last Updated: 2026-06-19
>
> Owner: Product / Backend Runtime / LLM Platform
>
> Related:
> [Runtime Input Router Contract](runtime-input-router-contract.md),
> [Runtime Input Router Technical Design](runtime-input-router-contract-technical-design.md),
> [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md),
> [Runtime Input And Contract Revision Program](runtime-input-and-contract-revision-program.md),
> [LLM Provider Retry Thinking](llm-provider-retry-thinking.md),
> [Context Manager 1.0](context-manager-1-0.md),
> [Context Manager 1.0 Technical Design](context-manager-1-0-technical-design.zh-CN.md),
> [Token Usage Analytics](token-usage-analytics.md)

---

## 1. 背景

当前 Plato 已经具备这些 LLM 基础：

- `taskweavn.llm.LLMClient` / `LazyLLMClient`：支持 `deepseek`、`litellm`、
  `openrouter`，并通过环境变量解析 `LLM_PROVIDER`、`LLM_MODEL`、API key、
  timeout、thinking、OpenRouter routing。
- Settings 全局配置：Electron 侧传入 `global_settings_root` 后，`settings/config.json`
  和 `settings/secrets.json` 作为所有 workspace 的 Plato-level 配置。
- `UsageRecordingLLM`：记录 token usage，并已支持 `agent_kind`、`agent_id`、
  `request_purpose` 等 metadata。
- 现有调用点：
  - Execution Agent：`AgentLoop`；
  - Collaborator authoring；
  - Read-only Inquiry answer provider；
  - Audit Agent 等后续 LLM 使用者。
- Runtime Input Router 当前是确定性规则 Router，已经可以把主输入路由到 ASK、
  confirmation、read-only inquiry、guidance、execution handoff 等路径，并把
  Router trace / question card / user input 写入 durable conversation。

主要缺口：

1. 所有 Agent 当前基本共用同一个 `usage_llm`，无法按 Agent 选择不同模型。
2. Runtime Input Router 还没有 LLM interpretation 能力，只能靠 deterministic
   rule 识别输入。
3. Agent 级 LLM 配置需要 backend-only 可配置，暂不暴露在 Settings UI。

---

## 2. 目标

### 2.1 Agent 级 LLM 配置

让不同 Agent 可以使用不同 provider/model/timeout/routing/thinking 配置：

- `runtime_input_router`
- `execution_agent`
- `collaborator`
- `read_only_inquiry`
- later: `audit_agent`
- later: `summary_agent`

默认必须保持兼容：未配置 Agent 级 LLM 时，所有 Agent 继续使用当前全局 LLM。

### 2.2 Router LLM 能力

Runtime Input Router 增加 LLM route planner：

```text
user input + selected scope + active ASK/confirmation/session/task state
  -> LLM route proposal
  -> deterministic policy validation
  -> command-backed dispatch or clarification
  -> durable conversation/activity
```

LLM 只产生 route proposal，不直接执行命令、不写 workspace、不绕过后端白名单。
对于简单的“解释/查找/总结当前 workspace 内容”的问题，Router 不应该强行发布
execution task。Router LLM 可以在 proposal 中声明需要的只读 `readOnlyRefs`
（例如 workspace-relative file path 或 diff ref），再交给 Read-Only Inquiry
服务通过既有 workspace inspection/file viewer 能力读取上下文并生成 answer-only
回复。这个路径必须保持 `sideEffect=no_effect`，并把 Router 判断摘要和最终回答都作为
durable conversation/activity 证据。

### 2.3 可审计和可观测

- 每次 Agent LLM 调用都带 `agent_kind`、`agent_id`、`request_purpose`。
- Token usage 按 Agent/provider/model 可归因。
- Router LLM 的用户可见判断摘要进入 conversation 的 `router_trace`。
- 不暴露隐藏 chain-of-thought；只展示 `visibleReasoningSummary`。

---

## 3. 非目标

本设计不做：

- Settings UI 的 Agent LLM 配置入口；
- 多 Agent orchestration / Agent Manager；
- Router 直接执行 workspace mutation；
- LLM 自由选择任意 backend command；
- LLM chain-of-thought 展示；
- provider key 管理 UI 细分；
- per-session/per-workspace UI override。

---

## 4. 配置模型

### 4.1 存储位置

沿用现有 Settings 存储：

```text
<global_settings_root>/settings/config.json
<global_settings_root>/settings/secrets.json
```

CLI 或未传入 `global_settings_root` 的调用者仍可使用 workspace-local：

```text
<workspace>/.plato/settings/config.json
<workspace>/.plato/settings/secrets.json
```

现有 Settings update 逻辑会保留未知 top-level 字段，因此 backend-only 的
`agentLlm` 不会被 UI 保存配置时删除。

### 4.2 Safe config schema

`settings/config.json` 新增可选字段：

```json
{
  "schemaVersion": "plato.local_settings_storage.v1",
  "llm": {
    "provider": "deepseek",
    "model": "deepseek-v4-pro"
  },
  "agentLlm": {
    "schemaVersion": "plato.agent_llm_config.v1",
    "defaultProfile": "default",
    "profiles": {
      "default": {
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "timeoutSeconds": 180
      },
      "router": {
        "inherits": "default",
        "model": "deepseek-chat",
        "timeoutSeconds": 30,
        "temperature": 0
      },
      "execution": {
        "inherits": "default",
        "timeoutSeconds": 180
      },
      "collaborator": {
        "inherits": "default",
        "timeoutSeconds": 120
      },
      "readOnlyInquiry": {
        "inherits": "default",
        "timeoutSeconds": 45,
        "temperature": 0
      }
    },
    "bindings": {
      "runtime_input_router": "router",
      "execution_agent": "execution",
      "collaborator": "collaborator",
      "read_only_inquiry": "readOnlyInquiry"
    }
  }
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `agentLlm.schemaVersion` | Agent LLM 配置版本。 |
| `defaultProfile` | 未显式绑定或绑定失效时使用的 profile。 |
| `profiles` | provider/model/timeout/thinking/routing 的组合。 |
| `profiles.*.inherits` | 从另一个 profile 继承字段。最多允许有限深度，禁止循环。 |
| `bindings` | Agent role 到 profile 的映射。 |
| `timeoutSeconds` | 单次 chat request timeout。 |
| `temperature` | 可选；需要扩展 `LLMClient.chat` 透传到 `ChatRequest.temperature`。 |
| `thinking` | 可选；沿用 `ThinkingConfig` 语义。 |
| `providerRouting` | 可选；沿用 OpenRouter routing 语义。 |

### 4.3 Secrets schema

默认复用现有单 provider key：

```json
{
  "schemaVersion": "plato.local_settings_storage.v1",
  "llm": {
    "provider": "deepseek",
    "apiKey": "..."
  }
}
```

需要多个 provider key 时，允许新增 `llmProviders`：

```json
{
  "schemaVersion": "plato.local_settings_storage.v1",
  "llm": {
    "provider": "deepseek",
    "apiKey": "..."
  },
  "llmProviders": {
    "deepseek": {
      "apiKey": "..."
    },
    "openrouter": {
      "apiKey": "..."
    },
    "litellm": {
      "apiKey": "..."
    }
  }
}
```

Key 解析优先级：

1. `secrets.llmProviders[provider].apiKey`
2. provider-specific env，例如 `DEEPSEEK_API_KEY`、`OPENROUTER_API_KEY`
3. `secrets.llm`，仅当 provider 匹配
4. `LLM_API_KEY`

---

## 5. Backend 模块设计

### 5.1 新增模块

建议新增：

```text
src/taskweavn/llm/agent_config.py
src/taskweavn/llm/agent_resolver.py
src/taskweavn/server/runtime_input_llm_router.py
```

职责：

| 模块 | 职责 |
|---|---|
| `llm/agent_config.py` | 解析 `agentLlm` config、profile inheritance、binding、validation。 |
| `llm/agent_resolver.py` | 根据 Agent role 返回 lazy LLM client，并包装 usage recorder。 |
| `server/runtime_input_llm_router.py` | Runtime Input Router 的 LLM planner、JSON schema、proposal validation。 |

### 5.2 Router read-only workspace context

Router LLM 不是 workspace tool executor。它只能产出经过 schema 约束的
`readOnlyRefs`，由后端 Read-Only Inquiry pipeline 负责真正读取和回答：

```text
Router LLM proposal
  dispatchTarget=read_only_inquiry
  sideEffect=no_effect
  readOnlyRefs=[{kind:"file", path:"README.md"}]

DefaultRuntimeInputRouter
  -> validate route proposal
  -> merge request refs + planner refs + selection refs
  -> DefaultReadOnlyInquiryService
  -> WorkspaceInspectionGateway / file viewer / diff viewer
  -> GuardedLLMReadOnlyInquiryAnswerProvider
  -> durable answer activity
```

规则：

- `readOnlyRefs` 只允许在 `dispatchTarget=read_only_inquiry` 下出现。
- Router LLM 不返回文件内容，只返回需要读取的安全引用。
- workspace path 必须由 Read-Only Inquiry / WorkspaceInspectionGateway
  做 path traversal、防二进制/大文件、最大字符数等限制。
- 如果用户请求“帮我实现/修改/运行/生成文件”，Router 必须走
  `execution_handoff`，不能用 answer-only 路径完成 mutation。
- 如果用户只是问“这个项目怎么启动”“这个文件是做什么的”“当前 diff 改了什么”，
  Router 应优先走 `read_only_inquiry`，避免为了简单答案发布 task。

### 5.3 Agent role contract

```python
AgentLlmRole = Literal[
    "runtime_input_router",
    "execution_agent",
    "collaborator",
    "read_only_inquiry",
    "audit_agent",
    "summary_agent",
]
```

### 5.3 Resolved profile model

```python
class AgentLlmProfile(BaseModel):
    provider: str
    model: str
    timeout_seconds: float | None = None
    temperature: float | None = None
    thinking: ThinkingConfig | None = None
    provider_routing: ProviderRoutingConfig | None = None


class AgentLlmConfig(BaseModel):
    schema_version: Literal["plato.agent_llm_config.v1"]
    default_profile: str = "default"
    profiles: dict[str, AgentLlmProfileInput]
    bindings: dict[AgentLlmRole, str] = {}
```

### 5.4 Resolver contract

```python
class AgentLlmResolver(Protocol):
    def client_for(self, role: AgentLlmRole) -> Any: ...
    def profile_for(self, role: AgentLlmRole) -> ResolvedAgentLlmProfile: ...
```

默认实现：

```python
class SettingsBackedAgentLlmResolver:
    def __init__(
        self,
        *,
        settings_store: FileSettingsConfigStore,
        base_env: Mapping[str, str],
        workspace_id: str,
        token_usage_store: TokenUsageEventSink,
        task_plan_resolver: TaskPlanResolver | None,
        fallback_default_model: str,
    ) -> None: ...
```

`client_for(role)` 返回：

```text
LazyLLMClient(profile env)
  -> UsageRecordingLLM(workspace_id, usage_store, task_plan_resolver)
  -> optional AgentLlmMetadataDecorator(role)
```

其中 profile env 是按该 role 解析出的局部 env：

```text
LLM_PROVIDER=<profile.provider>
LLM_MODEL=<profile.model>
provider api key env=<resolved secret>
LLM_REQUEST_TIMEOUT_SECONDS=<profile.timeoutSeconds>
LLM_THINKING_*
OPENROUTER_*
```

---

## 6. Main Page Runtime 注入改造

当前 `build_main_page_workspace_runtime(...)` 大致是：

```text
llm = _workspace_llm(...)
usage_llm = UsageRecordingLLM(llm, ...)

Execution Agent <- usage_llm
Collaborator <- usage_llm
Read-only Inquiry <- usage_llm
Runtime Input Router <- deterministic only
```

目标改为：

```text
agent_llms = SettingsBackedAgentLlmResolver(...)

Execution Agent <- agent_llms.client_for("execution_agent")
Collaborator <- agent_llms.client_for("collaborator")
Read-only Inquiry <- agent_llms.client_for("read_only_inquiry")
Runtime Input Router <- deterministic router + llm planner using
                       agent_llms.client_for("runtime_input_router")
```

兼容要求：

- `MainPageSidecarDependencies.llm` 和 `llm_factory` 仍保留，测试和特殊运行模式可继续注入。
- 如果没有 `agentLlm` 配置，resolver 生成与当前全局 `llm` 等价的 client。
- 如果某个 role 配置非法，只影响该 role，并回退全局默认或禁用该 role 的 LLM planner；
  不应阻止 UI 启动。

---

## 7. Runtime Input Router LLM Planner

### 7.1 Planner 接口

```python
class RuntimeInputRoutePlanner(Protocol):
    def plan(
        self,
        request: RuntimeInputRouteRequest,
        context: RuntimeInputRouterContext,
    ) -> RuntimeInputRouteProposal: ...
```

`DefaultRuntimeInputRouter` 的 route 顺序调整为：

1. active ASK deterministic answer；
2. active confirmation deterministic yes/no；
3. deterministic stop/retry；
4. LLM planner proposal；
5. deterministic read-only question/guidance/change fallback；
6. unsupported/clarification。

注意：active ASK/confirmation 的直接答案仍优先，因为用户正在回答具体阻塞问题。
LLM planner 主要覆盖模糊自然语言：

- “这个问题先放一放，继续后面的任务”
- “按你刚刚说的第 2 个方案”
- “这个任务不是要做网站，是要做作品集”
- “我是在问你现在为什么卡住，不是让你改文件”

### 7.2 Router context

LLM planner 只能看到最小上下文：

```python
class RuntimeInputRouterContext(BaseModel):
    session_id: str
    selected_scope: RuntimeInputSelection
    active_ask: AskRequestView | None
    active_confirmation: ConfirmationActionView | None
    session_status: str
    plan_summary: str | None
    selected_task_summary: str | None
    recent_conversation: tuple[RouterConversationFact, ...]
    allowed_dispatch_targets: tuple[str, ...]
```

不提供 workspace file contents，不提供 secrets，不提供 full event stream。

### 7.3 LLM output schema

LLM 必须返回 JSON object：

```json
{
  "intent": "question",
  "dispatchTarget": "read_only_inquiry",
  "scopeKind": "task",
  "sideEffect": "no_effect",
  "confidence": "medium",
  "visibleReasoningSummary": "User is asking for an explanation about the selected task state, not requesting a workspace change.",
  "userMessage": "I will answer based on the selected task state.",
  "needsClarification": false,
  "clarification": null
}
```

Allowed values 必须与 `RuntimeInputRouteDecision` 对齐：

- `intent`: `question`、`guidance`、`command`、`ask_answer`、
  `confirmation_response`、`execution_request`、`clarification`、`unsupported`
- `dispatchTarget`: `read_only_inquiry`、`record_guidance`、`resolve_ask`、
  `resolve_confirmation`、`existing_command`、`execution_handoff`、
  `clarification`、`unsupported`
- `sideEffect`: `no_effect`、`context_effect`、`state_effect`、
  `resume_effect`、`authorization_effect`
- `confidence`: `high`、`medium`、`low`

Clarification payload：

```json
{
  "needsClarification": true,
  "clarification": {
    "title": "Plato needs one more detail",
    "body": "Do you want this as guidance for the current task, or should Plato create a new execution task?",
    "questions": [
      {
        "id": "route_intent",
        "label": "What should Plato do?",
        "inputHint": "Example: add guidance, create task, or answer question",
        "required": true
      }
    ],
    "options": [
      {
        "id": "add_guidance",
        "label": "Add guidance"
      },
      {
        "id": "create_task",
        "label": "Create task"
      }
    ]
  }
}
```

### 7.4 Proposal validation

LLM proposal 必须通过 policy validation：

1. JSON parse 成功；
2. schema validation 成功；
3. `dispatchTarget` 在当前上下文 allowed list；
4. `sideEffect` 与 dispatch target 匹配；
5. confidence 低于阈值时禁止 mutation；
6. no active ASK 时禁止 `resolve_ask`；
7. no active confirmation 时禁止 `resolve_confirmation`；
8. workspace-changing input 只能进入 `execution_handoff`，不能直接执行；
9. LLM 不能指定 arbitrary command payload；
10. `visibleReasoningSummary` 不得包含 hidden chain-of-thought 或敏感路径。

校验失败时：

- 记录 safe warning metadata；
- Router 回退 deterministic 路径；
- 或返回 `needs_clarification`；
- 不抛出导致 UI 卡死的 provider 原始异常。

---

## 8. Conversation / Activity 集成

Router LLM planner 的判断结果继续进入现有 conversation render protocol：

```text
User input
Router interpretation
Optional Router question card
Optional command/result activity
```

`router_trace` 使用：

```json
{
  "renderKind": "router_trace",
  "routerTrace": {
    "intent": "question",
    "scopeKind": "task",
    "confidence": "medium",
    "sideEffect": "no_effect",
    "dispatchTarget": "read_only_inquiry",
    "explanation": "User is asking for an explanation about the selected task state.",
    "outcomeStatus": "answered"
  }
}
```

`explanation` 来源：

- LLM proposal 的 `visibleReasoningSummary`；
- 或 deterministic fallback 的 explanation。

对于 planner 驱动的 answer-only 路径，conversation/activity 至少产生两类安全内容：

- `router_interpretation`：保存 Router 的可见判断摘要，`sideEffect=no_effect`；
- `answer`：保存 Read-Only Inquiry 的最终回答，`sideEffect=no_effect`。

明确禁止：

- 展示 provider reasoning tokens；
- 展示 chain-of-thought；
- 保存完整 prompt；
- 保存 secret/API key；
- 保存 private file contents。

---

## 9. Observability And Usage

每个 Agent LLM call metadata 必须包含：

```python
{
    "agent_kind": "router",
    "agent_id": "runtime_input_router",
    "request_purpose": "runtime_input.route.plan",
    "session_id": request.session_id,
    "step": 0,
}
```

建议 request purpose：

| Agent | `agent_kind` | `agent_id` | `request_purpose` |
|---|---|---|---|
| Router | `router` | `runtime_input_router` | `runtime_input.route.plan` |
| Execution | `execution_agent` | `default_agent` | `execution.agent_loop.step` |
| Collaborator | `collaborator` | existing actor id | existing request purpose |
| Read-only Inquiry | `read_only_inquiry` | `read_only_inquiry` | `read_only_inquiry.answer` |

`UsageRecordingLLM` 已经会记录 provider/model/token usage。实现时需要确认：

- role-specific client 的 `model` property 返回 profile model；
- response provider_name 正确；
- metadata safe list 包含必要 Agent 字段。

---

## 10. Failure Policy

| 失败类型 | 行为 |
|---|---|
| `agentLlm` config 不存在 | 使用全局 `llm`。 |
| role binding 缺失 | 使用 `defaultProfile`。 |
| profile 循环继承 | 忽略 `agentLlm`，使用全局 fallback，并记录 warning。 |
| role provider key 缺失 | 该 role 的 LLM disabled；Router 回退 deterministic。 |
| LLM timeout | Router 回退 deterministic，Execution Agent 保持现有 timeout error 行为。 |
| Router LLM 非 JSON | 回退 deterministic。 |
| Router proposal 越权 | 拒绝 proposal，返回 clarification 或 fallback。 |
| Usage recording 失败 | 不影响业务返回。 |

---

## 11. Implementation Slices

### ALLM-0. Technical Design

Status: this document.

Acceptance:

- Agent-level config schema accepted.
- Router LLM planner safety boundary accepted.
- Implementation slices and tests identified.

### ALLM-1. Config Models And Resolver

Add:

- `taskweavn.llm.agent_config`
- `taskweavn.llm.agent_resolver`

Acceptance:

- Parses empty config into global fallback.
- Parses profile inheritance.
- Rejects cyclic inheritance.
- Resolves role -> profile.
- Resolves provider API key using secrets/env precedence.
- Returns lazy usage-recorded clients.

Tests:

- `tests/test_agent_llm_config.py`
- `tests/test_agent_llm_resolver.py`

### ALLM-2. Main Page Runtime Injection

Update `build_main_page_workspace_runtime(...)`:

- create resolver once per workspace runtime;
- inject role-specific LLMs into Execution Agent, Collaborator, Read-only Inquiry;
- preserve dependency injection compatibility.

Acceptance:

- Existing tests with injected `llm` keep passing.
- Unconfigured app behavior is unchanged.
- Usage metadata still records provider/model.

Tests:

- targeted `main_page` sidecar dependency tests;
- token usage tests for role-specific model.

### ALLM-3. Router LLM Planner Contract

Add LLM planner:

- prompt;
- response schema;
- parser;
- policy validator;
- fallback behavior.

Acceptance:

- Valid proposal dispatches through existing Router paths.
- Low confidence mutation becomes clarification/unsupported.
- Invalid JSON falls back deterministic.
- Planner is disabled when role LLM unavailable.

Tests:

- `tests/test_runtime_input_llm_router.py`
- extend `tests/test_runtime_input_router.py`

### ALLM-4. Durable Conversation Integration

Use planner `visibleReasoningSummary` in existing `router_trace` and durable
`router_interpretation` activity.

Acceptance:

- User input, Router trace, question card remain durable.
- Router trace identifies LLM-planned vs deterministic route in metadata.
- No hidden reasoning is exposed.

### ALLM-5. Readiness And Diagnostics

Backend-only diagnostics:

- add safe config summary in diagnostic bundle;
- redact secrets;
- expose role/profile/provider/model without API keys.

Optional later:

- Settings readiness includes backend-only role warnings, still not surfaced as UI fields.

---

## 12. Test Plan

Backend unit:

- config parsing;
- profile inheritance;
- role binding fallback;
- secrets/env precedence;
- Lazy client creation;
- Router LLM proposal parser;
- proposal safety validation;
- fallback on timeout/invalid JSON.

Backend integration:

- main page runtime builds with no `agentLlm`;
- main page runtime builds with role-specific `agentLlm`;
- Runtime Input Router uses router model while Execution Agent uses execution model;
- token usage events show role-specific model and request purpose.

Frontend:

- no UI changes required for this slice;
- existing Settings tests should pass because unknown config fields are preserved.

Smoke:

- configure `agentLlm.router.model` to a cheap/fast model;
- ask ambiguous natural-language input;
- verify conversation shows Router trace;
- verify generated commands remain command-backed;
- verify usage analytics contains router model.

---

## 13. Acceptance Criteria

Feature is accepted when:

1. Agent LLM config is backend-only and optional.
2. Missing config preserves existing global LLM behavior.
3. Different Agent roles can resolve different models.
4. Runtime Input Router can use LLM planning for ambiguous input.
5. Router LLM cannot directly mutate workspace or bypass command whitelist.
6. Router trace and question card remain durable conversation content.
7. Token usage is attributable by Agent role and model.
8. Tests cover config, resolver, Router planner, fallback, and usage attribution.

---

## 14. Open Questions

1. Should `agentLlm` eventually be stored per workspace or Plato-global only?
   Product direction currently favors global Settings, with workspace-level override hidden
   unless a strong use case appears.
2. Should Router use a smaller/faster model by default?
   Proposed default is inherit global until we have provider-specific benchmarks.
3. Should `temperature` be provider-neutral now?
   `ChatRequest` already has `temperature`; `LLMClient.chat` may need explicit forwarding
   from profile config.
4. Should Router planner run before deterministic read-only question detection?
   Proposed order keeps high-confidence active interactions and deterministic commands first,
   then uses LLM for ambiguous input before broad fallback.

---

## 15. Rollout Plan

1. Land config/resolver with no behavior change.
2. Switch existing Agents to resolver-backed clients with fallback.
3. Add Router LLM planner behind backend flag:

```text
PLATO_RUNTIME_INPUT_ROUTER_LLM=1
```

4. Enable by default only after smoke confirms:
   - ambiguous route quality improves;
   - fallback protects mutation boundaries;
   - startup remains lazy and fast.
