# Tool Capability Layer Fact Calibration Fix Log

> Target document: `docs/architecture/tool-capability-layer.md`
> Original preserved as: `docs/architecture/tool-capability-layer.original.md`
> Calibration date: 2026-07-10

## Workflow Gate

- User request: continue architecture fact calibration one document at a time.
- Detected phase: P5 architecture maintenance, verified against P8/P9 code and
  tests.
- Task type: docs-only architecture fact correction.
- Required upstream artifacts: current tool implementation, Execution Plane
  policy/env facts, Collaborator authoring facts, skill governance facts,
  computer-use/web retrieval tests, related architecture docs.
- Found artifacts: `Tool` base class, Default Agent assembly, Context Manager
  controls, authoring `CapabilityCatalog`, Execution Plane models/service/env
  registry, computer-use runtime/adapter, web search/fetch tools, skill
  governance models/policy/source, and targeted tests.
- Missing or weak artifacts: previous document mixed implemented facts with
  future models such as `ToolPoolRef`, `ToolDescriptor`, `ToolAccessPolicy`,
  `WorkspaceRequest`, and dynamic tool supply.
- Implementation allowed now: yes, docs-only.
- Prework required: verify which capability/tool constructs exist in code before
  rewriting.
- Scope: preserve original, revise `tool-capability-layer.md`, add this fix-log.
- Acceptance criteria: current implemented boundaries are separated from future
  extension vocabulary; no unimplemented tool platform concept is described as
  current.
- Risks and assumptions: plan and gap docs may intentionally mention future tool
  platform concepts; current runtime code remains authoritative for current
  facts.

## Maintainability Gate

- Requested change: architecture hygiene for `tool-capability-layer.md`.
- Trigger: architecture fact calibration.
- Size signal: original document was 353 lines, below the 800-line threshold.
- Risk level: low for docs-only slice.
- Refactor required first: no.
- Allowed change type: docs-only boundary correction.
- Validation commands: `git diff --check` plus targeted tool/capability,
  computer-use, web retrieval, authoring, skill, and Execution Plane tests.

## Evidence Inspected

### Code

- `src/taskweavn/tools/base.py`
- `src/taskweavn/tools/fs.py`
- `src/taskweavn/tools/precision_fs.py`
- `src/taskweavn/tools/workspace.py`
- `src/taskweavn/tools/web_search.py`
- `src/taskweavn/tools/web_fetch.py`
- `src/taskweavn/tools/computer_use.py`
- `src/taskweavn/tools/computer_use_macos_adapter.py`
- `src/taskweavn/types/computer_use.py`
- `src/taskweavn/server/main_page_agent.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/computer_use_runtime.py`
- `src/taskweavn/context/models.py`
- `src/taskweavn/task/authoring.py`
- `src/taskweavn/task/publisher_input.py`
- `src/taskweavn/task/collaborator.py`
- `src/taskweavn/task/collaborator_loop.py`
- `src/taskweavn/task/collaborator_workspace_context.py`
- `src/taskweavn/execution_plane/models.py`
- `src/taskweavn/execution_plane/env_registry.py`
- `src/taskweavn/execution_plane/embedded_service.py`
- `src/taskweavn/skills/models.py`
- `src/taskweavn/skills/policy.py`
- `src/taskweavn/skills/context_source.py`

### Tests

- `tests/test_execution_plane_models.py`
- `tests/test_execution_plane_service.py`
- `tests/test_execution_plane_http_transport.py`
- `tests/test_web_search.py`
- `tests/test_web_fetch.py`
- `tests/test_computer_use_tool.py`
- `tests/test_computer_use_macos_adapter.py`
- `tests/test_main_page_sidecar_app.py`
- `tests/test_main_page_sidecar_config.py`
- `tests/test_task_authoring.py`
- `tests/test_authoring_context_builder.py`
- `tests/test_task_publisher_input.py`
- `tests/test_task_api_publisher.py`
- `tests/test_collaborator_authoring_loop_contract.py`
- `tests/test_collaborator_workspace_context.py`
- `tests/test_collaborator_sidecar_acceptance.py`
- `tests/test_skill_governance.py`

### Related Docs

- `docs/architecture/README.md`
- `docs/architecture/agent.md`
- `docs/architecture/task.md`
- `docs/architecture/bus.md`
- `docs/architecture/bus-v2.md`
- `docs/architecture/taskbus-service-multi-execution-env.md`
- `docs/architecture/workspace-communication-protocol.md`
- `docs/decisions/ADR-0016-collaborator-workspace-aware-authoring.md`
- `docs/decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md`
- `docs/releases/local-computer-use-tool-foundation.md`
- `docs/gaps/README.md`

## Verified Facts

1. Current production code has no `ToolPoolRef`, `ToolAccessPolicy`,
   `ToolDescriptor`, global dynamic tool registry, tool marketplace,
   `WorkspaceRequest` runtime gateway, MCP integration, or multi-provider tool
   router.

2. Current executable tools subclass `Tool` and register action executors with
   `LocalRuntime`; AgentLoop sees concrete tool schemas from mounted tool
   instances.

3. The Default Agent's base execution tools are `read_file`, `read_file_range`,
   `search_workspace`, `replace_file_range`, `append_file`, `write_file`,
   `list_dir`, and `run_command`.

4. `web_search` and `web_fetch` are current provider-backed tools, but they are
   mounted only when Settings-backed readiness and Tavily configuration/secrets
   allow it.

5. `computer_use` is current as an explicitly enabled local foundation with
   typed action/observation contracts, disabled/scripted backends, optional
   macOS adapter, sidecar enablement, Task API gating, and EventStream
   observation persistence.

6. Current `Workspace` path resolution keeps filesystem tools inside the
   workspace root and blocks protected metadata paths such as `.plato`.

7. Current precision file tools implement bounded read/search and hash-checked
   range/append mutations with mutation observations and inspection evidence.

8. `CapabilityDescriptor`, `CapabilityCatalog`, and `StaticCapabilityCatalog`
   are implemented for authoring and publish validation. The default sidecar
   catalog contains `general`, `writing`, `coding`, `testing`, and `research`.

9. `StaticAgentCapabilityCatalog` and `TaskTreeInputValidator` validate explicit
   agent/capability compatibility when supplied. This is publish-time
   validation, not runtime dynamic Agent assignment.

10. `CapabilityPolicy` exists in the Execution Plane service contract with
    `required_capability`, `allowed_tools`, `denied_tools`,
    `requires_human_confirmation`, runtime/token limits, workspace scope, and
    risk level.

11. `ExecutionEnv.supports(policy)` currently checks online status, required
    capability membership, and `allowed_tools` subset of `env.tool_pool`.
    It does not currently enforce denied tools, risk, runtime/token limits,
    workspace scope, permission profile, or active execution.

12. The current execution env registry is in-memory/local. When computer-use is
    enabled, local env assembly advertises `computer_use` and `wechat_send`
    capabilities and `computer_use` / `wechat_desktop` tool strings.

13. The built-in Collaborator template has empty `llm_visible_tool_pools`; it
    plans through read-only capability descriptors and command services rather
    than mounting execution tools by default.

14. The current Collaborator authoring loop allows
    `authoring_read_workspace`, `authoring_search_workspace`, `ask_authoring`,
    and `finish_authoring`, and explicitly treats write/shell/execute-code
    tools as forbidden.

15. Current Product 1.1 skill governance can narrow runtime tools, add denied
    tools, require approval, and constrain file scopes. It cannot grant tools
    that runtime controls did not already allow.

## Corrections Applied

1. Reframed the document as current fact baseline plus extension boundary.

2. Replaced future-first ToolPool/ToolDescriptor prose with current code facts
   for `Tool`, LocalRuntime registration, Default Agent assembly, Context
   Manager controls, Execution Plane policy, and skill governance.

3. Clarified that `ToolPoolRef`, `ToolAccessPolicy`, `ToolDescriptor`,
   `WorkspaceRequest`, marketplace, MCP, tool telemetry ranking, and generic
   IO-scope conflict guards are not current runtime features.

4. Added current facts for `StaticCapabilityCatalog`,
   `StaticAgentCapabilityCatalog`, and default sidecar capabilities.

5. Added current facts for optional web retrieval gating and computer-use
   enablement/gating.

6. Added current facts for precision file tools and workspace metadata
   protection.

7. Added current facts for Collaborator's bounded authoring tools and read-only
   workspace-informed authoring.

8. Added current facts for skill governance and its "never grant tools"
   invariant.

## Follow-up Candidates

- `docs/architecture/workspace-communication-protocol.md`: likely needs
  calibration because `WorkspaceRequest` remains future while workspace
  inspection and precision tools are implemented slices.
- `docs/architecture/collaborator-agent-task-authoring.md`: likely needs
  calibration around current `StaticCapabilityCatalog`, read-only authoring
  workspace context, and command-backed loops.
- `docs/architecture/README.md`: references this document as current; may need
  a date/status update after more individual docs are calibrated.

## Validation

- `git diff --check` passed.
- `uv run pytest tests/test_execution_plane_models.py tests/test_execution_plane_service.py tests/test_execution_plane_http_transport.py tests/test_web_search.py tests/test_web_fetch.py tests/test_computer_use_tool.py tests/test_computer_use_macos_adapter.py tests/test_main_page_sidecar_app.py::test_main_page_sidecar_task_api_rejects_computer_use_when_disabled tests/test_main_page_sidecar_app.py::test_main_page_sidecar_task_api_runs_scripted_computer_use_when_enabled tests/test_main_page_sidecar_config.py tests/test_task_authoring.py tests/test_authoring_context_builder.py tests/test_task_publisher_input.py tests/test_task_api_publisher.py tests/test_collaborator_authoring_loop_contract.py tests/test_collaborator_workspace_context.py tests/test_collaborator_sidecar_acceptance.py tests/test_skill_governance.py` passed: 155 tests.
