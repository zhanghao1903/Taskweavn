# Runtime Input Router API Contract

> Status: implemented for RIR-1/RIR-2 deterministic foundation plus
> Read-Only Inquiry result envelope
>
> Last Updated: 2026-06-14
>
> Related:
> [Runtime Input Router Contract](../plans/feature/runtime-input-router-contract.md),
> [Runtime Input Router Technical Design](../plans/feature/runtime-input-router-contract-technical-design.md),
> [Session Conversation / Activity Timeline](../plans/feature/session-conversation-activity-timeline.md)

---

## 1. Endpoint

```text
POST /api/v1/sessions/{sessionId}/runtime-input/route
POST /api/v1/workspaces/{workspaceId}/sessions/{sessionId}/runtime-input/route
```

The workspace-scoped route is an alias through the existing multi-workspace
runtime router. `sessionId` in the body must match the path. When the
workspace-scoped route is used, the path `workspaceId` is injected into the
validated request as an opaque renderer-safe id for downstream evidence links.
If the body also provides `workspaceId`, it must match the path.

---

## 2. Request

```json
{
  "commandId": "route-1",
  "sessionId": "session-1",
  "workspaceId": "workspace-1",
  "content": "stop",
  "mode": "auto",
  "selection": {
    "scopeKind": "task",
    "planId": "plan-1",
    "taskNodeId": "task-1",
    "refs": []
  },
  "inquiryRefs": [
    {
      "kind": "file",
      "path": "src/example.ts",
      "label": "src/example.ts"
    }
  ],
  "clientState": {
    "activeAskId": null,
    "activeConfirmationId": null
  }
}
```

Rules:

- `content` is required, trimmed, and capped at 8000 characters.
- `mode` defaults to `auto`.
- `workspaceId` is optional on active-session routes and is injected from the
  workspace-scoped path when present.
- `inquiryRefs` is optional and is used only when the Router selects
  `question/no_effect/read_only_inquiry`. It carries already-normalized
  `ReadOnlyInquiryRef` anchors for file, diff, Audit, diagnostic, result, and
  Activity evidence.
- `selection.refs` remains the generic object-ref surface used by Router
  classification. For read-only inquiry, backend may translate safe selection
  refs and merges them with explicit `inquiryRefs`.
- `inquiryRefs` never authorizes guidance, Plan/TaskNode mutation, TaskBus
  work, workspace execution, or file writes.
- `scopeKind=plan` requires `planId`.
- `scopeKind=task` requires `taskNodeId`.
- `clientState` is a hint; backend ASK and confirmation projections remain
  authoritative.

---

## 3. Response

The endpoint returns `QueryResponse<RuntimeInputRouteResult>`.

```json
{
  "requestId": "route-1",
  "ok": true,
  "data": {
    "sessionId": "session-1",
    "decision": {
      "id": "rir-...",
      "intent": "command",
      "scope": {
        "kind": "task",
        "planId": null,
        "taskNodeId": "task-1"
      },
      "confidence": "high",
      "sideEffect": "state_effect",
      "dispatchTarget": "existing_command",
      "explanation": "Input matched the deterministic stop-task command.",
      "relatedRefs": []
    },
    "outcome": {
      "status": "dispatched",
      "userMessage": "The selected task stop command was dispatched.",
      "recoveryActions": []
    },
    "activity": {
      "kind": "router_interpretation"
    },
    "commandResponse": null,
    "inquiryResult": null,
    "generatedAt": "2026-06-14T00:00:00Z"
  },
  "error": null,
  "cursor": null,
  "generatedAt": "2026-06-14T00:00:00Z"
}
```

`commandResponse` is present only when the Router dispatches an existing
command-backed operation.

`inquiryResult` is present only when `dispatchTarget=read_only_inquiry` reaches
Read-Only Inquiry Context. It carries the answer-only result, evidence refs,
warnings, optional answer Activity projection, and remains `no_effect`.

---

## 4. RIR-1/RIR-2 Deterministic Routes And Inquiry

Implemented:

- active ASK answer -> `answer_ask`;
- active confirmation clear yes/no -> `resolve_confirmation`;
- selected task `stop` phrase -> `stop_task`;
- selected task `retry` phrase -> `retry_task`;
- question route -> Read-Only Inquiry Context when session context is available;
- workspace-scoped question route propagates opaque `workspaceId` to Inquiry so
  file/diff/Audit evidence hrefs can preserve workspace context;
- explicit `inquiryRefs` are passed to Inquiry and can cite file, diff, Audit,
  diagnostic, result, or Activity evidence without overloading Router
  `selection.refs`;
- unsupported guidance/execution request -> non-mutating structured response.

Read-Only Inquiry result shape:

```json
{
  "inquiryId": "route-1",
  "sessionId": "session-1",
  "scope": {
    "kind": "session",
    "planId": null,
    "taskNodeId": null
  },
  "status": "answered",
  "answer": {
    "title": "Session status",
    "body": "Session 'Session' is running.",
    "confidence": "medium"
  },
  "evidenceRefs": [
    {
      "kind": "session_status",
      "refId": "session:session-1:status",
      "parentRefId": null,
      "label": "Session Session",
      "disclosure": "public",
      "truncated": false
    }
  ],
  "warnings": [],
  "activity": {
    "kind": "answer",
    "sideEffect": "no_effect"
  },
  "generatedAt": "2026-06-14T00:00:00Z"
}
```

Deferred:

- LLM classifier;
- LLM-backed read-only inquiry answers over bounded context;
- guidance persistence;
- Plan/TaskNode patch/create/delete commands;
- publish/cancel routing;
- workspace execution handoff.

---

## 5. Error Cases

- `400 bad_request`: invalid body, invalid selection scope, or path/body
  session mismatch.
- `405 bad_request`: method other than `POST`.
- `503 internal_error`: Runtime Input Router is not configured.

Low-confidence or deferred product capabilities should return successful
`QueryResponse` with `outcome.status=unsupported` or
`outcome.status=needs_clarification`, not an API error.
