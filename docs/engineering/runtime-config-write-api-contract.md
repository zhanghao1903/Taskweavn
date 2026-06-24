# Runtime Config Write API Contract

> Status: C5.5 design gate accepted; routes are not implemented.
> Related Store Contract: [Runtime Config Change Store](runtime-config-change-store.md)
> Related Plan:
> [Centralized Runtime Configuration](../plans/feature/centralized-runtime-configuration.md)
> Last Updated: 2026-06-24

## 1. Purpose

This document defines the future HTTP write boundary for centralized runtime
configuration. C5.1-C5.4 already provide:

- typed patch/change/snapshot models;
- durable SQLite change and snapshot storage;
- backend mutation validation;
- read gateway methods for persisted change facts.

C5.5 is a design gate only. It prevents Settings UI or external API work from
inventing runtime config write semantics in route handlers.

## 2. Non-Goals

- Do not implement the routes in C5.5.
- Do not add Settings UI.
- Do not publish ConfigBus events.
- Do not apply live mutations to running agents.
- Do not make app-specific playbooks, such as WeChat send steps, runtime config.
- Do not expose raw secrets through config writes or snapshots.

## 3. Source Of Truth

The route layer must delegate to:

- `RuntimeConfigPatch` for request intent;
- `DefaultRuntimeConfigMutationService` for validation and persistence;
- `SqliteRuntimeConfigChangeStore` for durable replay/query;
- `RuntimeConfigChange` and `RuntimeConfigSnapshotRecord` for response facts.

Route handlers must not:

- validate config keys ad hoc;
- normalize values independently;
- compute effective statuses independently;
- write directly to SQLite tables.

## 4. Route Candidates

### 4.1 Submit Runtime Config Patch

```text
PATCH /api/v1/runtime/config
```

Use this route for controlled runtime config mutation from Settings,
Diagnostics, tests, or future operator tools.

### 4.2 List Runtime Config Changes

```text
GET /api/v1/runtime/config/changes?workspaceId=...&sessionId=...&taskId=...
```

Use this route to inspect persisted config changes for Settings, Diagnostics,
and Audit evidence.

### 4.3 Deferred Snapshot HTTP Route

No snapshot HTTP route is required for the first write API slice.

The backend already has `RuntimeConfigGateway.get_snapshot(config_hash)`.
Expose a snapshot route only when Diagnostics or Audit needs direct HTTP access.

Candidate later route:

```text
GET /api/v1/runtime/config/snapshots/{configHash}
```

## 5. Patch Request

```ts
type RuntimeConfigPatchRequest = {
  schemaVersion: "plato.runtime_config_patch_request.v1";
  idempotencyKey: string;
  scope: {
    level: "global" | "workspace" | "session" | "task";
    workspaceId?: string | null;
    sessionId?: string | null;
    taskId?: string | null;
  };
  values: Record<string, unknown>;
  expectedBaseConfigHash?: string | null;
  reason?: string | null;
  dryRun?: boolean;
  allowPartialAcceptance?: boolean;
};
```

Rules:

- `idempotencyKey` is required for non-dry-run writes.
- `dryRun=true` may omit `idempotencyKey`; no change or snapshot is persisted.
- `scope.level=process` and `scope.level=agent_run` are not writable through
  HTTP in Product 1.0 / 1.1.
- `values` must be sparse. It is never a full effective config snapshot.
- The backend owns actor metadata. Clients must not send trusted actor fields.
- `expectedBaseConfigHash` enables optimistic concurrency. If supplied and
  stale, the route returns a recorded rejected change rather than mutating.

## 6. Partial Acceptance Policy

Backend service support:

- `DefaultRuntimeConfigMutationService` can represent partial acceptance.
- This is useful for Diagnostics/admin tooling because it exposes every key's
  validation result in one response.

HTTP route default:

- `allowPartialAcceptance=false` by default.
- Settings UI should not silently apply one valid key while another key fails.
- If any key would be rejected and `allowPartialAcceptance=false`, the route
  must return a rejected change with no accepted values.
- `allowPartialAcceptance=true` may be accepted only for privileged
  Diagnostics/admin/test clients.

Rationale:

- User-facing Settings needs predictable all-or-recorded behavior.
- Backend ledger still supports partial facts when the caller explicitly asks
  for that mode.

## 7. Patch Response

```ts
type RuntimeConfigPatchResponse = {
  schemaVersion: "plato.runtime_config_patch_response.v1";
  change: RuntimeConfigChange;
  snapshotRef?: {
    snapshotId: string;
    configHash: string;
  } | null;
  replayed: boolean;
  warnings: RuntimeConfigWriteWarning[];
};

type RuntimeConfigWriteWarning = {
  code:
    | "pending_restart"
    | "pending_next_agent_run"
    | "pending_next_task"
    | "higher_priority_source_active"
    | "partial_acceptance";
  message: string;
  configKeys: string[];
};
```

Existing HTTP envelope remains:

```json
{
  "ok": true,
  "data": {
    "schemaVersion": "plato.runtime_config_patch_response.v1"
  },
  "error": null
}
```

Rejected validation results are domain facts, not transport errors:

- unknown config key;
- invalid value;
- unsupported scope;
- stale base config;
- startup-only pending boundary;
- secret-not-patchable.

Transport errors are reserved for:

- malformed JSON;
- missing required request fields;
- missing authorization;
- idempotency conflict;
- store unavailable;
- internal service error.

## 8. Change List Response

```ts
type RuntimeConfigChangeListResponse = {
  schemaVersion: "plato.runtime_config_change_list.v1";
  scope: RuntimeConfigScope;
  changes: RuntimeConfigChange[];
  nextCursor?: string | null;
};
```

Initial implementation may omit cursor pagination if the query is scoped and
bounded. Add `limit` and cursor support before exposing broad global history.

## 9. Idempotency Semantics

For `PATCH /api/v1/runtime/config`:

- idempotency scope is `idempotencyKey + RuntimeConfigScope`;
- same key + same canonical request returns the original response with
  `replayed=true`;
- same key + different canonical request returns:

```json
{
  "ok": false,
  "error": {
    "code": "idempotency_conflict",
    "message": "runtime config idempotency key was reused for a different patch"
  }
}
```

The route layer should compare canonical request facts before returning replay:

- scope;
- values;
- expected base hash;
- dry-run flag;
- partial acceptance flag.

## 10. Authorization

Product 1.0 / 1.1 rule:

- writes are local-sidecar only;
- no remote runtime config write API without an explicit auth model;
- Settings UI can request user-visible workspace/session/task keys;
- process-level, agent-run-level, secret, and migration-only keys are not
  writable from ordinary Settings UI.

Future permission names:

```text
runtime_config.read
runtime_config.write
runtime_config.write_admin
runtime_config.write_secrets
```

The mutation service does not authorize by itself. Route/API boundary owns
authorization and actor construction.

## 11. User-Facing Copy Rules

Runtime config writes must distinguish:

- active now;
- pending next context build;
- pending next LLM call;
- pending next action;
- pending next agent run;
- pending next task;
- pending next session;
- pending restart;
- rejected.

Recommended UI copy:

| Effective Status | User Copy |
|---|---|
| `active` | Applied now. |
| `pending_next_context_build` | Applies when context is rebuilt. |
| `pending_next_llm_call` | Applies on the next model call. |
| `pending_next_action` | Applies before the next action. |
| `pending_next_agent_run` | Applies to the next agent run. |
| `pending_next_task` | Applies to the next task. |
| `pending_next_session` | Applies to the next session. |
| `pending_restart` | Requires restart. |

Settings UI must not imply that a running Agent has changed behavior unless the
effective status is `active`.

## 12. Error Codes

Transport-level error candidates:

| Code | HTTP | Retry | Meaning |
|---|---:|---|---|
| `bad_request` | 400 | no | Malformed request or missing required fields. |
| `unauthorized` | 401 | maybe | Caller is not authenticated. |
| `forbidden` | 403 | no | Caller lacks runtime config write permission. |
| `idempotency_conflict` | 409 | no | Same key reused for a different patch. |
| `runtime_config_store_unavailable` | 503 | yes | Store is not configured or not writable. |
| `internal_error` | 500 | maybe | Unexpected server failure. |

Domain-level rejections stay inside `RuntimeConfigChange.rejectedValues`.

## 13. Acceptance Criteria For Implementation

Before implementing HTTP write routes:

- request/response schemas above are accepted;
- authorization policy is accepted;
- partial acceptance default is accepted;
- Settings UI copy for pending/rejected states is accepted;
- idempotency conflict behavior is tested;
- existing read-only routes remain behavior-compatible;
- no app-specific automation config is introduced.

## 14. Recommended Implementation Slices

1. Add route parser and adapter tests with the mutation service mocked.
2. Add happy-path accepted/no-op/rejected transport tests.
3. Add idempotency replay/conflict tests.
4. Add authorization placeholder tests.
5. Add Settings UI only after the route behavior is stable.
6. Add ConfigBus only after Settings and runtime consumer boundaries are clear.

## 15. Open Questions

1. Should Product 1.0 expose write routes only in developer/diagnostics mode?
2. Should `allowPartialAcceptance=true` be available to local Settings UI, or
   only to tests/admin diagnostics?
3. Should change listing be workspace-scoped by default when no scope is
   provided?
4. Should snapshot HTTP access be diagnostics-only or available to Audit Page?
