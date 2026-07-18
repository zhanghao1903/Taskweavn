# UI-Backend Communication

> Status: fact-calibrated current architecture
>
> Last verified: 2026-07-10
>
> Original document:
> [ui-backend-communication.original.md](ui-backend-communication.original.md)
>
> Verification record:
> [fix-log/ui-backend-communication.md](fix-log/ui-backend-communication.md)

## 1. Purpose

This document describes the communication boundary that is implemented between
the Plato frontend and the local Taskweavn server runtime. It is a current-state
architecture document, not a proposal for a future public API.

The stable design rule is:

```text
Query   returns a transport-facing projection.
Command submits user intent and returns an acceptance result.
Event   invalidates or advances a projection cursor.
```

The frontend does not read SQLite stores, TaskBus state, PlanStore rows, or raw
domain objects directly. Backend gateways and projection services own those
reads and expose camel-case UI contract models over an HTTP/RPC-style sidecar
transport.

## 2. Current Boundary

### 2.1 Runtime topology

```text
React Main Page / Audit Page
  -> MainPageAdapter / PlatoApi
  -> HTTP JSON requests and EventSource subscription
  -> PlatoUiHttpTransport + route matcher
  -> UiQueryGateway / UiCommandGateway / transport-specific gateways
  -> projection, command, runtime-input, inspection, and execution services
  -> workspace-backed stores and TaskBus

SqliteUiEventSource
  -> finite SSE replay response
  -> frontend event router
  -> snapshot refetch
```

`src/taskweavn/server/main_page.py` assembles the local runtime. The live
workspace assembly includes the query and command gateways, durable Plan and
message stores, ASK storage, TaskBus, token usage, runtime configuration,
workspace inspection, diagnostic export, Runtime Input Router, and a
`SqliteUiEventSource`.

The frontend HTTP path is assembled by:

- `createHttpPlatoApi`, which owns URLs and JSON transport;
- `createHttpMainPageAdapter`, which adapts the API to Main Page operations;
- `useMainPageController` and its hooks, which own local interaction state;
- backend-projected `MainPageSnapshot`, which remains the server-state source
  for the Main Page.

The frontend also retains a mock adapter for test and non-HTTP runtime modes.
That mock path is not evidence of backend state.

### 2.2 Session and workspace identity

Most Main Page operations are session-scoped under:

```text
/api/v1/sessions/{sessionId}/...
```

The route matcher also accepts a workspace-prefixed form:

```text
/api/v1/workspaces/{workspaceId}/sessions/{sessionId}/...
```

`workspaceId` selects a registered workspace runtime. It does not imply that a
new filesystem tree is created per session. A session remains the conversation
and active-work boundary within the selected workspace.

The route matcher can prefix other recognized `/api/v1/...` routes with a
workspace id. The current frontend deliberately uses workspace-prefixed paths
for session operations and token-usage reads when a workspace is selected.

## 3. Contract Models

### 3.1 Serialization rules

Transport models derive from `UiContractModel`:

- Python fields use snake case and JSON fields use lower camel case;
- unknown fields are rejected;
- models are frozen;
- values can be populated by Python name or JSON alias;
- contract serialization uses frontend-compatible aliases.

These models, rather than domain entities, define the frontend/backend schema.

### 3.2 Query response

`QueryResponse[T]` contains:

```text
requestId
ok
data
error
cursor
generatedAt
```

For a successful response, `data` is required and `error` must be absent. For a
failed response, `error` is required. The optional top-level cursor defines a
read or replay boundary when a query supports one.

### 3.3 Command request and response

`CommandRequest[T]` contains:

```text
commandId
sessionId
idempotencyKey?
expectedVersion?
payload
```

`CommandResult` records acceptance or rejection plus affected identities:

```text
commandId
status                         # accepted | rejected
message
affectedTaskRefs
objectRefs
affectedObjects
emittedMessageIds
publishedTaskIds
debugRefs
```

`CommandResponse` contains `requestId`, `ok`, `result`, `error`, and `refresh`.
An `ok: true` response is valid only when the result is accepted. Rejected core
commands are represented by `ok: false`, a rejected result, and a structured
error.

`RefreshHint` contains:

```text
waitForEvents
suggestedQueries
affectedTaskRefs
affectedScopes
```

The frontend may wait for an event or refetch based on that hint. Command
acceptance does not prove that execution has completed; execution state must be
read from a later projection.

### 3.4 Error contract

`ApiError.code` is restricted to:

```text
bad_request
not_found
version_conflict
command_rejected
permission_denied
backend_busy
resync_required
internal_error
idempotency_conflict
```

An error also carries a user-facing message, a retryable flag, and structured
details. Request parsing, method, authentication, and idempotency failures use
HTTP error status codes. A valid command that is rejected by application logic
normally returns HTTP 200 with `CommandResponse.ok: false`; callers must inspect
the envelope as well as the HTTP status.

## 4. Query Surface

### 4.1 `UiQueryGateway`

The current UI query protocol exposes these methods:

| Method | Result |
| --- | --- |
| `get_session_snapshot` | `MainPageSnapshot` |
| `list_session_activity` | `SessionActivityTimelineResult` |
| `list_asks` | `AskListResult` |
| `get_ask` | `AskRequestView` |
| `get_audit_snapshot` | `AuditPageSnapshot` |
| `list_audit_records` | `AuditRecordsResult` |
| `get_audit_record_detail` | `AuditRecordDetail` |
| `get_evidence_detail` | `EvidenceDetail` |

There is no transport query named `getTaskTimeline` in `UiQueryGateway`.
`TaskInteractionTimelineService` exists as an internal server service and feeds
Audit projection, but it is not a standalone current UI endpoint.

### 4.2 Main Page snapshot

`get_session_snapshot` is the primary Main Page read. The projection currently
includes session metadata, active and archived Plan views, compatibility Task
Tree data, planning state, messages, pending confirmations, pending ASKs,
active ASK, result, file-change summary, Audit links, permissions, an event
cursor, and generation time.

Before a snapshot read, `PlatoUiHttpTransport` invokes the configured recovery
gateway on a best-effort basis. Recovery failure is traced but does not prevent
the snapshot query from running.

The snapshot's cursor is passed by the frontend when subscribing to session
events. This is the implemented replay boundary between the initial read and
later invalidations.

### 4.3 Other read gateways

Several HTTP reads are intentionally outside `UiQueryGateway` and are supplied
by focused transport gateways:

- settings readiness and settings configuration;
- runtime configuration schema, effective values, explanations, changes, and
  snapshots;
- workspace catalog, inspection status, diff, evidence, and file content;
- token-usage summaries;
- session lifecycle listing;
- execution-plane task, event, result, error, and evidence reads.

The route surface is therefore larger than the Main Page query protocol. Those
capabilities should not be invented as additional `UiQueryGateway` methods in
frontend code.

## 5. Command Surface

### 5.1 `UiCommandGateway`

The current UI command protocol exposes:

| Method | Intent |
| --- | --- |
| `append_session_input` | append direct session input |
| `generate_task_tree` | generate or revise authoring state |
| `update_task_node` | update an authoring/pending task node |
| `append_task_input` | add task-scoped guidance |
| `publish_task_tree` | publish the active Plan or legacy draft tree |
| `archive_plan` | archive a durable or compatibility Plan |
| `retry_task` | retry a failed task |
| `stop_task` | request task stop/interrupt behavior |
| `resolve_confirmation` | answer a pending confirmation |
| `answer_ask` | answer an execution ASK |
| `answer_authoring_ask_batch` | answer authoring ASKs in one command |
| `repair_authoring_state` | repair accepted authoring state |
| `defer_ask` | defer an ASK |
| `cancel_ask` | cancel an ASK |

Session create, rename, and delete are handled by the session lifecycle
gateway. Explicit execution dispatch is handled by an execution-trigger
gateway. Diagnostic export and runtime configuration mutation are also focused
transport capabilities rather than `UiCommandGateway` methods.

Publish, retry, and ASK-answer transport handlers can request immediate
execution dispatch after the underlying command is accepted. A dispatch
failure does not rewrite an already accepted publish/retry/answer result into a
different domain command; dispatch status is reported through response details
and refresh/debug data.

### 5.2 Runtime Input Router

The canonical Main Page input route is:

```text
POST /api/v1/sessions/{sessionId}/runtime-input/route
```

The workspace-prefixed form injects the path workspace id and rejects a body
workspace id that disagrees with it. The route also rejects a body session id
that disagrees with the path.

Runtime Input is not modeled as a plain UI command. The router interprets the
input and returns `QueryResponse[RuntimeInputRouteResult]`. A route result can
contain a read-only inquiry answer, Activity items, a downstream command
response, clarification, or another routing outcome. Any mutation still flows
through an owned command service; interpretation alone is not authorization to
mutate workspace state.

### 5.3 Idempotency and versions

When both an idempotency key and a command-idempotency store are configured,
the HTTP transport caches the completed response by `(sessionId,
idempotencyKey)`. Repeating the same route and request replays the cached
response. Reusing the key for a different request returns HTTP 409 with
`idempotency_conflict`.

`expectedVersion` is optional and is forwarded only by command paths that own
version checks. It is not a universal compare-and-swap guarantee for every
route.

## 6. Implemented HTTP Route Families

`src/taskweavn/server/ui_http_routes.py` is the route-matching source of truth.
The current families are:

| Family | Implemented routes |
| --- | --- |
| Sidecar | `GET /`, `GET /api/v1/health` |
| Settings | `GET /settings/readiness`, `POST /settings/readiness/recheck`, `GET/PATCH /settings/config` |
| Runtime config | `PATCH /runtime/config`, `GET /runtime/config/schema`, `/effective`, `/explain`, `/changes`, `/snapshots/{configHash}` |
| Workspace catalog | `GET /workspaces` |
| Workspace inspection | `GET /inspection/status`, `GET /inspection/diff`, `POST /inspection/evidence`, `GET /files/content` |
| Usage | `GET /usage/token-summary` |
| Session lifecycle | `GET/POST /sessions`, `PATCH /sessions/{sessionId}`, `POST /sessions/{sessionId}/delete` |
| Session reads | `GET /sessions/{sessionId}/snapshot`, `/activity`, `/audit`, `/audit/records`, `/audit/records/{recordId}`, `/audit/evidence/{evidenceId}` |
| Runtime input | `POST /sessions/{sessionId}/runtime-input/route` |
| Plan/task authoring | `POST /input`, `/task-tree/generate`, `/task-tree/publish`, `/plans/{planId}/archive`, `/authoring/repair`, `/authoring/raw-tasks/{rawTaskId}/asks/answers` |
| Task commands | `PATCH /tasks/{taskNodeId}`, `POST /tasks/{taskNodeId}/input`, `/retry`, `/stop` |
| Audit by task | `GET /tasks/{taskNodeId}/audit`, `/tasks/{taskNodeId}/audit/records` |
| Interaction | `GET /asks`, `GET /asks/{askId}`, `POST /asks/{askId}/answer`, `/defer`, `/cancel`, `POST /confirmations/{confirmationId}/respond` |
| Execution handoff | `POST /sessions/{sessionId}/execution/dispatch` |
| Events and support | `GET /sessions/{sessionId}/events`, `POST /client-logs/errors`, `POST /diagnostics/export` |
| Execution plane | `POST /api/v1/tasks`, `GET /tasks/{executionId}`, `POST /cancel`, `POST /retry`, `GET /events`, `/result`, `/error`, `/evidence` |

Paths in the table after `/api/v1` are abbreviated where the prefix is
unambiguous. The execution-plane paths are separate from session-scoped
TaskNode commands even though both contain a `tasks` segment.

## 7. Event and SSE Contract

### 7.1 Event shape

`UiEvent` contains:

```text
eventId
sessionId
eventType
cursor
taskNodeIds
taskRefs
messageIds
commandId?
payload
createdAt
```

Events are thin invalidation and identity hints. They are not authoritative
copies of a Main Page or Audit ViewModel. The frontend refetches projections
after receiving them.

### 7.2 Backend event types

The backend contract currently allows:

- session: `session.status_changed`, `session.resync_required`;
- task: `task.tree.changed`, `task.node.changed`;
- messages and interaction: `message.appended`, `confirmation.created`,
  `confirmation.resolved`, `ask.created`, `ask.answered`, `ask.deferred`,
  `ask.cancelled`, `ask.expired`;
- output: `result.updated`, `file_changes.updated`;
- Audit: `audit.summary_updated`, `audit.records_changed`,
  `audit.record_updated`, `audit.evidence_hidden`, `audit.snapshot_stale`;
- command: `command.completed`, `command.failed`.

Declaring an event type does not prove that every corresponding runtime change
currently emits it. Production call sites inspected for this calibration emit
task-tree, task-node, and Audit-record invalidations from selected runtime
paths; event-constructor tests cover a broader contract than current producer
wiring.

### 7.3 Storage and cursor behavior

`SqliteUiEventSource` is both an appendable store and a session-scoped replay
source. It persists the serialized event and enforces uniqueness for event id
and `(sessionId, cursor)`.

Subscription behavior is:

1. With no cursor, return all retained events for the session.
2. With a retained cursor, return later events.
3. With an unavailable cursor, first return `session.resync_required`, then the
   retained events available for that session.

`StaticUiEventSource` provides deterministic test replay. The default
`ResyncOnlyEventSource` emits only `session.resync_required` when no durable
source is configured.

Each SSE frame uses the event cursor as `id`, the event type as `event`, and the
serialized `UiEvent` as `data`.

### 7.4 Current SSE limitation

The current HTTP SSE helper materializes `event_source.subscribe(...)` into a
tuple and serializes it with `sse_stream`. `sse_stream` explicitly accepts a
finite batch. Therefore the implemented endpoint provides SSE framing and
cursor replay, but it does not attach the response to a continuously blocking
live event stream.

This distinction matters: the endpoint must not be documented as a complete
real-time event bus until live attachment, reconnect behavior, and production
delivery semantics are implemented and tested.

### 7.5 Current frontend event coverage

`createHttpPlatoApi` opens `EventSource`, subscribes to the generic `message`
event and a list of named event types, parses the JSON body, and forwards each
event to the Main Page adapter. The Main Page event router currently refetches
for every recognized event. `session.resync_required` temporarily marks the
connection as resyncing; `command.failed` may also expose a sanitized message.

There is a current contract-parity gap:

- backend `UiEventType` includes all five ASK event variants;
- frontend `UiEventType` and its named EventSource registration list omit those
  ASK variants;
- no inspected production call site currently emits the ASK event constructors.

The architecture must therefore not claim end-to-end named ASK event support.
ASK consistency currently depends on command refresh/refetch and snapshot or
Activity reads rather than a proven ASK event path.

## 8. Frontend Integration Rules

The current frontend follows these rules:

1. `httpMainPageAdapter` resolves a preferred session or selects one from the
   session list, then loads a Main Page snapshot.
2. The controller subscribes from `snapshot.cursor` after snapshot data exists.
3. Duplicate event cursors are ignored within the active subscription.
4. Duplicate `session.resync_required` events are keyed by cursor and reason.
5. Other recognized events request a snapshot refetch rather than patching
   domain state in the browser.
6. After a command, `handleCommandResponse` refetches when refresh hints,
   affected identities, emitted messages, or published tasks require it.
7. Frontend state owns pending controls, selection, overlays, input drafts, and
   display errors; backend projections own session, Plan, TaskNode, ASK,
   confirmation, result, file, Activity, and Audit facts.

`PlatoApi` covers the Main Page routes it consumes, but it is not a generated
client with guaranteed route parity. For example, the backend supports an ASK
detail query while the current `PlatoApi` interface exposes ASK listing and ASK
commands, not a dedicated `getAsk` method.

## 9. Authentication and Deployment Boundary

The stdlib sidecar server binds to loopback hosts by default. Remote binding
requires an explicit configuration override.

`SidecarAuth` is optional. When configured:

- JSON routes accept `Authorization: Bearer <token>`;
- the events route can accept the same token through a configurable query
  parameter because browser `EventSource` cannot set custom headers.

The stock frontend `ApiClient` currently has no bearer-token option, and
`subscribeSessionEvents` does not append the SSE query token. Optional sidecar
authentication is therefore a backend capability, not a complete end-to-end
frontend integration in the inspected code.

## 10. Consistency and Failure Rules

- A query response is a projection at `generatedAt`, optionally bounded by a
  cursor. It is not a transaction held open in the UI.
- A command is accepted or rejected synchronously at the application boundary;
  later task execution is observed through projections.
- Event payloads identify affected state and trigger reads; they do not replace
  durable stores.
- An unavailable event cursor requires a full projection resync.
- Snapshot recovery is best effort and read availability takes priority over
  surfacing recovery exceptions through the snapshot endpoint.
- Transport validation rejects method, path/body identity, and schema mismatch
  before gateway dispatch.
- UI command idempotency is active only when the request supplies a key and the
  runtime supplies an idempotency store.
- Activity is a user-readable history projection. Audit is a separate evidence
  and disclosure surface. Neither is a replacement for the other.

## 11. Current Limits

The following are current facts, not hidden roadmap assumptions:

1. SSE replay is finite and does not implement continuous live attachment.
2. Backend and frontend event type lists are not fully aligned for ASK events.
3. Runtime event constructors have broader test coverage than production
   producer wiring.
4. Frontend route coverage is hand-written and not guaranteed to match every
   backend route.
5. Optional bearer/query-token authentication is not wired through the stock
   frontend client.
6. `expectedVersion` is command-specific rather than universally enforced.
7. The transport is a local product sidecar contract, not a versioned public
   multi-tenant API.
8. Legacy Task Tree compatibility remains in snapshot and command paths while
   Product 1.1 Plan/TaskNode storage is the primary direction.

## 12. Source Map

Primary backend sources:

- `src/taskweavn/server/ui_contract/base.py`
- `src/taskweavn/server/ui_contract/envelopes.py`
- `src/taskweavn/server/ui_contract/errors.py`
- `src/taskweavn/server/ui_contract/events.py`
- `src/taskweavn/server/ui_contract/gateway_protocols.py`
- `src/taskweavn/server/ui_contract/gateways.py`
- `src/taskweavn/server/ui_contract/command_gateway.py`
- `src/taskweavn/server/runtime_input_router.py`
- `src/taskweavn/server/ui_events.py`
- `src/taskweavn/server/ui_http.py`
- `src/taskweavn/server/ui_http_routes.py`
- `src/taskweavn/server/ui_http_commands.py`
- `src/taskweavn/server/ui_http_sse.py`
- `src/taskweavn/server/main_page.py`

Primary frontend sources:

- `frontend/src/shared/api/client.ts`
- `frontend/src/shared/api/types.ts`
- `frontend/src/shared/api/platoApi.ts`
- `frontend/src/app/platoRuntime.ts`
- `frontend/src/pages/main-page/httpMainPageAdapter.ts`
- `frontend/src/pages/main-page/useMainPageController.ts`
- `frontend/src/pages/main-page/useMainPageEventSubscription.ts`
- `frontend/src/pages/main-page/runtime/eventRouter.ts`
- `frontend/src/pages/main-page/runtime/commandRefresh.ts`

## 13. Summary

The implemented UI/backend boundary is a local HTTP/RPC-style sidecar contract
built around query projections, command intent, and event invalidation. The
query and command gateways, Runtime Input Router, workspace-aware routes,
Activity, Audit, settings, diagnostics, usage, and execution-plane routes are
implemented. SSE cursor replay is implemented as a finite batch; continuous
live delivery, full ASK event parity, and frontend authentication support are
not implemented end to end and must remain explicit limits.
