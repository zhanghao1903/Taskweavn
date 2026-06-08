# ADR-0016: Collaborator Workspace-Informed Authoring

> Status: accepted
> Date: 2026-06-08
> Related: [Authoring Domain](../architecture/authoring-domain.md), [Collaborator Agent](../architecture/collaborator-agent-task-authoring.md), [Tool Capability Layer](../architecture/tool-capability-layer.md), [Workspace Communication Protocol](../architecture/workspace-communication-protocol.md), [Context Manager](../architecture/context-manager.md), [Collaborator Workspace-Informed Authoring Plan](../plans/feature/collaborator-workspace-informed-authoring.md), [Collaborator Workspace-Informed Authoring Contract](../engineering/collaborator-workspace-informed-authoring-contract.md), [ADR-0008](ADR-0008-authoring-domain-execution-boundary.md), [ADR-0013](ADR-0013-cache-aware-append-only-context-rendering.md)

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

Examples from this repository's current project workflow:

- "Read this repo and make a Product 1.0 closure plan."
- "Use our project docs as the implementation guide."
- "Update the plan document first, then derive Tasks from it."
- "Draft Tasks from an existing PRD, README, or architecture note."

In these cases, planning is partly stored in workspace files. The plan may not
be only a system object. It can depend on project-owned documents, like this
repository's ADRs, plans, architecture notes, QA runbooks, and gap registry.
That is a project workflow and project capability, not a general Plato system
requirement that every workspace must use documents as the planning control
plane.

Current Collaborator authoring context is intentionally narrow: it reads
RawTask, DraftTaskTree, MessageStream, and CapabilityCatalog. It does not read,
query, or search workspace files before planning.

That is too weak for workspace-centered products.

---

## Decision

Collaborator will gain a bounded **workspace-informed authoring** capability.

The first version has three parts:

```text
1. Read workspace context before authoring.
2. Query/search workspace guidance before authoring.
3. Continue authoring over multiple read/search observations when needed.
```

This decision keeps the earlier default that Collaborator should not mount
workspace-changing tools. It narrows the new capability to read/search context:

```text
Collaborator may use authoring-scoped workspace read/query/search operations.
Collaborator must not write workspace files in the first version.
Collaborator must not become an unrestricted execution Agent by default.
```

This can be understood as adding a bounded, read-only authoring loop to the
current Collaborator:

```text
authoring intent
  -> request read/query/search context
  -> receive workspace evidence observations
  -> update RawTask / DraftTaskTree / ask proposal
  -> repeat when more context is needed
```

The loop is not a general execution AgentLoop. It has no write operation, no
shell, and no code/config mutation.

### Loop Implementation Reuse

The first implementation should not create a separate Collaborator-only loop
engine.

Collaborator should reuse the shared AgentLoop core where possible, but through
an authoring-specific profile:

```text
Shared AgentLoop Core
  -> ExecutionProfile
  -> CollaboratorAuthoringProfile
  -> future specialized Agent profiles
```

`CollaboratorAuthoringProfile` owns the authoring-specific boundary:

- allowed tools: read/query/search workspace context and terminal authoring
  ask/finish tools only;
- forbidden tools: write, shell, command execution, unrestricted workspace
  mutation;
- states: `running`, `reading_context`, `waiting_for_context`, `finished`,
  `rejected`;
- terminal actions: `finish_authoring(proposal)` and
  `ask_authoring(question)`;
- outcome mapping: final proposal -> AuthoringCommandService validation;
- audit semantics: context reads/searches are evidence, not Tasks and not file
  mutations.

This avoids one loop implementation per future Agent while still keeping
execution and authoring contracts separate.

### Terminal Contract Remains Authoring

The existing Collaborator is close to a single function call: it receives a
user authoring request and returns a proposal that becomes either a RawTask,
RawTaskAsk, DraftTaskTree, DraftTask patch, or a rejected authoring result.

That terminal contract stays the same.

Workspace read/query/search calls are intermediate context-gathering steps.
They do not directly mutate Authoring Domain state. RawTask, RawTaskAsk,
DraftTaskTree, and DraftTask patches are still produced only when the
Collaborator reaches an explicit terminal authoring state and the
AuthoringCommandService validates the final proposal.

```text
start authoring call
  -> optional read/query/search observations
  -> finish_authoring(proposal) OR ask_authoring(question)
  -> AuthoringCommandService validates and persists
```

Intermediate observations may be logged, audited, and exposed as evidence, but
they are not user-visible Tasks and they are not workspace writes.

### Authoring Loop States

The first implementation should define a small lifecycle instead of reusing the
execution AgentLoop lifecycle wholesale:

| State | Meaning |
|---|---|
| `running` | Collaborator is evaluating the request with current authoring context. |
| `reading_context` | Collaborator requested a bounded workspace read/query/search. |
| `waiting_for_context` | More context cannot be fetched without user selection, permission, or an unavailable source recovering. |
| `finished` | Collaborator produced the final authoring proposal for validation. |
| `rejected` | Collaborator failed safely or exceeded policy/step limits. |

`waiting_for_context` is not the same as a RawTaskAsk. It is a control state for
context acquisition, such as "choose which files I may read". `ask_authoring`
is the terminal tool-call form that creates a RawTaskAsk. A RawTaskAsk is part
of the final authoring proposal when the user's goal itself needs
clarification.

The loop must have explicit limits:

- maximum read/search calls;
- maximum selected files and snippets;
- maximum context bytes/tokens;
- no write calls;
- no shell calls;
- no direct AuthoringCommandService mutation before `finished`.

## Scope Of The New Capability

### Workspace Read Before Planning

Collaborator may read bounded workspace context before it creates or refines
authoring state.

Allowed read sources include:

- user-selected files;
- files referenced by the user's prompt;
- project guidance documents selected by the user or declared by project policy;
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

### Workspace Write Is Not A Collaborator Capability

Collaborator does not write workspace files in the first version.

If a project workflow requires writing or updating documents, that work is a
separate execution task handled by an Execution Agent using the existing
AgentLoop, tool, Audit, and diagnostics surfaces.

If the user asks to "write the plan document first", Collaborator should create
or refine a DraftTask that asks the Execution Agent to write that file after
publish. Collaborator may reference target paths and required source evidence in
the DraftTask, but it does not apply the write itself.

This ADR does not define project document writing as a Plato system capability.
It only defines that Collaborator can read/search workspace evidence before
authoring.

### Project Documents As Optional Workspace Evidence

Some projects use documents as implementation guidance. This repository does so,
but that pattern belongs to the project workflow. Plato should not require or
assume that every workspace has the same document-driven process.

For projects that do use guidance documents, the relationship becomes:

```text
Project-selected or policy-declared guidance docs
  -> Collaborator read/query/search preflight
  -> RawTask / DraftTaskTree / asks
  -> publish
  -> TaskBus execution performs any requested project-file writes separately
```

This lets Collaborator avoid guessing when the user's project workflow depends
on files, without making file-backed planning a universal Plato capability and
without making Collaborator responsible for file mutation.

---

## Boundary Rules

1. Collaborator workspace operations go through an authoring-scoped workspace
   channel, not raw shell access.
2. Reads, queries, and search results must be workspace-root relative and must
   not expose raw absolute paths in renderer diagnostics.
3. `.plato` metadata remains protected from normal workspace access.
4. Collaborator does not write workspace files in the first version.
5. Any workspace write requested by a project workflow is a published execution
   Task, not a Collaborator authoring side effect.
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
- Authoring Domain can decide what should be planned from workspace evidence,
  while Task Domain remains responsible for any project file writes.
- Project-specific document workflows can be supported as workspace evidence
  without becoming mandatory Plato system behavior.
- The UI can later show which workspace files influenced authoring decisions.
- Workspace-root-as-agent-cwd semantics become more useful because planning
  paths are project-relative.

Trade-offs:

- Collaborator becomes more capable and therefore needs stronger access policy,
  audit, and path normalization.
- Search quality and context selection become part of authoring quality.
- Project documents can still drift from system RawTask/DraftTaskTree state;
  this ADR does not solve project document governance.
- Tests must cover system-state authoring plus workspace evidence selection.

Rejected alternatives:

| Alternative | Reason Rejected |
|---|---|
| Keep Collaborator chat-only | It cannot plan reliably for workspace-dependent tasks. |
| Give Collaborator the full execution AgentLoop | Too broad for authoring; it blurs planning and execution and increases risk. |
| Store all authoring context only in system databases | Collaborator would still miss workspace-dependent project facts. |
| Let execution Tasks read docs only after publish | Too late; the plan may be wrong before execution starts. |
| Let file writes directly replace AuthoringCommandService | Breaks validation, replay, and UI state consistency. |
| Let Collaborator write planning docs in version one | Adds write observability and permission complexity before the read/search need is validated. |

---

## Implementation Plan

### C1. Read-Only Authoring Loop And Workspace Read Preflight

Add a `CollaboratorWorkspaceContextSource` that can resolve bounded read
requests from:

- selected paths;
- user-mentioned paths;
- configured guidance paths;
- small workspace manifests;
- prior planning artifact refs.

The output is added to `AuthoringContext` as sanitized workspace evidence.

The first implementation should support repeated authoring turns over read and
search observations. It must not add write, shell, or command execution tools.

The implementation should be profile-based rather than a bespoke Collaborator
loop. If the current AgentLoop cannot support this directly, the first
technical slice should extract or parameterize the reusable loop pieces:

- LLM call and tool-call dispatch;
- append-only transcript handling;
- step limits;
- tool schema registration;
- observation logging;
- terminal action handling;
- outcome mapping.

Add an explicit authoring-loop result contract:

```text
running
reading_context
waiting_for_context
finished
rejected
```

Only `finished` may submit the final proposal to AuthoringCommandService. The
other states are context acquisition or safe failure states.

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

- collaborator preserves the existing final authoring outcomes after one or
  more read/search observations;
- collaborator can enter `waiting_for_context` without creating a RawTaskAsk;
- only `finished` submits an authoring proposal to AuthoringCommandService;
- collaborator reads selected/guidance docs before DraftTaskTree generation;
- collaborator searches configured guidance paths before planning;
- collaborator cannot read `.plato` through normal paths;
- collaborator has no first-version write operation;
- audit/diagnostics path labels do not expose raw absolute paths.

---

## Follow-up

- Feature plan created:
  [Collaborator Workspace-Informed Authoring](../plans/feature/collaborator-workspace-informed-authoring.md).
- Engineering contract created:
  [Collaborator Workspace-Informed Authoring Contract](../engineering/collaborator-workspace-informed-authoring-contract.md).
- Decide the default project guidance path policy for Product 1.0 local RC.
- Keep the first implementation narrow: read preflight plus query/search, not a
  full Collaborator execution loop and not file writes.
