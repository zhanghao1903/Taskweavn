# Task Domain And UI ViewModel Separation

> Status: implemented / ready for acceptance
> Last Updated: 2026-05-14
> Work Stream: Phase 3C — Task Authoring Foundation
> Related Plan: [Task Domain/UI Separation](../plans/feature/task-domain-ui-model-separation.md)
> Related ADR: [ADR-0002](../decisions/ADR-0002-task-domain-viewmodel-and-replay.md)
> Related Docs: [Task Architecture](task.md), [TaskBus](bus.md), [UI API Interfaces](../plans/ui/ui-api-interfaces.md), [Collaborator Agent](../plans/feature/collaborator-agent-task-authoring.md)

---

## 1. Purpose

Task is now the primary user-facing object in TaskWeavn. That makes the Task model dangerous territory: if every UI need is pushed into the backend `Task`, TaskBus becomes noisy and unstable; if every interaction fact is kept only in the frontend, the backend cannot replay what the user confirmed, changed, or instructed.

This design defines the boundary between:

1. backend Task domain facts;
2. draft Task authoring facts;
3. UI projection data;
4. frontend-only UI state;
5. replayable Task interaction history.

The first implementation should build the model boundary and projection contracts. It should not try to build the full UI, TaskBus v2, or a complete persistence layer in one pass.

Implementation note: the first server-core pass now lives under `src/taskweavn/task/` and covers domain/draft models, view models, projection, command mapping, replay timeline, and UI API alignment. It remains intentionally storage-light: concrete TaskBus persistence, Collaborator Agent tools, and API transport are follow-up work packages.

---

## 2. Current Facts

The current repository has these architectural facts:

| Area | Fact |
|---|---|
| Task | `docs/architecture/task.md` defines Task as a small backend domain object: id, parent, intent, required capability, status, result. |
| TaskBus | `docs/architecture/bus.md` treats TaskBus as the execution/state authority for published Tasks. |
| MessageStream | Interaction Layer already stores session messages with `session_id`, `agent_id`, `task_id`, `created_at`. Task views should filter/aggregate this single stream. |
| UI API | `docs/plans/ui/ui-api-interfaces.md` already defines query/command/event boundaries for Task-first UI. |
| Collaborator Agent | `docs/plans/feature/collaborator-agent-task-authoring.md` defines `DraftTaskNode`, `DraftTaskTree`, patching, validation, and publish tools. |
| ADR | `ADR-0002` already accepts domain/view/local-state separation and replayable interactions. |

The next server-core design should turn those docs into an implementation-ready module boundary.

---

## 3. Design Goals

1. Keep backend `Task` stable and execution-focused.
2. Support rich Task cards without polluting TaskBus state.
3. Let draft Tasks and published Tasks render through one UI projection shape.
4. Preserve every user-visible Task interaction as backend replayable facts.
5. Keep messages physically as one Session Message Stream, with Task views as projections.
6. Make parent Task file summaries recursively aggregate child file changes without changing direct ownership.
7. Define APIs that Collaborator Agent, TaskPublisher, and UI can share.

---

## 4. Non-goals

- Do not implement frontend components in this slice.
- Do not introduce DAG Tasks; Task topology remains a list of trees.
- Do not change TaskBus execution semantics.
- Do not store frontend local state in TaskBus, EventStream, or MessageStream.
- Do not design the full database schema for TaskBus v2.
- Do not implement multi-user collaborative editing.

---

## 5. Layer Model

```text
Backend facts
  TaskDomain / DraftTaskNode / Message / Confirmation / FileChange / Summary

Projection layer
  TaskProjectionService
  TaskInteractionTimelineService
  Permission and action resolver

UI view data
  TaskTreeView / TaskCardView / TaskDetailView / TaskInteractionTimeline

Frontend local state
  selected / expanded / focused / draft input / optimistic patch
```

The hard rule:

```text
TaskBus owns published Task truth.
DraftTaskStore owns unpublished authoring truth.
MessageStream owns user-visible message and confirmation history.
Projection owns UI shape.
Frontend store owns local visual state.
```

---

## 6. Object Boundary

### 6.1 TaskDomain

`TaskDomain` is the published backend entity used by TaskBus and Agents.

Minimum fields:

```python
class TaskDomain(BaseModel):
    task_id: str
    session_id: str
    parent_id: str | None
    root_id: str
    order_index: int

    intent: str
    required_capability: str
    dispatch_constraints: TaskDispatchConstraints | None = None

    status: Literal["pending", "running", "done", "failed"]
    result_ref: str | None = None
    error_ref: str | None = None

    created_by: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

Notes:

- `title`, `badge`, `expanded`, `selected`, `unread_count`, and UI action layout do not belong here.
- `result_ref` and `error_ref` are references so large payloads stay in a result/summary store or event payload.
- `root_id` and `order_index` make tree list projection deterministic.
- `status` remains execution truth. UI-only states such as `editing` are external.

### 6.2 DraftTaskNode

`DraftTaskNode` is an unpublished authoring fact. It can be created and patched by Collaborator Agent tools before any Task enters TaskBus.

Minimum fields:

```python
class DraftTaskNode(BaseModel):
    draft_task_id: str
    session_id: str
    draft_tree_id: str
    parent_draft_task_id: str | None
    order_index: int

    title: str
    intent: str
    required_capability: str
    constraints: tuple[str, ...] = ()
    rationale: str | None = None

    status: Literal["draft", "accepted", "published", "cancelled"]
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime
```

Notes:

- Draft nodes can be edited more freely than published Tasks.
- Draft nodes must keep versioned patch history.
- Once published, draft nodes are not mutated into `TaskDomain`; instead, a mapping connects draft ids to published ids.

### 6.3 DraftToPublishedMapping

Publishing must preserve identity lineage:

```python
class DraftToPublishedMapping(BaseModel):
    session_id: str
    draft_tree_id: str
    draft_task_id: str
    task_id: str
    published_at: datetime
    publish_command_id: str
```

This mapping lets `TaskInteractionTimeline` stitch together:

```text
draft creation -> user edits -> publish -> execution -> result
```

### 6.4 TaskViewData

Task view data is derived and safe for UI. It may combine many backend facts.

It can include:

- display title and intent preview;
- badges;
- permissions;
- available actions;
- pending confirmation;
- latest message;
- child progress;
- file summary;
- result summary.

It must not include:

- raw internal stack traces;
- large result payloads by default;
- hidden scheduling internals unless debug mode is requested;
- frontend-only local state.

### 6.5 TaskUIState

Task UI state is frontend-owned.

Examples:

```typescript
type TaskUIState = {
  selectedTaskId?: string
  expandedTaskIds: string[]
  focusedTaskId?: string
  draftInputs: Record<string, string>
  optimisticPatches: Record<string, unknown>
  lastSeenMessageIds: Record<string, string>
}
```

This state can live in browser memory or local storage. It is not part of backend replay.

---

## 7. ViewModel Contracts

The UI should consume view models, not raw domain objects.

### 7.1 TaskTreeView

```python
class TaskTreeView(BaseModel):
    session_id: str
    roots: list[TaskCardView]
    total_count: int
    pending_confirmation_count: int
    running_count: int
    failed_count: int
    generated_at: datetime
```

`roots` may contain nested `children`, or the API may return a flat topologically ordered list. The first implementation should pick one representation and document sorting.

Recommended first version:

```python
class TaskTreeView(BaseModel):
    session_id: str
    nodes: list[TaskCardView]  # topological preorder
```

Preorder is easier to diff, paginate, and test.

### 7.2 TaskCardView

```python
class TaskCardView(BaseModel):
    task_ref: TaskRef
    parent_ref: TaskRef | None
    root_ref: TaskRef

    title: str
    intent_preview: str
    status: Literal["draft", "pending", "running", "done", "failed", "cancelled"]
    depth: int
    order_index: int

    badges: TaskCardBadges
    permissions: TaskCardPermissions
    primary_actions: list[TaskCardAction]

    confirmation: ConfirmationActionView | None = None
    latest_message: SessionMessageView | None = None
    file_summary: TaskFileChangeSummary | None = None
    progress: TaskProgressView | None = None
```

### 7.3 TaskRef

One view shape must support draft and published tasks:

```python
class TaskRef(BaseModel):
    kind: Literal["draft", "published"]
    id: str
```

This avoids fake ids and makes command mapping explicit.

### 7.4 TaskCardBadges

```python
class TaskCardBadges(BaseModel):
    pending_confirmation_count: int = 0
    unread_message_count: int = 0
    direct_file_change_count: int = 0
    subtree_file_change_count: int = 0
    child_count: int = 0
    done_child_count: int = 0
    failed_child_count: int = 0
    risk_level: str | None = None
```

### 7.5 TaskCardPermissions

```python
class TaskCardPermissions(BaseModel):
    can_edit: bool
    can_append_guidance: bool
    can_resolve_confirmation: bool
    can_publish: bool
    can_cancel: bool
    can_retry: bool
    readonly_reason: str | None = None
```

Permission rules are derived from Task kind/status, current command capabilities, and user role.

### 7.6 TaskCardAction

```python
class TaskCardAction(BaseModel):
    action_id: str
    kind: Literal[
        "confirm",
        "edit",
        "append_guidance",
        "publish",
        "cancel",
        "retry",
        "open_detail",
    ]
    label: str
    disabled: bool = False
    reason: str | None = None
```

The UI renders actions; the server decides which actions are valid.

### 7.7 TaskDetailView

```python
class TaskDetailView(BaseModel):
    card: TaskCardView
    full_intent: str
    constraints: list[str]
    messages: list[SessionMessageView]
    confirmations: list[ConfirmationActionView]
    file_changes: list[TaskFileChangeSummary]
    result_summary: TaskSummaryView | None = None
    timeline_cursor: str | None = None
```

The detail view can be loaded after card selection. It should not be required for rendering the tree.

---

## 8. Projection Service

### 8.1 Protocol

```python
class TaskProjectionService(Protocol):
    def list_task_tree(
        self,
        session_id: str,
        *,
        root_ref: TaskRef | None = None,
        include_drafts: bool = True,
        include_published: bool = True,
    ) -> TaskTreeView:
        ...

    def get_task_card(self, session_id: str, task_ref: TaskRef) -> TaskCardView:
        ...

    def get_task_detail(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        message_limit: int = 100,
    ) -> TaskDetailView:
        ...
```

### 8.2 Input Sources

| Source | Responsibility |
|---|---|
| `TaskStore` / TaskBus materialized view | Published Task identity, topology, execution status. |
| `DraftTaskStore` | Draft Task Tree, patch versions, draft state. |
| `MessageStream` | Session and task-scoped messages, confirmations, latest activity. |
| Confirmation/actionable message view | Pending and resolved user choices. |
| File change store | Direct and recursive file summaries. |
| Task summary store | Result summaries, failure summaries, follow-up suggestions. |
| UI state input | Optional selected/expanded/unread hints, if projection happens close to frontend. |

### 8.3 Projection Rules

| Rule | Requirement |
|---|---|
| Sort | Tree cards are returned in topological preorder, then `order_index`, then `created_at`. |
| Status | Draft status comes from `DraftTaskNode`; published status comes from TaskBus/TaskStore. |
| Messages | Task messages are filtered from the single Session Message Stream by `task_id` or draft task id. |
| Confirmations | Pending confirmation is the newest unresolved actionable message for that Task. |
| File summary | `direct_file_change_count` counts direct owner changes; `subtree_file_change_count` recursively includes descendants. |
| Permissions | Done/failed published Tasks are read-only except retry/follow-up actions. Running Tasks allow guidance but not direct intent mutation. |
| Privacy | Raw internal errors stay in logs/debug views; default UI receives user-readable summaries. |

### 8.4 Cache Boundary

Projection can be cached, but cache invalidation must be driven by facts:

- draft task patched;
- Task status changed;
- message appended;
- confirmation resolved;
- file change recorded;
- task summary updated;
- UI local state changed.

The first implementation can skip caching and keep projection deterministic. Caching is an optimization, not part of the domain model.

---

## 9. Stores And Protocol Requirements

### 9.1 TaskStore

`TaskStore` is the read side of published Task truth. It may initially be backed by TaskBus materialized state.

```python
class TaskStore(Protocol):
    def get(self, session_id: str, task_id: str) -> TaskDomain | None:
        ...

    def list_for_session(self, session_id: str) -> list[TaskDomain]:
        ...

    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]:
        ...
```

First version can be in-memory or SQLite, but the protocol should not expose storage details.

### 9.2 DraftTaskStore

```python
class DraftTaskStore(Protocol):
    def create_tree(self, session_id: str, roots: list[DraftTaskNode]) -> DraftTaskTree:
        ...

    def get_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree:
        ...

    def list_trees(self, session_id: str) -> list[DraftTaskTree]:
        ...

    def get_node(self, session_id: str, draft_task_id: str) -> DraftTaskNode | None:
        ...

    def update_node(
        self,
        session_id: str,
        draft_task_id: str,
        patch: TaskNodePatch,
        *,
        expected_version: int,
    ) -> DraftTaskNode:
        ...

    def mark_published(
        self,
        session_id: str,
        draft_tree_id: str,
        mappings: list[DraftToPublishedMapping],
    ) -> DraftTaskTree:
        ...
```

`expected_version` protects users from overwriting a newer collaborator/user edit.

### 9.3 FileChangeStore

```python
class FileChangeStore(Protocol):
    def list_for_task(
        self,
        session_id: str,
        task_id: str,
        *,
        recursive: bool = False,
    ) -> list[TaskFileChangeSummary]:
        ...
```

Recursive mode rolls up child changes but does not change ownership.

### 9.4 TaskSummaryStore

```python
class TaskSummaryStore(Protocol):
    def get(self, session_id: str, task_id: str) -> TaskSummaryView | None:
        ...
```

This store can be thin in the first pass. It exists so UI cards do not read raw Task result payloads directly.

---

## 10. Command Mapping

UI commands should express user intent. They should not mutate domain objects directly.

### 10.1 Protocol

```python
class TaskCommandService(Protocol):
    def update_task_node(
        self,
        session_id: str,
        task_ref: TaskRef,
        patch: TaskNodePatch,
        *,
        expected_version: int | None = None,
    ) -> CommandResult:
        ...

    def append_task_message(
        self,
        session_id: str,
        task_ref: TaskRef,
        content: str,
        *,
        mode: Literal["guidance", "constraint", "clarification", "correction"],
    ) -> CommandResult:
        ...

    def resolve_confirmation(
        self,
        session_id: str,
        confirmation_id: str,
        value: str,
        *,
        note: str | None = None,
    ) -> CommandResult:
        ...

    def publish_task_tree(
        self,
        session_id: str,
        draft_tree_id: str,
    ) -> CommandResult:
        ...

    def retry_task(
        self,
        session_id: str,
        task_id: str,
        instruction: str | None = None,
    ) -> CommandResult:
        ...
```

### 10.2 Command Rules

| User action | Command | Backend effect |
|---|---|---|
| Edit draft Task | `update_task_node` | Patch DraftTaskStore and append draft patch history. |
| Edit pending published Task | `update_task_node` | Allowed only before execution; may create Task patch event. |
| Add guidance to running Task | `append_task_message` | Append task-scoped message; running Agent may consume it next. |
| Confirm option | `resolve_confirmation` | Append response message; confirmation becomes resolved. |
| Publish draft tree | `publish_task_tree` | Validate draft, create published Tasks, publish through TaskPublisher/TaskBus. |
| Retry failed Task | `retry_task` | Create a new follow-up/retry Task, preserving original as immutable history. |

### 10.3 Status Permissions

| Kind/status | Edit intent | Append guidance | Resolve confirmation | Publish | Retry/cancel |
|---|---:|---:|---:|---:|---:|
| draft | yes | yes | yes, if present | yes | cancel yes |
| pending | yes, with rules | yes | yes | no | cancel yes |
| running | no | yes | yes | no | cancel deferred |
| done | no | no direct mutation | no | no | follow-up only |
| failed | no | no direct mutation | no | no | retry yes |

---

## 11. Replay And Timeline

Projection makes UI rich; timeline makes interactions reconstructible.

### 11.1 Timeline Protocol

```python
class TaskInteractionTimelineService(Protocol):
    def get_timeline(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        include_subtree: bool = False,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> TaskInteractionTimeline:
        ...

    def get_snapshot(
        self,
        session_id: str,
        task_ref: TaskRef,
    ) -> TaskInteractionSnapshot:
        ...
```

### 11.2 Timeline Entry

```python
class TaskInteractionEntry(BaseModel):
    entry_id: str
    session_id: str
    task_ref: TaskRef
    occurred_at: datetime
    source: Literal["draft", "message", "confirmation", "event", "file", "summary"]
    kind: str
    actor: str | None = None
    summary: str
    payload_ref: str | None = None
```

The first version should store `payload_ref` rather than duplicating large payloads.

### 11.3 Timeline Sources

| Source | Timeline examples |
|---|---|
| DraftTaskStore | draft created, node patched, tree accepted, tree published. |
| MessageStream | user guidance, collaborator reply, task-scoped clarification. |
| Confirmation/actionable message | confirmation created, option selected, timeout/default applied. |
| EventStream | Task published, Action emitted, Observation received, Task status changed. |
| FileChangeStore | direct file changed, child file roll-up changed. |
| TaskSummaryStore | result summarized, failure summarized, follow-up proposed. |

### 11.4 Replay Guarantees

Backend replay must be able to answer:

- What did the user initially ask?
- Which draft Task nodes did Collaborator Agent propose?
- Which Task node did the user select?
- What did the user add, confirm, reject, or correct?
- Which draft nodes became published Tasks?
- What happened during execution?
- Which files changed directly under this Task, and which came from descendants?
- What final summary did the user see?

UI local state is not part of this replay guarantee.

---

## 12. Event And Subscription Requirements

Task-first UI should subscribe at session level.

```python
class SessionEventEnvelope(BaseModel):
    event_id: str
    session_id: str
    task_ref: TaskRef | None
    type: str
    created_at: datetime
    cursor: str
    payload: dict[str, object]
```

Minimum event types:

| Event | Projection impact |
|---|---|
| `draft_tree.created` | Add draft root cards. |
| `draft_task.updated` | Re-project changed draft card/subtree. |
| `task.published` | Link draft and published ids; show pending cards. |
| `task.status_changed` | Update status, permissions, progress. |
| `message.appended` | Update latest message, unread counts, timeline. |
| `confirmation.created` | Add pending confirmation badge/action. |
| `confirmation.resolved` | Clear pending confirmation and append history. |
| `file_change.recorded` | Update direct and recursive file badges. |
| `task.summary_updated` | Update done/failed summary. |

The projection service can be query-based first; event subscription is the refresh mechanism.

---

## 13. Persistence Requirements

First version can keep schema details small, but these access paths must be supported.

### 13.1 Draft Task Access Paths

| Query | Required ordering/index idea |
|---|---|
| list draft trees by session | `(session_id, created_at, draft_tree_id)` |
| list draft nodes by tree | `(session_id, draft_tree_id, parent_id, order_index)` |
| get node by id | `(session_id, draft_task_id)` |
| list patch history | `(session_id, draft_task_id, version)` |
| map draft to published | `(session_id, draft_task_id)` and `(session_id, task_id)` |

### 13.2 Published Task Access Paths

| Query | Required ordering/index idea |
|---|---|
| list tasks by session | `(session_id, root_id, parent_id, order_index)` |
| get task | `(session_id, task_id)` |
| list children | `(session_id, parent_id, order_index)` |
| list by status | `(session_id, status, updated_at)` |

### 13.3 Projection Access Paths

| Query | Source |
|---|---|
| newest task message | MessageStream `(session_id, task_id, created_at desc)` |
| pending confirmation | MessageStream pending actionable anti-join |
| unread counts | UI state + MessageStream cursor |
| direct file changes | FileChangeStore `(session_id, task_id, created_at)` |
| recursive file changes | task subtree expansion + FileChangeStore |

---

## 14. Integration With Existing UI API Document

`docs/plans/ui/ui-api-interfaces.md` should evolve in the next doc/code slice:

| Existing name | Proposed stable name |
|---|---|
| `TaskNodeSummary` | `TaskCardView` or `TaskNodeSummaryView` |
| `TaskNodeDetail` | `TaskDetailView` |
| `listTaskTrees` | returns `TaskTreeView` |
| `getTaskNode` | returns `TaskDetailView` |
| `appendTaskMessage` | keeps single MessageStream, requires `task_ref`/`task_id` |
| `getTaskFileChanges` | must support `recursive=true` for parent roll-up |

Do not create a second physical Task message stream. `listTaskMessages` remains a semantic filter over Session Message Stream.

---

## 15. Implementation Slices

### Slice 1 — Model Boundary And Protocols

Deliver:

- `TaskRef`;
- `TaskDomain`;
- `DraftTaskNode`;
- `DraftTaskTree`;
- `DraftToPublishedMapping`;
- `TaskStore` Protocol;
- `DraftTaskStore` Protocol;
- initial tests for frozen/validated models and tree ordering.

No TaskBus behavior changes in this slice.

### Slice 2 — ViewModel Schemas

Deliver:

- `TaskTreeView`;
- `TaskCardView`;
- `TaskDetailView`;
- `TaskCardBadges`;
- `TaskCardPermissions`;
- `TaskCardAction`;
- shared aliases for status and view ids.

Tests should cover draft card, pending card, running card, done/failed readonly card.

### Slice 3 — Projection Service

Deliver:

- `TaskProjectionService`;
- in-memory test doubles for TaskStore/DraftTaskStore/FileChangeStore/SummaryStore;
- deterministic topological preorder projection;
- permissions resolver;
- file-change recursive roll-up.

### Slice 4 — Command Mapping

Deliver:

- `TaskCommandService` skeleton;
- command validation for status permissions;
- mapping from UI actions to MessageStream/DraftTaskStore/TaskPublisher boundaries.

Publishing can still be a stub until TaskPublisher implementation.

### Slice 5 — Interaction Timeline

Deliver:

- `TaskInteractionTimelineService`;
- `TaskInteractionEntry`;
- `TaskInteractionSnapshot`;
- draft-to-published timeline stitching.

Tests should prove that user guidance, confirmation resolution, and publish mapping are replayable.

### Slice 6 — UI API Doc Alignment

Deliver:

- update `docs/plans/ui/ui-api-interfaces.md`;
- update `docs/plans/feature/collaborator-agent-task-authoring.md` if DraftTaskStore naming changes;
- add user case notes if the new model changes testing workflow.

### Slice 7 — Tests And Docs

Deliver:

- reconcile implementation with this architecture document and the feature plan;
- add/update the feature release record;
- update roadmap/project roadmap status;
- run targeted and full validation for the task package;
- capture follow-ups for Collaborator Agent, TaskPublisher, UI transport, and concrete persistence.

The first implementation also tightens timeline pagination: `TaskInteractionTimeline.cursor` is an opaque returned cursor, and the service resumes after the matching entry in the chronologically sorted timeline. It must not compare UUID strings as if they were time-ordered.

---

## 16. Test Strategy

| Test | Expected result |
|---|---|
| draft tree projection | Draft nodes become editable cards with publish/edit actions. |
| published tree projection | Published Tasks become cards ordered by preorder. |
| running task permissions | Running Task cannot edit intent but can append guidance. |
| done task permissions | Done Task is readonly except follow-up/retry-style commands. |
| pending confirmation badge | New actionable message appears as card confirmation. |
| confirmation resolution | Resolution clears pending action and appears in timeline. |
| task-scoped guidance | Guidance appends to MessageStream and appears in detail/timeline. |
| file roll-up | Parent shows recursive child file summary while direct ownership remains child. |
| draft publish mapping | Timeline links draft edits to published execution. |
| UI state isolation | selected/expanded/draft input never changes backend Task facts. |

---

## 17. Open Questions

1. Should first implementation return tree cards as a flat preorder list or nested children? Preference: flat preorder for easier diffing and tests.
2. Should `TaskRef` use `{kind, id}` everywhere, or should published APIs keep plain `task_id` and draft APIs keep `draft_task_id`? Preference: use `TaskRef` at UI/projection boundary, keep plain ids inside stores.
3. Should pending published Tasks allow intent edits? Preference: yes for first version, but only before claim/running and with patch history.
4. Should cancelled be a first-class backend published status? Current backend Task architecture says no; UI can show `cancelled` for draft/cancelled pending projection while TaskBus may still model cancellation as failed/not-run history.
5. Where should unread counts live? Preference: frontend/UI state first, with backend support later if multi-device user state becomes important.

---

## 18. Acceptance Criteria

This design slice is complete when:

- domain, draft, view, and local UI state boundaries are documented and reflected in model/protocol names;
- first implementation can project draft and published Tasks into the same `TaskCardView`;
- projection can aggregate messages, confirmations, child progress, and file summaries;
- command mapping prevents invalid state mutations;
- backend can reconstruct Task interaction history without frontend local state;
- UI API docs no longer imply that raw backend Task is the main UI payload.
