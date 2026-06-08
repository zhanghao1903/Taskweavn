# ADR-0016: Collaborator Workspace-Informed Authoring

> Status: accepted
> Date: 2026-06-08
> Related: [Authoring Domain](../architecture/authoring-domain.md), [Collaborator Agent](../architecture/collaborator-agent-task-authoring.md), [Tool Capability Layer](../architecture/tool-capability-layer.md), [Workspace Communication Protocol](../architecture/workspace-communication-protocol.md), [Context Manager](../architecture/context-manager.md), [ADR-0008](ADR-0008-authoring-domain-execution-boundary.md), [ADR-0013](ADR-0013-cache-aware-append-only-context-rendering.md)

---

## Context

Product 1.0 now has a clear Authoring Domain and Task Domain boundary:

```text
User input
  -> Collaborator authoring
  -> RawTask / DraftTaskTree
  -> publish
  -> TaskBus execution
```

That boundary keeps non-executable planning state out of TaskBus. It also
creates a limitation: some user requests cannot be planned well from chat
history and system-owned authoring state alone.

Examples:

- "Read this repo and make a Product 1.0 closure plan."
- "Use our project docs as the implementation guide."
- "Update the plan document first, then derive Tasks from it."
- "Draft Tasks from an existing PRD, README, or architecture note."

In these cases, planning is partly stored in workspace files. The plan may not
be only a system object. It can be a project-owned document, like this
repository's ADRs, plans, architecture notes, QA runbooks, and gap registry.

Current Collaborator authoring context is intentionally narrow: it reads
RawTask, DraftTaskTree, MessageStream, and CapabilityCatalog. It does not read,
query, or search workspace files before planning.

That is too weak for workspace-centered products.

---

## Decision

Collaborator will gain a bounded **workspace-informed authoring** capability.

The first version has two parts:

```text
1. Read workspace context before authoring.
2. Query/search workspace guidance before authoring.
```

This decision keeps the earlier default that Collaborator should not mount
workspace-changing tools. It narrows the new capability to read/search context:

```text
Collaborator may use authoring-scoped workspace read/query/search operations.
Collaborator must not write workspace files in the first version.
Collaborator must not become an unrestricted execution Agent by default.
```

## Scope Of The New Capability

### Workspace Read Before Planning

Collaborator may read bounded workspace context before it creates or refines
authoring state.

Allowed read sources include:

- user-selected files;
- files referenced by the user's prompt;
- project guidance documents declared by policy;
- small workspace manifests or indexes;
- planning documents created by previous execution Tasks;
- explicit file snippets already surfaced by Audit or Context Manager.

The first implementation should avoid whole-workspace crawling. It should use
bounded discovery such as:

```text
selected paths
  -> project guidance candidates
  -> small manifest/index
  -> explicit snippets
```

Read facts are added to Collaborator's authoring context as workspace evidence,
not as hidden instructions that bypass the user or the project policy.

### Workspace Query And Search Before Planning

Collaborator may ask for bounded workspace search before it creates or refines
authoring state.

Allowed query/search operations include:

- find likely guidance documents;
- search filenames by user-mentioned terms;
- search text within allowlisted guidance paths;
- list a shallow directory view for selected folders;
- return ranked candidate refs and small snippets.

Search results are evidence candidates. They do not automatically become
instructions. Collaborator must still ground RawTask, DraftTaskTree, and asks in
the selected evidence returned by the authoring context source.

### Workspace Write Is Deferred To Execution

Collaborator does not write project files in the first version.

Project planning documents are written by Execution Agents as normal execution
Tasks, using the existing AgentLoop, tool, Audit, and diagnostics surfaces.

If the user asks to "write the plan document first", Collaborator should create
or refine a DraftTask that asks the Execution Agent to write that file after
publish. Collaborator may reference target paths and required source evidence in
the DraftTask, but it does not apply the write itself.

### Files As A Planning Control Plane

TaskWeavn should treat project documents as a legitimate planning control
plane, not only as passive context.

The relationship becomes:

```text
Workspace guidance docs
  -> Collaborator read/query/search preflight
  -> RawTask / DraftTaskTree / asks
  -> publish
  -> TaskBus execution writes or updates agreed planning docs when needed
```

This lets Authoring Domain and Task Domain interact through files when that is
the natural project workflow, without making Collaborator responsible for file
mutation. System state remains useful for UI, validation, replay, and TaskBus
execution, but it is not the only place planning can live.

---

## Boundary Rules

1. Collaborator workspace operations go through an authoring-scoped workspace
   channel, not raw shell access.
2. Reads, queries, and search results must be workspace-root relative and must
   not expose raw absolute paths in renderer diagnostics.
3. `.taskweavn` metadata remains protected from normal workspace access.
4. Collaborator does not write workspace files in the first version.
5. Planning document writes are published execution Tasks, not Collaborator
   authoring side effects.
6. Read/search operations must produce auditable intent, path labels, snippets
   or result refs, and policy decisions.
7. AuthoringCommandService remains the authority for RawTask and DraftTaskTree
   mutation.
8. Published Tasks may reference planning docs, but TaskBus remains the
   authority for execution lifecycle.

---

## Consequences

Positive:

- Collaborator can plan from actual workspace facts instead of only chat
  history.
- Product planning can still live naturally in project docs, matching how this
  repo already uses ADRs, plans, gap registries, and QA runbooks.
- Authoring Domain can decide what should be planned from workspace evidence,
  while Task Domain remains responsible for writing project files.
- The UI can later show which workspace files influenced authoring decisions.
- Workspace-root-as-agent-cwd semantics become more useful because planning
  paths are project-relative.

Trade-offs:

- Collaborator becomes more capable and therefore needs stronger access policy,
  audit, and path normalization.
- Search quality and context selection become part of authoring quality.
- Planning docs can still drift from system RawTask/DraftTaskTree state unless
  execution Tasks keep file updates explicit.
- Tests must cover system-state authoring plus workspace evidence selection.

Rejected alternatives:

| Alternative | Reason Rejected |
|---|---|
| Keep Collaborator chat-only | It cannot plan reliably for workspace-dependent tasks. |
| Give Collaborator the full execution AgentLoop | Too broad for authoring; it blurs planning and execution and increases risk. |
| Store all plans only in system databases | Does not match project workflows where docs are the durable implementation guide. |
| Let execution Tasks read docs only after publish | Too late; the plan may be wrong before execution starts. |
| Let file writes directly replace AuthoringCommandService | Breaks validation, replay, and UI state consistency. |
| Let Collaborator write planning docs in version one | Adds write observability and permission complexity before the read/search need is validated. |

---

## Implementation Plan

### C1. Workspace Read Preflight

Add a `CollaboratorWorkspaceContextSource` that can resolve bounded read
requests from:

- selected paths;
- user-mentioned paths;
- configured guidance paths;
- small workspace manifests;
- prior planning artifact refs.

The output is added to `AuthoringContext` as sanitized workspace evidence.

### C2. Workspace Query And Search Contract

Add an authoring-scoped query/search contract:

```text
query
search_scope
candidate_paths
max_results
max_snippet_chars
purpose
evidence refs
```

The first implementation should support shallow directory listing, filename
search, and bounded text search over selected or policy-declared guidance
paths. It should not run shell commands.

### C3. Audit And Diagnostics

Record:

- read sources;
- path labels;
- snippets included;
- search queries;
- search result refs;
- rejected policy checks.

Diagnostics must normalize paths to `workspace://current/...` and redact raw
absolute paths.

### C4. UI Contract

Expose enough state for the Main Page to show:

- which workspace files influenced planning;
- which search/query results were selected;
- links from DraftTaskTree or PublishedTask to referenced planning docs.

### C5. Acceptance Tests

Add focused tests for:

- collaborator reads selected/guidance docs before DraftTaskTree generation;
- collaborator searches configured guidance paths before planning;
- collaborator cannot read `.taskweavn` through normal paths;
- collaborator has no first-version write operation;
- audit/diagnostics path labels do not expose raw absolute paths.

---

## Follow-up

- Create a feature plan for `Collaborator Workspace-Informed Authoring`.
- Define the first API contract for workspace read preflight and
  query/search.
- Decide the default project guidance path policy for Product 1.0 local RC.
- Keep the first implementation narrow: read preflight plus query/search, not a
  full Collaborator execution loop and not file writes.
