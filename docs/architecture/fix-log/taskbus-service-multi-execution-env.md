# Execution Plane / Multi-Execution-Env Memo Fact Calibration Fix Log

> Target document: `docs/architecture/taskbus-service-multi-execution-env.md`
> Original preserved as: `docs/architecture/taskbus-service-multi-execution-env.original.md`
> Calibration date: 2026-07-10

## Workflow Gate

- User request: continue one-document-at-a-time architecture fact calibration.
- Detected phase: P5 architecture maintenance, checked against P8/P9 implementation and tests.
- Task type: docs-only architecture fact correction.
- Required upstream artifacts: TaskBus docs, Execution Plane code, service/API tests, local WeChat runtime plan and tests, sidecar assembly.
- Found artifacts: `EmbeddedTaskApiService`, Execution Plane DTOs/stores, local HTTP shell, local env registry, WeChat send runtime, runtime assembly, targeted tests.
- Missing or weak artifacts: previous memo mixed service/multi-env direction with current shipped behavior.
- Implementation allowed now: yes, docs-only.
- Prework required: verify current Execution Plane and runtime facts before editing.
- Scope: preserve original memo, revise target memo, add this fix-log.
- Acceptance criteria: current embedded/local facts are separated from future remote/multi-env service direction.
- Risks and assumptions: service-compatible DTO fields such as `TaskLease` and `CallbackPolicy` must not be treated as runtime protocols until service/store behavior exists.

## Maintainability Gate

- Requested change: architecture hygiene for Execution Plane / multi-execution-env memo.
- Trigger: architecture fact calibration.
- Size signal: target document was 499 lines, below the 800-line threshold.
- Risk level: low for docs-only slice.
- Refactor required first: no.
- Allowed change type: docs-only boundary correction.
- Validation commands: `git diff --check` plus targeted Execution Plane, TaskBus, HTTP, computer-use, and WeChat runtime tests.

## Evidence Inspected

### Code

- `src/taskweavn/execution_plane/models.py`
- `src/taskweavn/execution_plane/service.py`
- `src/taskweavn/execution_plane/embedded_service.py`
- `src/taskweavn/execution_plane/env_registry.py`
- `src/taskweavn/execution_plane/store.py`
- `src/taskweavn/execution_plane/wechat_send_boundary.py`
- `src/taskweavn/execution_plane/wechat_send_execution.py`
- `src/taskweavn/execution_plane/wechat_send_runtime.py`
- `src/taskweavn/server/ui_http_execution_plane.py`
- `src/taskweavn/server/ui_http_routes.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/computer_use_runtime.py`
- `src/taskweavn/task/bus.py`
- `src/taskweavn/task/sqlite_bus.py`

### Tests

- `tests/test_execution_plane_models.py`
- `tests/test_execution_plane_service.py`
- `tests/test_execution_plane_http_transport.py`
- `tests/test_api_publish_transport.py`
- `tests/test_computer_use_runtime.py`
- `tests/test_wechat_send_boundary_store.py`
- `tests/test_wechat_send_execution.py`
- `tests/test_wechat_send_runtime.py`
- `tests/test_task_api_publisher.py`
- `tests/test_task_bus_lifecycle.py`
- `tests/test_sqlite_task_bus.py`

### Related Docs

- `docs/architecture/bus.md`
- `docs/architecture/task.md`
- `docs/architecture/agent.md`
- `docs/architecture/overview.md`
- `docs/decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md`
- `docs/plans/feature/execution-plane-service-task-api.md`
- `docs/plans/feature/local-macos-wechat-send-mvp-technical-design.zh-CN.md`

## Verified Facts

1. Execution Plane service-level DTOs exist in `models.py`: `TaskRequest`, `TaskExecution`, `TaskEvent`, `TaskResult`, `TaskError`, `EvidenceRef`, `ExecutionEnv`, `CapabilityPolicy`, `CallbackPolicy`, and `TaskLease`.

2. `TaskRequest` currently uses nested `policy.requiredCapability`; the old memo's top-level `requiredCapability` shape is not the current DTO shape.

3. `TaskRequest` rejects unknown fields, requires namespaced `task_type`, and rejects `external_app` publishing `plato.*` task types.

4. `CapabilityPolicy` rejects overlap between `allowed_tools` and `denied_tools`.

5. `CallbackPolicy` validates webhook URL/signing key shape, but no callback delivery service or delivery store is implemented.

6. `TaskLease` validates timestamps, but no lease issuance, renewal, expiry, revocation, persistence, or worker claim service exists.

7. `TaskApiService` currently exposes publish, get, cancel, retry, list events, get result/error, and list evidence methods.

8. `EmbeddedTaskApiService` is in-process over TaskBus; it is service-compatible but not a separate service process.

9. Ordinary `publish_task()` resolves a compatible local env, maps `TaskRequest` to `TaskDomain`, publishes into TaskBus, persists `TaskExecution` and idempotency, appends `task.accepted`, and returns `pending`.

10. Current execution progress for ordinary tasks is still TaskBus plus fixed-route dispatcher/executor.

11. `ExecutionPlaneStore` has in-memory and SQLite implementations for idempotency, executions, events, results, errors, and evidence refs.

12. Main sidecar creates `SqliteExecutionPlaneStore(layout.meta_dir / "execution_plane.sqlite")`.

13. Current `ExecutionEnvRegistry` is in-memory. `find_compatible()` checks online status, required capability, and allowed tool subset.

14. Sidecar assembly creates a single `local-default` env. Computer-use enabled adds `computer_use`, WeChat send capability, and tool pool entries.

15. Local HTTP shell routes exist for `/api/v1/tasks`, `/api/v1/tasks/{executionId}`, cancel, retry, events, result, error, evidence, and workspace-prefixed publish.

16. HTTP shell routes delegate to `TaskApiService` and can request dispatch through `ExecutionTriggerGateway` after publish.

17. No remote ExecutionEnv register/heartbeat/claim endpoint exists.

18. Local WeChat send runtime handler exists for `communication.wechat.send_message`, but it is an opt-in local runtime handler, not remote ExecutionEnv.

19. WeChat runtime requires human confirmation policy, drafts first, waits for confirmation, resumes/replays by idempotency key, sends once after confirmation, and records result/error/evidence.

20. `SqliteWeChatSendBoundaryStore` persists execution/idempotency/fingerprint/status/confirmation/observation/result/error refs and blocks unsafe retry for unknown/send-attempted boundaries.

21. The Execution Plane plan and ADR describe accepted service direction, but implementation is still local embedded foundation.

## Corrections Applied

1. Changed the memo status from broad exploratory service language to fact-calibrated current/future layering.

2. Added explicit current implementation facts for DTOs, embedded service, stores, local env registry, HTTP shell, and local runtime handlers.

3. Replaced the old top-level `requiredCapability` publish example with the current nested `policy.requiredCapability` shape.

4. Marked `TaskLease`, `claimed`, `lease_expired`, callback/webhook delivery, remote env registration, heartbeat, and distributed claim as non-current facts.

5. Clarified that TaskBus remains lifecycle authority and ExecutionPlaneStore owns service-level idempotency/execution/events/result/error/evidence records.

6. Clarified that ordinary tasks still run through TaskBus plus fixed-route execution, not a service-owned scheduler.

7. Added local HTTP route facts and execution-id path semantics.

8. Added local WeChat runtime facts while making clear it is not remote ExecutionEnv, generic Agent Manager, or unreviewed outbound automation.

9. Removed implication that email outreach MVP is implemented; retained it as future low-risk vertical proof.

10. Added explicit current non-goals for Product 1.1.

## Follow-up Candidates

- `docs/architecture/bus-v2.md`: likely still assumes dynamic routing, lease, or TaskBus service behavior not yet implemented.
- `docs/architecture/tool-capability-layer.md`: should be checked against current `CapabilityPolicy`, tool pool, and computer-use runtime facts.
- `docs/architecture/workspace-communication-protocol.md`: should be checked for remote/local service assumptions.
- `docs/plans/feature/execution-plane-service-task-api.md`: plan says "No implementation has started" in one section and is now stale.

## Validation

- `git diff --check` passed.
- `uv run pytest tests/test_execution_plane_models.py tests/test_execution_plane_service.py tests/test_execution_plane_http_transport.py tests/test_api_publish_transport.py tests/test_computer_use_runtime.py tests/test_wechat_send_boundary_store.py tests/test_wechat_send_execution.py tests/test_wechat_send_runtime.py tests/test_task_api_publisher.py tests/test_task_bus_lifecycle.py tests/test_sqlite_task_bus.py tests/test_task_commands.py` passed: 132 tests.
