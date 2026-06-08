# Technical Design: Collaborator Workspace-Informed Authoring

> Status: draft technical design
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

This technical design is intentionally draft. Implementation should not start
until this design is accepted.

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
- semantic/vector search;
- broad `AgentLoop` rewrite;
- concurrent multi-Agent context ownership.

## 5. Architecture

Target shape:

```text
Shared loop mechanics
  -> ExecutionProfile
       terminal: agent_finish
       tools: read/write/list/run/ask_user
       result: LoopResult

  -> CollaboratorAuthoringProfile
       terminal: finish_authoring
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

## 6. Module Direction

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

## 7. Profile Protocols

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
    allowed_tool_names: tuple[str, ...] = (
        "authoring_read_workspace",
        "authoring_search_workspace",
        "finish_authoring",
    )
```

Execution profile can remain implicit in the first extraction if needed, but
the design goal is for execution to become a profile over the same core.

## 8. Collaborator Tools

### authoring_read_workspace

Purpose:

- read selected or referenced files;
- return bounded snippets and evidence refs;
- reject `.taskweavn` and unsafe paths.

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

### finish_authoring

Purpose:

- terminate the authoring loop;
- submit one final proposal to strict validators;
- hand accepted proposals to `AuthoringCommandService`.

Only `finish_authoring` may lead to Authoring Domain mutation.

## 9. Loop States

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

## 10. Outcome Mapping

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

## 11. Audit And Diagnostics

Every read/search observation should produce an evidence ref containing:

- loop id;
- session id;
- operation;
- tool name;
- purpose;
- safe path label;
- snippet hash or omitted reason;
- policy decision;
- timestamp.

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

## 12. Implementation Slices

### Slice A: Technical Seam

Goal:

- add profile/result protocols and terminal action model;
- no behavior change to execution Agent;
- no Collaborator workspace reads yet.

Validation:

- existing `AgentLoop` tests pass;
- Collaborator one-shot tests pass;
- no public behavior change.

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
- keep `.taskweavn` protected.

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

## 13. Test Matrix

Backend tests:

- current one-shot raw task creation remains valid;
- current draft task tree generation remains valid;
- current draft task refinement remains valid;
- read/search can precede `finish_authoring`;
- only `finish_authoring` mutates authoring stores;
- `waiting_for_context` does not create RawTaskAsk;
- `.taskweavn` paths reject;
- write/shell tools are absent;
- step limits reject safely;
- evidence refs are persisted or projected with safe labels.

Regression tests:

- `AgentLoop` execution path still supports existing tools;
- Context Manager metadata still appears in execution LLM calls;
- provider tool-call ordering remains valid;
- existing sidecar authoring command tests pass.

## 14. Open Design Questions

1. Should the first shared loop core extraction happen before the first
   Collaborator profile slice, or can the profile be introduced as a wrapper
   and later extracted?
2. Should read/search observations write into EventStream, MessageStream, a new
   authoring evidence store, or a small adapter over existing audit sources?
3. Should `waiting_for_context` be represented through existing CommandResult
   details first, or should it add a new explicit UI contract field?
4. What is the Product 1.0 default guidance path policy?

## 15. Acceptance Gate

Implementation should not begin until this technical design is accepted.

Acceptance requires agreement on:

- profile vs direct `AgentLoop` reuse strategy;
- terminal action model;
- evidence storage/projection choice;
- `waiting_for_context` result shape;
- first implementation slice.
