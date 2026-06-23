# Local Computer-Use Tool Foundation

> Status: implemented foundation / accepted for local scripted backend
>
> Last Updated: 2026-06-19
>
> Related:
> [Remote WeChat Message Task PRD](../../product/remote-wechat-message-task-prd.md),
> [Execution Plane Service And Task API](execution-plane-service-task-api.md),
> [Technical Design](local-computer-use-tool-technical-design.zh-CN.md),
> [Tool Capability Layer](../../architecture/tool-capability-layer.md)

---

## 1. Problem

The remote WeChat message scenario depends on a lower-level capability:

```text
local Task API request
  -> Execution Plane
  -> TaskBus
  -> AgentLoop
  -> computer_use tool
  -> result / evidence
```

The current product has local Task API DTOs and a fixed-route AgentLoop bridge.
This slice adds the first `computer_use` tool foundation to the execution
Agent and verifies that the real sidecar Task API route can dispatch a local
task through the embedded `TaskApiService`.

This blocks any local proof that a service-level task can reach an Agent and
complete through desktop-automation-style tool calls.

## 2. Product Decision

Build `computer_use` as a local, policy-gated tool foundation first.

Do not implement remote execution yet.
Do not implement WeChat send yet.
Do not silently perform high-risk external communication.

The first slice should provide:

1. a typed `ComputerUseAction`;
2. a typed `ComputerUseObservation`;
3. a pluggable `ComputerUseBackend`;
4. a disabled backend for production-safe fallback;
5. a scripted backend for local API / AgentLoop tests;
6. sidecar wiring so `POST /api/v1/tasks` can trigger the Agent locally.

## 3. Scope

In scope:

- `computer_use` tool contract;
- local scripted backend for deterministic tests;
- optional sidecar AgentLoop registration;
- local Execution Plane service assembly;
- publish-time dispatcher trigger for local Task API requests;
- tests proving a local API request can complete through AgentLoop and
  `computer_use`.

Out of scope:

- real macOS Accessibility / AppleScript backend;
- real Windows UI Automation backend;
- WeChat Desktop adapter;
- contact identity resolution;
- send-before-confirm policy;
- screenshot redaction pipeline;
- remote ExecutionEnv registration, claim, lease, heartbeat;
- LAN auth.

## 4. Tool Contract

Tool name:

```text
computer_use
```

Action operations:

| Operation | Meaning |
|---|---|
| `observe` | Inspect current desktop/app state. |
| `open_app` | Bring an application to foreground. |
| `click` | Click a target or coordinate. |
| `type_text` | Type text into the focused target. |
| `press_key` | Press one or more keys. |
| `wait` | Wait for UI state to settle. |

Observation fields:

- operation;
- status;
- summary;
- optional screenshot ref;
- optional text extract;
- safe metadata.

The first implementation must not expose raw screenshots or chat contents by
default.

## 5. Local API Flow

```text
POST /api/v1/tasks
  -> EmbeddedTaskApiService.publish_task
  -> TaskBus pending task
  -> dispatch local fixed-route executor
  -> AgentLoop sees computer_use when enabled
  -> scripted ComputerUseBackend returns observation
  -> Agent finishes
  -> TaskBus done
  -> GET /api/v1/tasks/{executionId} shows done
```

## 6. Acceptance Criteria

1. A `TaskRequest` requiring `computer_use` is accepted only when the local
   environment advertises that capability.
2. The execution Agent sees `computer_use` only when explicitly enabled.
3. A scripted backend can make the AgentLoop complete a local API-published
   task.
4. The tool observation is persisted in the session EventStream.
5. Existing Main Page fixed-route behavior is unchanged when the feature is
   disabled.
6. No real desktop automation or WeChat send is performed in this slice.

## 7. Implementation Closure

Accepted on 2026-06-19:

1. Added typed `ComputerUseAction` and `ComputerUseObservation` contracts.
2. Added `ComputerUseTool`, `DisabledComputerUseBackend`, and
   `ScriptedComputerUseBackend`.
3. Wired optional sidecar configuration so the execution Agent only sees
   `computer_use` when explicitly enabled.
4. Wired the embedded local Execution Plane service into the sidecar and
   triggered fixed-route dispatch from `POST /api/v1/tasks`.
5. Added sidecar smoke coverage proving:
   - disabled local environment rejects `computer_use` requests;
   - enabled local environment accepts a `computer_use` request;
   - scripted backend action reaches AgentLoop;
   - task completes through TaskBus;
   - `ComputerUseObservation` is persisted in the session EventStream.

This is not a real desktop automation backend. It is the local service/tool
foundation required before macOS, Windows, WeChat, screenshot, or remote
ExecutionEnv work.

## 8. Follow-Up Slices

1. [macOS computer-use capability package](macos-computer-use-package.md), then
   [Plato macOS adapter/backend](macos-computer-use-backend.md) behind an
   explicit permission/readiness gate.
2. Windows local backend behind an explicit permission/readiness gate.
3. screenshot/evidence redaction.
4. WeChat Desktop adapter.
5. contact resolver and ambiguity ASK.
6. high-risk send confirmation policy.
7. remote ExecutionEnv registration and LAN task distribution.
