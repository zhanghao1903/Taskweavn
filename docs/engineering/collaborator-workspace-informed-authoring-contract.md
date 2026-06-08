# Collaborator Workspace-Informed Authoring Contract

> Status: accepted contract / Slice A implementation open
> Date: 2026-06-08
> Related Plan: [Collaborator Workspace-Informed Authoring](../plans/feature/collaborator-workspace-informed-authoring.md)
> Related ADRs: [ADR-0016](../decisions/ADR-0016-collaborator-workspace-aware-authoring.md), [ADR-0017](../decisions/ADR-0017-session-and-workspace-context-management-foundation.md)

---

## 1. Contract Goal

Collaborator may gather bounded workspace evidence before producing the same
authoring outcomes it produces today.

The contract is:

```text
Authoring request
  -> zero or more read/query/search observations
  -> finished authoring proposal OR waiting_for_context OR rejected
```

Only a `finished` result may submit a proposal to AuthoringCommandService.

## 2. CollaboratorAuthoringProfile

`CollaboratorAuthoringProfile` is a profile over the shared AgentLoop core. It
must not be a separate loop implementation.

Profile settings:

```ts
type CollaboratorAuthoringProfile = {
  profileId: "collaborator_authoring";
  allowedTools: [
    "authoring_read_workspace",
    "authoring_search_workspace",
    "finish_authoring"
  ];
  forbiddenTools: [
    "write_file",
    "run_command",
    "shell",
    "execute_code"
  ];
  maxReadCalls: number;
  maxSearchCalls: number;
  maxSelectedFiles: number;
  maxSnippetChars: number;
};
```

The first implementation may use Python models instead of TypeScript types; the
shape above is the contract.

## 3. Loop States

Internal states:

```ts
type CollaboratorAuthoringLoopState =
  | "running"
  | "reading_context"
  | "waiting_for_context"
  | "finished"
  | "rejected";
```

Rules:

- `running`: evaluating with current authoring/session/workspace evidence.
- `reading_context`: executing a bounded read/query/search operation.
- `waiting_for_context`: blocked on user selection, permission, or unavailable
  context source.
- `finished`: final proposal is ready for AuthoringCommandService validation.
- `rejected`: policy, validation, step limit, or provider failure stopped the
  loop safely.

`waiting_for_context` is a context acquisition control state. It is not a
RawTaskAsk. RawTaskAsk remains a final authoring proposal when the user's goal
requires clarification.

## 4. Request Shape

```ts
type CollaboratorAuthoringLoopRequest = {
  sessionId: string;
  operation:
    | "create_raw_task"
    | "generate_task_tree"
    | "refine_task_node";
  userInput?: string;
  instruction?: string;
  rawTaskId?: string;
  selectedTaskRef?: {
    kind: "draft";
    id: string;
  };
  selectedEvidenceRefs?: string[];
  workspaceContextPolicy?: {
    allowWorkspaceRead: boolean;
    allowWorkspaceSearch: boolean;
    guidancePathGlobs: string[];
    maxReadCalls: number;
    maxSearchCalls: number;
    maxSnippetChars: number;
  };
};
```

## 5. Result Shape

```ts
type CollaboratorAuthoringLoopResult =
  | {
      status: "finished";
      proposalKind:
        | "raw_task"
        | "draft_task_tree"
        | "draft_task_patch";
      proposal: unknown;
      evidenceRefs: string[];
      authoringCommandResultRef?: string;
    }
  | {
      status: "waiting_for_context";
      reason: string;
      requestedContext: CollaboratorContextRequest;
      candidateEvidenceRefs: string[];
    }
  | {
      status: "rejected";
      reason: string;
      errorRef?: string;
      evidenceRefs: string[];
    };
```

`finished.proposal` must still pass the existing strict authoring proposal
validators before mutation is accepted.

## 6. Read/Search Tools

### authoring_read_workspace

```ts
type AuthoringReadWorkspaceRequest = {
  paths: string[];
  purpose: string;
  maxSnippetChars: number;
};

type AuthoringReadWorkspaceObservation = {
  evidenceRefs: string[];
  files: {
    pathLabel: string;
    contentSnippet?: string;
    contentHash?: string;
    omittedReason?: string;
  }[];
};
```

### authoring_search_workspace

```ts
type AuthoringSearchWorkspaceRequest = {
  query: string;
  scope: {
    pathGlobs: string[];
    selectedFolders?: string[];
  };
  maxResults: number;
  maxSnippetChars: number;
  purpose: string;
};

type AuthoringSearchWorkspaceObservation = {
  evidenceRefs: string[];
  results: {
    pathLabel: string;
    score?: number;
    matchSnippet?: string;
    contentHash?: string;
  }[];
};
```

Rules:

- Requests use workspace-relative paths or safe labels.
- Results use `workspace://current/...` labels in renderer-facing payloads.
- `.taskweavn` is rejected for normal authoring read/search.
- No write, shell, or command execution tool is available.
- Search/read observations are evidence, not instructions by default.

## 7. Finish Tool

```ts
type FinishAuthoringRequest = {
  proposalKind: "raw_task" | "draft_task_tree" | "draft_task_patch";
  proposal: unknown;
  evidenceRefs: string[];
  rationale?: string;
};
```

`finish_authoring` is the only terminal action that can lead to authoring state
mutation.

Flow:

```text
finish_authoring
  -> strict proposal validation
  -> AuthoringCommandService
  -> AuthoringCommandResult
```

## 8. Audit And Diagnostics

Record at minimum:

- loop id;
- session id;
- operation;
- read/search request purpose;
- safe path labels;
- evidence refs;
- omitted/rejected path reasons;
- final loop state;
- final proposal kind;
- authoring command result ref when available.

Diagnostics must not expose:

- raw absolute workspace paths;
- secrets;
- raw prompts;
- provider payloads;
- raw log payloads;
- SQLite payloads.

## 9. Backward Compatibility

Existing one-shot Collaborator behavior remains valid:

```text
request
  -> finish_authoring(proposal)
```

No workspace read/search is required for simple requests.

## 10. Accepted Implementation Notes

The accepted first technical slice is a shared profile seam. It should introduce
the profile/result protocols, terminal action model, and authoring evidence
store contract without adding Collaborator workspace reads or changing execution
Agent behavior.

The implementation should not directly mount Collaborator onto the current
execution `AgentLoop`. If extraction is too large for the first slice, an
adapter boundary is acceptable only if it preserves the profile contract and
keeps Collaborator-specific behavior outside `src/taskweavn/core/loop.py`.

The first slice must preserve:

- append-only transcript behavior;
- provider tool-call ordering;
- step limits;
- metadata and LLM logging;
- evidence/audit refs;
- strict terminal outcome mapping.

Read/search tools, configurable guidance paths, and dedicated frontend
`waiting_for_context` UI are later slices.
