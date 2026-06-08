# Collaborator Workspace-Informed Authoring

> Status: planned / accepted technical design
> Date: 2026-06-08
> Related ADR: [ADR-0016 Collaborator Workspace-Informed Authoring](../../decisions/ADR-0016-collaborator-workspace-aware-authoring.md)
> Related Contract: [Collaborator Workspace-Informed Authoring Contract](../../engineering/collaborator-workspace-informed-authoring-contract.md)
> Technical Design: [Collaborator Workspace-Informed Authoring Technical Design](collaborator-workspace-informed-authoring-technical-design.md)
> Related Architecture: [Authoring Domain](../../architecture/authoring-domain.md), [Tool Capability Layer](../../architecture/tool-capability-layer.md), [Context Manager](../../architecture/context-manager.md), [ADR-0017 Session And Workspace Context Management Foundation](../../decisions/ADR-0017-session-and-workspace-context-management-foundation.md)

---

## 1. Purpose

Collaborator currently behaves like a near-single LLM function call: it receives
authoring input and produces a RawTask, RawTaskAsk, DraftTaskTree, DraftTask
patch, or rejected authoring result.

Some authoring requests require workspace context before the final proposal can
be correct. Product 1.0 should not force Collaborator to guess when the user asks
it to plan from project files.

This feature adds a bounded, read-only authoring loop for Collaborator.

The loop may read, query, and search workspace context before finishing the
same terminal authoring contract.

## 2. Non-Goals

This feature does not:

- give Collaborator write access to workspace files;
- give Collaborator shell or command execution;
- make Collaborator an unrestricted execution Agent;
- implement session/workspace context storage from ADR-0017;
- implement plan-level or session-level cross-loop context management;
- make document-driven planning a general Plato system capability;
- change AuthoringCommandService as the authority for authoring mutation.

## 3. Product Boundary

The user-facing behavior remains:

```text
User authoring request
  -> Collaborator may gather bounded read/search context
  -> Collaborator finishes with an authoring proposal
  -> AuthoringCommandService validates and persists
```

Intermediate workspace observations are evidence. They are not Tasks, not file
writes, and not direct Authoring Domain mutations.

If a project workflow requires writing a plan document, Collaborator should
draft or refine an execution Task that asks an Execution Agent to write that
document after publish.

## 4. Implementation Slices

Implementation may start with Slice A from the accepted
[technical design](collaborator-workspace-informed-authoring-technical-design.md).
Later slices remain gated by their own acceptance criteria and must return to
design review if they change the profile, evidence storage, waiting result, or
access policy decisions.

### C1. Shared Loop Profile Contract

Define `CollaboratorAuthoringProfile` as a profile over the shared AgentLoop
core rather than building a bespoke Collaborator-only loop.

Profile boundaries:

- allowed tools: read/query/search workspace context and terminal
  ask/finish authoring tools;
- forbidden tools: write, shell, command execution;
- states: `running`, `reading_context`, `waiting_for_context`, `finished`,
  `rejected`;
- terminal actions: `finish_authoring(proposal)` and
  `ask_authoring(question)`;
- outcome mapping: final proposal to AuthoringCommandService validation.

### C2. Workspace Context Source

Add a read-only authoring context source for selected or policy-declared
workspace evidence.

Supported first operations:

- read selected file snippets;
- search selected or configured guidance paths;
- list shallow selected directories;
- return evidence refs and safe path labels.

### C3. Wait/Finish Contract

Differentiate:

- `waiting_for_context`: control state for context acquisition, such as needing
  user file selection;
- RawTaskAsk: final authoring proposal when the user's goal itself needs
  clarification;
- `ask_authoring`: terminal tool-call form that creates a RawTaskAsk during
  RawTask authoring;
- `finished`: only state that submits a final proposal to
  AuthoringCommandService.

### C4. Audit And Diagnostics

Record:

- read/search intent;
- selected paths and safe labels;
- snippets included or omitted;
- evidence refs;
- policy denials;
- final proposal refs.

Renderer diagnostics must not expose raw absolute paths, secrets, prompts,
provider payloads, raw logs, or SQLite payloads.

### C5. UI Follow-Up

The first backend slice may return `waiting_for_context` without full UI polish.
The later frontend slice should show:

- context selection request;
- candidate files or guidance paths;
- selected evidence summary;
- final authoring outcome.

## 5. Acceptance Criteria

The feature is accepted when:

1. Collaborator can finish the existing authoring outcomes without workspace
   tool calls.
2. Collaborator can perform one or more read/search observations before
   finishing the same authoring outcome.
3. `waiting_for_context` can be returned without creating a RawTaskAsk.
4. Only `finished` submits proposals to AuthoringCommandService.
5. `.plato` is protected from normal read/search paths.
6. No workspace write, shell, or command execution operation is exposed.
7. Audit/diagnostics use safe path labels and evidence refs.

## 6. Test Plan

Focused tests:

- profile denies write/shell tools;
- read/search observations can precede RawTask creation;
- read/search observations can precede DraftTaskTree generation;
- `waiting_for_context` is distinct from RawTaskAsk;
- `finished` is the only state that mutates authoring state;
- path labels normalize to `workspace://current/...`;
- `.plato` is rejected for normal authoring context reads;
- existing one-shot Collaborator behavior remains compatible.

## 7. Accepted Decisions And Deferred Questions

Accepted by the technical design:

1. Slice A starts with a shared loop profile seam and authoring evidence store
   contract, not direct Collaborator reuse of the current execution
   `AgentLoop`.
2. Authoring read/search evidence uses `AuthoringEvidenceStore` as the
   authoritative first-version source.
3. `waiting_for_context` is an explicit loop result shape and may be carried
   through existing command details before a dedicated UI field exists.
4. Product 1.0 starts with a conservative static guidance policy over selected,
   prompt-referenced, README, AGENTS, and docs guidance paths.

Deferred:

- dedicated context-selection UI;
- configurable guidance policy;
- EventStream mirroring for authoring evidence;
- semantic/vector search;
- Product 1.1 plan-level and session-level context management, including
  context snapshots, promotion rules, and cross-loop selected-evidence memory.
