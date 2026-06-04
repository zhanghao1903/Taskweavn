# Release: Cooperative Task Interruption

> Status: done / accepted for Product 1.0 task control
> Date: 2026-06-05
> Work Stream: Product 1.0 task interruption and execution safety / P9 closure
> Related Plan: [Cooperative Task Interruption](../plans/feature/cooperative-task-interruption.md)
> Technical Design: [Cooperative Task Interruption 详细技术方案](../plans/feature/cooperative-task-interruption-technical-design.zh-CN.md)
> Architecture: [Task](../architecture/task.md), [TaskBus](../architecture/bus.md), [Context Manager](../architecture/context-manager.md), [UI/backend Communication](../architecture/ui-backend-communication.md)
> Implementation Commits: `939f951`, `190b7a3`
> Pull Request: #42

---

## 1. Summary

This release closes the Product 1.0 cooperative task interruption slice.

TaskWeavn now supports a truthful stop path for published Tasks without adding
hard cancellation, `paused`, or `cancelled` as canonical PublishedTask states.
TaskBus records stop intent, Main Page projects running interrupted tasks as
stopping, AgentLoop observes interruption at safe points, and terminal
interrupted outcomes are represented as failed tasks with `cancelled:` reasons.

---

## 2. Release Scope

### 2.1 TaskBus Interrupt Intent

- Added interrupt intent fields on published Tasks.
- Pending Tasks can stop immediately as terminal `failed` with a
  `cancelled:` reason.
- Running Tasks keep status `running` while recording active interrupt intent.
- Retry clears active interruption metadata for a new execution attempt.
- Interrupted running tasks can be recovered to terminal failure after process
  restart or stale stopping state recovery.

### 2.2 AgentLoop Safe Points

- AgentLoop can receive an interrupt checker.
- Safe-point checks run before LLM calls, after LLM responses, before tool
  dispatch, after tool observations, and around timeout handling.
- Interruption is cooperative. In-flight LLM/tool work is not hard-killed.
- Interrupted loop results map to TaskBus `fail(...)` with a `cancelled:`
  reason.

### 2.3 Context Manager And Cache-Aware Rendering

- Task context sources read active interrupt intent.
- `InterruptionContext` is rendered into governed LLM input when active.
- Cache-aware provider treats interrupt changes as high-value delta/checkpoint
  input without rewriting stable prompt prefixes unnecessarily.

### 2.4 Main Page Projection And Commands

- Main Page command routing can request stop for published pending/running
  Tasks.
- Running plus active interrupt projects as `Stopping`.
- Duplicate stop controls are disabled while stopping is active.
- Detail and audit surfaces retain enough evidence to explain stop request and
  terminal outcome.

### 2.5 Timeout Hardening

- Long LLM calls now have timeout handling aligned with cooperative stop
  semantics.
- If an interrupt intent exists when timeout handling resumes, interruption can
  win instead of leaving the UI permanently stuck as stopping.

---

## 3. Validation Evidence

Acceptance evidence includes:

- PR #42 merge into `main`;
- user acceptance of the cooperative interruption slice;
- targeted coverage in:
  - `tests/test_task_bus_lifecycle.py`;
  - `tests/test_sqlite_task_bus.py`;
  - `tests/test_loop.py`;
  - `tests/test_context_manager.py`;
  - `tests/test_main_page_sidecar_app.py`;
  - frontend Main Page stopping projection tests.

This docs-only closure records the accepted state. It does not introduce new
runtime behavior.

---

## 4. Follow-ups After Acceptance

- Keep hard cancellation out of Product 1.0.
- Treat stuck stopping reports as recovery/observability bugs, not as a reason
  to add a canonical `cancelled` status.
- Product 1.1+ may consider richer partial-result recovery, selected runtime
  hard-cancel adapters, pause/resume, and user-configurable interruption
  policy.
