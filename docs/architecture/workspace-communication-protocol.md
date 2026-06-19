# Workspace Communication Protocol

> Status: architecture planning / not implemented in current package
> Last Updated: 2026-05-14
> Related Architecture: [Tool Capability Layer](tool-capability-layer.md), [Task](task.md), [Agent](agent.md), [Interaction Layer](interaction-layer.md), [Authoring Command Protocol](authoring-command-protocol.md)

---

## 1. Purpose

Current TaskWeavn uses `Tool` as the executable boundary between the Agent and the user workspace.

That works for early implementation, but it makes `Tool` too hard as the long-term abstraction:

- every new workspace ability must be implemented as a first-class Tool by TaskWeavn core;
- tool selection and permission become fragmented across Tool classes;
- third-party or user-supplied abilities are hard to introduce safely;
- the system has no stable protocol-level way to ask "what can this workspace do?";
- the ability boundary is scattered across concrete code instead of one communication contract.

The higher-level abstraction should be a **Workspace Communication Protocol**:

```text
TaskWeavn System
  -> WorkspaceRequest
  -> WorkspaceEndpoint / WorkspaceGateway
  -> WorkspaceResult
  -> Task/Event/Message/Log facts
```

In this model, `Tool` becomes one possible adapter over the protocol, not the protocol itself.

This document is a planning document. It is not part of the current Collaborator/Authoring implementation package.

---

## 2. Core Claim

Most tool calls are a special case of:

```text
System requests a workspace operation.
Workspace validates and performs the operation.
Workspace returns result, diagnostics, and state delta.
```

Examples:

| Current Tool Shape | Protocol Shape |
|---|---|
| `ReadFileTool` | `WorkspaceRequest(operation="file.read")` |
| `WriteFileTool` | `WorkspaceRequest(operation="file.write")` |
| `RunCommandTool` | `WorkspaceRequest(operation="process.run")` |
| `CodeActionTool` | `WorkspaceRequest(operation="code.apply_patch" / "sandbox.run")` |
| future image/project analyzer | `WorkspaceRequest(operation="domain.inspect", capability=...)` |

The protocol defines what the system is allowed to ask the workspace to do. Concrete tools/adapters only implement that protocol.

---

## 3. Boundary With Authoring Commands

TaskWeavn now has two different mutation worlds:

```text
TaskWeavn internal state -> Authoring Commands / TaskBus / Config commands
User workspace state     -> Workspace Communication Protocol
```

Do not blur these:

| Mutation Target | Boundary |
|---|---|
| `RawTask`, `DraftTaskTree`, feasibility, asks, messages | Authoring Command Protocol |
| published Task lifecycle | TaskBus / TaskPublisher |
| configuration/logging control plane | Config/control commands |
| files, repo, project process, generated artifacts | Workspace Communication Protocol |

This split matters because authoring is exploratory system-state mutation, while workspace operations can change user-owned project state. They need different permission, audit, rollback, and extension models.

---

## 4. Conceptual Model

```text
Task Node
  required_capability
        |
        v
Execution Agent
        |
        v
WorkspaceCapabilityCatalog
        |
        v
WorkspaceRequest
        |
        v
WorkspaceGateway
        |
        +--> Built-in Tool Adapter
        +--> Local Workspace Host
        +--> Sandbox Runner
        +--> Organization Provider
        +--> User/Third-party Provider
        |
        v
WorkspaceResult
        |
        v
Observation / EventStream / MessageStream / Logs
```

The Agent does not need to know whether a capability is implemented by an in-process Python Tool, a sandbox runner, a local daemon, an MCP server, or a future extension provider.

It only sees a capability and receives a structured result.

---

## 5. Protocol Objects

### 5.1 WorkspaceManifest

The workspace endpoint should be able to describe its abilities.

```python
class WorkspaceManifest(BaseModel):
    endpoint_id: str
    workspace_id: str
    protocol_version: str
    capabilities: tuple[WorkspaceCapabilityDescriptor, ...]
    limits: WorkspaceLimits
    policy: WorkspacePolicySummary
```

`WorkspaceManifest` is the protocol-level answer to:

```text
What can this workspace do?
Which operations are available?
What are the risks, limits, and preconditions?
```

### 5.2 WorkspaceCapabilityDescriptor

```python
class WorkspaceCapabilityDescriptor(BaseModel):
    capability_id: str
    operation_kinds: tuple[str, ...]
    display_name: str
    summary: str
    input_schema: dict[str, object]
    result_schema: dict[str, object]
    effect_profile: WorkspaceEffectProfile
    preconditions: tuple[str, ...] = ()
    risk_level: Literal["read", "low", "medium", "high"] = "low"
    requires_confirmation: bool = False
    supports_preview: bool = False
    supports_dry_run: bool = False
    supports_idempotency: bool = False
```

This is more general than `ToolDescriptor`. A descriptor can be implemented by one or many concrete adapters.

### 5.3 WorkspaceRequest

```python
class WorkspaceRequest(BaseModel):
    request_id: str
    session_id: str
    task_id: str | None = None
    actor: ActorRef
    operation: str
    capability_id: str
    target: WorkspaceTarget | None = None
    payload: dict[str, object]
    mode: Literal["validate", "preview", "execute"] = "execute"
    expected_state: WorkspaceExpectedState | None = None
    idempotency_key: str | None = None
    timeout_seconds: float | None = None
    policy_overrides: dict[str, object] = {}
```

Important fields:

| Field | Reason |
|---|---|
| `operation` | Stable protocol verb, e.g. `file.write`, `process.run`, `code.patch`. |
| `capability_id` | Semantic ability requested by the Task/Agent. |
| `target` | File path, directory, project, process, or artifact target. |
| `mode` | Allows validation/preview before execution. |
| `expected_state` | Prevents stale writes and supports conflict detection. |
| `idempotency_key` | Prevents duplicate effects during retries. |

### 5.4 WorkspaceResult

```python
class WorkspaceResult(BaseModel):
    request_id: str
    ok: bool
    operation: str
    capability_id: str
    summary: str
    output: dict[str, object] = {}
    delta: WorkspaceDelta | None = None
    artifacts: tuple[WorkspaceArtifactRef, ...] = ()
    diagnostics: tuple[WorkspaceDiagnostic, ...] = ()
    retryable: bool = False
    error_code: str | None = None
```

The result must be useful to:

- create an Observation for the Agent loop;
- update Task result/state;
- write audit events;
- render UI summaries;
- debug failures from logs.

### 5.5 WorkspaceDelta

```python
class WorkspaceDelta(BaseModel):
    files_created: tuple[str, ...] = ()
    files_modified: tuple[str, ...] = ()
    files_deleted: tuple[str, ...] = ()
    commands_run: tuple[str, ...] = ()
    artifacts_created: tuple[WorkspaceArtifactRef, ...] = ()
    summary: str
```

This is the protocol-level source for File Change Summary.

Important rule:

```text
Parent Task file summaries aggregate child Task deltas.
Child Task deltas still belong directly to the child.
```

### 5.6 WorkspaceEndpoint

```python
class WorkspaceEndpoint(Protocol):
    def manifest(self) -> WorkspaceManifest: ...

    def validate(self, request: WorkspaceRequest) -> WorkspaceValidation: ...

    def preview(self, request: WorkspaceRequest) -> WorkspacePreview: ...

    def execute(self, request: WorkspaceRequest) -> WorkspaceResult: ...
```

The first real implementation can be a local in-process gateway over current Tools. Future implementations can be remote, user-provided, or organization-provided.

---

## 6. Operation Namespaces

Operation names should be stable strings.

Suggested first namespaces:

| Namespace | Examples | Effect |
|---|---|---|
| `file.*` | `file.read`, `file.write`, `file.patch`, `file.delete`, `file.list` | File system state. |
| `process.*` | `process.run`, `process.kill`, `process.inspect` | Project/runtime process state. |
| `project.*` | `project.build`, `project.test`, `project.install_dependency` | Project-level operations. |
| `code.*` | `code.apply_patch`, `code.format`, `code.analyze` | Code-aware operations. |
| `artifact.*` | `artifact.create`, `artifact.read`, `artifact.publish` | Generated artifacts. |
| `workspace.*` | `workspace.snapshot`, `workspace.diff`, `workspace.search` | Workspace-level inspection. |

Avoid one-off operation names such as:

```text
fix_user_bug
make_website
improve_code
```

Those are Tasks, not workspace protocol operations.

---

## 7. Capability Binding

The protocol should support a two-stage binding:

```text
Task.required_capability
  -> WorkspaceCapabilityDescriptor
  -> WorkspaceRequest(operation=...)
  -> concrete adapter
```

This keeps Task Nodes stable even when implementation changes.

Example:

```text
required_capability = "code_editing"
  -> descriptor supports:
       code.apply_patch
       code.format
       project.test
  -> gateway chooses built-in file/shell tools today
  -> gateway may choose organization code-edit provider later
```

The Collaborator should reason over capabilities. Execution Agents or service code can translate capabilities into operation requests.

---

## 8. Relationship To Current Tool Layer

Current `Tool` should be reinterpreted as:

```text
Tool = in-process adapter for one or more Workspace operations.
```

Possible migration:

| Current | Future Role |
|---|---|
| `Tool` class | Adapter implementation detail. |
| `Action` | Serialized request or adapter-specific request body. |
| `Observation` | Adapter-specific result, normalized into `WorkspaceResult`. |
| `Runtime` | Execution host behind `WorkspaceGateway`. |
| `Workspace` path resolver | Local workspace policy component. |

No current implementation needs to be removed immediately. The protocol is a design target, not a rewrite mandate.

---

## 9. Policy And Safety

Workspace operations must pass policy checks before execution.

Policy dimensions:

| Dimension | Examples |
|---|---|
| Actor | user, execution Agent, system service. |
| Task state | draft, pending, running, completed. |
| Operation risk | read, write, delete, run process, network. |
| Target scope | session project root, shared directory, external path. |
| Confirmation | required, optional, already granted. |
| Sandbox | local, docker, remote runner. |
| Idempotency | required for retryable operations. |

The protocol should make policy inputs explicit instead of hiding them in Tool code.

---

## 10. Audit And Observability

Every executed request should be traceable:

```text
WorkspaceRequest
  -> validation/preflight result
  -> WorkspaceResult
  -> WorkspaceDelta
  -> EventStream / logs / Task summary
```

Minimum audit fields:

- `request_id`;
- `session_id`;
- `task_id`;
- `actor`;
- `operation`;
- `capability_id`;
- target summary;
- policy decision;
- result status;
- delta summary;
- error/diagnostic codes.

Raw command output may be large or sensitive. Store compact structured summaries in default views, with full logs behind debug/archive access.

---

## 11. Extension Strategy

The reason to define this protocol is not to implement every ability ourselves.

Future supply layers:

| Supply Layer | Example | Governance |
|---|---|---|
| Built-in | local file/shell/code adapters | core tests, strict policy. |
| Organization | team-specific build/deploy/test provider | org admin approval, secrets boundary, audit. |
| User | custom workspace operation provider | sandbox, schema validation, disabled by default. |
| Remote | remote runner or MCP-like endpoint | protocol handshake, capability manifest, policy gate. |

The protocol allows TaskWeavn to ask:

```text
Can this workspace endpoint satisfy capability X?
Can it preview the change?
What will it modify?
Can we trust and audit the result?
```

without hard-coding every operation as a first-party Tool.

---

## 12. Relationship To UI

The UI should not show raw protocol payloads by default.

It can show:

- operation summary;
- changed files;
- diagnostics;
- preview/diff;
- confirmation prompts;
- artifact links;
- task result summary.

The protocol makes these UI facts available without making the UI parse arbitrary tool observations.

---

## 13. Non-goals For Current Phase

Do not implement this protocol in the current authoring package.

Also do not do these yet:

- replace current Tools;
- introduce third-party providers;
- expose user-supplied workspace operations;
- build a remote workspace daemon;
- implement full marketplace/discovery;
- change AgentLoop execution semantics.

The goal is to reserve the architecture boundary now, so future Tool growth does not force a rewrite.

---

## 14. Migration Path

Recommended future phases:

| Phase | Goal |
|---|---|
| W0 | Architecture only. Define protocol and keep current Tools. |
| W1 | Add `WorkspaceCapabilityDescriptor` metadata beside current Tool descriptors. |
| W2 | Add `WorkspaceGateway` that wraps current Runtime/Tools. |
| W3 | Normalize key Tool observations into `WorkspaceResult` and `WorkspaceDelta`. |
| W4 | Let TaskPublisher/Execution Agent bind `required_capability` to workspace operations. |
| W5 | Add remote/user/org provider support behind the same gateway. |

The first practical implementation should probably be W1 or W2, not a full protocol rewrite.

---

## 15. Open Questions

1. Should `WorkspaceRequest` replace `Action`, or should `Action` remain the LLM-facing envelope and be translated into requests? Current leaning: keep `Action` for compatibility, translate inside gateway.
2. Should shell/process operations be first-class protocol operations or hidden behind project operations? Current leaning: both, with shell gated more strictly.
3. Should external data retrieval be part of workspace protocol or a separate external communication protocol? Current leaning: separate later, but allow adapters that create workspace artifacts from external data.
4. Should user-provided providers run in-process? Current leaning: no, require sandbox/remote boundary.
5. Should workspace endpoint return full file diffs or only references to diff artifacts? Current leaning: references plus compact summaries by default.

---

## 16. Summary

The stable mental model:

```text
Authoring Commands change TaskWeavn state.
Workspace Requests change user workspace state.
Tools are adapters, not the top-level abstraction.
Capabilities are the planning language.
Workspace Protocol is the execution communication boundary.
```

This gives TaskWeavn room to grow beyond first-party Tools while preserving policy, audit, UI projection, Session conversation, and task execution semantics.
