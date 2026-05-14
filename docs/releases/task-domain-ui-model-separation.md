# Release: Task Domain And UI ViewModel Separation

> Status: done / accepted
> Date: 2026-05-14
> Accepted: 2026-05-14
> Work Stream: Phase 3C — Task Authoring Foundation
> Related Plan: [Task Domain/UI Separation](../plans/feature/task-domain-ui-model-separation.md)
> Technical Design: [Task Domain And UI ViewModel Separation](../architecture/task-domain-ui-model-separation.md)
> Related ADR: [ADR-0002](../decisions/ADR-0002-task-domain-viewmodel-and-replay.md)

---

## 1. Summary

This release establishes the first server-core Task model boundary for TaskWeavn's Task-first UI.

It separates:

- published Task domain facts;
- draft Task authoring facts;
- UI ViewModels;
- command mappings;
- replayable Task interaction timelines.

The main outcome is that the UI can render and operate on `TaskCardView` / `TaskDetailView` / `TaskInteractionTimeline` without treating raw backend Task records as the UI payload. Backend replay remains possible because user guidance, confirmations, draft edits, publish mappings, events, file summaries, and task summaries are stitched from durable fact sources.

---

## 2. Shipped

### 2.1 Domain And Draft Models

- `TaskRef` distinguishes draft and published Task references at the UI/API boundary.
- `TaskDomain` keeps published Task facts execution-focused.
- `DraftTaskNode`, `DraftTaskTree`, and `DraftToPublishedMapping` preserve authoring state and draft-to-published lineage.
- `TaskStore` and `DraftTaskStore` protocols define read/write boundaries without choosing final storage.

### 2.2 View Models

- `TaskTreeView`, `TaskCardView`, and `TaskDetailView`.
- Card badges, permissions, actions, progress, confirmations, task messages, file summaries, and result summaries.
- View models are frozen Pydantic models and intentionally exclude frontend-only local state such as selected, expanded, focused, or optimistic input.

### 2.3 Projection Service

- `DefaultTaskProjectionService` projects draft and published Tasks into a shared card/detail shape.
- Published trees are returned in deterministic topological preorder.
- Projection aggregates latest messages, pending confirmations, file summary rollups, result summaries, child progress, and status-based permissions.
- Parent file summaries can include subtree rollups while child Tasks remain the direct owners of their file changes.

### 2.4 Command Mapping

- `DefaultTaskCommandService` maps UI actions into backend intent:
  - draft/pending Task patching;
  - task-scoped guidance messages;
  - confirmation responses;
  - draft tree publication;
  - failed Task retry.
- Commands return `CommandResult` and do not mutate raw Task domain objects directly from UI gestures.

### 2.5 Replay Timeline

- `DefaultTaskInteractionTimelineService` returns replayable chronological entries for a Task.
- Timeline sources include draft facts, messages, confirmation creation/resolution, task events, file summaries, and result summaries.
- Published Task timelines can stitch earlier draft history through `DraftToPublishedMapping`.
- Timeline cursor semantics resume after the returned entry in sorted timeline order.

### 2.6 UI API Alignment

- `docs/plans/ui/ui-api-interfaces.md` now states that query APIs return ViewModels rather than raw backend Tasks.
- `listTaskMessages` is documented as a filtered view over the single Session Message Stream, not a second physical Task message stream.
- API docs name `TaskRef`, `CommandResult`, `TaskInteractionTimeline`, and `TaskInteractionSnapshot` as first-class boundary objects.

---

## 3. Validation

This release is validated as a server-core contract slice, not as a user-facing UI workflow. Full user-case testing should wait for the Task-first UI prototype, because the meaningful user flow depends on seeing and manipulating Task cards, selected Task Nodes, confirmations, and file summaries in the UI.

Final validation for this release:

- `uv run pytest` in `docs/user_cases/workspace/user-test-cli` — 24 passed
- `uv run pytest tests/test_task_timeline.py` — 5 passed, 1 warning
- `uv run ruff check src/taskweavn/task tests/test_task_timeline.py`
- `uv run mypy src/taskweavn/task tests/test_task_timeline.py`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv run pytest` — 495 passed, 1 warning
- `git diff --check`

Previous full-package validation during this feature:

- targeted task package tests passed;
- full `src`/`tests` ruff and mypy passed;
- full pytest passed with the existing OpenHands/Authlib deprecation warning.

User-case acceptance note:

- This slice does not require a new end-to-end user case because the user-facing Task-first UI is not available yet.
- The previous UC-005 generated CLI workspace was rerun as a regression check and still passes.
- UC-001 through UC-004 remain manual/LLM user cases and should be rerun when the UI prototype or a user-facing interaction layer change needs full workflow validation.

---

## 4. Follow-ups

- Add end-to-end user cases after the Task-first UI can render Task Tree Lists, selected Task details, confirmations, guidance input, file summaries, and replay timeline.
- Implement Collaborator Agent and Task authoring tools on top of `DraftTaskStore` and `TaskCommandService`.
- Implement concrete TaskPublisher and TaskBus publish lifecycle.
- Decide concrete storage for TaskDomain, draft history, publish mappings, file summaries, and task summaries.
- Expose the ViewModels through a real API transport.
- Build the Task-first UI prototype using the ViewModel and command contracts.
- Add richer cursor/token design if timeline pagination later needs cross-process stable resume beyond the first in-process service contract.
