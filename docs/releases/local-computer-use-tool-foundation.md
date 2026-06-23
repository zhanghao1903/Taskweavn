# Release: Local Computer-Use Tool Foundation

> Status: done / accepted for local scripted foundation
> Date: 2026-06-19
> Work Stream: Product 1.1 execution tools / Execution Plane service boundary
> Related Plan: [Local Computer-Use Tool Foundation](../plans/feature/local-computer-use-tool.md)
> Technical Design: [Local Computer-Use Tool Foundation 技术方案](../plans/feature/local-computer-use-tool-technical-design.zh-CN.md)
> Related PRD: [Remote WeChat Message Task PRD](../product/remote-wechat-message-task-prd.md)

---

## 1. Summary

This release adds the first local `computer_use` tool foundation for Plato's
Execution Plane.

It proves the local service path:

```text
POST /api/v1/tasks
  -> EmbeddedTaskApiService
  -> TaskBus
  -> fixed-route dispatcher
  -> AgentLoop
  -> computer_use tool
  -> scripted backend
  -> TaskBus done
  -> EventStream observation
```

The release does not perform real desktop automation, send WeChat messages,
capture raw screenshots, or distribute tasks across machines.

## 2. Release Scope

### 2.1 Tool Contract

- Added typed `ComputerUseAction`.
- Added typed `ComputerUseObservation`.
- Added operation payload validation for `open_app`, `click`, `type_text`, and
  `press_key`.
- Enforced that `success=True` only corresponds to `status=ok`.

### 2.2 Backend Seam

- Added `ComputerUseBackend` protocol.
- Added `DisabledComputerUseBackend` as the safe default.
- Added `ScriptedComputerUseBackend` for deterministic local and CI tests.
- Added `ComputerUseTool` as the AgentLoop tool boundary.

### 2.3 Sidecar And AgentLoop Wiring

- Added explicit sidecar config/dependency fields for enabling computer-use.
- Registered `computer_use` only when explicitly enabled.
- Added local ExecutionEnv capability/tool-pool advertisement only when
  enabled.
- Triggered fixed-route dispatch after successful local Task API publish.

### 2.4 Local Task API Smoke

- Verified default sidecar rejects `computer_use` requests when local env
  does not advertise the capability.
- Verified enabled sidecar accepts and executes a scripted `computer_use`
  request through AgentLoop.
- Verified `ComputerUseObservation` is persisted in the session EventStream.

## 3. Validation

Release validation included:

- `uv run pytest tests/test_computer_use_tool.py`
- `uv run pytest tests/test_main_page_sidecar_app.py::test_main_page_sidecar_task_api_rejects_computer_use_when_disabled tests/test_main_page_sidecar_app.py::test_main_page_sidecar_task_api_runs_scripted_computer_use_when_enabled`
- confirmation targeted regression tests for `waiting_for_user`
- frontend MainPage confirmation tests
- targeted `ruff`
- targeted `mypy`
- frontend build
- `git diff --check`

Full `uv run mypy src/taskweavn` currently has unrelated pre-existing failures
in read-only inquiry and diagnostics export files; targeted mypy for touched
computer-use/confirmation/runtime files passes.

## 4. Follow-Ups

- macOS Accessibility / AppleScript backend behind readiness and permission
  gates.
- Windows UI Automation backend.
- screenshot/text evidence redaction.
- WeChat Desktop adapter and contact resolver.
- explicit send-before-confirm policy and exactly-once external side-effect
  tracking.
- remote ExecutionEnv registration, claim, lease, heartbeat, and LAN auth.
