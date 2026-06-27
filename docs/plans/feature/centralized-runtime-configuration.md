# Feature Plan: Centralized Runtime Configuration

> Status: C1-C7.5 implemented control-plane foundation
> Type: Runtime control plane / configuration governance
> Last Updated: 2026-06-25
> Owner/Session: computer-use hardening discussion
> Target Implementation Session: runtime-config Settings read-only behavior complete
> Related Docs: [Configuration Guide](../../configuration.md), [Settings, Logs, And Audit Boundary](../../product/plato-settings-logs-audit-boundary.md), [Runtime Config Change Store](../../engineering/runtime-config-change-store.md), [Runtime Config Write API](../../engineering/runtime-config-write-api-contract.md), [Configurable Logging System](configurable-logging-system.md), [LLM Provider Plan](llm-provider-retry-thinking.md), [Execution Plane Service Task API](execution-plane-service-task-api.md), [Context Manager 1.0](context-manager-1-0.md), [Skill Governance](product-1-1-skill-governance.md)

---

## 1. Problem

Plato / Taskweavn now has enough runtime behavior that scattered configuration
is becoming a product risk.

Current behavior-shaping values are spread across:

- CLI flags in `taskweavn run`, `taskweavn plato-sidecar`, and `taskweavn plato-dev`;
- environment variables such as `PLATO_COMPUTER_USE_BACKEND`,
  `PLATO_COMPUTER_USE_ALLOWED_APPS`, `PLATO_ENABLE_READ_ONLY_INQUIRY_LLM`,
  `LLM_PROVIDER`, `LLM_MODEL`, `LLM_REQUEST_TIMEOUT_SECONDS`,
  `PLATO_WEB_SEARCH_ENABLED`, and logging/debug variables;
- dataclass defaults such as `MainPageSidecarConfig.default_agent_max_steps`;
- direct constructor defaults such as `AgentLoop.max_steps = 20`;
- Context Manager defaults such as context budgets and checkpoint intervals;
- feature-specific stores such as Settings config, logging config, thought
  config, web-search config, and computer-use runtime assembly;
- tests and scripts that pass their own local runtime parameters.

The result is that users and developers cannot reliably answer:

```text
Why did the Agent stop now?
Why did it compact/checkpoint context at this point?
Why did it ask me for confirmation here but not there?
Why can this workspace use computer-use but another cannot?
Why is this LLM/model/provider active?
Why did this timeout happen?
Which behavior will change immediately if I edit a setting?
```

The product need is not merely "more settings". The need is a single control
plane that explains the current expected behavior of the system.

---

## 2. Goals

1. Define a centralized runtime configuration model with typed domains,
   metadata, validation, and defaults.
2. Make current effective behavior queryable as an immutable
   `EffectiveRuntimeConfig` snapshot.
3. Separate configuration scope from configuration mutability:
   - where a value applies;
   - when a value takes effect.
4. Preserve source attribution for every effective value:
   built-in default, environment, CLI, global settings, workspace override,
   session override, task override, or runtime patch.
5. Give users and developers one place to inspect the expected behavior of the
   system.
6. Migrate high-impact behavior-shaping values first:
   Agent loop limits, Context Manager budgets/checkpointing, dispatcher ticks,
   computer-use enablement, LLM provider/timeouts, logging, web search, and
   safety/confirmation policy.
7. Keep the first implementation read-only and behavior-preserving.

---

## 3. Non-Goals

- Do not implement remote configuration service in the first version.
- Do not make every setting editable in the UI immediately.
- Do not force all configuration to be hot-updatable.
- Do not mix secrets into ordinary config diffs. Secrets should remain in a
  dedicated secret/settings boundary and only expose configured/not-configured
  status in effective config.
- Do not turn runtime configuration into an app automation playbook.
- Do not make app-specific behavior such as "how to send a WeChat message" a
  top-level config domain.
- Do not replace EventStream, MessageStream, TaskBus, or Context snapshots.
  Config is control-plane state, not work history.

---

## 4. Current State Inventory

### 4.1 Existing Config Entry Points

| Area | Current Entry | Example | Problem |
|---|---|---|---|
| CLI run | `taskweavn run` flags | `--max-steps 20`, `--logging-profile debug-tools`, `--autonomy careful` | Applies only to CLI run path. |
| Plato sidecar | `taskweavn plato-sidecar` / `taskweavn plato-dev` flags and env | `--computer-use-backend macos`, `PLATO_ENABLE_READ_ONLY_INQUIRY_LLM=0` | Not visible as an effective config object. |
| Packaged sidecar | `src/taskweavn/server/plato_sidecar.py` args/env | `PLATO_COMPUTER_USE_BACKEND` | Duplicates CLI concepts. |
| Main Page runtime | `MainPageSidecarConfig` | `default_agent_max_steps=20` | Some values are hidden constructor defaults. |
| Agent loop | `AgentLoop` dataclass | `max_steps=20` | Hardcoded default, no source attribution. |
| Context Manager | `ContextBudget`, `SessionAgentLoopContextProvider` | `checkpoint_interval_steps=5` | User cannot inspect why context checkpointing happens. |
| Execution dispatcher | `MainPageSidecarConfig` | `execution_dispatcher_max_ticks_per_trigger=10` | Runtime behavior not surfaced. |
| LLM | env + Settings config + agent resolver | provider/model/timeout | Multiple resolver paths. |
| Logging | logging config + Settings | profile/level/sinks | Has its own partial control plane. |
| Computer use | sidecar flags/env | backend, allowed apps | Product-critical, but not surfaced as effective behavior. |
| Web search/fetch | Settings + env | provider, enablement, fetch limits | Behavior-changing config is feature-local. |
| Safety/confirmation | autonomy/gate defaults and task handlers | risk thresholds, confirmation requirements | Not yet centralized. |
| Main Page trace | env | `PLATO_MAIN_PAGE_TRACE`, `PLATO_MAIN_PAGE_TRACE_FILE` | Debug behavior is environment-only. |
| Runtime Input Router | runtime config registry + Router LLM assembly | `llm_first`; planner required; fail-closed no-mutation policy; builtin runtime skills | Effective Router behavior keys are projected for diagnostics. Workspace/session Router override entry points remain future work. |

### 4.2 Current Hardcoded / Distributed Defaults

These are current implementation facts that the first registry must represent
without changing behavior.

| Concern | Current Default / Source | Current Location |
|---|---|---|
| Main Page sidecar port | `52789` | `DEFAULT_PLATO_SIDECAR_PORT` |
| Sidecar host | `127.0.0.1` | CLI / packaged sidecar args |
| Default Agent max steps | `20` | `MainPageSidecarConfig.default_agent_max_steps`, CLI `run --max-steps`, `main_page_agent` |
| Execution dispatcher | enabled | `MainPageSidecarConfig.enable_execution_dispatcher` |
| Dispatcher ticks per trigger | `10` | `MainPageSidecarConfig.execution_dispatcher_max_ticks_per_trigger` |
| Read-only inquiry LLM | enabled | `MainPageSidecarConfig.enable_read_only_inquiry_llm`, `PLATO_ENABLE_READ_ONLY_INQUIRY_LLM` |
| Computer-use backend | `disabled` | CLI/packaged sidecar `--computer-use-backend`, `PLATO_COMPUTER_USE_BACKEND` |
| Computer-use allowed apps | empty allowlist unless passed | `PLATO_COMPUTER_USE_ALLOWED_APPS` / sidecar args |
| Computer-use helper launch timeout | `90` seconds | `PLATO_COMPUTER_USE_HELPER_LAUNCH_TIMEOUT_SECONDS` |
| Computer-use helper launch poll interval | `0.2` seconds | `PLATO_COMPUTER_USE_HELPER_LAUNCH_POLL_INTERVAL_SECONDS` |
| Computer-use coordinate click | `false` | `build_computer_use_runtime(... allow_coordinate_click=False)` |
| Computer-use screen recording requirement | `false` | `build_computer_use_runtime(... screen_recording_required=False)` |
| Computer-use max text chars | `4000` | `MacOSComputerUseBackendConfig.max_text_chars` |
| Context max prior messages | `200` | `SessionAgentLoopContextProvider.max_prior_messages` |
| Context checkpoint interval | `5` steps | `SessionAgentLoopContextProvider.checkpoint_interval_steps` |
| Context recent events budget | `20` | `ContextBudget.max_events` |
| Context tool results budget | `10` | `ContextBudget.max_tool_results` |
| Context file snippets budget | `6` | `ContextBudget.max_file_snippets` |
| Context file snippet chars | `8000` | `ContextBudget.max_file_snippet_chars` |
| Context rendered chars | `60000` | `ContextBudget.max_rendered_chars` |
| Default LLM provider | `deepseek` | `DEFAULT_LLM_PROVIDER` |
| First-run LLM model | `deepseek-v4-pro` | Settings readiness/config defaults |
| LLM request timeout | `180` seconds | `DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS` |
| Web search | disabled unless Settings/env enable it | Settings config / `PLATO_WEB_SEARCH_ENABLED` |
| Web fetch | disabled unless Settings/env enable it | Settings config / `PLATO_WEB_FETCH_ENABLED` |
| Web fetch limits | Settings/env-derived | `PLATO_WEB_FETCH_MAX_*` |
| Structured logging level | `INFO` | CLI / `MainPageSidecarConfig.logging_level` |
| Main Page trace | enabled by default | `PLATO_MAIN_PAGE_TRACE`, `PLATO_MAIN_PAGE_TRACE_PRINT`, `PLATO_MAIN_PAGE_TRACE_FILE` |
| Runtime Input Router mode | `llm_first` in Main Page runtime | `DefaultRuntimeInputRouter(route_planner=LLMRuntimeInputRoutePlanner(...))` |

### 4.3 Existing Plan Status

This document previously described a general hierarchical configuration system.
That direction remains valid, but it did not account for Product 1.0 / 1.1
work that now exists:

- Task-first Main Page runtime;
- fixed-route task execution bridge;
- Task API / Execution Plane service shell;
- ASK and confirmation lifecycle;
- Context Manager and cache-aware rendering;
- Skill Governance and skill context sources;
- macOS computer-use and Local WeChat Send MVP;
- Settings config and Diagnostics surfaces.

The updated plan below treats centralized runtime config as a control-plane
hardening effort over the current system, not as a greenfield configuration
rewrite.

As of 2026-06-24, the first centralized runtime config implementation slices
exist:

- `src/taskweavn/runtime_config/` defines typed registry, defaults, env/process
  source layers, resolver, and effective config models;
- `src/taskweavn/server/runtime_config_gateway.py` exposes a sidecar-facing
  gateway;
- `src/taskweavn/server/ui_http_runtime_config.py` exposes HTTP adapters for
  schema/effective/explain, change history, snapshot lookup, and controlled
  local patch writes;
- `src/taskweavn/server/ui_http_routes.py` registers:
  - `GET /api/v1/runtime/config/schema`
  - `GET /api/v1/runtime/config/effective`
  - `GET /api/v1/runtime/config/explain`
  - `GET /api/v1/runtime/config/changes`
  - `GET /api/v1/runtime/config/snapshots/{configHash}`
  - `PATCH /api/v1/runtime/config`
- `src/taskweavn/server/main_page.py` wires sidecar process inputs into the
  runtime config gateway and wires the workspace-local change store/mutation
  service into the local sidecar transport.
- `frontend/src/pages/settings/SettingsRuntimeBehaviorTab.tsx` adds a
  read-only Settings runtime behavior section backed by
  `GET /api/v1/runtime/config/effective`.

The implementation is intentionally behavior-preserving. Runtime components
still primarily receive their values through the existing constructor/config
paths. The centralized config layer now reflects, explains, and records
workspace-local runtime config changes in the local sidecar. It is not yet the
sole source of runtime behavior, and most changed values do not mutate
already-running agents. C7.3b wires the durable change/snapshot store and
mutation service into local sidecar assembly so the HTTP write route can persist
changes. C7.4 exposes a read-only Settings runtime behavior section for the
current effective config, source attribution, mutability, and effective status.
C7.5 projects runtime config snapshot/change facts into Audit config evidence
through the existing Audit config provider seam. Editable Settings controls and
broader runtime consumers remain deferred.

### 4.4 Current Product UI Scope Boundary

The current Product 1.1 Settings surface is app-level only.

This is a product boundary, not only an implementation detail:

- Settings changes affect the whole local app/runtime process.
- There is no workspace-level configuration entry point yet.
- There is no session-level configuration entry point yet.
- The effective config model may represent global/workspace/session/task
  scopes, but the UI must not imply that users can edit workspace/session
  overrides today.
- Future workspace/session config requires a separate product entry, effective
  config explanation, audit evidence, and conflict/override semantics.

Until those entry points exist, Settings copy, runtime config diagnostics, and
Router logs should label editable Settings values as `app` or `global` scope.

---

## 5. Core Decisions

### 5.1 Config Explains Expected Behavior

Runtime config should answer:

```text
What behavior should this process/workspace/session/task currently exhibit?
Where did each behavior value come from?
When will changes to that value take effect?
```

### 5.2 Effective Config Is Immutable

Runtime components should consume an immutable snapshot:

```text
ConfigRegistry
  -> ConfigSources
  -> RuntimeConfigResolver
  -> EffectiveRuntimeConfig
  -> runtime component constructors / diagnostics / audit
```

Components should not independently read environment variables, ad hoc dicts,
or hidden defaults once their domain is migrated.

### 5.3 Scope And Mutability Are Separate

Scope defines where a value applies.

Mutability defines when a changed value becomes effective.

These must not be collapsed.

### 5.4 First Implementation Is Read-Only

The first implementation should not change runtime behavior. It should:

1. register important config keys;
2. compute effective values from existing defaults/CLI/env/settings;
3. expose source attribution;
4. add tests proving existing behavior is represented.

Write APIs and UI editing come later.

### 5.5 App Behavior Belongs To Skills / Adapters

Specific application procedures are not top-level runtime config.

For example, WeChat should not be a first-class config domain.

Correct split:

| Concern | Owner |
|---|---|
| Whether computer-use is enabled | `computer_use` config |
| Which apps may be controlled | `computer_use.allowed_apps` |
| Whether high-risk sends require confirmation | `safety` / `computer_use.action_policy` config |
| How WeChat contact search works | WeChat adapter / skill |
| Whether WeChat submits by Return or button click | WeChat adapter / skill |
| WeChat send evidence schema | adapter / skill contract |

If app-specific configuration is later needed, it should live under
`computer_use.app_profiles`, not as a top-level `wechat` domain.

---

## 6. Scope Model

Recommended scope levels:

```text
built_in_default
  -> user_global
  -> workspace
  -> session
  -> task
  -> agent_run
  -> runtime_override
  -> cli_env_process
```

Product-facing scopes:

| Scope | Meaning | Example |
|---|---|---|
| `global` | Default user/device behavior. | Default LLM provider. |
| `workspace` | Behavior for one workspace. | Enable web search for this workspace. |
| `session` | Behavior for one user collaboration session. | More careful confirmation policy. |
| `task` | Behavior for one task. | Require audit/evidence for this task. |
| `agent_run` | Frozen behavior for one execution attempt. | Max steps for this run. |
| `process` | Startup-only sidecar behavior. | Host, port, computer-use backend. |

Implementation sources may include CLI/env, but source is not the same as
scope. For example, `PLATO_COMPUTER_USE_BACKEND=macos` is a process source for
the `computer_use.backend` key.

---

## 7. Mutability Model

Every registered key must declare when a changed value takes effect.

| Mutability | Meaning | Examples |
|---|---|---|
| `live` | Current process applies immediately. | logging level, UI density. |
| `next_context_build` | Next Context Manager build applies. | context budget limits. |
| `next_llm_call` | Next LLM request applies. | request timeout, retry policy. |
| `next_action` | Next action/safety decision applies. | risk threshold, audit strength. |
| `next_agent_run` | Next agent execution attempt applies. | Agent loop max steps, checkpoint interval. |
| `next_task` | Next published/claimed task applies. | tool allowlist, capability routing. |
| `next_session` | New session applies. | default task authoring behavior. |
| `startup_only` | Requires process restart. | host, port, computer-use backend package backend. |
| `migration_only` | Requires data/schema migration. | config schema version. |

`agent_loop.default_max_steps` and
`context_manager.checkpoint_interval_steps` should be `next_agent_run`, not
`live`. Changing them mid-run would make current execution difficult to explain.

---

## 8. Runtime Domains

First-class top-level domains should be stable system behavior domains.

| Domain | Purpose | First-batch examples |
|---|---|---|
| `agent_loop` | Execution loop behavior. | `default_max_steps` |
| `context_manager` | Context assembly and compaction/checkpoint behavior. | `checkpoint_interval_steps`, budgets |
| `execution_dispatcher` | TaskBus dispatch trigger behavior. | `max_ticks_per_trigger`, enabled |
| `task_api` | Local Task API / Execution Plane service behavior. | enabled, idempotency policy, session validation |
| `computer_use` | OS automation backend and safety envelope. | backend, allowed apps, coordinate-click policy |
| `safety` | Confirmation and risk behavior. | high-risk confirmation requirement |
| `llm` | Provider/model/retry/timeout/routing. | default model, request timeout |
| `logging` | Log profiles, levels, sinks. | selected profile, level |
| `audit` | Audit strength and evidence behavior. | mode, relevant record collection |
| `web` | Web search/fetch behavior. | enabled, provider, fetch limits |
| `settings` | Settings storage/readiness behavior. | global settings root |
| `ui` | Presentation defaults. | density, raw-result visibility |

Not top-level domains:

| Not Top-Level | Reason |
|---|---|
| `wechat` | App procedure belongs to adapter/skill; config only controls whether WeChat can be automated. |
| `tavily` | Provider detail under `web`. |
| `deepseek` / `openrouter` | Provider detail under `llm`. |
| `local_wechat_send_smoke` | Test harness / skill, not runtime config. |

---

## 9. First-Batch Key Registry

The initial registry should be intentionally small and focused on behavior users
can observe.

| Key | Current Source | Scope | Mutability | Notes |
|---|---|---|---|---|
| `agent_loop.default_max_steps` | `AgentLoop.max_steps`, `MainPageSidecarConfig.default_agent_max_steps`, CLI `--max-steps` | workspace/session/agent_run | `next_agent_run` | Current common value is 20. |
| `context_manager.checkpoint_interval_steps` | `SessionAgentLoopContextProvider.checkpoint_interval_steps` | workspace/session/agent_run | `next_agent_run` | Current common value is 5. |
| `context_manager.max_prior_messages` | `SessionAgentLoopContextProvider.max_prior_messages` | workspace/session/agent_run | `next_agent_run` | Current common value is 200. |
| `context_manager.budget.max_events` | `ContextBudget.max_events` | workspace/session/task | `next_context_build` | Current common value is 20. |
| `context_manager.budget.max_tool_results` | `ContextBudget.max_tool_results` | workspace/session/task | `next_context_build` | Current common value is 10. |
| `context_manager.budget.max_file_snippets` | `ContextBudget.max_file_snippets` | workspace/session/task | `next_context_build` | Current common value is 6. |
| `context_manager.budget.max_file_snippet_chars` | `ContextBudget.max_file_snippet_chars` | workspace/session/task | `next_context_build` | Current common value is 8000. |
| `context_manager.budget.max_rendered_chars` | `ContextBudget.max_rendered_chars` | workspace/session/task | `next_context_build` | Current common value is 60000. |
| `execution_dispatcher.enabled` | `MainPageSidecarConfig.enable_execution_dispatcher` | process/workspace | `startup_only` initially | Can become live later. |
| `execution_dispatcher.max_ticks_per_trigger` | `MainPageSidecarConfig.execution_dispatcher_max_ticks_per_trigger` | process/workspace | `next_task` | Current common value is 10. |
| `task_api.enabled` | sidecar route/service assembly | process/workspace | `startup_only` | Needs explicit surface. |
| `task_api.require_valid_session` | planned hardening | workspace | `next_task` | Should prevent orphan external tasks. |
| `computer_use.enabled` | derived from backend/dependency | process/workspace | `startup_only` | Current default disabled. |
| `computer_use.backend` | CLI/env `PLATO_COMPUTER_USE_BACKEND` | process | `startup_only` | `disabled`, `helper`, or `macos`. |
| `computer_use.allowed_apps` | CLI/env `PLATO_COMPUTER_USE_ALLOWED_APPS` | process/workspace | `startup_only` initially | Example: `WeChat`. |
| `computer_use.allow_coordinate_click` | backend assembly | process/workspace | `startup_only` initially | Default should remain false. |
| `computer_use.screen_recording_required` | backend assembly | process/workspace | `startup_only` initially | Default should remain false. |
| `computer_use.max_text_chars` | `MacOSComputerUseBackendConfig.max_text_chars` | process/workspace | `startup_only` initially | Current value is 4000. |
| `safety.high_risk_confirmation` | confirmation/handler policy | workspace/session/task | `next_action` | Required for send-like actions. |
| `llm.default_provider` | env/settings | global/workspace/session | `next_llm_call` | Current default is `deepseek`. |
| `llm.default_model` | env/settings/CLI | global/workspace/session | `next_llm_call` | Current first-run default is `deepseek-v4-pro`. |
| `llm.request_timeout_seconds` | env/settings/profile | global/workspace/session | `next_llm_call` | Current default is 180 seconds. |
| `logging.profile` | CLI/settings/logging config | global/workspace/session | `live` where supported |
| `logging.level` | CLI/settings/logging config | global/workspace/session | `live` where supported |
| `web.search_enabled` | Settings/env | global/workspace/session | `next_action` |
| `web.fetch_limits` | Settings/env | global/workspace/session | `next_action` |
| `read_only_inquiry.llm_enabled` | CLI/env | process/workspace | `startup_only` initially |
| `debug.main_page_trace_enabled` | env | process | `live` or `startup_only` initially | Current default is enabled. |
| `debug.main_page_trace_sink` | env | process | `startup_only` initially | stdout/file behavior is env-only today. |

---

## 10. Core Contracts

### 10.1 RuntimeConfigKey

```python
class RuntimeConfigKey(BaseModel):
    key: str
    domain: str
    value_type: str
    default: Any
    scope_levels: tuple[str, ...]
    mutability: str
    description: str
    user_visible: bool = True
    secret: bool = False
    restart_required: bool = False
```

### 10.2 RuntimeConfigSource

```python
class RuntimeConfigSource(BaseModel):
    source_id: str
    kind: Literal[
        "built_in_default",
        "environment",
        "cli",
        "settings_store",
        "workspace_file",
        "session_override",
        "task_override",
        "runtime_patch",
    ]
    scope: ConfigScope
    priority: int
```

### 10.3 EffectiveRuntimeConfigValue

```python
class EffectiveRuntimeConfigValue(BaseModel):
    key: str
    value: Any
    source: RuntimeConfigSource
    mutability: str
    effective_status: Literal[
        "active",
        "pending_next_context_build",
        "pending_next_llm_call",
        "pending_next_action",
        "pending_next_agent_run",
        "pending_next_task",
        "pending_next_session",
        "pending_restart",
    ]
    redacted: bool = False
```

### 10.4 EffectiveRuntimeConfig

```python
class EffectiveRuntimeConfig(BaseModel):
    config_id: str
    scope: ConfigScope
    created_at: datetime
    schema_version: str
    values: dict[str, EffectiveRuntimeConfigValue]
    source_layers: tuple[RuntimeConfigSource, ...]
    config_hash: str
```

### 10.5 RuntimeConfigResolver

```python
class RuntimeConfigResolver(Protocol):
    def resolve(self, scope: ConfigScope) -> EffectiveRuntimeConfig:
        ...

    def explain(self, key: str, scope: ConfigScope) -> EffectiveRuntimeConfigValue:
        ...
```

---

## 11. Config Source Order

Initial merge order:

```text
built-in defaults
  -> user global settings
  -> workspace settings
  -> session overrides
  -> task overrides
  -> runtime patches
  -> CLI/env process overrides
```

For Product 1.0/1.1 compatibility, CLI/env process overrides should remain
highest priority for startup-only process behavior. This avoids surprising
developers who intentionally launched a sidecar with explicit flags.

Future product settings can decide whether user-visible UI overrides outrank
environment overrides for non-startup settings.

---

## 12. Runtime Lifecycle

### 12.1 Process Startup

```text
load built-in registry defaults
read environment variables
read CLI args
read global/workspace settings if available
resolve process/workspace EffectiveRuntimeConfig
assemble sidecar/runtime dependencies
expose effective config through diagnostics/API
```

### 12.2 Session Creation / Selection

```text
resolve workspace config
apply session config overlay
persist or reference session effective config hash
show behavior summary in diagnostics/settings
```

### 12.3 Task Claim / Agent Run Start

```text
resolve task/agent_run config
freeze agent_run effective config
construct AgentLoop / ContextProvider / tool policy from snapshot
store config hash with execution trace
```

### 12.4 Runtime Patch

```text
receive patch from UI/CLI/API
validate against registry
write ConfigChange
compute pending/active effective status
publish ConfigChanged when supported
surface when restart or next boundary is required
```

### 12.5 Archive / Audit

Session diagnostics and Audit evidence should be able to show:

- effective config summary;
- config hash timeline;
- relevant config changes;
- rejected config patches;
- whether a surprising behavior came from a setting, CLI flag, env var, or
  built-in default.

---

## 13. User Surfaces

### 13.1 Settings / Runtime Behavior

User-facing Settings should show stable behavior controls:

- Agent loop maximum steps;
- Context Manager checkpoint/context budget behavior;
- default LLM provider/model/readiness;
- logging profile;
- computer-use enabled/disabled and allowed apps;
- high-risk confirmation policy;
- web search/fetch enablement.

Settings should avoid exposing every registry key by default. Advanced details
belong in Diagnostics.

### 13.2 Diagnostics / Effective Config

Diagnostics should expose:

- current `EffectiveRuntimeConfig`;
- source per key;
- mutability per key;
- pending restart / pending next-run indicators;
- config hash;
- redacted secret status.

### 13.3 Audit Page

Audit Page should not edit configuration. It should show relevant configuration
evidence for the current session/task/action:

- effective config summary;
- config change records;
- config validation rejections;
- related logging/profile/tool policy at the time of action.

---

## 14. API Surface

First version should be read-only:

```text
GET /api/v1/runtime/config/schema
GET /api/v1/runtime/config/effective?workspaceId=...&sessionId=...&taskId=...
GET /api/v1/runtime/config/explain?key=...&workspaceId=...&sessionId=...
```

Later write APIs:

```text
PATCH /api/v1/runtime/config
GET /api/v1/runtime/config/changes
```

The write API must return whether the patch is active now, pending a boundary,
or rejected.

---

## 15. Implementation Slices

### C1: Read-Only Config Registry

Status: implemented.

- Add typed registry models.
- Register first-batch keys.
- Include defaults, scope, mutability, descriptions, and source labels.
- Add unit tests for registry completeness and duplicate key rejection.
- No runtime behavior changes.

### C2: Effective Config Resolver

Status: implemented.

- Resolve built-in defaults plus existing CLI/env/settings sources.
- Produce `EffectiveRuntimeConfig`.
- Preserve source attribution.
- Add tests proving current values are represented.
- No runtime behavior changes unless tests explicitly cover equivalence.

### C3: Diagnostics/API Exposure

Status: implemented for read-only HTTP routes.

- Expose schema/effective/explain endpoints.
- Add sidecar read-only effective config exposure.
- Add config hash to startup diagnostics.
- Keep write APIs out of scope.

### C4: Runtime Constructor Wiring

Status: implemented.

Implemented C4.1 behavior-preserving migration:

- Main Page sidecar resolves a workspace-scoped `EffectiveRuntimeConfig`
  during runtime assembly.
- `src/taskweavn/server/runtime_config_consumers.py` adapts the effective
  config snapshot into typed execution constructor settings.
- `AgentLoop.max_steps` for the resident default agent is now sourced from
  `agent_loop.default_max_steps` in the effective config snapshot.
- `FixedRouteExecutionDispatcher.enabled` is now sourced from
  `execution_dispatcher.enabled`.
- `FixedRouteExecutionDispatcher.max_ticks_per_trigger` is now sourced from
  `execution_dispatcher.max_ticks_per_trigger`.
- `MainPageWorkspaceRuntime` retains the effective runtime config snapshot and
  config hash for the assembled runtime.

Implemented C4.2 behavior-preserving migration:

- `RuntimeContextSettings` adapts the effective config snapshot into typed
  Context Manager constructor settings.
- `SessionAgentLoopContextProvider.checkpoint_interval_steps` is now sourced
  from `context_manager.checkpoint_interval_steps`.
- `SessionAgentLoopContextProvider.max_prior_messages` is now sourced from
  `context_manager.max_prior_messages`.
- The AgentLoop context provider now passes a configured `ContextBudget` into
  every `ContextBuildRequest`, using `context_manager.budget.*` keys.
- Main Page sidecar process inputs expose the Context Manager keys so
  diagnostics and runtime constructor behavior share one effective snapshot.

Implemented C4.3 behavior-preserving migration:

- `RuntimeComputerUseSettings` adapts the effective config snapshot into typed
  computer-use runtime envelope settings.
- The resident Default Agent tool assembly, Execution Plane environment
  registry, and WeChat runtime handler registration now use
  `computer_use.enabled` from the effective config snapshot.
- Main Page sidecar process inputs expose `computer_use.backend` and
  `computer_use.allowed_apps`, preserving CLI/packaged sidecar selections in
  diagnostics.
- `RuntimeReadOnlyInquirySettings` adapts the effective config snapshot into
  the read-only inquiry service toggle.
- The guarded read-only inquiry LLM service is now assembled from
  `read_only_inquiry.llm_enabled` in the effective config snapshot.

Implemented C4.4 behavior-preserving migration:

- `ContextBuildRequest`, `RenderedLlmInput`, `ContextSnapshot`, and
  `ContextTrace` can carry the effective `runtime_config_hash`.
- `SessionAgentLoopContextProvider` propagates the sidecar-resolved config
  hash into every Context Manager build.
- AgentLoop LLM call metadata includes `context_runtime_config_hash` when the
  context provider supplies it.
- Main Page sidecar resident agent assembly passes the effective config hash
  from `RuntimeContextSettings`, giving execution/context diagnostics a stable
  reference to the runtime snapshot used for that agent run.

All C4 migrations must preserve current defaults unless a later slice
explicitly authorizes runtime behavior changes.

### C5: Config Change Store

Status: implemented.

The C5 contract is defined in
[Runtime Config Change Store](../../engineering/runtime-config-change-store.md).

Required implementation slices:

- C5.1 Contract Models: implemented additive patch/change/snapshot models and
  validation tests.
- C5.2 SQLite Store: durable change ledger and effective config snapshot
  storage implemented in `SqliteRuntimeConfigChangeStore`; accepted,
  rejected, no-op, snapshot, idempotency lookup, and duplicate idempotency
  rejection tests are covered.
- C5.3 Mutation Service: validate patches, normalize values, resolve base and
  candidate effective configs, and persist accepted/rejected/no-op records
  implemented in `DefaultRuntimeConfigMutationService`; tests cover accepted,
  rejected, no-op, partial acceptance, stale base hash, dry-run, process-scope
  rejection, and idempotency replay.
- C5.4 Read Gateway Extension: expose change/snapshot queries without changing
  existing read-only schema/effective/explain behavior implemented in
  `DefaultRuntimeConfigGateway`; tests cover optional store queries and
  existing HTTP route compatibility.
- C5.5 HTTP Write API Design Gate: design patch/list routes only after the
  backend store and mutation service are proven; implemented in
  [Runtime Config Write API](../../engineering/runtime-config-write-api-contract.md).

C5 remains backend/control-plane work. It must not add Settings UI, live
ConfigBus application, or app-specific automation behavior.

### C6: Runtime Patches And ConfigBus

Status: implemented.

- C6.1 Internal Bus And Publication Boundary: implemented in
  [Runtime Config ConfigBus](../../engineering/runtime-config-configbus-contract.md).
- Publish accepted non-dry-run config changes through an internal typed
  ConfigBus.
- Do not publish rejected, no-op, dry-run, or idempotency replay changes.
- Separate active values from pending values so live consumers cannot
  accidentally mutate already-running AgentLoop or Context Manager state.
- Support a first production `live` consumer for active `logging.level`
  changes through the existing observability manager.
- Keep `logging.profile` deferred until session/global scope semantics are
  clearer.
- Keep other changes pending appropriate boundaries such as next context build,
  next agent run, next task, next session, or restart.
- Project recent ConfigBus publication and consumer result facts into internal
  diagnostics summaries without adding external routes.

### C7: Settings UI And Audit/Diagnostics Integration

Status: C7.1-C7.5 implemented as a control-plane foundation.

- Settings shows a read-only runtime behavior summary for selected effective
  config keys.
- Diagnostics shows raw effective config, C7.1 read-only combined diagnostics
  facts, and C7.2 read-only HTTP change/snapshot routes.
- HTTP transport exposes C7.3 controlled runtime config patch semantics.
- Local sidecar assembly creates a workspace-local runtime config SQLite store,
  constructs `DefaultRuntimeConfigMutationService`, and passes both read and
  write dependencies into the HTTP transport.
- Settings runtime config editing controls remain deferred until safe controls,
  pending-state copy, and authorization behavior are accepted.
- Audit evidence projection includes effective runtime config snapshot records
  and runtime config change records with config snapshot evidence refs. Audit
  does not expose raw config values and remains read-only.
- Do not overload Audit as a config editor.
- Integration design is defined in
  [Runtime Config Settings, Diagnostics, And Audit Integration](../../engineering/runtime-config-settings-diagnostics-integration.md).

---

## 16. Acceptance Criteria

1. A developer can query one effective config snapshot and see why the current
   Agent loop will stop after N steps.
2. A developer can query why Context Manager checkpointing happens every N
   steps.
3. Computer-use enablement and allowed apps are visible in effective config.
4. LLM provider/model/timeout source is visible without reading env or CLI code.
5. Logging profile/level source is visible.
6. Startup-only values clearly say restart is required.
7. Next-run values clearly say current Agent run is unaffected.
8. No app-specific playbook, including WeChat send behavior, becomes a top-level
   config domain.
9. Initial read-only registry/resolver does not change runtime behavior.
10. Tests cover defaults, source priority, mutability metadata, and duplicate
    key validation.
11. Context/execution trace metadata can reference the effective config hash
    used at runtime assembly.
12. Settings can show a read-only runtime behavior section with effective
    values, source attribution, mutability/effective status copy, and no edit
    controls.

---

## 17. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Config system becomes too abstract | Start with read-only registry and high-impact keys only. |
| Runtime behavior changes accidentally | C1-C3 must be behavior-preserving. |
| UI exposes too many controls | Split Settings summary from Diagnostics raw config. |
| App automation scripts leak into config | Keep app procedures in skills/adapters; config only controls permission/safety envelope. |
| Hot updates cause inconsistent execution | Require mutability metadata and freeze agent-run snapshots. |
| Secrets leak into diagnostics | Store only redacted configured/not-configured status. |
| CLI/env compatibility breaks | Treat explicit process flags/env as high-priority startup sources initially. |

---

## 18. Open Questions

1. Should `task_api.enabled` be independently configurable, or does the sidecar
   process itself imply local Task API availability?
2. Should session-level config snapshots be persisted at session creation or
   resolved lazily at task/agent-run start?
3. Should `computer_use.allowed_apps` become workspace-level later, or remain a
   process launch boundary for safety?
4. Which config store should own global/workspace/session overrides:
   existing Settings config store, a new ConfigStore, or a shared SQLite config
   database?
5. Should runtime patches have TTL by default?
6. Which Settings controls are safe for Product 1.0/1.1 users versus
   Diagnostics-only?

---

## 19. Recommended Next Task

C4 is closed for the read-only, behavior-preserving runtime constructor and
trace metadata path. C5 is closed through durable change/snapshot facts,
backend-only mutation validation, read gateway queries, and the HTTP write API
design gate. C6 is closed for the internal ConfigBus event boundary, active
`logging.level` live-safe application, and internal diagnostics projection. C7
design is accepted for Settings, Diagnostics, and Audit integration. C7.1 is
closed with an internal read-only diagnostics gateway. C7.2 is closed with
read-only HTTP extensions for change list and snapshot lookup. C7.3 is closed
with the framework-neutral `PATCH /api/v1/runtime/config` route. C7.3b is
closed with local sidecar store and mutation service wiring. C7.4 is closed
with a read-only Settings runtime behavior section backed by the effective
config HTTP route. C7.5 is closed with Audit config evidence records for the
effective runtime config snapshot and durable runtime config changes.

Recommended next task:

```text
Use the product-workflow-gate skill first.

Task:
Define the next Centralized Runtime Configuration closure slice.

Scope:
- Decide whether the next slice should be Settings safe-edit controls, broader
  runtime consumer migration, or diagnostics bundle export.
- Keep runtime config as the system behavior control plane.
- Keep app-specific procedures such as WeChat send behavior in skills/adapters.

Do not:
- Treat app-specific automation behavior such as WeChat send steps as top-level
  runtime config.
- Add a generic raw config editor or Settings write controls.
- Expose remote runtime config writes.
- Apply non-live config changes to already-running agents.

Output:
- Workflow Gate Report
- files changed
- selected next slice and rationale
- tests required, if any
- checks run
- remaining runtime config blockers
```
