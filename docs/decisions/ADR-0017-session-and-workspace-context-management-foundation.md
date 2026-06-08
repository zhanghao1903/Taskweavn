# ADR-0017: Session And Workspace Context Management Foundation

> Status: accepted foundation / not implemented
> Date: 2026-06-08
> Related: [Context Manager](../architecture/context-manager.md), [Workspace Entry Contract](../engineering/workspace-entry-contract.md), [ADR-0013](ADR-0013-cache-aware-append-only-context-rendering.md), [ADR-0016](ADR-0016-collaborator-workspace-aware-authoring.md), [Authoring Domain](../architecture/authoring-domain.md), [Task](../architecture/task.md)

---

## Context

Product 1.0 implemented a Task execution Context Manager. It is wired into the
fixed-route Default Agent path and builds context for a specific PublishedTask
LLM call.

That is no longer enough as the product moves toward workspace selection and
Collaborator workspace-informed authoring.

The system now has at least three context horizons:

```text
Workspace horizon
  durable project/workspace facts and evidence candidates

Session horizon
  the current user work session, selected evidence, active workflow, and decisions

Task horizon
  one published execution task's objective, runtime facts, and tool observations
```

The current `SessionContextManager` implementation name can be misleading: it
is session-scoped storage and orchestration, but its rendered output is still
Task execution context. This ADR defines the future layered contract without
renaming or implementing anything now.

---

## Decision

TaskWeavn will use a layered context model:

```text
WorkspaceContext
  -> SessionContext
  -> TaskExecutionContext
  -> Agent-specific LLM input rendering
```

Each layer has a different owner, lifetime, and inclusion policy. Higher-level
context is not automatically dumped into every lower-level prompt. Agents
request or receive selected context according to their profile and current
workflow.

## Product Version Boundary

Product 1.0 does not implement durable WorkspaceContext or SessionContext
storage. It keeps the existing Product 1.0 continuation model:

- RawTask, RawTaskAsk, RawTaskAnswer, DraftTaskTree, recent messages, active
  authoring state, and bounded authoring evidence remain the durable facts.
- When Collaborator asks the user through `ask_authoring`, that authoring loop
  ends and the RawTask waits for the answer.
- When the user answers all required RawTaskAsk objects, the backend starts a
  new authoring loop against the same RawTask to generate the DraftTaskTree.
  It does not resume the provider transcript from the prior loop.
- Any context carried into that new loop is rebuilt from durable authoring facts
  and bounded read/search policy, not from a new plan-level or session-level
  memory system.

Plan-level and session-level context management, including context snapshots,
promotion rules, and cross-loop selected-evidence memory, is deferred to
Product 1.1.

## Layer Contract

### Workspace Context

Workspace Context is durable, workspace-scoped, and cross-session.

It may contain:

- safe workspace identity labels;
- workspace root semantics and `.plato` metadata boundary;
- project policy or guidance path declarations;
- lightweight workspace manifests or indexes;
- user-selected reusable guidance refs;
- high-level capability declarations;
- prior session summaries that were explicitly promoted;
- redacted references to important project documents or artifacts.

It must not contain:

- raw absolute paths in renderer-facing payloads;
- secrets, provider payloads, raw prompts, raw logs, or SQLite payloads;
- unbounded full workspace snapshots;
- unrelated file contents by default;
- hidden project instructions that bypass user or project policy.

Workspace Context can support search and discovery, but it is not a generic
memory dump. Project documents can be evidence for projects that use document
workflows, but Plato must not assume every workspace is document-driven.

### Session Context

Session Context is scoped to one active workspace session.

It may contain:

- active workflow/domain state, such as authoring vs published task execution;
- current RawTask, DraftTaskTree, selected Task, or current Task refs;
- user-selected files, folders, or evidence refs for this session;
- session decisions, assumptions, constraints, and open questions;
- accepted workspace evidence selected during Collaborator read/search;
- current settings readiness and runtime mode labels when relevant;
- links to diagnostic, audit, and result refs.

It must not contain:

- cross-workspace facts;
- unrelated sessions' private transcripts;
- raw absolute workspace paths in renderer diagnostics;
- file content that has not been selected, summarized, or policy-approved.

Session Context is the right place to remember "what this user is working on
now" without turning that state into a PublishedTask.

### Task Execution Context

Task Execution Context is scoped to one PublishedTask execution call.

It may contain:

- task identity, objective, parent/root refs, and required capability;
- latest execution status and assigned agent;
- recent runtime events and tool observations;
- selected file snippets and workspace refs;
- ASK, confirmation, retry, interruption, and guidance facts;
- result/error refs and task-local audit evidence.

It must not contain:

- a whole workspace index;
- all session messages by default;
- every project guidance document by default;
- unrelated RawTask/DraftTask state after the active workflow has crossed into
  Task Domain.

The current Product 1.0 Context Manager remains primarily responsible for this
layer.

---

## Composition Rules

1. Context layers are composable but not hierarchical dumps.
2. Each Agent profile declares which layers it may read.
3. Inclusion is selected, bounded, and traceable.
4. Workspace and Session facts should be represented as refs, summaries, or
   snippets unless the agent explicitly needs content.
5. Reads/searches create evidence refs and policy decisions.
6. Rendered LLM input is not the audit record; snapshots and traces retain
   provenance separately.
7. `.plato` remains protected from normal workspace access.
8. Cross-session reuse happens only through promoted Workspace Context, not by
   replaying arbitrary session transcripts.

## Agent Usage

### Collaborator Authoring Profile

Collaborator may read:

- Workspace Context search/discovery results;
- Session Context authoring state and selected evidence;
- current RawTask/DraftTask state.

Collaborator may not write workspace files in the first version.

Collaborator output remains:

```text
RawTask | RawTaskAsk | DraftTaskTree | DraftTaskPatch | rejected result
```

Workspace read/search observations are intermediate evidence, not state
mutation.

### Execution Profile

Execution Agents may read:

- selected Workspace Context refs;
- Session Context guidance relevant to the task;
- Task Execution Context.

Execution Agents may write workspace files through existing tools and policy
only when executing PublishedTasks.

### Future Profiles

Audit, diagnostic, routing, reviewer, and recovery agents should reuse the same
layered context contract instead of creating independent memory models.

---

## Storage And Snapshot Direction

This ADR does not implement storage, but future storage should preserve the
layer boundary:

```text
<workspace>/.plato/
  context/
    workspace.sqlite or workspace.jsonl
  sessions/<session_id>/
    context.sqlite
    events.sqlite
```

Conceptual records:

```text
WorkspaceContextSnapshot
SessionContextSnapshot
TaskContextSnapshot
ContextTrace
ContextEvidenceRef
```

Snapshots should store stable labels and refs by default. Full payloads should
be included only when they are safe, bounded, and necessary for replay or
diagnostics.

---

## Consequences

Positive:

- Prevents Task execution context from becoming a catch-all memory layer.
- Gives Collaborator a clean path to read workspace/session evidence before
  planning.
- Keeps workspace-wide facts from leaking into every task prompt.
- Gives future agents a shared context foundation instead of one-off memory
  systems.
- Supports Product 1.0 root semantics and `.plato` metadata ownership.

Trade-offs:

- Adds another architecture layer to reason about.
- Requires clear promotion rules from Session Context to Workspace Context.
- Requires UI and diagnostics to distinguish "selected evidence" from
  "available evidence".
- Future tests must verify layer isolation and path redaction.

Rejected alternatives:

| Alternative | Reason Rejected |
|---|---|
| Keep only TaskExecutionContext | Collaborator and future agents would lack stable workspace/session grounding. |
| Put all workspace facts into every task prompt | Bloats prompts, hurts cache behavior, and risks irrelevant instructions. |
| Treat Session Context as long-term memory | Sessions are transient and workspace-scoped; durable facts must be explicitly promoted. |
| Let each Agent define its own memory model | Increases complexity and makes audit/diagnostics inconsistent. |

---

## Follow-up Plan

This ADR is contract-only. No implementation is accepted by this document.

Product 1.1 planning slices:

1. Define `WorkspaceContextSnapshot`, `SessionContextSnapshot`, and evidence ref
   schemas.
2. Define promotion rules from Session Context to Workspace Context.
3. Add Collaborator read/search context source against Workspace/Session
   context.
4. Add audit/diagnostic projection for selected context evidence.
5. Add tests for layer isolation, path redaction, and context inclusion policy.
