# Tool Capability Layer

> Status: design baseline / extension point
> Last Updated: 2026-05-14
> Related Discussion: [Product positioning 10.7-10.8](../discussion/2026-05-11-product-positioning-and-boundaries.md#107-新暴露的系统级问题工具供给与选择负载比工具可扩展更关键)
> Related Architecture: [Authoring Domain](authoring-domain.md), [Authoring Command Protocol](authoring-command-protocol.md), [Workspace Communication Protocol](workspace-communication-protocol.md), [Collaborator Agent](collaborator-agent-task-authoring.md), [Task](task.md), [TaskBus](bus.md)
> User Needs: [UN-105](../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md), [UN-101](../user_model/needs/UN-101-photo-curation-batch-screening.md), [UN-102](../user_model/needs/UN-102-courseware-html-generation.md), [UN-103](../user_model/needs/UN-103-car-purchase-decision-support.md)

---

## 1. Purpose

TaskWeavn can support more user scenarios by adding tools, but a growing tool pool creates two risks:

1. **Tool supply bottleneck**: core developers cannot hard-code every domain tool forever.
2. **Tool selection load**: Collaborator or planner quality drops if an LLM sees the full tool universe.

The first version does not need a full tool marketplace or dynamic provider platform. It does need a stable design seam so future tool supply and routing do not require rewriting Authoring Domain, Collaborator, TaskBus, or Agent templates.

This document defines that seam:

```text
Workspace Operation -> Tool Adapter -> Capability -> Task Node
```

The planning layer should reason over **Capabilities**, not raw executable Tools.

Long term, `Tool` should be understood as an adapter over [Workspace Communication Protocol](workspace-communication-protocol.md), not the top-level system/workspace boundary.

---

## 2. Definitions

### 2.1 Tool

A Tool is an executable adapter for changing the user workspace or calling external execution capabilities.

Examples:

- read/write/list files;
- run shell command;
- analyze image;
- fetch web data;

System-state authoring actions such as `create RawTask`, `update DraftTaskNode`, and `publish DraftTaskTree` should be modeled as [Authoring Commands](authoring-command-protocol.md), not ordinary tools.

In the long-term architecture, workspace-changing Tools implement one or more `WorkspaceRequest` operation kinds. System-state mutations should not go through this path.

Tools may mutate different worlds:

| Effect Target | Meaning | Example |
|---|---|---|
| `user_workspace` | Changes user files or project state. | write file, run command. |
| `system_state` | Changes TaskWeavn internal state. | authoring command handler, config update. |
| `message_stream` | Emits or resolves user-visible messages. | ask clarification, append authoring message. |
| `external_world` | Calls external APIs or data sources. | web retrieval, image service. |
| `read_only` | Reads state without mutation. | capability discovery, task projection query. |

### 2.2 Capability

A Capability is the semantic planning unit.

Collaborator should choose capabilities such as:

- `image_quality_assessment`;
- `courseware_html_generation`;
- `web_retrieval`;
- `code_editing`;
- `task_authoring`;
- `task_validation`.

It should not choose concrete tool implementations directly unless it is inside a narrow service-owned command.

### 2.3 Task Node

A Task Node describes user-visible work.

Task Nodes should refer to `required_capability`, not `tool_id`.

Execution-time binding maps:

```text
TaskNode.required_capability
  -> CapabilityDescriptor
  -> candidate Tools
  -> policy/risk/preflight
  -> selected Tool / Agent Template
```

---

## 3. Tool Pools

Tools and command adapters should be grouped into pools with different access policies.

| Pool | Effect Target | Default Visibility | Example Consumers |
|---|---|---|---|
| `workspace.basic` | `user_workspace` | LLM-visible for execution Agents | file/shell/code Agents |
| `authoring.system` | `system_state`, `message_stream` | command-service only by default | AuthoringCommandService |
| `publishing.system` | `system_state` | command-service only by default | TaskPublisher |
| `observability.system` | `read_only` | admin or service-only | debug UI, support tools |
| `admin.control` | `system_state` | admin-only | config hot update, maintenance |
| `external.connectors` | `external_world` | policy-gated | retrieval/data Agents |

Important rule:

```text
Ordinary execution Agents must not mount `authoring.system` or `publishing.system`.
```

Otherwise they can bypass Authoring Domain, mutate DraftTask state, or publish Tasks without the intended validation path.

Important nuance:

```text
`authoring.system` and `publishing.system` are not LLM-visible tool pools by default.
They are policy labels for command/service handlers.
```

If a compatibility layer exposes one of these handlers as a tool, the tool must be a thin adapter over the command service.

---

## 4. Access Policy

Agent Templates should not own arbitrary raw tool lists. They should request tool pools and capabilities through a policy boundary.

```python
class ToolPoolRef(BaseModel):
    pool_id: str
    visibility: Literal["llm_visible", "service_only", "admin_only"]
```

```python
class ToolAccessPolicy(BaseModel):
    allowed_actor_kinds: tuple[str, ...]
    allowed_template_ids: tuple[str, ...] = ()
    allowed_pool_ids: tuple[str, ...]
    denied_pool_ids: tuple[str, ...] = ()
```

```python
class ToolDescriptor(BaseModel):
    tool_id: str
    pool_id: str
    effect_target: Literal[
        "user_workspace",
        "system_state",
        "message_stream",
        "external_world",
        "read_only",
    ]
    visibility: Literal["llm_visible", "service_only", "admin_only"]
    capability_ids: tuple[str, ...]
    audit_required: bool = True
    requires_validation: bool = False
```

This can start as static metadata. The important design choice is that access policy exists as a boundary before the system grows.

For system-state mutation, prefer `AuthoringCommandService` validation over descriptor-level tool validation. Tool metadata is not enough to protect TaskWeavn's internal state.

---

## 5. Capability Descriptor

A CapabilityDescriptor should be machine-readable enough for planning and preflight.

```python
class CapabilityDescriptor(BaseModel):
    capability_id: str
    display_name: str
    summary: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    preconditions: tuple[str, ...] = ()
    cost_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    latency_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    risk_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    reliability_score: float | None = None
    applicable_domains: tuple[str, ...] = ()
    anti_patterns: tuple[str, ...] = ()
```

The first implementation can be a static catalog. Later versions can derive descriptors from registered Agent Templates, tool specs, validation results, and runtime telemetry.

---

## 6. Collaborator Design Implication

Collaborator needs to understand what the system can do, but it should not mount all workspace-changing tools.

Recommended split:

```text
Collaborator Agent / CollaboratorAuthoringService
  owns: RawTask, feasibility, clarification, DraftTaskTree, validation, publish request
  sees: read-only CapabilityCatalog
  submits: AuthoringCommandBatch through service-only command surface
  does not mount: workspace.basic, external.connectors by default
```

This lets Collaborator generate good Task Trees without giving it the ability to mutate user files or call every external connector.

The Collaborator can ask:

```text
Which capabilities can satisfy this RawTask?
What preconditions are missing?
Which capability is risky or unreliable?
Should this become a clarification question?
```

It should not directly ask:

```text
Which exact file/shell/image/web tool should I call right now?
```

Execution Agents bind capabilities to workspace operations later.

Collaborator's LLM should output proposals, not perform state mutation through a sequence of tool calls. The command service is responsible for validation, persistence, messages, and traceability.

For execution Agents, the later binding target should be a `WorkspaceRequest`, with current Tool classes acting as adapters while the protocol matures.

### 2026-06-08 Addendum: Workspace-Informed Authoring

[ADR-0016](../decisions/ADR-0016-collaborator-workspace-aware-authoring.md)
amends the default boundary above.

Collaborator still must not mount unrestricted execution tools by default, but
it may use a bounded read-only authoring loop and workspace context channel for:

- reading selected or policy-declared workspace guidance before planning;
- querying and searching selected or policy-declared guidance paths.

These operations are authoring context operations, not general project mutation.
Collaborator does not write workspace files in the first version. If a project
workflow requires writing planning documents, code, config, or generated
artifacts, that remains Execution Agent work unless a later decision explicitly
expands Collaborator scope.

---

## 7. Should Collaborator Be Split?

The user-facing role should stay as one Collaborator in the first version.

Internally, it should be decomposed into replaceable services:

| Internal Component | Responsibility | Split Into Separate Agent Now? |
|---|---|---:|
| `RawTaskService` | Create and update RawTask. | No |
| `FeasibilityAssessor` | Evaluate feasibility and missing inputs. | No |
| `CapabilityCatalog` | Read-only capability discovery. | No |
| `TaskTopologyPlanner` | Generate DraftTaskTree proposals. | No |
| `TopologyQualityGate` | Validate capability coverage and topology quality. | No |
| `TaskPublisher` | Convert confirmed draft into PublishedTasks. | No |

Do not split into multiple user-facing Agents yet. Splitting now would make RawTask state, clarification ownership, and UI explanation harder to keep coherent.

The architecture should still allow future hidden specialist Agents:

- capability planner;
- topology reviewer;
- domain-specific planner;
- feasibility assessor.

Those can be introduced behind the same service protocols if data shows the single Collaborator role is overloaded.

---

## 8. Capability-First Planning Flow

Recommended planning flow:

```text
RawTask
  -> CapabilityCatalog.query(intent, constraints, limit=N)
  -> Collaborator drafts Task Nodes with required_capability
  -> TopologyQualityGate checks capability coverage and preconditions
  -> User reviews/edits DraftTaskTree
  -> TaskPublisher publishes PublishedTasks
  -> Execution Agent resolves capability to concrete tool/agent
```

This flow leaves room for future tool supply without changing Task Node semantics.

---

## 9. Preflight And Topology Quality

Before publish or execution, topology checks should eventually verify:

- every node maps to at least one capability;
- capability preconditions are satisfied by RawTask, upstream nodes, or user answers;
- high-risk capabilities have confirmation strategy;
- obvious tool/capability anti-patterns are avoided;
- node count and depth remain within complexity budgets.

First version can report warnings instead of blocking. The seam should exist in the service/API shape.

---

## 10. Future Tool Supply

The architecture should reserve three supply layers:

| Layer | Who Provides | Governance |
|---|---|---|
| Official | TaskWeavn core | strict tests, high trust, maintained docs |
| Organization | team/workspace admins | scoped permissions, org secrets, audit |
| User | individual users | sandbox, quota, validation harness |

This is not required for the first Collaborator implementation. The required first step is only:

- explicit ToolDescriptor metadata;
- future-compatible WorkspaceCapabilityDescriptor / WorkspaceRequest concepts;
- static CapabilityCatalog;
- ToolPool / command-service boundaries;
- access policy hooks.

---

## 11. Non-goals For First Implementation

- No marketplace.
- No user-submitted script tools.
- No automatic tool ranking from telemetry.
- No multi-provider tool routing.
- No full topology scoring model.
- No separate AuthoringBus just for tool discovery.

The goal is to avoid future rewrite, not to build the platform too early.

---

## 12. Summary

The long-term shape is:

```text
Tools are implementations.
Capabilities are planning language.
Task Nodes are user-facing work.
Commands change TaskWeavn state.
Workspace Requests change user workspace state.
Tool Pools and AccessPolicy protect workspace/external execution boundaries while the protocol matures.
```

This keeps Collaborator useful without turning it into an overloaded agent with every possible tool mounted.
