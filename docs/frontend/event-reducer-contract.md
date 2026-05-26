# Event Reducer Contract

> Status: draft
> Last Updated: 2026-05-24
> Scope: Frontend event reducer behavior for Main Page and Audit Page runtime data.
> Related: `docs/frontend/ui-viewmodel-contract.md`, `docs/frontend/api-ui-mapping.md`, `docs/engineering/audit-page-contract.md`, `docs/ux/screen-state-spec.md`, `docs/product/plato-ui-api-contract.md`

## 1. Purpose

This document defines how the frontend consumes backend UI events and updates local runtime state.

Events are notifications that facts changed. They are not a replacement for queries. When a patch is ambiguous, unsafe, malformed, or refers to unknown objects, the reducer must request a snapshot resync.

## 2. Reducer Inputs And Outputs

```ts
type RuntimeState = {
  snapshot: MainPageSnapshot | AuditPageSnapshot | null;
  local: MainPageLocalState | AuditPageLocalState;
  pendingCommands: Record<string, PendingCommandState>;
  event: EventConnectionState;
  lastAppliedCursor: EventCursor | null;
};

type EventReducerInput =
  | { kind: "snapshot.loaded"; snapshot: MainPageSnapshot | AuditPageSnapshot }
  | { kind: "event.received"; event: UiEvent }
  | { kind: "event.error"; error: ApiError | Error }
  | { kind: "command.accepted"; result: CommandResult }
  | { kind: "command.rejected"; error: ApiError }
  | { kind: "resync.started"; reason: string }
  | { kind: "resync.finished"; snapshot: MainPageSnapshot | AuditPageSnapshot }
  | { kind: "resync.failed"; error: ApiError | Error };
```

The reducer output is a new runtime state plus side effect requests.

```ts
type EventReducerEffect =
  | { kind: "query"; name: string; params: Record<string, unknown> }
  | { kind: "resync"; reason: string }
  | { kind: "restart_events"; cursor: EventCursor | null }
  | { kind: "log"; level: "debug" | "warn" | "error"; message: string };
```

The reducer should be pure where practical. Network requests should be emitted as effects and executed by the API layer.

## 3. Reducer Principles

1. Snapshot is the base truth for UI projection.
2. Events patch only known, safe portions of the snapshot.
3. Command accepted is not final truth.
4. Duplicate events must be ignored idempotently.
5. Out-of-order, unknown, or malformed events trigger resync when they may affect visible state.
6. Unsupported events must never crash the UI.
7. High-risk controls are disabled while state is stale or resyncing.
8. User selection should be restored after resync when the selected task or record still exists.

## 4. Event Type Contract

```ts
type UiEventType =
  | "session.status_changed"
  | "session.resync_required"
  | "task.tree.changed"
  | "task.node.changed"
  | "message.appended"
  | "confirmation.created"
  | "confirmation.resolved"
  | "result.updated"
  | "file_changes.updated"
  | "audit.summary_updated"
  | "audit.records_changed"
  | "audit.record_updated"
  | "audit.evidence_hidden"
  | "audit.snapshot_stale"
  | "command.completed"
  | "command.failed";
```

Backend contract models and builders for `audit.records_changed`,
`audit.record_updated`, `audit.evidence_hidden`, and `audit.snapshot_stale`
exist additively. Runtime emission and frontend handling are still future work.

## 5. Event Handling Table

| Event | Required Reducer Behavior | Preferred Effect |
|---|---|---|
| `session.status_changed` | Patch `session` status-related fields if payload is complete; otherwise mark resync. | Query session overview or snapshot. |
| `session.resync_required` | Enter `resyncing`; disable high-risk controls. | Full session snapshot query. |
| `task.tree.changed` | Replace or re-query TaskTreeView; preserve selection if possible. | Query task tree or snapshot. |
| `task.node.changed` | Patch known node fields if payload has full card; otherwise query node/detail. | Query task node detail when selected. |
| `message.appended` | Append message if not duplicate and session matches. | Query messages if payload lacks full message. |
| `confirmation.created` | Add pending confirmation and update affected task badge. | Query pending confirmations or task detail. |
| `confirmation.resolved` | Mark confirmation resolved, clear local resolving state, update messages/task badge. | Query task detail if affected task is selected. |
| `result.updated` | Replace result card or mark result stale. | Query result. |
| `file_changes.updated` | Replace file summary or mark file summary stale. | Query file changes. |
| `audit.summary_updated` | Patch audit summary/link/verdict where visible. | Query audit summary or AuditPageSnapshot. |
| `audit.records_changed` | Refresh audit records for current scope/filter. | Query AuditPageSnapshot or records. |
| `audit.record_updated` | Refresh the selected record detail if it matches; otherwise refresh visible list/overview if the record is in scope. | Query selected record detail or AuditPageSnapshot. |
| `audit.evidence_hidden` | Mark affected evidence stale/hidden only if payload is complete; otherwise refetch detail. | Query selected record detail or evidence detail. |
| `audit.snapshot_stale` | Enter stale/resync for the current Audit Page scope. | Query AuditPageSnapshot. |
| `command.completed` | Mark pending command completed; wait for fact events if no affected data. | None or targeted query. |
| `command.failed` | Mark pending command failed; show user-visible local error if command originated from current UI. | None or query affected view. |

## 6. Unsupported Event Handling

Unsupported event handling must be explicit.

| Case | Behavior |
|---|---|
| Unknown `eventType` | Log warning, store cursor, do not crash. If payload declares affected visible ids, request resync. |
| Known type with malformed payload | Log warning and request resync. |
| Event for another session | Ignore and log debug. |
| Event cursor older than or equal to `lastAppliedCursor` | Ignore as duplicate or stale. |
| Event cursor gap detected | Request resync. |
| Event references unknown task/message/record visible in current view | Request resync. |
| Event references unknown object not visible in current view | Prefer targeted query; full resync only if target cannot be scoped. |

Unknown event types must not display raw payload to the user.

## 7. Cursor And Ordering

Reducer rules:

1. Maintain `lastAppliedCursor`.
2. Apply an event only after validating `sessionId`, cursor order, and schema.
3. Ignore duplicates.
4. If the event stream reconnects with no cursor, query fresh snapshot before applying new events.
5. If backend reports cursor expired, enter stale/resync flow.

The cursor comparison implementation belongs to the API adapter because cursor format is transport-owned.

## 8. Command Lifecycle

```ts
type PendingCommandState = {
  commandId: string;
  kind:
    | "append_session_input"
    | "generate_task_tree"
    | "update_task_node"
    | "append_task_input"
    | "publish_task_tree"
    | "resolve_confirmation"
    | "cancel_task"
    | "retry_task";
  status: "submitting" | "accepted" | "completed" | "failed";
  affectedTaskNodeIds: TaskNodeId[];
  createdAt: string;
  error?: ApiError | null;
};
```

Command rules:

- `submitting`: local network request is in flight.
- `accepted`: backend accepted the command, but UI facts are not final.
- `completed`: backend emitted `command.completed` or affected facts arrived.
- `failed`: backend rejected command or emitted `command.failed`.

UI components may show spinners from pending command state, but must not mutate canonical statuses directly.

## 9. Confirmation Lifecycle

```text
pending
  -> user selects option
  -> local resolving
  -> command accepted
  -> confirmation.resolved event
  -> resolved
```

Failure paths:

```text
pending
  -> local resolving
  -> command rejected or command.failed
  -> local resolve_failed
  -> backend confirmation remains pending unless event says otherwise
```

Expiration path:

```text
pending
  -> confirmation.resolved with expired status, or targeted query returns expired
  -> expired
```

The reducer must never mark backend confirmation `resolved` only because a respond command was accepted.

## 10. Stale Snapshot And Resync Behavior

The reducer enters `stale` or `resyncing` when:

- `session.resync_required` arrives;
- cursor expires;
- cursor gap is detected;
- an event is malformed but affects visible state;
- command returns `version_conflict` or `resync_required`;
- snapshot query says current version is older than server version.

Resync behavior:

1. Set `local.sync = { kind: "resyncing", reason }`.
2. Disable publish, edit, cancel, retry, and confirmation submit.
3. Keep read-only content visible.
4. Query the relevant snapshot.
5. Replace snapshot atomically.
6. Restore selection by id when possible.
7. Restart event stream from new cursor.
8. If resync fails, set `local.sync = { kind: "stale", reason }` and show retry.

## 11. Main Page Event Patch Requirements

Main Page may patch in place only when the event payload includes a complete frontend ViewModel fragment:

- full `SessionMessageView` for `message.appended`;
- full `ConfirmationActionView` for `confirmation.created`;
- full `TaskNodeCardView` for `task.node.changed`;
- full `ResultCardView` for `result.updated`;
- full `FileChangeSummaryView` for `file_changes.updated`;
- full `AuditSummaryView` for `audit.summary_updated`.

If payload is only ids and reason, issue targeted query.

## 12. Audit Page Event Patch Requirements

Audit Page should favor targeted query over local reconstruction. Audit records are evidence and must not be guessed from raw events in the browser.

Allowed patches:

- replace overview if payload includes full `AuditOverviewView`;
- replace selected record if payload includes full `AuditRecordDetailView`;
- append a record only if payload includes full `AuditRecordView` and its
  scope/filter matches current view.
- update hidden/redacted indicators only if `audit.evidence_hidden` includes
  affected record and evidence ids for the current scope.

Otherwise query `AuditPageSnapshot` or scoped audit records.

## 13. Mock Event Scenarios

The mock event layer must cover:

| Scenario | Events |
|---|---|
| input becomes draft | `message.appended`, `task.tree.changed` |
| publish starts execution | `task.tree.changed`, `task.node.changed`, `session.status_changed` |
| running progress | repeated `message.appended`, `task.node.changed` |
| confirmation created | `confirmation.created`, `message.appended`, `task.node.changed` |
| confirmation resolved | `confirmation.resolved`, `message.appended`, `task.node.changed` |
| result complete | `result.updated`, `file_changes.updated`, `audit.summary_updated`, `session.status_changed` |
| task failed | `task.node.changed`, `message.appended`, `command.failed` if command related |
| audit record arrives | `audit.records_changed`, `audit.summary_updated` |
| audit record detail changes | `audit.record_updated` |
| audit evidence is hidden or redacted | `audit.evidence_hidden` |
| audit snapshot becomes stale | `audit.snapshot_stale` |
| unsupported event | unknown type with harmless payload |
| cursor expired | stream error or `session.resync_required` |
| malformed visible event | bad payload, then resync |

## 14. Acceptance Criteria

- Reducer handles every declared event type.
- Unsupported events do not crash the UI.
- Command accepted does not mutate final canonical status.
- Confirmation resolution waits for backend fact or query result.
- Cursor duplicate, gap, and expired cases are covered.
- Resync disables high-risk controls and preserves readable content.
- Audit Page does not reconstruct evidence records from raw events.
- Mock events can exercise happy path, failure path, unsupported events, and resync.
