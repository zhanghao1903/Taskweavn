# Technical Design: Collaborator Workspace-Informed Authoring

> Status: accepted technical design
> Last Updated: 2026-06-08
> Feature Plan: [Collaborator Workspace-Informed Authoring](collaborator-workspace-informed-authoring.md)
> Engineering Contract: [Collaborator Workspace-Informed Authoring Contract](../../engineering/collaborator-workspace-informed-authoring-contract.md)
> Decision: [ADR-0016 Collaborator Workspace-Informed Authoring](../../decisions/ADR-0016-collaborator-workspace-aware-authoring.md)

---

## 1. Design Summary

Collaborator should gain a bounded read-only authoring loop without becoming an
execution Agent.

The existing terminal authoring contract remains unchanged:

```text
Collaborator input
  -> RawTask | RawTaskAsk | DraftTaskTree | DraftTaskPatch | rejected result
```

The new behavior is that Collaborator may perform zero or more read/search
context-gathering turns before it finishes that same terminal proposal.

This technical design is accepted for the first implementation slice. Later
slices must return to design review if they change the profile boundary,
evidence storage, result shape, write capability, or search policy.

## 2. Current Baseline

Current Collaborator implementation:

- `DefaultCollaboratorAuthoringService` is close to a one-shot LLM proposal
  mapper;
- it calls `llm.chat(...)` directly with `tools=None`;
- it builds context through `DefaultAuthoringContextBuilder`;
- it submits validated proposals through `AuthoringCommandService`;
- it does not own a loop, tool dispatch, wait state, or workspace evidence
  source.

Current execution loop implementation:

- `AgentLoop` owns LLM call orchestration, tool schema registration, tool-call
  dispatch, append-only transcript, event stream writes, context provider
  integration, audit/logging, pending decisions, interrupts, and terminal
  `agent_finish`;
- it is currently execution-oriented and should not be reused by Collaborator
  without a profile boundary.

## 3. Design Goals

1. Reuse shared loop mechanics rather than creating a Collaborator-only loop
   engine.
2. Keep Collaborator's terminal authoring outcome unchanged.
3. Add read/query/search workspace evidence as intermediate observations.
4. Keep `waiting_for_context` distinct from RawTaskAsk.
5. Prevent workspace writes, shell, command execution, and direct authoring
   mutation before `finish_authoring`.
6. Preserve append-only transcript behavior and provider tool-call ordering.
7. Keep implementation slices small enough to protect the current execution
   Agent path.

## 4. Non-Goals

This design does not implement:

- workspace writes;
- shell or command execution for Collaborator;
- project document writing as a Plato system capability;
- session/workspace context storage from ADR-0017;
- plan-level or session-level cross-loop context management;
- semantic/vector search;
- broad `AgentLoop` rewrite;
- concurrent multi-Agent context ownership.

Product 1.0 uses durable Authoring Domain facts for ask continuation. After a
RawTaskAsk is answered, the backend starts a new authoring loop for the same
RawTask instead of resuming the previous provider transcript. Plan/session
context snapshots, promotion rules, and cross-loop selected-evidence memory are
deferred to Product 1.1.

## 5. Accepted Review Decisions

### Profile Boundary

Collaborator should reuse shared loop mechanics through a profile contract, not
by directly mounting the current execution `AgentLoop`.

The accepted first slice is a profile seam:

- introduce shared `AgentLoopProfile` and terminal action/result protocols;
- keep the execution Agent behavior unchanged;
- do not add Collaborator read/search tools in the seam slice;
- do not add Collaborator-specific behavior directly to
  `src/taskweavn/core/loop.py`.

If extraction proves too large, the first slice may add an adapter boundary, but
the adapter must still define the profile-facing contract and keep
Collaborator profile code outside the execution loop implementation.

### Evidence Storage

Read/search observations should use an authoring evidence source of truth,
conceptually `AuthoringEvidenceStore`.

MessageStream remains the user-facing conversation/proposal surface.
EventStream remains the execution/run fact stream. Audit and diagnostics may
project authoring evidence records, but neither MessageStream nor EventStream is
the authoritative storage for first-version Collaborator read/search evidence.

### Waiting Result Shape

`waiting_for_context` is an explicit authoring loop result:

```ts
type CollaboratorWaitingForContextResult = {
  status: "waiting_for_context";
  reason: string;
  requestedContext: CollaboratorContextRequest;
  candidateEvidenceRefs: string[];
};
```

The existing gateway can carry this shape through command result details in the
first backend slice. It is not a RawTaskAsk, and it must not call
AuthoringCommandService.

### Default Guidance Policy

Product 1.0 starts with a conservative static policy:

- user-selected paths;
- prompt-referenced paths that resolve inside the workspace;
- `README*`;
- `AGENTS.md`;
- `docs/plans/**`;
- `docs/architecture/**`;
- `docs/decisions/**`;
- `docs/engineering/**`.

The policy must respect read/search limits, reject `.plato`, avoid full
workspace crawls, and remain configurable only in a later slice.

## 6. Architecture

Target shape:

```text
Shared loop mechanics
  -> ExecutionProfile
       terminal: agent_finish
       tools: read/write/list/run/ask_user
       result: LoopResult

  -> CollaboratorAuthoringProfile
       terminal: finish_authoring, ask_authoring
       tools: authoring_read_workspace, authoring_search_workspace
       result: CollaboratorAuthoringLoopResult
```

The shared mechanics should cover:

- LLM call construction;
- tool schema registration;
- provider tool-call dispatch ordering;
- append-only transcript preservation;
- step limits;
- metadata and LLM logging;
- observation/event emission hooks;
- terminal action detection.

The profile owns:

- allowed tools;
- forbidden tools;
- terminal tool/action type;
- state mapping;
- result mapping;
- audit/evidence metadata policy.

## 7. Module Direction

The first implementation should avoid adding more broad behavior to
`src/taskweavn/core/loop.py` directly.

Preferred module direction:

```text
src/taskweavn/core/
  loop.py                         # compatibility wrapper / execution loop
  loop_core.py                    # shared loop mechanics, if extracted
  loop_profile.py                 # profile protocols and shared state models

src/taskweavn/task/
  collaborator_loop.py            # CollaboratorAuthoringProfile runner
  collaborator_workspace_context.py
```

If extraction is too large for the first slice, an adapter may wrap current
`AgentLoop` only if it preserves execution behavior and keeps Collaborator
profile code outside `loop.py`.

The first implementation slice is not a Collaborator feature slice. It is a
zero-behavior profile seam and authoring evidence contract slice that makes the
later feature work safe to add.

## 8. Profile Protocols

Draft Python-facing protocol:

```python
class AgentLoopProfile(Protocol):
    profile_id: str
    allowed_tool_names: tuple[str, ...]
    terminal_tool_name: str

    def build_initial_messages(self, request: object) -> list[dict[str, object]]: ...
    def map_terminal_action(self, action: object, context: object) -> object: ...
    def map_rejection(self, error: Exception, context: object) -> object: ...
```

Collaborator profile:

```python
@dataclass(frozen=True)
class CollaboratorAuthoringProfile:
    profile_id: str = "collaborator_authoring"
    terminal_tool_name: str = "finish_authoring"
    terminal_tool_names: tuple[str, ...] = (
        "ask_authoring",
        "finish_authoring",
    )
    allowed_tool_names: tuple[str, ...] = (
        "authoring_read_workspace",
        "authoring_search_workspace",
        "ask_authoring",
        "finish_authoring",
    )
```

Execution profile can remain implicit in the first extraction if needed, but
the design goal is for execution to become a profile over the same core.

## 9. Collaborator Tools

### authoring_read_workspace

Purpose:

- read selected or referenced files;
- return bounded snippets and evidence refs;
- reject `.plato` and unsafe paths.

Not allowed:

- writing;
- shelling out to search;
- returning raw absolute paths;
- returning unbounded file content.

### authoring_search_workspace

Purpose:

- search selected or configured guidance paths;
- find filename/text matches;
- return ranked refs and short snippets.

Search implementation should start simple and deterministic. It can use local
structured filesystem APIs or controlled text search, but the contract should
not expose shell execution.

### ask_authoring

Purpose:

- ask the user one RawTask clarification or permission question;
- stop the current authoring loop until the user answers;
- preserve the existing authoring-domain `RawTaskAsk` semantics.

Rules:

- `ask_authoring` is a terminal tool, not an intermediate observation.
- It is only valid during `create_raw_task` for Product 1.0.
- It maps to a RawTaskProposal with `needs_clarification` or
  `needs_user_permission`, then AuthoringCommandService records the RawTask and
  RawTaskAsk.
- It is not `waiting_for_context`; `waiting_for_context` is for missing
  workspace selection, permission to read context, or unavailable context
  source.

### finish_authoring

Purpose:

- terminate the authoring loop;
- submit one final proposal to strict validators;
- hand accepted proposals to `AuthoringCommandService`.

Only `finish_authoring` may lead to Authoring Domain mutation.

## 10. Loop States

```text
running
reading_context
waiting_for_context
finished
rejected
```

State mapping:

- `running`: default evaluation state.
- `reading_context`: a read/search tool call is being executed.
- `waiting_for_context`: required context is unavailable without user
  selection or permission.
- `finished`: terminal proposal was produced.
- `rejected`: provider, policy, validation, or step-limit failure.

`waiting_for_context` is not RawTaskAsk. It is a control result for context
selection. RawTaskAsk remains a final proposal when user intent needs
clarification.

## 11. Outcome Mapping

One-shot path:

```text
request
  -> finish_authoring(raw_task proposal)
  -> existing proposal parser
  -> AuthoringCommandService
```

Read/search path:

```text
request
  -> authoring_search_workspace
  -> observation/evidence refs
  -> authoring_read_workspace
  -> observation/evidence refs
  -> finish_authoring(draft_task_tree proposal)
  -> existing proposal parser
  -> AuthoringCommandService
```

Waiting path:

```text
request
  -> needs context not selected or not allowed
  -> waiting_for_context(requestedContext)
  -> no RawTaskAsk created
  -> no AuthoringCommandService mutation
```

Rejected path:

```text
request
  -> policy/step/provider/validation failure
  -> rejected(errorRef, evidenceRefs)
  -> no AuthoringCommandService mutation
```

## 12. Audit And Diagnostics

Every read/search observation should produce an authoring evidence record and a
stable evidence ref. Conceptual first-version record shape:

```ts
type AuthoringEvidenceRecord = {
  evidenceId: string;
  sessionId: string;
  loopId: string;
  operation: "read_workspace" | "search_workspace";
  toolName: "authoring_read_workspace" | "authoring_search_workspace";
  purpose: string;
  pathLabel: string;
  contentHash?: string;
  snippet?: string;
  omittedReason?: string;
  policyDecision: "allowed" | "denied" | "omitted";
  timestamp: string;
};
```

`AuthoringEvidenceStore` is the authoritative first-version storage/projection
source. Audit and diagnostics should consume evidence refs or safe projected
records from that store.

Diagnostics must use safe labels such as:

```text
workspace://current/docs/plans/example.md
```

Diagnostics must not expose:

- raw absolute paths;
- secrets;
- raw prompts;
- provider payloads;
- raw logs;
- SQLite payloads.

## 13. Implementation Slices

### Slice A: Shared Profile Seam And Evidence Contract

Goal:

- add profile/result protocols and terminal action model;
- define the `AuthoringEvidenceStore` interface/model;
- no behavior change to execution Agent;
- no Collaborator workspace reads yet.
- no Collaborator-specific behavior inside `src/taskweavn/core/loop.py`.

Validation:

- existing `AgentLoop` tests pass;
- Collaborator one-shot tests pass;
- no public behavior change.
- no read/search tool is registered yet.

### Slice B: Collaborator One-Shot Through Profile

Goal:

- route existing Collaborator calls through the authoring profile;
- `finish_authoring` immediately produces current proposal behavior;
- no read/search tools yet.

Validation:

- existing Collaborator tests pass unchanged or with only metadata assertions;
- no new workspace access.

### Slice C: Read/Search Context Tools

Goal:

- add `authoring_read_workspace`;
- add `authoring_search_workspace`;
- add evidence refs and path redaction;
- keep `.plato` protected.

Validation:

- read/search can precede RawTask and DraftTaskTree generation;
- forbidden paths reject;
- no write/shell tools are registered.

### Slice D: Waiting For Context

Goal:

- add `waiting_for_context` result;
- keep it distinct from RawTaskAsk;
- expose enough gateway result metadata for future UI.

Validation:

- `waiting_for_context` does not mutate authoring stores;
- UI command result can represent the state without inventing a RawTaskAsk.

### Slice E: Audit/Diagnostic Projection

Goal:

- make read/search evidence inspectable;
- include diagnostic-safe refs.

Validation:

- audit/diagnostic tests prove path labels and no raw absolute paths.

## 14. Test Matrix

Backend tests:

- current one-shot raw task creation remains valid;
- current draft task tree generation remains valid;
- current draft task refinement remains valid;
- read/search can precede `finish_authoring`;
- only `finish_authoring` mutates authoring stores;
- `waiting_for_context` does not create RawTaskAsk;
- `.plato` paths reject;
- write/shell tools are absent;
- step limits reject safely;
- evidence refs are persisted or projected with safe labels.

Regression tests:

- `AgentLoop` execution path still supports existing tools;
- Context Manager metadata still appears in execution LLM calls;
- provider tool-call ordering remains valid;
- existing sidecar authoring command tests pass.

## 15. Accepted Decisions And Deferred Questions

Accepted:

1. Use a profile boundary over shared loop mechanics. Do not directly reuse the
   execution `AgentLoop` as the Collaborator runtime.
2. Use `AuthoringEvidenceStore` as the authoritative first-version source for
   read/search evidence. Project audit/diagnostics from evidence refs.
3. Represent `waiting_for_context` as an explicit
   `CollaboratorAuthoringLoopResult` shape. Carry it through existing command
   details first if a gateway response wrapper is required.
4. Use the conservative Product 1.0 static guidance policy listed in this
   design.

Deferred:

- dedicated frontend context-selection UI field beyond command result details;
- configurable workspace guidance policy;
- optional EventStream mirror for authoring evidence;
- semantic/vector search.

## 16. Acceptance Gate

Accepted on 2026-06-08 for Slice A implementation.

Implementation may start with Slice A only:

- profile/result protocols;
- terminal action model;
- `AuthoringEvidenceStore` interface/model;
- no behavior change;
- no workspace read/search tools yet.

Slices B-E remain gated by their per-slice validation criteria and must return
to design review if they change the accepted profile, evidence, waiting result,
or access policy decisions.
