# LLM-First Skill-Driven Runtime Router 技术方案

> 状态：planned
>
> 最后更新：2026-06-25
>
> Feature Plan:
> [LLM-First Skill-Driven Runtime Router](llm-first-runtime-router.md)
>
> 相关文档：
> [Runtime Input Router Contract](runtime-input-router-contract.md),
> [Runtime Input Router Technical Design](runtime-input-router-contract-technical-design.md),
> [Agent LLM Config And Router LLM](agent-llm-config-and-router-llm.md),
> [Product 1.1 Skill Governance Technical Design](product-1-1-skill-governance-technical-design.zh-CN.md),
> [UI Natural-Language WeChat Send Task Technical Design](ui-natural-language-wechat-send-task-technical-design.zh-CN.md)

---

## 1. 设计目标

Runtime Input Router 已经具备 LLM planner seam。本方案删除生产路径中曾经
混入的代码语义识别：

- `_STOP_PHRASES`
- `_RETRY_PHRASES`
- `_QUESTION_PREFIXES`
- `_QUESTION_SUBSTRINGS`
- `_WORKSPACE_CHANGE_MARKERS`
- 旧版 WeChat 自然语言 parser

这些逻辑不再作为 Router 兜底路径存在。

新目标：

```text
所有自由文本自然语言
  -> Router LLM semantic planner
  -> skill-guided structured proposal
  -> deterministic validator
  -> command/task/inquiry/clarification dispatch
```

代码不再承担自然语言语义理解。代码只承担状态、权限、安全、幂等、确认和
分发。

## 2. 核心边界

### 2.1 Router LLM 负责

- 判断用户输入属于：
  - question;
  - guidance;
  - command;
  - ASK answer;
  - confirmation response;
  - execution request;
  - plan/task creation;
  - clarification;
  - unsupported。
- 根据 skill 提取结构化 slot。
- 根据 skill 输出 task / command / read-only inquiry proposal。
- 给出用户可见的短 reasoning summary。

### 2.2 Router 代码负责

- API request 校验。
- session / plan / task selection 解析。
- active ASK / confirmation 权威状态加载。
- allowed dispatch targets 计算。
- skill activation policy。
- LLM proposal schema 校验。
- 权限、side effect、confidence 校验。
- high-risk confirmation 强制规则。
- idempotency / replay。
- command-backed dispatch。
- Execution Plane task publish。
- Activity / Audit / diagnostics 投影。

### 2.3 Skill 负责

- command 语义示例，如 stop / retry / resume / cancel。
- read-only inquiry 使用边界。
- task / plan 创建语义。
- WeChat send 任务语义、slot、task type、确认要求。
- app 操作知识，例如 WeChat Desktop 如何操作。

Skill 不是权限源。Skill 只能影响 LLM proposal，不能授权工具或绕过确认。

## 3. 模块设计

### 3.1 保留模块

| 模块 | 保留职责 |
|---|---|
| `DefaultRuntimeInputRouter` | orchestration, validation, dispatch。 |
| `LLMRuntimeInputRoutePlanner` | LLM proposal 生成。 |
| `validate_route_proposal` | deterministic proposal validation。 |
| `TaskApiService` | Execution Plane task publish。 |
| `DefaultReadOnlyInquiryService` | no-mutation answer/tool context path。 |
| `SkillRegistry` / `SkillActivation` | runtime skill governance。 |

### 3.2 新增或扩展模块

建议新增：

```text
src/taskweavn/server/runtime_input_protocol.py
src/taskweavn/server/runtime_input_proposal_validator.py
src/taskweavn/server/runtime_input_skill_context.py
src/taskweavn/server/runtime_input_task_drafts.py
src/taskweavn/server/runtime_input_command_drafts.py
```

职责：

| 模块 | 职责 |
|---|---|
| `runtime_input_protocol.py` | request normalization, active interaction facts, allowed target computation。 |
| `runtime_input_skill_context.py` | 选择并渲染 Router skills 到 planner prompt。 |
| `runtime_input_proposal_validator.py` | proposal schema / policy / side-effect validation。 |
| `runtime_input_task_drafts.py` | 从 validated task draft 构造 Execution Plane TaskRequest。 |
| `runtime_input_command_drafts.py` | 从 validated command draft 调用已有 command handlers。 |

### 3.3 需要收敛的旧模块

`runtime_input_wechat.py` 当前包含自然语言 slot extraction。迁移后它不应再
承担输入解析职责。

建议拆成：

```text
runtime_input_wechat_task.py
  - validate_wechat_send_task_draft
  - build_wechat_send_task_request
  - build_wechat_pending_clarification
```

迁移后：

- phrase pattern examples 进入 `router-wechat-send` skill；
- slot extraction 由 Router LLM proposal 完成；
- Python 代码只校验 proposal 和构造 TaskRequest。

## 4. Runtime Skill 设计

Product runtime skill 不等于 Codex 开发用 `.agents/skills`。

建议 runtime skill root 由配置显式指定，例如：

```text
<workspace>/.plato/runtime-skills/
<app-bundle>/resources/runtime-skills/
```

第一批内置 trusted skills：

```text
runtime-skills/
  router-core/
    SKILL.md
    manifest.json
  router-control-commands/
    SKILL.md
    manifest.json
  router-read-only-inquiry/
    SKILL.md
    manifest.json
  router-task-authoring/
    SKILL.md
    manifest.json
  router-wechat-send/
    SKILL.md
    manifest.json
  # WeChat 执行 skill 由 wechat-desktop-tool wheel 提供，不在此复制。
```

### 4.1 Router skill manifest

建议 manifest:

```json
{
  "schemaVersion": "plato.runtime_skill.v1",
  "skillId": "router-wechat-send",
  "kind": "router_capability",
  "capabilities": ["communication.wechat.send_message"],
  "allowedDispatchTargets": ["execution_handoff", "clarification", "unsupported"],
  "requiredSlots": ["contactDisplayName", "messageText"],
  "riskLevel": "high",
  "requiresHumanConfirmation": true,
  "outputSchemaRef": "RuntimeInputRouteProposal.taskRequestDraft"
}
```

`manifest.json` 用于代码验证。`SKILL.md` 用于 LLM 语义理解。

### 4.2 Router control commands skill

`router-control-commands` 应描述：

- stop task;
- retry task;
- resume task;
- cancel pending operation;
- pause / wait if supported later;
- 不要把控制命令解释成新任务；
- 没有 selected task 时应 clarification 或 unsupported。

注意：自然语言 “stop” 的识别在 skill + LLM，真正能否 stop 由代码校验。

## 5. Proposal Schema

当前 `RuntimeInputRouteProposal` 需要扩展。建议先添加可选字段，保持向后兼容。

```python
class RuntimeInputRouteProposal(UiContractModel):
    intent: RuntimeInputIntent
    dispatch_target: RuntimeInputDispatchTarget
    scope_kind: RuntimeInputScopeKind | None = None
    side_effect: SessionActivitySideEffect
    confidence: RuntimeInputConfidence
    visible_reasoning_summary: str
    user_message: str
    needs_clarification: bool = False
    clarification: RouterClarification | None = None
    read_only_refs: tuple[ReadOnlyInquiryRef, ...] = ()

    route_source: Literal["llm_planner"] = "llm_planner"
    activated_skill_ids: tuple[str, ...] = ()
    command_draft: RouterCommandDraft | None = None
    task_request_draft: RouterTaskRequestDraft | None = None
    ask_answer_draft: RouterAskAnswerDraft | None = None
    confirmation_response_draft: RouterConfirmationResponseDraft | None = None
    requested_read_only_context: RouterReadOnlyContextRequest | None = None
```

### 5.1 Command draft

```python
class RouterCommandDraft(UiContractModel):
    command_kind: Literal[
        "stop_task",
        "retry_task",
        "resume_task",
        "cancel_task",
        "record_guidance",
        "patch_task_node",
        "create_task_node",
        "delete_task_node",
    ]
    target_scope_kind: RuntimeInputScopeKind
    target_task_node_id: str | None = None
    target_plan_id: str | None = None
    rationale: str
```

MVP 可以只允许 `stop_task` 和 `retry_task`。

### 5.2 Task request draft

```python
class RouterTaskRequestDraft(UiContractModel):
    task_type: str
    title: str | None = None
    instructions: str
    input: dict[str, Any] = {}
    policy: RouterTaskPolicyDraft
    capability: str | None = None
```

WeChat draft:

```json
{
  "taskType": "communication.wechat.send_message",
  "instructions": "Send one confirmation-gated WeChat message.",
  "input": {
    "contactDisplayName": "文件传输助手",
    "messageText": "你好"
  },
  "policy": {
    "requiredCapability": "communication.wechat_desktop_send",
    "requiresHumanConfirmation": true,
    "riskLevel": "high"
  }
}
```

## 6. Router Prompt 输入

Router LLM 不应收到无限上下文。建议输入：

```json
{
  "sessionId": "...",
  "workspaceId": "...",
  "content": "给微信的文件传输助手发送“你好”",
  "mode": "auto",
  "selection": {...},
  "activeAsk": {...},
  "activeConfirmation": {...},
  "allowedDispatchTargets": [...],
  "availableSkills": [
    {
      "skillId": "router-core",
      "description": "...",
      "loadedExcerpt": "..."
    },
    {
      "skillId": "router-wechat-send",
      "description": "...",
      "loadedExcerpt": "..."
    }
  ],
  "outputSchema": {...}
}
```

规则：

- 不给 Router LLM workspace 文件全文。
- 不给 Router LLM raw logs。
- Router LLM 可请求 read-only refs，但不直接读取文件。
- Router LLM 只返回 JSON。
- hidden chain-of-thought 禁止进入输出。

## 7. Dispatch 流程

### 7.1 Active ASK

旧逻辑：代码发现 active ASK 后，把输入直接作为 ASK answer。

新逻辑：

1. 代码加载 active ASK facts。
2. allowed target 包含 `resolve_ask`。
3. Router LLM 判断用户是在回答 ASK 还是提出新问题/命令。
4. 如果 proposal 是 `resolve_ask`，代码校验 ask id 仍 pending。
5. 调用 command-backed ASK resolution。

好处：用户可以在 ASK 状态下说“先别管这个，停止任务”，Router 有机会区分。

当前实现状态：

- 当 route planner 存在时，active ASK 会进入 planner allowed targets；
- planner 只有输出 `dispatchTarget=resolve_ask` 且包含
  `askAnswerDraft.answerText`，才会调用 ASK resolution；
- draft 中的 `askId` 如果存在，必须匹配当前 active ASK；
- planner unavailable / invalid 时 fail closed，不会把原始输入直接当成 ASK
  answer。

### 7.2 Active confirmation

旧逻辑：代码用 yes/no phrase set 判定确认。

新逻辑：

1. 代码加载 active confirmation facts。
2. Router LLM 根据 `router-control-commands` / confirmation context 判断。
3. proposal 输出：

```json
{
  "dispatchTarget": "resolve_confirmation",
  "confirmationResponseDraft": {
    "confirmationId": "...",
    "resolution": "confirmed"
  }
}
```

4. 代码校验 confirmation id、状态和 allowed options。

当前实现状态：

- 当 route planner 存在时，active confirmation 会进入 planner allowed targets；
- planner 只有输出 `dispatchTarget=resolve_confirmation` 且包含
  `confirmationResponseDraft.resolution`，才会调用 confirmation resolution；
- draft 中的 `confirmationId` 如果存在，必须匹配当前 active confirmation；
- planner unavailable / invalid 时 fail closed，不会继续使用 yes/no phrase set
  处理确认。

### 7.3 Stop / retry / resume

旧逻辑：代码 phrase set。

新逻辑：

1. `router-control-commands` skill 描述自然语言表达。
2. Router LLM 输出 command draft。
3. 代码校验 selected task、permission、command availability。
4. 调用 existing command handler。

### 7.4 Question / file read / search

Router LLM 可决定：

- 直接 answer 需要 read-only inquiry；
- 需要文件 / diff / search 上下文；
- 问题其实是 workspace-changing task，不应 answer-only。

Router 不直接工具调用。它输出：

```json
{
  "dispatchTarget": "read_only_inquiry",
  "requestedReadOnlyContext": {
    "refs": [
      {"kind": "file", "path": "README.md"}
    ],
    "searchQuery": "how to start this project"
  }
}
```

Read-Only Inquiry / Workspace Inspection 层执行安全读取或搜索。

### 7.5 Create task / plan

Router LLM 可根据 `router-task-authoring` skill 输出：

- create one task;
- create/update plan;
- ask clarification before task creation。

MVP 建议：

- WeChat send task 先走 Execution Plane task draft；
- general plan/task authoring 只在 command-backed contract revision capability
  已存在时启用；
- 没有 command-backed path 时返回 clarification/unsupported，不静默修改 plan。

## 8. Safety Validator

Validator 是本方案的核心。它必须 fail closed。

校验项：

1. `dispatchTarget` 在 allowed set。
2. `sideEffect` 与 `dispatchTarget` 匹配。
3. `confidence=low` 不允许 mutation / execution。
4. `resolve_ask` 必须有 active pending ASK。
5. `resolve_confirmation` 必须有 active pending confirmation。
6. `existing_command` 必须有 command draft 且 command kind 已允许。
7. `execution_handoff` 必须有 task request draft。
8. external communication task 必须 `requiresHumanConfirmation=true`。
9. WeChat send 必须有 `contactDisplayName` 和 `messageText`。
10. task type 必须在 capability registry / skill manifest allowlist 中。
11. skill ids 必须来自 active trusted runtime skills。
12. proposal 不得包含隐藏 reasoning、raw secrets、absolute paths。

## 9. 配置

建议 runtime config:

```json
{
  "runtimeInput": {
    "routerMode": "llm_first",
    "llmPlannerRequired": true,
    "plannerTimeoutSeconds": 30,
    "plannerUnavailablePolicy": "no_mutation_unavailable"
  }
}
```

可选模式：

```text
routerMode = llm_shadow | llm_first
```

目标最终状态：

```text
routerMode = llm_first
legacyDeterministicSemanticsEnabled = false
```

### 9.1 当前配置入口边界

当前产品设置页只有 app 级别配置入口。虽然 centralized runtime
configuration 的 resolver 可以表达 global / workspace / session 等层级，
但 UI 暂时没有 workspace-level 或 session-level 配置入口。

因此本方案的配置约束是：

- `runtimeInput.routerMode`、Router LLM profile、planner timeout 等配置先按
  app/global 生效；
- 设置页面中的变更影响整个 app runtime，不是当前 workspace，也不是当前
  session；
- 不在本 slice 中实现 workspace/session override UI；
- 不在 Router 行为中暗示用户可以按 workspace/session 调整配置；
- 后续若要支持 workspace/session 配置，需要单独设计入口、effective config
  展示、Audit 证据和冲突解释。

实现时应在 diagnostics / effective config 输出中明确配置来源，例如：

```json
{
  "key": "runtimeInput.routerMode",
  "effectiveValue": "llm_first",
  "scope": "global",
  "source": "app_settings"
}
```

## 10. Observability

Route decision 应新增或投影：

- `route_source`: `llm_planner`;
- `activated_skill_ids`;
- `planner_model`;
- `planner_timeout`;
- `proposal_status`: `valid | invalid | unavailable`;
- `validator_rejection_reason`;
- `dispatch_target`;
- `side_effect`;
- `confidence`;
- `task_type`, if execution handoff;
- `requires_confirmation`, if applicable。

用户 UI 可以只显示简短解释。Diagnostics / Audit 可显示详细 trace。

### 10.1 Router 日志要求

Router 需要新增专门日志，以便后续通过日志确认“这段输入为什么被路由到这个
路径”。日志目标不是展示模型推理链，而是暴露可审计的 routing facts。

建议事件：

| 事件 | 内容 |
|---|---|
| `runtime_input_router_request` | session/workspace/scope、输入长度、redacted input summary、mode。 |
| `runtime_input_router_config` | app/global effective Router config、planner timeout、router mode。 |
| `runtime_input_router_skills` | activated Router skill ids、content hashes、budget/truncation。 |
| `runtime_input_router_llm_input` | 复用现有 Agent LLM input logging，`agent_kind=router`。 |
| `runtime_input_router_llm_output` | 复用现有 Agent LLM output logging，记录 response metadata。 |
| `runtime_input_router_proposal` | proposal status、intent、dispatch target、confidence、side effect。 |
| `runtime_input_router_validation` | valid/invalid、validator rejection reason。 |
| `runtime_input_router_dispatch` | 最终 dispatch target、command/task/inquiry id、是否 requires confirmation。 |
| `runtime_input_router_fallback` | planner unavailable、timeout、invalid proposal、unsupported capability 等原因。 |

日志约束：

- 不记录 hidden chain-of-thought。
- 不记录 secrets。
- 不默认记录 raw workspace 文件内容。
- raw user input、raw prompt、raw response 仍遵循 configurable logging 的
  profile/redaction policy。
- normal profile 至少记录 summary 级 route source、skill、validation 和
  dispatch facts。
- debug/full profile 可以记录经过脱敏的 planner payload，便于排查 Router
  误路由。

这些日志应最终能被 diagnostics bundle 或日志 render 命令读取，避免用户只能
从页面结果猜测 Router 是否调用了 LLM。

## 11. Implementation Slices

### Slice A - Skill artifacts and fixtures

状态：implemented foundation。

- 新增 runtime Router skill descriptors/fixtures。
- 不接入生产 Router。

已落地：

- `src/taskweavn/runtime_skills/router-core/SKILL.md`
- `src/taskweavn/runtime_skills/router-control-commands/SKILL.md`
- `src/taskweavn/runtime_skills/router-read-only-inquiry/SKILL.md`
- `src/taskweavn/runtime_skills/router-task-authoring/SKILL.md`
- `src/taskweavn/runtime_skills/router-wechat-send/SKILL.md`
- `wechat-desktop-tool` 包内 `wechat-use` skill，由
  `taskweavn.integrations.wechat_tool.skill` 直接加载并适配。
- 每个 skill 均有 `manifest.json`。
- SkillRegistry 支持受信任 skill 通过 frontmatter 声明稳定 `skill_id`。
- `tests/test_runtime_router_skills.py` 覆盖 stable id、manifest 对齐和
  WeChat send confirmation/slot 约束。

Tests:

- registry can load trusted runtime Router skills;
- descriptors include manifests and output capability constraints。

### Slice B - Proposal schema and validator

Status: implemented foundation in this branch.

- 扩展 proposal models。
- 新增 `routeSource`、`activatedSkillIds`、`commandDraft`、
  `taskRequestDraft`、`askAnswerDraft`、`confirmationResponseDraft` 和
  `requestedReadOnlyContext`。
- 新增 validator tests。

Tests:

- invalid proposal fail closed;
- low-confidence mutation rejected;
- `execution_handoff` without task draft rejected;
- WeChat task draft accepts only one-contact, confirmation-gated
  `communication.wechat.send_message`;
- WeChat external communication without confirmation rejected;
- `existing_command` requires an enabled command draft。

### Slice C - LLM planner skill context

Status: partially implemented foundation in this branch.

- Router planner prompt 接入内置 Router runtime skills。
- 内置 Router skills 以只读 prompt context 进入 planner prompt；skill 只提供
  语义、输出契约和示例，不授予运行时权限。
- 增加 Router request/config/skills/proposal/validation/fallback summary
  logs。
- Runtime router 增加 final dispatch summary log，记录最终 dispatch target、
  side effect、outcome、command/inquiry summary 和 confirmation requirement，
  不记录 raw user input。
- `runtime_input_router_config` 明确记录当前 effective config scope 为
  `app/global`，因为 Settings 目前没有 workspace/session 级配置入口。
- Shadow mode 对比、LLM input/output metadata log 和 diagnostics UI 展示仍在
  后续 slice。

Tests:

- mocked LLM receives Router skill ids, content hashes, output contracts, and
  bounded instruction excerpts;
- summary logs include effective app/global Router config scope;
- final dispatch summary logs include dispatch target and outcome without raw
  user input;
- runtime log taxonomy accepts Router event names;
- fallback summary log is emitted when planner fails closed。

### Slice D - Stop/retry through LLM proposal

Status: implemented in this branch.

- Router planner proposal 支持 `existing_command` dispatch。
- `commandDraft.commandKind=stop_task` / `retry_task` 可驱动现有 command
  gateway。
- 当 route planner 存在但返回 `invalid` / `unavailable` 或没有安全 proposal
  时，Router 现在 fail closed，返回无副作用 unsupported outcome，不再继续
  落入代码语义识别。
- 该边界覆盖 stop/retry、question/read-only inquiry、workspace-change 和
  WeChat send 语义 fallback。planner 失败就不会继续让代码 parser 创建命令或
  任务。
- 主产品 Main Page runtime 已接入 `LLMRuntimeInputRoutePlanner`，自由文本默认
  走 planner。
- 兼容 flag、phrase set、WeChat parser code 和相关 parser tests 已删除。

Tests:

- selected-task stop/retry works with valid proposal;
- active ASK / confirmation works with valid proposal;
- invalid or unavailable proposal does not dispatch and does not fall back to
  legacy direct ASK/confirmation handling。

### Slice E - Question/change heuristics removal

- 移除 question/workspace-change hardcoded heuristics。
- question / read-only / execution handoff 由 LLM proposal 决定。

Tests:

- read-only inquiry route works;
- workspace-changing input becomes task/plan proposal or unsupported。

### Slice F - WeChat semantic parser removal

Status: production default switched to LLM-first in this branch.

- WeChat task draft 可由 LLM proposal + `router-wechat-send` skill 提供。
- 已校验的 `taskRequestDraft` 会转换为现有 bounded WeChat dispatch input，
  并发布 confirmation-gated `communication.wechat.send_message` TaskRequest。
- 当 route planner 失败、超时或 proposal invalid 时，Router fail closed，
  不会继续调用代码 parser 解析原始自然语言。
- 旧版 WeChat 自然语言 parser 已删除。测试和 smoke 必须使用 planner-driven
  fixture 或明确的结构化 Task API 输入。
- Python 代码仍负责 deterministic policy validation、TaskRequest 构造、
  confirmation/idempotency/safety 边界。

Tests:

- `给微信的文件传输助手发送“你好”` mocked planner proposal creates
  `communication.wechat.send_message` task;
- missing contact/message proposal returns clarification;
- bulk send proposal rejected。

### Slice G - Production switch

- runtime config / Router 默认行为切换到 `llm_first`。
- 代码自然语言 semantic parser 已删除，不能 opt-in。
- Settings 仍只提供 app/global 入口；workspace/session Router config
  overrides 作为后续独立入口处理。

Status: implemented for Router production paths. Main Page runtime 已接入 LLM
Router planner。兼容测试和手工 smoke 已改为 planner-driven fixture；legacy
parser 已删除。

Tests:

- API route smoke;
- fake runtime WeChat no-send / confirm-send path;
- Electron runtime-input smoke;
- no real send in CI。

## 12. Code Change Inventory

Expected touched areas:

```text
src/taskweavn/server/runtime_input_router.py
src/taskweavn/server/runtime_input_llm_router.py
src/taskweavn/server/runtime_input_wechat.py
src/taskweavn/server/ui_contract/runtime_input.py
src/taskweavn/skills/
src/taskweavn/runtime_config/
tests/test_runtime_input_router*.py
tests/test_runtime_input_llm_router*.py
tests/test_runtime_input_wechat*.py
```

Potential frontend impact:

```text
frontend/src/... runtime input result/activity types
frontend/src/... route interpretation diagnostics display
```

MVP 可先不改 UI，只通过现有 outcome/activity 展示用户可见结果。

## 13. Rollback

不再提供回滚到自然语言代码语义识别的模式。若 Router LLM 不可用，自由文本
应 fail closed，并通过诊断日志暴露失败原因。

Rollback 不得允许：

- external send bypass confirmation;
- invalid LLM proposal dispatch;
- skill 权限扩张。

## 14. 验收标准

1. Router 生产路径不再依赖硬编码自然语言 phrase set。
2. 自由文本输入默认调用 Router LLM planner。
3. Router planner 使用 runtime skills，而不是把 app 语义写在代码里。
4. stop/retry/resume 等自然语言控制由 `router-control-commands` skill 指导。
5. WeChat 自然语言 task creation 由 `router-wechat-send` skill 指导。
6. Execution Agent / WeChat runtime 使用 execution-side WeChat skill 完成操作。
7. 所有 mutation / execution proposal 都经过 deterministic validator。
8. high-risk external communication 永远要求 confirmation。
9. diagnostics 可以解释 route source、active skills、validator 决策。
10. Router 日志可以解释 effective app/global config、activated skills、
    proposal validation、dispatch target 和 fallback reason。
11. 当前设置页变更明确按 app/global 生效，不声明 workspace/session 级配置入口。
12. 测试证明 LLM 错误、低置信度、缺 slot、越权 task type 均不会产生副作用。
