# Release: RawTask And DraftTaskTree Persistence

> Status: done
> Date: 2026-05-28
> Accepted: 2026-05-28
> Work Stream: Product 1.0 authoring recovery / P8 backend integration
> Related Plan: [RawTask And DraftTaskTree Persistence Foundation](../plans/feature/raw-task-draft-tree-persistence.md)
> Technical Design: [RawTask / DraftTaskTree 持久化基础中文详细技术方案](../plans/feature/raw-task-draft-tree-persistence-technical-design.zh-CN.md)
> Decisions: [ADR-0008](../decisions/ADR-0008-authoring-domain-execution-boundary.md), [ADR-0009](../decisions/ADR-0009-single-active-session-worktree.md), [ADR-0010](../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md)

---

## 1. Summary

This release closes the Product 1.0 authoring recovery gap.

Unpublished RawTask and DraftTaskTree state now survives backend restart, and
publish resolves the real active draft tree identity instead of depending on a
synthetic `TaskTreeView.id` from UI projection.

---

## 2. Shipped

- `SqliteRawTaskStore`
- `SqliteDraftTaskStore`
- `SqliteAuthoringStateStore`
- `authoring.sqlite` local-first persistence under the workspace `.taskweavn`
  directory
- active RawTask / DraftTaskTree recovery after restart
- single active draft tree per Session projection behavior
- publish gateway identity alignment for active draft trees
- local sidecar assembly with SQLite authoring stores
- durable authoring command idempotency
- API command response idempotency with request hash conflict detection

---

## 3. Product Impact

- Users can return to the last unpublished draft after backend restart.
- A Session has one active draft/work tree for Product 1.0, avoiding forest-like
  Main Page complexity.
- Publish failures caused by missing in-memory draft tree state are closed.
- Retry/restart paths for generate and publish commands are durable enough for
  Product 1.0 user testing.

---

## 4. Validation

Implementation branch validation included:

- `uv run ruff check src tests`
- `uv run mypy src/taskweavn/server src/taskweavn/core`
- `LLM_API_KEY=test uv run pytest` — 826 passed, 1 warning

Product acceptance:

- publish failure caused by synthetic draft tree identity was verified fixed;
- RawTask / DraftTaskTree restart persistence was verified fixed.

---

## 5. Follow-ups

- Post-publish editing policy and user-facing edit/revise behavior.
- Fixed-route task execution bridge for Product 1.0 execution closure.
- Full Audit / Trust Page evidence projection.
- Durable SSE replay, if event replay becomes necessary for broader user
  testing.
- API idempotency `in_progress` reservation, if concurrent duplicate submits
  become observable.
