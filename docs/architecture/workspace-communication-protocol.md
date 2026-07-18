# Workspace Communication Protocol

> Status: implemented workspace inspection / precision-tool facts plus future
> unification protocol
> Last Updated: 2026-07-10
> Scope: workspace inspection routes, workspace path policy, precision file
> tools, read-only workspace evidence, and future WorkspaceRequest direction
> Related Architecture: [Tool Capability Layer](tool-capability-layer.md),
> [Task](task.md), [Agent](agent.md), [Authoring Command Protocol](authoring-command-protocol.md),
> [Contract Revision And Execution Loops](contract-revision-and-execution-loops.md),
> [TaskBus](bus.md)
>
> 2026-07-10 fact calibration: current code has no production
> `WorkspaceManifest`, `WorkspaceCapabilityDescriptor`, `WorkspaceRequest`,
> `WorkspaceResult`, `WorkspaceDelta`, `WorkspaceEndpoint`, or
> `WorkspaceGateway` implementation. The current implemented surface is:
> Product 1.1 workspace inspection status/diff/file/evidence routes, safe
> workspace-relative path policy, precision file read/search/replace/append
> tools, inspection evidence storage, precision mutation idempotency storage,
> read-only inquiry file/diff refs, and Collaborator read-only workspace
> context. Treat the unified protocol objects in this document as future
> design direction.

---

## 1. Purpose

Workspace communication has two layers today:

```text
Current implemented layer
  -> concrete Tool classes
  -> Workspace path resolver
  -> workspace_inspection gateway
  -> precision file service
  -> HTTP inspection routes
  -> EventStream / result / evidence projections

Future unification layer
  -> WorkspaceRequest
  -> WorkspaceGateway / WorkspaceEndpoint
  -> WorkspaceResult / WorkspaceDelta
  -> capability manifest and provider model
```

The current architecture should not pretend the future protocol already exists.
It should document what is implemented and explain how the future protocol can
unify it later.

The main invariant remains:

```text
Authoring Commands change TaskWeavn internal state.
Workspace tools and inspection services read or change user workspace state.
```

Do not route RawTask, Plan, TaskBus lifecycle, Settings, or MessageStream
mutations through the future workspace protocol. Those remain command/service
boundaries.

---

## 2. Current Fact Baseline

### 2.1 Implemented workspace inspection

`DefaultWorkspaceInspectionGateway` is current and read-only.

It exposes:

```text
status(max_files=None)
diff(path, base="head", context_lines=None, max_bytes=None)
file_content(path, start_line=1, line_count=None, evidence_id=None)
capture_evidence(request)
```

The gateway uses:

- `ControlledGitCliInspectionProvider` for bounded git status/diff/file reads;
- `WorkspaceInspectionPathPolicy` for safe path resolution;
- `SqliteInspectionEvidenceStore` for captured inspection evidence.

Supported evidence capture kinds:

```text
git_status_snapshot
diff_snapshot
file_snapshot
```

Supported capture reasons:

```text
task_result
audit_record
diagnostic_export
manual_capture
```

### 2.2 Implemented HTTP routes

Current sidecar routes include active-workspace and workspace-scoped aliases:

```text
GET  /api/v1/inspection/status
GET  /api/v1/inspection/diff
POST /api/v1/inspection/evidence
GET  /api/v1/files/content

GET  /api/v1/workspaces/{workspaceId}/inspection/status
GET  /api/v1/workspaces/{workspaceId}/inspection/diff
POST /api/v1/workspaces/{workspaceId}/inspection/evidence
GET  /api/v1/workspaces/{workspaceId}/files/content
```

These routes return JSON envelopes with `ok`, `data`, and `error`. Input
validation failures return product-error details with recovery actions.

### 2.3 Implemented path policy

`WorkspaceInspectionPathPolicy` accepts only safe workspace-relative POSIX
paths.

It rejects:

- empty paths;
- control characters;
- backslash separators;
- absolute paths;
- `..` traversal;
- protected metadata roots such as `.plato`, `.taskweavn`, and `.code-agent`.

Successful paths are represented as labels:

```text
workspace://{workspaceId}/{relative_path}
```

This keeps API responses and read-only inquiry answers from leaking local
absolute paths.

### 2.4 Implemented git inspection provider

`ControlledGitCliInspectionProvider` is a bounded read-only provider.

It uses fixed git commands for:

- repository status;
- file-level diffs against `head` or `index`;
- file content reads.

Current behavior:

- non-git workspaces return safe `not_git` status;
- dirty/untracked status is summarized;
- local noise such as `.DS_Store` is suppressed;
- local tooling files such as `.idea/...` are categorized;
- untracked text files can return synthetic new-file diffs;
- binary, too-large, missing, unchanged, directory, and unsupported-encoding
  cases return unavailable responses instead of unsafe raw reads;
- payloads are bounded by `WorkspaceInspectionLimits`.

### 2.5 Implemented precision file service

`PrecisionFileService` is current.

It backs these execution tools:

```text
read_file_range
search_workspace
replace_file_range
append_file
```

Current precision read/search facts:

- `read_range` returns bounded line ranges, content hash, range hash, and
  truncation metadata;
- `search` supports literal and filename modes;
- search skips protected metadata, binary files, and large files;
- search applies file and match limits.

Current precision mutation facts:

- `replace_range` and `append` require `operation_id`;
- both require expected SHA-256 content hash;
- stale hash raises `workspace.file_drift`;
- operation ids are persisted in `SqlitePrecisionFileOperationStore`;
- replaying the same completed operation id returns the original response with
  `replayed=True`;
- reusing an operation id with a different request is rejected;
- mutation output includes changed line ranges, before/after hashes, bytes
  written, and an inspection evidence ref;
- writes are atomic through a temporary file replacement.

### 2.6 Implemented workspace root resolver

General filesystem tools use `taskweavn.tools.workspace.Workspace`.

Current facts:

- relative paths resolve under one workspace root;
- absolute paths are allowed only when they still resolve inside that root;
- protected metadata directories are blocked;
- this is a defense-in-depth workspace boundary, not a full sandbox.

### 2.7 Implemented file-change projection

There is no `WorkspaceDelta` protocol object today.

Current file-change projection is assembled from observed events:

- `FileWriteObservation`;
- `PrecisionFileMutationObservation`;
- `CodeExecutionObservation` declared/undeclared file changes.

`EventStreamFileChangeStore` projects those observations into
`TaskFileChangeSummary` records. Recursive parent/child roll-up belongs to the
Task projection layer, not to a workspace protocol delta model.

### 2.8 Implemented read-only inquiry workspace refs

Read-only inquiry can consume safe workspace refs:

- file refs;
- diff refs;
- result refs;
- audit record/evidence refs;
- diagnostic refs.

Current service and deterministic Router tests verify the inquiry path:

- rejects unsafe file paths;
- preserves safe file/diff hrefs with workspace id;
- does not mutate files;
- does not mutate TaskBus state;
- avoids raw absolute path leakage in answers.

The sidecar Runtime Input route also depends on the configured Router planner.
Planner behavior is part of the Runtime Input boundary, not the workspace
protocol itself.

### 2.9 Implemented Collaborator read-only workspace context

`LocalCollaboratorWorkspaceContextSource` is current.

It supports:

```text
authoring_read_workspace
authoring_search_workspace
```

Current facts:

- reads return bounded snippets, content hashes, path labels, and authoring
  evidence refs;
- denied/omitted reads still create evidence records with policy decisions;
- raw absolute request paths are redacted;
- search is scoped to guidance paths by default;
- full-workspace glob search is skipped;
- it is read-only and does not write workspace files.

---

## 3. What Is Not Current

These protocol objects remain future design vocabulary:

| Not current | Current status |
|-------------|----------------|
| `WorkspaceManifest` | Not implemented. No endpoint-wide manifest API exists. |
| `WorkspaceCapabilityDescriptor` | Not implemented. Capability descriptors exist for authoring, not workspace operation manifests. |
| `WorkspaceRequest` | Not implemented. Tools still use typed Actions directly. |
| `WorkspaceResult` | Not implemented. Tools and inspection gateways return tool/route-specific observations and dictionaries. |
| `WorkspaceDelta` | Not implemented. File summaries are projections over observed events. |
| `WorkspaceEndpoint` / `WorkspaceGateway` | Not implemented as a unified runtime boundary. |
| Generic operation namespace enforcement | Not implemented. Current operations are tool names and route names. |
| Third-party workspace providers | Not implemented. |
| Remote workspace daemon / MCP workspace provider | Not implemented. |
| Marketplace or user-supplied operations | Not implemented. |
| Generic preview/dry-run layer | Not implemented. Some routes are read-only and precision mutations are hash-guarded, but no protocol-wide preview mode exists. |

---

## 4. Boundary With Authoring And Runtime Input

Current mutation boundaries are:

| Mutation target | Current boundary |
|-----------------|------------------|
| RawTask, DraftTaskTree, Plan, TaskNode proposals | Authoring commands and contract revision commands |
| Published Task lifecycle | TaskBus and TaskPublisher |
| Runtime input routing / read-only answers | Runtime Input Router and Read-Only Inquiry service |
| Settings and runtime config | Settings/runtime config command services |
| Workspace file edits | Execution tools such as precision file tools and legacy file tools |
| Workspace status/diff/file reads | Workspace inspection gateway |
| Collaborator planning context reads | Collaborator read-only workspace context source |

This split matters because product-state commands and user workspace effects
have different validation, idempotency, audit, and recovery requirements.

---

## 5. Current Operation Surfaces

The current system does not enforce a generic operation namespace, but the
implemented surfaces map cleanly to the future vocabulary:

| Current surface | Current operation | Future protocol analogy |
|-----------------|-------------------|-------------------------|
| `ReadFileTool` | direct file read Action | `file.read` |
| `WriteFileTool` | direct file write Action | `file.write` |
| `ReadFileRangeTool` | precision line read Action | `file.read_range` |
| `SearchWorkspaceTool` | precision literal/filename search Action | `workspace.search` |
| `ReplaceFileRangeTool` | hash-checked line replacement Action | `file.replace_range` |
| `AppendFileTool` | hash-checked append Action | `file.append` |
| `RunCommandTool` | shell command Action | `process.run` |
| inspection status route | read-only git status | `workspace.status` |
| inspection diff route | read-only file diff | `workspace.diff` |
| file content route | bounded file content read | `file.read` |
| inspection evidence route | capture status/diff/file snapshot | `workspace.evidence.capture` |
| Collaborator read/search | read-only authoring context | `workspace.authoring_context.read/search` |

This table is descriptive. It is not an implemented dispatch map.

---

## 6. Policy And Safety Facts

Current policy is distributed across several concrete boundaries:

| Policy area | Current implementation |
|-------------|------------------------|
| Workspace path safety | `Workspace` and `WorkspaceInspectionPathPolicy` |
| Inspection limits | `WorkspaceInspectionLimits` |
| Precision write drift | expected content hashes and `workspace.file_drift` |
| Precision idempotency | `SqlitePrecisionFileOperationStore` |
| Metadata protection | protected roots in workspace layout policy |
| Read-only inquiry no-mutation | inquiry service tests and route behavior |
| Collaborator no-write authoring context | bounded read/search tools and forbidden execution tool names |
| Tool visibility | Default Agent assembly and Context Manager `allowed_tools` |
| Skill narrowing | skill governance can reduce allowed tools, not grant new ones |

Future protocol policy should unify these inputs without weakening the current
concrete checks.

---

## 7. Audit, Evidence, And UI Facts

Current workspace evidence is not centralized in a protocol result object.

Implemented evidence paths include:

- session EventStream observations for tool actions;
- `SqliteInspectionEvidenceStore` records for captured status/diff/file and
  precision mutation snapshots;
- precision mutation evidence refs on tool observations;
- Task result/error summary refs;
- Audit records/evidence refs;
- read-only inquiry evidence refs and Activity related refs;
- diagnostics-safe inspection summaries.

The UI should continue to show stable summaries:

- operation/file summary;
- changed files;
- safe workspace path labels;
- diff/file refs;
- diagnostics;
- confirmation prompts where applicable;
- result and evidence links.

It should not parse arbitrary raw tool observations when a stable projection or
evidence ref exists.

---

## 8. Future Unified Protocol Direction

The original protocol idea remains useful as a future unification layer:

```text
Task / Agent intent
  -> capability
  -> policy/preflight
  -> WorkspaceRequest
  -> WorkspaceGateway / WorkspaceEndpoint
  -> WorkspaceResult
  -> evidence, UI projection, audit, diagnostics
```

Future object shapes may include:

```python
class WorkspaceManifest(BaseModel):
    endpoint_id: str
    workspace_id: str
    protocol_version: str
    capabilities: tuple[WorkspaceCapabilityDescriptor, ...]


class WorkspaceRequest(BaseModel):
    request_id: str
    session_id: str
    task_id: str | None = None
    operation: str
    capability_id: str
    payload: dict[str, object]
    mode: Literal["validate", "preview", "execute"] = "execute"
    idempotency_key: str | None = None


class WorkspaceResult(BaseModel):
    request_id: str
    ok: bool
    operation: str
    capability_id: str
    summary: str
    output: dict[str, object] = {}
    diagnostics: tuple[object, ...] = ()
```

Those are design examples, not current code contracts.

### 8.1 Future operation namespaces

Useful future namespaces:

| Namespace | Examples |
|-----------|----------|
| `file.*` | `file.read`, `file.write`, `file.replace_range`, `file.append`, `file.delete` |
| `workspace.*` | `workspace.status`, `workspace.diff`, `workspace.search`, `workspace.evidence.capture` |
| `process.*` | `process.run`, `process.inspect`, `process.kill` |
| `project.*` | `project.build`, `project.test`, `project.install_dependency` |
| `artifact.*` | `artifact.create`, `artifact.read`, `artifact.publish` |

Avoid operation names that are really user tasks, such as:

```text
fix_user_bug
make_website
improve_code
```

### 8.2 Future migration path

A safe route is:

1. keep current Tools and inspection routes stable;
2. add descriptor metadata beside current Tool classes and inspection gateway
   methods;
3. introduce an internal `WorkspaceGateway` adapter over current precision file
   tools and inspection gateway without changing AgentLoop behavior;
4. normalize a small subset of observations into a `WorkspaceResult`-like
   projection;
5. route new features through the gateway only after tests prove parity with
   current tools;
6. add remote or organization providers only after local policy, evidence, and
   idempotency are stable.

No current implementation needs to be removed to get there.

---

## 9. Non-Goals For Current Phase

Do not treat this document as authorization to:

- replace current Tools;
- rewrite AgentLoop execution semantics;
- bypass existing workspace path policy;
- route authoring/system-state commands through workspace operations;
- introduce third-party providers;
- expose user-supplied workspace operations;
- build a remote workspace daemon;
- add MCP workspace providers;
- add marketplace/discovery.

Those require separate product/API/security decisions and tests.

---

## 10. Summary

Current TaskWeavn workspace communication is concrete, not protocol-generic:

```text
Tools execute typed Actions.
Workspace path policies protect local roots and metadata.
Inspection routes expose bounded status/diff/file/evidence reads.
Precision file tools provide hash-checked, idempotent line/file mutations.
Read-only inquiry and Collaborator consume safe workspace refs without writes.
File summaries are projected from observed events, not WorkspaceDelta objects.
```

The future Workspace Communication Protocol should unify these pieces only after
it preserves the current safety properties: safe paths, bounded reads,
idempotent mutations, evidence refs, no raw absolute path leakage, no authoring
state mutation through workspace channels, and testable UI projections.
