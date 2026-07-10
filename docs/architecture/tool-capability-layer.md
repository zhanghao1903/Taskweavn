# Tool Capability Layer

> Status: current fact baseline plus extension boundary
> Last Updated: 2026-07-10
> Scope: tools, capabilities, authoring catalogs, execution policy, computer-use,
> web retrieval, and skill governance
> Related Discussion:
> [Product positioning 10.7-10.8](../discussion/2026-05-11-product-positioning-and-boundaries.md#107-新暴露的系统级问题工具供给与选择负载比工具可扩展更关键)
> Related Architecture: [Authoring Domain](authoring-domain.md),
> [Authoring Command Protocol](authoring-command-protocol.md),
> [Workspace Communication Protocol](workspace-communication-protocol.md),
> [Collaborator Agent](collaborator-agent-task-authoring.md), [Task](task.md),
> [TaskBus](bus.md), [Agent](agent.md),
> [Execution Plane service memo](taskbus-service-multi-execution-env.md)
>
> 2026-07-10 fact calibration: current code has no production
> `ToolPoolRef`, `ToolAccessPolicy`, `ToolDescriptor`, global dynamic tool
> registry, tool marketplace, workspace `WorkspaceRequest` execution gateway,
> MCP integration, or multi-provider tool router. Current facts are:
> concrete `Tool` classes registered into `LocalRuntime`; sidecar Default Agent
> tool assembly; Context Manager `allowed_tools` / `denied_tools`; static
> authoring `CapabilityCatalog`; Execution Plane `CapabilityPolicy` plus local
> `ExecutionEnv.tool_pool` compatibility checks; optional `web_search`,
> `web_fetch`, and `computer_use`; and Product 1.1 skill governance that can
> narrow, but not grant, runtime tools.

---

## 1. Purpose

The tool capability layer prevents three concerns from collapsing into one:

```text
user-visible work intent
  -> capability required to do the work
  -> runtime policy for whether the capability is allowed
  -> concrete tools mounted into an AgentLoop
```

The current system already uses this separation in several places, but it does
not yet have a single dynamic tool platform.

Current implementation is intentionally modest:

- Task and Plan nodes carry `required_capability`.
- Authoring validates `required_capability` through a static
  `CapabilityCatalog`.
- Execution Plane requests carry `CapabilityPolicy`.
- Local execution environments advertise `capabilities` and `tool_pool`.
- The Default Agent receives a concrete tool list at run time.
- Context Manager renders `allowed_tools`, `denied_tools`, guidance, and skill
  constraints into execution context.

Long-term tool supply, capability routing, and workspace operation protocols
remain extension work.

---

## 2. Current Implementation Snapshot

```text
Authoring / publish time
  RawTask / Plan / TaskNode
    -> required_capability
    -> StaticCapabilityCatalog / StaticAgentCapabilityCatalog validation
    -> PublishedTask.required_capability

Execution Plane publish time
  TaskRequest.policy: CapabilityPolicy
    -> InMemoryExecutionEnvRegistry.find_compatible()
    -> ExecutionEnv.supports(required_capability, allowed_tools)
    -> TaskBus.publish()

Default Agent run time
  build_agent_loop_resident_default_agent()
    -> concrete Tool objects
    -> LocalRuntime.register(action_type, execute)
    -> Context Manager controls.allowed_tools
    -> AgentLoop tool schemas

Context and governance
  SkillContextSource / merge_skill_controls()
    -> can narrow allowed tools
    -> can add denied tools, approval requirements, and file scopes
    -> cannot grant tools the runtime did not already allow
```

This is the current fact baseline. Anything beyond these boundaries is future
design unless a later release updates this document.

---

## 3. Tool Runtime Boundary

### 3.1 Current `Tool` contract

Production tools subclass `taskweavn.tools.base.Tool`.

Each tool provides:

- `name`;
- `description`;
- `action_type`;
- `observation_type`;
- `execute(action)`;
- optional `startup()` and `shutdown()` hooks;
- `register(runtime)`, which binds the tool's action type to `LocalRuntime`.

The AgentLoop therefore executes typed Actions through `LocalRuntime`, not
through a descriptor registry.

### 3.2 Default execution tool set

The sidecar Default Agent currently mounts these workspace tools for normal
task execution:

```text
read_file
read_file_range
search_workspace
replace_file_range
append_file
write_file
list_dir
run_command
```

Conditional tools are mounted only when the sidecar/runtime prerequisites are
present:

| Tool | Current enablement rule |
|------|-------------------------|
| `web_search` | `FileSettingsConfigStore` exists, web search is ready, provider is `tavily`, and a usable secret/config path exists. |
| `web_fetch` | Web search is ready, fetch is ready, provider is `tavily`, and fetch limits are configured. |
| `computer_use` | `enable_computer_use_tool=True`; the backend is injected or resolved from runtime config. |
| `ask_user` | Ask store, TaskBus, and task id are available. |
| `request_confirmation` | MessageBus, TaskBus, and task id are available. |

The Context Manager control source mirrors this mounted tool set through
`ExecutionControls.allowed_tools`, and execution guidance adds tool-specific
rules for web retrieval, confirmation, and computer-use when those tools are
available.

### 3.3 Current workspace protection

Filesystem tools resolve paths through `Workspace`.

Current protection:

- relative paths are resolved under one workspace root;
- absolute paths must still be inside that root;
- protected metadata directories, such as `.plato`, are blocked from ordinary
  tool access;
- directory listings omit protected metadata entries.

This is a local workspace boundary, not a full sandbox.

### 3.4 Precision file tools

Precision tools are current:

```text
read_file_range
search_workspace
replace_file_range
append_file
```

`replace_file_range` and `append_file` require an operation id and expected
content hash. Mutation observations include changed line ranges, before/after
hashes, bytes written, and an inspection evidence ref.

These tools are a real implemented slice of the future workspace operation
direction. They are not yet routed through a generic `WorkspaceRequest` gateway.

---

## 4. Capability And Catalog Facts

### 4.1 `required_capability`

`required_capability` is current across authoring, publish, TaskBus, and
Execution Plane boundaries.

Important current uses:

- `DraftTaskNodeProposal` and `PlanTaskNodeProposal` require it.
- normalized publish input requires `required_capability` or `capability`.
- `PublishedTask` / `TaskDomain` stores it.
- TaskBus `claim_next()` matches pending tasks by exact capability string.
- Execution Plane `TaskRequest.policy.required_capability` maps into
  `TaskExecution.required_capability` and the published Task.

### 4.2 Authoring `CapabilityCatalog`

`CapabilityDescriptor`, `CapabilityCatalog`, and `StaticCapabilityCatalog` are
implemented in `taskweavn.task.authoring`.

Current descriptor fields include:

```text
capability_id
display_name
summary
input_schema
output_schema
preconditions
cost_level
latency_level
risk_level
reliability_score
applicable_domains
anti_patterns
```

`StaticCapabilityCatalog` supports:

- `all()`;
- `get(capability_id)`;
- `contains(capability)`;
- `query(intent, domains=(), limit=20)`.

The default Main Page sidecar catalog currently contains:

```text
general
writing
coding
testing
research
```

This is enough for deterministic authoring and publish validation. It is not a
dynamic registry of executable tools.

### 4.3 Agent capability validation

`StaticAgentCapabilityCatalog` and `TaskTreeInputValidator` validate that an
explicit `agent_ref` supports the node's required capability when an agent
catalog is supplied.

This is publish-time validation. It is not current dynamic Agent assignment,
not Agent Manager routing, and not a runtime claim protocol.

---

## 5. Execution Plane Policy Facts

### 5.1 `CapabilityPolicy`

Execution Plane requests carry `CapabilityPolicy`:

```text
required_capability
allowed_tools
denied_tools
requires_human_confirmation
max_runtime_seconds
max_llm_tokens
workspace_scope
risk_level
```

Current validation rejects overlap between `allowed_tools` and `denied_tools`.

### 5.2 Environment compatibility

`ExecutionEnv` has:

```text
capabilities
tool_pool
status
workspace_scope
permission_profile_id
active_execution_id
last_heartbeat_at
runtime_version
```

Current `ExecutionEnv.supports(policy)` checks:

1. env status is `online`;
2. `policy.required_capability` is in `env.capabilities`;
3. if `policy.allowed_tools` is non-empty, every allowed tool is present in
   `env.tool_pool`.

Current compatibility does not evaluate `denied_tools`, risk level, token/runtime
limits, workspace scope, permission profile, or active execution. Those fields
are service contract surface for future enforcement and handler-specific logic.

### 5.3 Local env registry

`InMemoryExecutionEnvRegistry` is current. It supports `upsert`, `get`, `list`,
and `find_compatible`.

The default local env advertises:

```text
capabilities: ("execute", "testing")
tool_pool: ()
```

When computer-use is enabled through runtime settings, local sidecar assembly
adds:

```text
capabilities: ("execute", "testing", "computer_use", "wechat_send")
tool_pool: ("computer_use", "wechat_desktop")
```

This `tool_pool` tuple is a simple compatibility string set. It is not the same
thing as the future `ToolPoolRef` / `ToolDescriptor` design.

---

## 6. Optional External And Desktop Tools

### 6.1 Web retrieval

`web_search` and `web_fetch` are current execution tools.

Current facts:

- both are provider-backed tools;
- current provider path is Tavily;
- both are gated by Settings-backed readiness and secret availability;
- `web_fetch` normalizes and rejects non-public targets such as private,
  localhost, file, data, or credential-bearing URLs;
- tool descriptions and execution guidance state that results are external
  evidence, not instructions;
- observations are emitted through the AgentLoop/EventStream path.

### 6.2 Computer-use

`computer_use` is current as a local, explicitly enabled tool foundation.

Current contracts:

- `ComputerUseAction`;
- `ComputerUseObservation`;
- `ComputerUseBackend`;
- `DisabledComputerUseBackend`;
- `ScriptedComputerUseBackend`;
- `ComputerUseTool`;
- optional `MacOSComputerUseBackend` adapter over the external
  `macos_computer_use` package.

Default behavior is safe:

- without an enabled backend, no OS automation is performed;
- an action with `require_confirmation=True` returns `blocked`;
- backend exceptions are sanitized into failed observations;
- the sidecar rejects `computer_use` Task API requests when the local env does
  not advertise the capability;
- enabled sidecar wiring can execute scripted computer-use through AgentLoop and
  persist `ComputerUseObservation` in the session EventStream.

Current Product 1.1+ WeChat send work builds on the same computer-use and
Execution Plane boundary, but remote ExecutionEnv registration, LAN auth,
remote claim/lease/heartbeat, Windows automation, and generic screenshot
redaction remain future or feature-specific gaps.

---

## 7. Collaborator Boundary

The built-in Collaborator template is metadata-first:

```text
template_id: system.collaborator
capability: task_authoring
capability_catalog: execution.capabilities.readonly
llm_visible_tool_pools: ()
```

This empty `llm_visible_tool_pools` tuple is intentional. Collaborator should
plan with read-only capability descriptors and submit authoring commands; it
should not mount the execution workspace file/shell tool set by default.

Current Collaborator authoring loop tools are bounded:

```text
authoring_read_workspace
authoring_search_workspace
ask_authoring
finish_authoring
```

Forbidden authoring loop tool names include:

```text
write_file
run_command
shell
execute_code
```

Current workspace-informed authoring is read-only. It can read/search selected
or policy-declared workspace guidance and records authoring evidence. It does
not write workspace files and does not bypass `AuthoringCommandService`.

---

## 8. Skill Governance Boundary

Product 1.1 skill governance is now a current backend/context foundation.

Current models include:

- `SkillDescriptor`;
- `SkillToolPolicy`;
- `SkillActivation`;
- `SkillContextSource`;
- `SkillPermissionMergeResult`;
- `SkillPermissionOutcome`.

The important rule is:

```text
skill policy can narrow runtime tools;
skill policy cannot grant tools the runtime did not already allow.
```

`merge_skill_controls()`:

- removes skill-denied tools from allowed tools;
- adds denied tools;
- adds approval requirements;
- intersects or carries file scopes;
- reports outcomes such as `granted_by_runtime`, `denied_by_runtime`,
  `narrowed_by_skill`, and `blocked_untrusted_skill`.

`SkillContextSource` can auto-activate a matching skill based on
`required_capability` when runtime controls allow the required tools. If runtime
controls deny those tools, activation is blocked and the denied requirements are
recorded.

This is context and permission governance. It is not a public skill marketplace,
MCP integration, or dynamic tool provider platform.

---

## 9. Current Non-Facts

These names or ideas may appear in older docs or plans, but they are not current
runtime facts unless explicitly listed above.

| Not current | Current status |
|-------------|----------------|
| `ToolPoolRef` production model | Not implemented. Future design vocabulary. |
| `ToolAccessPolicy` production model | Not implemented. Current policy is split across Context Manager, Execution Plane, skill governance, and sidecar assembly. |
| `ToolDescriptor` production registry | Not implemented. Tool classes expose name/description/action/observation, but there is no descriptor catalog. |
| Global dynamic `CapabilityCatalog` sourced from tools/providers/telemetry | Not implemented. Current catalog is static and authoring-oriented. |
| Generic `WorkspaceRequest` execution gateway | Not implemented. Precision file tools are direct Tool classes. |
| Tool marketplace or user-submitted tools | Not implemented. |
| MCP integration | Not implemented; tracked as future research. |
| Multi-provider tool routing | Not implemented. |
| Automatic tool ranking from telemetry | Not implemented. |
| General IO-scope conflict guard | Not implemented. See `bus-v2.md` for future direction. |
| Remote ExecutionEnv tool worker protocol | Not implemented. See `taskbus-service-multi-execution-env.md`. |

---

## 10. Future Extension Direction

The long-term direction remains useful:

```text
Task / Plan required_capability
  -> capability descriptor
  -> policy and preflight
  -> candidate runtime environments
  -> concrete tools or workspace operation adapters
  -> evidence and diagnostics
```

Future work can introduce:

- descriptor metadata beside concrete Tool classes;
- a typed Tool/Workspace capability registry;
- `WorkspaceRequest` adapters for file/process/domain operations;
- richer tool pool policy with visibility and effect targets;
- capability preflight for risk, evidence, confirmation, and missing inputs;
- dynamic catalog sources from Agent templates, skills, registered execution
  environments, and validated connectors;
- MCP integration under the same confirmation, risk, and audit boundary.

Any such extension must preserve current invariants:

1. internal authoring/system-state changes go through command services;
2. execution workspace changes go through execution tools or future workspace
   request gateways;
3. Collaborator does not receive unrestricted execution tools by default;
4. skill policy never grants tools beyond runtime controls;
5. Execution Plane compatibility checks remain explicit and testable;
6. user-visible evidence distinguishes external source content from
   instructions.

---

## 11. Summary

Current TaskWeavn capability handling is practical and layered:

```text
Capabilities are planning and validation language.
Tools are concrete AgentLoop execution adapters.
Execution Plane policy chooses compatible local environments.
Context Manager renders allowed/denied tools and guidance.
Skills can narrow the runtime envelope.
Collaborator remains command-backed and mostly read-only.
```

The missing platform pieces are real, but they should be added as explicit
slices. The current architecture should not describe future ToolPool,
WorkspaceRequest, marketplace, MCP, or IO-scope concepts as implemented runtime
behavior.
