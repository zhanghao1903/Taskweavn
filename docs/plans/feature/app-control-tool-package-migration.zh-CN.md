# App-Control Tool Package Migration Plan

> Status: M0-M6 repository implementation is complete on the branch. Electron
> owns the Helper lifecycle, the signed Helper hosts the full
> `computer-use-macos` Unix socket command service, and the Python sidecar is a
> manifest-driven client only. Dev and release Helper bundles build from the
> same frozen entrypoint; release directory packaging embeds the independently
> identified Helper under `Contents/Library/LoginItems`. Package `ToolEvent` /
> `ToolObservation` projection is present in runtime logs, Audit records, and
> diagnostic bundles. Fixed-Helper no-submit, one controlled external send,
> strict manual reconciliation of its unverified package result, and same-key
> replay/no-duplicate evidence are complete. The remaining release operation is
> distribution signing/notarization; package post-submit parsing can still be
> hardened so future successful sends do not require reconciliation.
>
> Date: 2026-06-30
>
> Architecture decision updated: 2026-07-19
>
> Phase: P8 Backend Integration / P9 QA Readiness
>
> Scope: Migrate Plato/Taskweavn from the repo-owned macOS computer-use and
> WeChat runtime path to the published app-control tool package suite.

## 1. Decision Summary

Plato should consume the new package suite as external tool capabilities:

- `app-control-protocol>=0.3.0,<0.4.0` (current lock: `0.3.0`)
- `computer-use-macos[accessibility]>=0.3.0,<0.4.0; sys_platform == "darwin"`
  (current lock: `0.3.0`)
- `wechat-desktop-tool>=0.3.0,<0.4.0` (current lock: `0.3.0`)

The old compatibility package `macos-computer-use` is not part of the active
integration path.

The migration should not continue expanding `WeChatSendRuntime` or the
repo-local helper protocol. The target model is:

```text
Plato Electron main process
  -> launches and supervises Plato Computer Use Helper.app
  -> launches Plato Python sidecar

Python sidecar
  -> Router / user intent
  -> TaskBus as source of truth
  -> Agent loop
  -> semantic tool call: wechat_desktop.send_message
  -> wechat-desktop-tool
  -> app-control-protocol ToolCommand / ToolEvent / ToolObservation
  -> UnixSocketServiceClient

Plato Computer Use Helper.app
  -> full computer-use-macos LocalCommandService
  -> UnixSocketCommandService
  -> macOS desktop APIs
```

The package suite provides execution capability. It does not decide product
authorization, task lifecycle, conversation projection, audit persistence, or
LLM behavior. Those remain Plato responsibilities.

The Helper service is not an Execution Plane, task queue, or Agent runtime. It
is a local command executor and stable macOS TCC permission subject. TaskBus and
the resident Agent loop remain the only product execution path.

## 2. Product Goal

Support local macOS desktop-control use cases, starting with:

> Open WeChat and send a message to File Transfer Assistant / 文件传输助手.

The same integration should also support future desktop app operations such as:

- reading visible WeChat chat messages;
- drafting without sending;
- sending after a product-level authorization policy permits it;
- adding more app-specific packages without changing Plato core runtime.

## 3. Non-Goals

This migration does not:

- implement remote/LAN execution;
- add LLM logic inside `computer-use-macos` or `wechat-desktop-tool`;
- make the tool package own user confirmation;
- keep extending the repo-local `plato.computer_use_helper.v1` protocol;
- make `WeChatSendRuntime` the long-term app-control execution engine;
- perform hidden retries for side-effecting submit/send commands;
- add screenshot-based automation by default.

## 4. Source Documents

External package docs:

- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/protocol.md`
- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/api.md`
- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/wechat-desktop-tool.md`
- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/agent-integration-guide.md`
- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/wechat-window-data-model.md`
- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/wechat-smoke.md`
- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/manual-smoke.md`
- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/migration-notes.md`
- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/permissions.md`
- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/helper-packaging.md`
- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/local-service.md`
- `/Users/zhanghao/PycharmProjects/pythonProject/macos-computer-use/docs/quickstart.md`

Existing Plato context:

- `docs/plans/feature/local-computer-use-tool.md`
- `docs/plans/feature/local-macos-wechat-send-mvp.md`
- `docs/plans/feature/ui-natural-language-wechat-send-task.md`
- `docs/plans/feature/llm-first-runtime-router.md`
- `docs/plans/feature/computer-use-runtime-observability-and-env-boundary.md`
- `docs/plans/feature/app-control-tool-package-smoke-runbook.zh-CN.md`

## 5. Current State

The current branch now keeps Plato on the package-backed path:

- `src/taskweavn/tools/computer_use.py`
  - generic Plato `computer_use` tool abstraction;
  - safe disabled backend and scripted test backend.
- `src/taskweavn/integrations/app_control/*`
  - owns the new package-facing client factory, observation mapper, and
    observer shim;
  - owns the private Unix socket service manifest, sidecar client adapter, and
    full Helper service host;
  - keeps `app-control-protocol` and `computer-use-macos` imports out of Router
    and TaskBus code.
- `src/taskweavn/server/app_control_helper.py` and
  `app_control_helper_executable.py`
  - host the selector-capable package service in the fixed Helper identity;
  - preserve the package worker contracts for frozen `python -u -c` selector
    children and the strictly allowlisted
    `python -m computer_use_macos._coordinate_click` worker.
- `frontend/electron/computerUseHelperManager.mjs` and
  `computerUseHelperProcess.mjs`
  - launch one Helper per Electron application session;
  - validate the private manifest/token/socket before sidecar startup;
  - inject only the manifest path and structured startup failure into the
    sidecar;
  - stop the Helper when Plato exits.
- `scripts/build_plato_computer_use_helper_dev.py`
  - builds both `dev` and `release` bundle variants from one service entrypoint;
  - includes package schemas/data and PyObjC native runtime files;
  - ad-hoc signs local verification builds before parent release signing.
- `src/taskweavn/tools/computer_use_macos_adapter.py`
  - now builds `ToolCommand` envelopes with `computer-use-macos`;
  - executes through `AppControlClient.run_command`;
  - maps `ToolObservation` into Plato `ComputerUseObservation`;
  - preserves the existing `ComputerUseTool` API during migration.
- `src/taskweavn/tools/wechat_desktop.py`
  - exposes the package-backed semantic WeChat Agent tool;
  - maps package `ToolObservation` into Plato tool observations;
  - records package observer events for runtime diagnostics.
- `src/taskweavn/integrations/wechat_tool/skill.py`
  - loads and validates the wheel-bundled `wechat-use` skill;
  - adapts its version, content hash, instructions, and reference metadata to
    Plato skill governance without exporting a filesystem copy;
  - activates only for `communication.wechat_desktop_send` execution context.
- `src/taskweavn/execution_plane/wechat_task_types.py`
  - owns shared WeChat task type/capability constants without depending on any
    deterministic runtime implementation.

Retired from this branch:

- repo-owned `computer_use_helper_adapter.py`;
- repo-owned `computer_use_helper*.py` server/app/executable builders;
- repo-owned `integrations/wechat_desktop/*` deterministic adapter;
- `wechat_send_runtime.py`, `wechat_send_execution.py`, and
  `wechat_send_boundary.py`;
- legacy smoke scripts that called repo-local helper endpoints;
- tests that asserted `plato.computer_use_helper.v1` or the deterministic
  WeChat runtime path.

The remaining architecture gap is not another runtime. Package `ToolEvent` and
final `ToolObservation` records are projected into runtime logs, diagnostic
bundles, and first-class Audit log evidence records. The remaining proof gap is
external macOS smoke evidence, tracked by
`docs/plans/feature/app-control-tool-package-smoke-runbook.zh-CN.md`.

2026-07-19 package/skill refresh:

- `uv.lock` now resolves `app-control-protocol==0.3.0`,
  `computer-use-macos==0.3.0`, and `wechat-desktop-tool==0.3.0` under the
  active `<0.4.0` constraints.
- The active macOS dependency uses the `computer-use-macos[accessibility]`
  extra so `objc`, `ApplicationServices`, `Cocoa`, and `Quartz` are available
  for real `accessibility_query` operations.
- The installed `wechat-desktop-tool==0.3.0` exposes
  `load_wechat_use_skill()` and a validated `wechat.agent-skill.v1` payload.
  The bundled skill version is `1.0.0`; skill and package versions are tracked
  independently.
- Plato no longer owns `execution-wechat-desktop-send`. Execution context uses
  the package skill's current guidance, including `open_contact`, bounded reads,
  one authorized `send_message(..., verifyAfterSubmit=true)` call, and no
  automatic replay after an unknown mutating outcome.
- The active Plato adapter now exposes `accessibility_query` on the generic
  macOS tool and the read-model WeChat operations on `wechat_desktop`.
- Manual WeChat smoke now requires package contact selection through
  `--allow-focus-select`, which uses the package `open_contact` command. The
  smoke path must not assume the current WeChat chat already matches the target
  contact.

## 6. Target Package Boundaries

### 6.1 `app-control-protocol`

Owns:

- `ToolCommand`
- `ToolObservation`
- `ToolEvent`
- structured tool errors
- JSON schemas
- `AppControlClient` and observer protocols
- logging observer helpers

Does not own:

- LLM decisions;
- business authorization;
- TaskBus state;
- product UI;
- audit persistence.

Plato should use this package as the stable wire/data boundary.

### 6.2 `computer-use-macos`

Owns macOS desktop primitives:

- `readiness`
- `observe`
- `open_app`
- `focus_app`
- `click`
- `type_text`
- `press_key`
- `hotkey`
- `wait`

It can run in:

- direct mode for package development and isolated smoke tests;
- helper transport mode for applications whose helper implements the required
  command set;
- local Unix socket service mode for a long-lived process that owns the macOS
  permission identity and exposes the complete direct backend.

Plato's product path must use the local Unix socket service hosted inside the
signed Helper app. The direct backend is not a Plato product runtime because
its TCC subject changes with the Python host, terminal, IDE, or sidecar launch
chain.

The package-generated minimal helper skeleton is also insufficient for the
WeChat 0.3 path. It does not expose the complete selector-backed
`accessibility_query` / `accessibility_action` surface used by
`wechat-desktop-tool`. Plato Computer Use Helper must therefore embed the full
service host:

```python
app_control = ComputerUseClient.from_config("app-control.toml")
service = LocalCommandService(app_control, token=token)
server = UnixSocketCommandService(socket_path, service)
server.serve_forever()
```

The Helper owns the direct backend and executes macOS APIs. The sidecar uses
`UnixSocketServiceClient` and never executes macOS Accessibility work itself.

### 6.3 `wechat-desktop-tool`

Owns WeChat semantic operations:

- `open_wechat`
- `focus_contact`
- `observe_current_chat`
- `read_visible_messages`
- `draft_message`
- `submit_draft`
- `send_message`

It depends only on the app-control protocol/client surface:

```python
from computer_use_macos.service import UnixSocketServiceClient
from wechat_desktop_tool import build_wechat_tool

app_control = UnixSocketServiceClient(socket_path, token=token)
wechat = build_wechat_tool(app_control)
```

Plato should prefer granular calls for read, inspect, and draft-only flows. For
an exact authorized send task, Plato should prefer one semantic Agent tool
call:

```text
wechat_desktop.send_message(
  contact="文件传输助手",
  message="你好",
  verify_after_submit=true
)
```

The Agent-visible schema does not expose `idempotency_key`. Before invoking the
package, the Plato tool adapter derives a stable send-boundary key from durable
product execution identity (`session_id + TaskBus task_id`) and injects it into
the package command. The LLM therefore chooses the semantic operation and its
business arguments, but cannot invent, replace, or reuse the product's
side-effect identity.

`wechat-desktop-tool` expands that semantic call into the bounded sequence of
`open_app`, observation, Accessibility query/action, text entry, keyboard
submit, and post-submit observation commands. Those lower-level commands cross
the Unix socket individually; the Agent receives one semantic WeChat
observation plus streamed evidence. This keeps the side-effect boundary visible
without asking the LLM to reproduce deterministic macOS command sequences.

## 7. Plato Integration Architecture

### 7.1 New Internal Modules

Add a small package-facing integration layer:

```text
src/taskweavn/integrations/app_control/
  __init__.py
  config.py
  client_factory.py
  observation_mapper.py
  observer.py

src/taskweavn/integrations/wechat_tool/
  __init__.py
  client.py
  tool_adapter.py
```

Responsibilities:

- read the Electron-provided endpoint manifest and create
  `UnixSocketServiceClient`;
- create `WeChatDesktopTool`;
- map `ToolObservation` into Plato tool observations, activity logs, audit
  evidence, and diagnostic-safe summaries;
- map `ToolEvent` into structured runtime logs;
- keep package-specific imports out of Router and TaskBus code.

Electron owns a separate process-supervisor module. It resolves the packaged
Helper app, launches it once per Plato application session, passes the endpoint
manifest path to the sidecar, and terminates the Helper when Plato exits. The
sidecar client factory must not launch, restart, or rebuild the Helper.

### 7.2 Agent Loop Tool Surface

Expose app-control capabilities as Agent loop tools:

```text
tool: computer_use
  operations:
    readiness
    observe
    accessibility_query
    open_app
    focus_app
    click
    type_text
    press_key
    hotkey
    wait

tool: wechat_desktop
  operations:
    open_wechat
    inspect_window
    list_contacts
    list_conversations
    open_contact
    focus_contact
    observe_current_chat
    read_visible_messages
    read_contact_messages
    draft_message
    submit_draft
    send_message
```

`wechat_desktop.submit_draft` and `wechat_desktop.send_message` are
side-effecting operations. The package-backed tool exposes capability; it does
not decide product authorization. Plato owns the authorization boundary through
task policy and runtime skill guidance before making the tool call.

#### 7.2.1 Tool Call To Service Command Contract

The Agent calls a semantic tool; it does not call the Helper service or Unix
socket directly. The package-facing adapter is the dependency boundary between
Agent reasoning and the local command service:

```text
Agent loop
  -> AgentToolCall(name="wechat_desktop", operation="send_message", args=...)
  -> Plato tool registry / package adapter
  -> inject managed send-boundary key from session_id + TaskBus task_id
  -> WeChatDesktopTool.send_message(..., idempotency_key=<managed key>)
  -> one or more app-control-protocol ToolCommand envelopes
  -> UnixSocketServiceClient
  -> Plato Computer Use Helper service
  -> macOS desktop APIs

Plato Computer Use Helper service
  -> ToolEvent* + final ToolObservation
  -> UnixSocketServiceClient
  -> WeChat package adapter
  -> AgentToolResult
  -> Agent loop / TaskBus result / Conversation reply
```

This split is intentional:

| Layer | Accepts | Returns | May decide |
| --- | --- | --- | --- |
| Agent loop | Task context, skills, tool schemas | Tool calls and task result | What capability to call and how to respond to the result |
| Plato tool adapter | Semantic Agent tool call plus TaskBus execution identity | `AgentToolResult` | Schema validation, managed send-boundary identity, package invocation, and projection only |
| `wechat-desktop-tool` | Semantic WeChat operation | Semantic observation plus streamed evidence | Deterministic bounded command expansion only |
| Helper service | Protocol `ToolCommand` | `ToolEvent` and `ToolObservation` | Command validation and desktop execution only |

The Agent never receives the socket path or service token, and the Helper never
receives conversation history, prompts, TaskBus state, or product authorization
policy. This prevents transport details from leaking into Agent reasoning and
prevents the service from becoming a second runtime or decision layer.

A failed service command is still a completed tool call with a structured
failure observation. The adapter must preserve at least `failureKind`,
`message`, `phase`, `recoveryHint`, `retryable`, `sendAttempted`, and safe
evidence references. The Agent uses that result to finish the current task and
produce a concise user-visible reason. It must not translate the failure into a
generic "tool unavailable" answer when a concrete package reason exists.

For a mutating operation, neither the adapter, sidecar, Helper, nor Agent loop
automatically replays the command. A later retry is a new user- or
policy-authorized action with an explicit send-boundary decision. Read-only
operations may use bounded retry only when the package marks the failure as
retryable and the product runtime policy permits it.

### 7.3 TaskBus And Agent Loop

TaskBus remains the single source of truth for task state. The migration should
not introduce a separate durable execution plane for WeChat.

For `communication.wechat.send_message`:

1. Router publishes or updates a TaskBus task.
2. Agent loop receives the task.
3. Runtime skills explain how to use `wechat_desktop` and `computer_use`.
4. Product authorization policy is resolved before a send tool call.
5. Agent loop calls `wechat_desktop.send_message` once with the exact contact,
   message, and post-submit verification flag.
6. Plato's tool adapter derives and claims the durable send-boundary key from
   `session_id + TaskBus task_id`, then injects that managed key into the
   package invocation. The key is not part of the Agent-visible schema.
7. `wechat-desktop-tool` expands the semantic operation into multiple bounded
   `ToolCommand` requests to the Helper service.
8. Streamed events and the final semantic observation become task evidence.
9. Agent loop finalizes the task result.

`WeChatSendRuntime` is not part of the target route. The migrated path should
fail closed if no package-backed tool/runtime handler is configured, instead
of falling back to the retired deterministic runtime.

### 7.4 Service Startup And Process Ownership

There are two local services with different responsibilities:

- Plato Python sidecar: Router, TaskBus, Agent loop, HTTP/SSE product API;
- Plato Computer Use Helper: local app-control Unix socket command service and
  macOS TCC permission subject.

Electron main is the only process owner for both. The app-control startup
sequence is:

1. Electron resolves the stable Helper app path and endpoint manifest path.
2. Electron launches the Helper app through the macOS application launch path.
3. The Helper starts the full `LocalCommandService` /
   `UnixSocketCommandService`, creates the token and socket with `0600`
   permissions, and publishes endpoint metadata.
4. Electron starts the Python sidecar with the manifest path as process input.
5. The sidecar creates a service client but never starts the service itself.
6. On Plato exit, Electron terminates the Helper and, as the process owner,
   removes the private manifest, token, and socket paths it provisioned. The
   Helper also performs best-effort service cleanup when it exits. macOS
   permissions remain attached to the stable Helper identity.

Helper startup failure must not prevent the rest of Plato from opening. It
marks computer use unavailable; the next affected tool call returns the
concrete structured service or permission failure to the Agent, which projects
one concise reason and bounded recovery action into Conversation. Plato does
not launch `launchd`, a login item, or a detached daemon for this first product
slice.

The Helper is launched at most once per Plato application session. If it exits
during an active task, the task fails with `service_unavailable`. Neither the
sidecar nor the Agent loop restarts the Helper or replays the mutating command
inside that task.

## 8. Configuration Model

### 8.1 App-Level Config

Current Plato settings are app-level. The first migration slice should keep
that behavior. Normal users should not choose a transport or edit socket/token
values. Electron owns service discovery and injects the manifest path into the
sidecar process.

Recommended config keys:

```toml
[computer_use]
enabled = true
allowed_apps = ["WeChat"]
timeout_ms = 10000
allow_coordinate_click = true

[computer_use.allowed_app_bundle_ids]
WeChat = "com.tencent.xinWeChat"

[helper]
transport = "unix_socket"
manifest_path = "<Electron process input>"
```

`allow_coordinate_click` is an app-level, startup-only policy and remains
explicitly configurable. It defaults to `true` for Plato's private,
app-allowlisted Helper because current WeChat conversation rows can expose a
verified in-window frame without advertising `AXPress`; `wechat-desktop-tool`
then uses that current frame as its bounded semantic-operation fallback. This
does not authorize a message send, bypass TaskBus identity, or replace
operation-level confirmation and audit.

The existing `computer_use.backend` key may remain as a transitional diagnostic
value, but the packaged macOS product fixes it to the Helper-hosted service
path. The Helper app path and process lifecycle are Electron-owned; endpoint
and token values are private service outputs. The sidecar receives only the
manifest path. None of these values are user-facing runtime behavior. WeChat
operation behavior is owned by `wechat-desktop-tool` configuration and the
package `wechat-use` skill, not by new Plato top-level settings.

### 8.2 Dev Mode

Development must mirror the release process boundary:

```text
Helper app: ~/Applications/Plato Computer Use Helper Dev.app
Bundle id:  com.taskweavn.plato.computer-use-helper.dev
Launcher:   Electron main via npm run electron:dev
Service:    full computer-use-macos Unix socket command service
```

The user grants macOS Accessibility permission to this fixed Dev Helper once.
Direct mode remains available only for package-level tests and isolated CLI
smokes; it is not an accepted Plato end-to-end product test path. Ordinary
sidecar or frontend changes do not rebuild the Helper. A package/runtime change
inside the Helper requires an explicit Helper rebuild and restart.

Build or refresh the stable Dev Helper explicitly:

```bash
uv run --group packaging python scripts/build_plato_computer_use_helper_dev.py \
  --variant dev
```

After the app exists at the fixed path, plain `npm run electron:dev` on macOS
selects the Helper-hosted WeChat service. Set
`PLATO_COMPUTER_USE_BACKEND=disabled` for a run that must not start it.

### 8.3 Release Mode

The release contains one user-installed Plato application with an embedded,
independently signed nested Helper app:

```text
Plato.app
  Contents/Library/LoginItems/Plato Computer Use Helper.app

Helper bundle id: com.taskweavn.plato.computer-use-helper
```

The Helper is the stable TCC permission subject and contains the complete
service runtime needed by `wechat-desktop-tool`. Plato owns its identity,
signing, notarization, packaging, and launch lifecycle. Package helper tooling
may scaffold, sign, notarize, and diagnose the bundle, but the generated
minimal `helper_main.py` must be replaced by Plato's full service host before
release.

`frontend/scripts/package-electron-dir.mjs` builds the release Helper variant,
places it in `Contents/Library/LoginItems`, and records its path in
`package-manifest.json`. The release-assets checker requires that nested app to
exist and remain inside the Plato bundle. Final distribution signing and
notarization replace the local ad-hoc verification signature.

## 9. Side-Effect And Authorization Policy

Tool packages do not own business authorization. Plato must gate side effects.

Policy:

- `open_wechat`, `focus_contact`, `draft_message`, and read operations may run
  under normal task execution policy.
- `submit_draft` and `send_message` require whatever authorization the product
  policy selects before the tool call. The Helper service never asks for
  confirmation and never makes this business decision.
- If `submit_draft` or verified send returns `unknown`, Plato must not auto
  retry.
- Future "automatic chat" can be enabled by a product-level authorization
  policy, not by making the tool package decide.

This keeps automation useful while preserving a clear action boundary.

Failure handling is intentionally narrow:

1. Preserve the package's `failureKind`, `message`, `phase`, and
   `sendAttempted` evidence.
2. Finish the task as failed or unknown.
3. Project one concise reason into Conversation.
4. Do not create an ordinary plan/task fallback, restart the Helper, replan, or
   replay the mutating command automatically.

When `sendAttempted=false`, the user message must state that the message was not
sent and why. When a submit may have been attempted but verification is
inconclusive, the user message must state that the send result is unknown and
that Plato will not retry automatically.

## 10. Observation And Logging Projection

Every package command should produce structured logs:

```json
{
  "source": "app_control_tool",
  "commandId": "cmd_...",
  "tool": "wechat.desktop",
  "operation": "focus_contact",
  "phase": "focus_contact.type_contact",
  "status": "ok",
  "success": true,
  "failureKind": null,
  "summary": "Contact focused.",
  "durationMs": 321
}
```

Projection rules:

- `ToolEvent` -> runtime log rows, optionally task evidence refs.
- final `ToolObservation` -> task evidence and audit detail.
- `failureKind`, `message`, `recoveryHint`, `retryable`, and `phase` must be
  preserved.
- Conversation projects only the concise product failure reason. Technical
  fields remain available in Audit and diagnostics; the Router does not invent
  an alternative explanation or recovery workflow.
- message bodies should be redacted in logs by default. Store preview/hash or
  bounded product-visible content only where the user already provided it.
- diagnostic bundle should include command ids, operation names, status,
  failure kinds, recovery hints, and safe evidence refs.

## 11. Migration Phases

### M0. Dependency Baseline

Status: completed on branch.

- Add three package dependencies.
- Remove old `macos-computer-use` dependency.
- Verify imports and command builders through `uv run`.

Acceptance:

- `pyproject.toml` declares only the three active packages.
- `uv.lock` contains `app-control-protocol`, `computer-use-macos`, and
  `wechat-desktop-tool`.

### M1. Protocol-First Client Bridge

Status: completed on branch for protocol mapping and observation projection.
The production service-client selection is part of the re-opened M5.

Add `taskweavn.integrations.app_control`.

Implementation:

- `AppControlClientFactory`
  - accepts an `AppControlClient` protocol implementation;
  - uses fake/direct clients for tests and package smokes;
  - will select `UnixSocketServiceClient` from the Electron-provided endpoint
    manifest for the product path.
- `ToolObservationMapper`
  - maps protocol observations to Plato-safe status/evidence.
- `PlatoToolObserver`
  - records `ToolEvent` progress into existing runtime logs.

Acceptance:

- fake `AppControlClient` unit tests pass without macOS.
- readiness command can be executed through the new bridge.
- no Router or TaskBus code imports `computer_use_macos` directly.

### M2. Replace Old macOS Adapter

Status: completed on branch for the package-backed macOS adapter.

Replace `src/taskweavn/tools/computer_use_macos_adapter.py` internals.

Implementation:

- remove dynamic import of `macos_computer_use`;
- use `computer_use_macos.ComputerUseClient`;
- prefer `ToolCommand` and `run_command` over old convenience result mapping;
- preserve current `ComputerUseTool` API for existing callers during transition.

Acceptance:

- `rg "macos_computer_use" src/taskweavn` returns no production imports.
- existing generic computer-use tests pass with fake clients.
- direct readiness smoke can run on macOS when enabled.

### M3. Introduce WeChat Package Tool Adapter

Status: implemented on branch for the Agent-loop tool surface. Plato exposes a
package-backed `wechat_desktop` tool, maps `ToolObservation` evidence into
Plato observations, and records streamed package `ToolEvent` rows as sanitized
runtime log metadata for diagnostic bundle export and Audit log evidence records.

Add `taskweavn.integrations.wechat_tool`.

Implementation:

- create `WeChatDesktopTool` from the shared app-control client;
- expose granular operations to the Agent loop;
- map package observations into task evidence;
- preserve failure kinds such as `wechat_not_ready`, `wechat_not_logged_in`,
  `contact_not_found`, `contact_ambiguous`, `input_not_focused`,
  `submit_unknown`, and `send_unverified`.

Acceptance:

- fake app-control client verifies the exact sequence for:
  - focus contact;
  - draft message;
  - read visible messages;
  - submit draft with authorization.
- no product code reimplements WeChat search/focus/draft sequencing.

### M4. Move WeChat Send To Agent Loop

Status: implemented on branch for routing. `communication.wechat.send_message`
publishes to TaskBus without a special `WeChatSendRuntimeHandler`; Runtime
Input Router hands off to the resident Agent loop / package-backed tool path
for pending WeChat tasks. The deterministic runtime handler has been deleted
from production and test code. A session-scoped SQLite effect ledger now claims
the send boundary before package execution and persists the terminal
observation. The managed key is derived from `session_id + TaskBus task_id`; it
is not part of the LLM-visible `WeChatDesktopAction` schema.

Route `communication.wechat.send_message` to normal Agent loop execution using
runtime skills.

Implementation:

- load the package-owned `wechat-use` skill into matching execution context;
- ensure Router creates a task, not a special runtime-only execution object;
- resolve product authorization before the mutating tool call;
- let Agent loop call `wechat_desktop.send_message` once for the exact contact
  and message;
- derive a stable send-boundary idempotency key from TaskBus execution state;
- persist `in_progress`, `completed`, and `unknown` send-boundary states before
  and after the package call;
- replay a matching completed observation without calling the package again,
  reject a changed payload as `idempotency_conflict`, and fail closed for
  unknown or interrupted records;
- let the package own deterministic contact selection, input verification,
  submit, and post-submit observation.

Acceptance:

- UI natural-language request creates a TaskBus task.
- Conversation shows user input immediately.
- Task activity shows tool command progress.
- No ordinary Default Agent fallback claims WeChat is unavailable when the
  package tool is configured.

### M5. Helper Migration

Status: repository implementation complete. External product smoke and final
distribution signing/notarization evidence remain.

Do not restore repo-local helper protocols. Build a Plato-owned signed app that
hosts the package's complete local command service.

Implementation:

- build `Plato Computer Use Helper Dev.app` with stable dev bundle id
  `com.taskweavn.plato.computer-use-helper.dev`;
- build release `Plato Computer Use Helper.app` with stable bundle id
  `com.taskweavn.plato.computer-use-helper`;
- embed the full `ComputerUseClient` direct backend,
  `LocalCommandService`, and `UnixSocketCommandService` in the Helper app;
- package the required `computer-use-macos[accessibility]` runtime and PyObjC
  dependencies inside the Helper;
- publish socket/token endpoint metadata for `UnixSocketServiceClient`;
- have Electron main launch the Helper once, pass the manifest path to the
  sidecar, and terminate the Helper on app exit;
- remove product-side direct backend selection and sidecar Helper auto-launch;
- continue using package helper build/sign/notarize/doctor tooling where it
  applies, while replacing the minimal generated service entrypoint with the
  complete Plato service host.

Acceptance:

- `npm run electron:dev` launches the fixed Dev Helper without a separate
  terminal service command;
- all macOS Accessibility calls originate from the Helper permission subject;
- sidecar restart does not replace or restart the Helper;
- Helper startup or permission failure is returned as a structured observation
  and concise Conversation reason;
- the Helper service supports the complete WeChat 0.3 selector-backed command
  sequence;
- release packaging installs one Plato app containing the signed nested
  Helper;
- old helper HTTP endpoints and the minimal helper skeleton are not active
  product dependencies.

### M6. Retire Old WeChat Runtime

Status: implemented on branch for production/test code. Historical design docs
may still mention older scripts as archive context, but no source or active test
imports the retired modules.

After M1-M5 pass, remove or isolate old code.

Retire:

- `WeChatSendRuntimeHandler`;
- `WeChatDesktopAdapter`;
- `FakeWeChatDesktopAdapter` except as rewritten package-test fakes;
- `computer_use_helper_adapter.py`;
- `computer_use_helper*.py` server/app/executable builders;
- tests that assert `plato.computer_use_helper.v1`;
- smoke scripts that call repo-local helper endpoints.

Acceptance:

- no production route depends on `WeChatSendRuntime`;
- no production route depends on `plato.computer_use_helper.v1`;
- package-backed smoke evidence replaces old smoke evidence.

## 12. Test Strategy

### Unit Tests

- fake `AppControlClient` returns deterministic `ToolObservation`;
- observer records `ToolEvent` progress;
- observation mapper preserves:
  - `status`
  - `success`
  - `failureKind`
  - `message`
  - `recoveryHint`
  - `retryable`
  - `phase`
  - `evidence`
- product-level policy resolves authorization before mutating calls; the
  package-backed tool and Helper remain command executors;
- send-boundary idempotency is derived from stable TaskBus execution identity,
  not invented by the LLM;
- failure projection emits the package reason without automatic recovery or
  ordinary-task fallback.

### Integration Tests Without macOS

- Router publishes `communication.wechat.send_message` task.
- Agent loop sees `wechat_desktop` tool availability.
- fake package client receives one semantic `send_message` call and expands it
  into bounded service commands.
- the configured authorization path reaches that call exactly once.
- a completed same-key call reuses the durable observation across process
  reopen without invoking the package client again;
- same key with changed contact/message returns `idempotency_conflict` before
  package execution;
- unknown and residual `in_progress` records never replay a send;
- `unknown` submit observation fails closed and does not retry.
- `service_unavailable` and `permission_missing` become concise Conversation
  failures with the original technical evidence retained in Audit.

### macOS Manual Smokes

Follow `docs/plans/feature/app-control-tool-package-smoke-runbook.zh-CN.md`
for operator commands, evidence paths, safety rules, and pass/fail
classification.

1. Fixed Dev Helper startup and service readiness through Electron.
2. TextEdit service-backed smoke from the Dev Helper permission subject.
3. WeChat service-backed focus/draft smoke, no submit.
4. Controlled submit-once smoke to `文件传输助手`.
5. Same idempotency key replay must not send again.
6. Helper stopped and permission-missing failures show the concrete reason and
   do not trigger automatic recovery.

### Release Checks

- helper doctor JSON archived;
- helper signature/notarization evidence when release helper exists;
- packaged Helper exposes selector-backed `accessibility_query` and
  `accessibility_action`, not only the minimal helper operation set;
- one installed Plato app launches the nested Helper and cleans it up on exit;
- diagnostic bundle includes safe package command evidence;
- Electron smoke verifies UI projection of user input, task progress, concise
  failure reason, and result.

## 13. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Package API changes within the `0.3` line | Adapter churn | Keep all package imports behind `integrations/app_control` and `integrations/wechat_tool`. |
| macOS TCC subject confusion | Readiness false negatives | Use the fixed Helper permission subject in both Plato dev and release paths. |
| Minimal package helper lacks selector operations | WeChat tool cannot resolve contacts or actions | Embed the full local command service/direct backend in the Plato Helper and test its enabled operations. |
| Helper lifecycle is split across Electron and sidecar | Duplicate service or stale socket | Make Electron the only launcher; sidecar is client-only. |
| `submit_draft` returns `unknown` after key press | Duplicate message risk | Fail closed and do not retry automatically. |
| WeChat UI changes | Contact focus/draft failures | Preserve failureKind/recoveryHint and keep package smoke current. |
| Old runtime re-enters active code | Confusing behavior | Keep retired modules deleted and scan for old imports in migration checks. |
| Logs leak message content | Privacy risk | Redact tool events; keep preview/hash only where product explicitly displays user-provided text. |

## 14. Implementation Order

Completed foundation:

1. `app-control` protocol bridge and observation mapper.
2. package-backed `computer_use` and `wechat_desktop` adapters.
3. Agent loop tool registration and package skill loading.
4. UI/evidence/log projection for package events and observations.
5. Old deterministic runtime and repo-local helper protocol removal.

Completed product integration:

1. Full Dev/Release Plato Helper service host and frozen worker contract.
2. Electron Helper launch, manifest injection, and shutdown supervision.
3. Sidecar-only `UnixSocketAppControlClient` over the package
   `UnixSocketServiceClient`.
4. Stable send-boundary policy and concise failure projection contracts.
5. Release directory embedding and nested Helper asset/signature checks.

Completed operator sequence:

1. Install or rebuild the fixed Dev Helper and grant Accessibility once.
2. Run Electron startup/readiness and service-failure E2E.
3. Run Helper-backed no-submit contact resolution.
4. Authorize one controlled send-once, reconcile its fail-closed unknown result
   from exact read-only evidence, and prove same-key replay sends no duplicate.

Remaining release/improvement work:

1. Apply Developer ID distribution signing and notarization when release
   credentials are available; local packaging remains deliberately ad-hoc.
2. Improve package post-submit message parsing so an exact successful send can
   complete automatically instead of requiring manual reconciliation.

## 15. Acceptance Criteria

The migration is accepted when:

- `macos-computer-use` is not declared as a dependency.
- production source no longer imports `macos_computer_use`.
- Plato creates package-backed `computer_use` and `wechat_desktop` tools.
- WeChat send task runs through Agent loop tool calls, not hardcoded
  `WeChatSendRuntime` sequencing.
- Agent calls semantic tools only; package adapters own protocol translation,
  and only `UnixSocketServiceClient` communicates with the Helper service.
- Agent uses one semantic `wechat_desktop.send_message` call for an exact
  authorized send; deterministic lower-level command sequencing stays inside
  the package.
- Electron is the sole owner of Helper startup and shutdown; the sidecar only
  consumes the endpoint manifest.
- Development and release both execute macOS APIs from a fixed Helper bundle
  identity, never from the sidecar's direct backend.
- The packaged Helper hosts the full selector-capable command service.
- Helper/service/permission failures produce a concise Conversation reason and
  no automatic restart, replan, fallback, or send replay.
- Failed tool calls preserve the concrete package failure fields through
  `AgentToolResult`, TaskBus evidence, Audit, and the user-visible failure
  summary.
- release packaging presents one Plato installation containing the signed
  nested Helper app.
- `ToolEvent` and `ToolObservation` are visible in logs/audit/diagnostics.
- real package-backed focus/draft smoke passes without sending.
- one real controlled confirm/send-once smoke to `文件传输助手` passes.
- real replay with the same product idempotency key does not send again.

## 16. Verification Snapshot

Date: 2026-07-21.

Verified in the current worktree:

- `uv tree --depth 1` and `uv.lock` resolve `app-control-protocol==0.3.0`,
  `computer-use-macos==0.3.0`, and `wechat-desktop-tool==0.3.0`; it does not
  list `macos-computer-use`.
- Package import probing confirms the `0.3.0` command builders remain
  compatible and `wechat-desktop-tool` loads the complete `wechat-use` skill
  with verified file hashes.
- Earlier migration baseline used `uv sync --frozen` to prune the stale local
  `.venv` install of `macos-computer-use==0.1.0`.
- `uv run python ...` confirms:
  - new package imports are available;
  - `importlib.util.find_spec("macos_computer_use")` is false.
- `rg` over `src/taskweavn tests scripts` finds no active imports or class
  references for the retired repo-local helper/runtime path:
  - `taskweavn.server.computer_use_helper*`
  - `taskweavn.tools.computer_use_helper_adapter`
  - `taskweavn.execution_plane.wechat_send_*`
  - `taskweavn.integrations.wechat_desktop`
  - `WeChatSendRuntimeHandler`
  - `WeChatDesktopAdapter`
  - `macos_computer_use`
- `uv run pytest` passed with `1561 passed, 10 skipped` after the complete
  package migration, send-boundary reconciliation, and Electron product-backend
  hardening. Socket-based tests were rerun outside the filesystem sandbox after
  the sandbox-only run failed exclusively at `socket.bind`.
- `uv run python scripts/manual_wechat_desktop_tool_smoke.py --help` passed
  without opening WeChat.
- `tests/test_manual_wechat_desktop_tool_smoke_script.py` verifies the
  replacement smoke script's no-submit path, explicit submit guard, and
  `--allow-submit --confirm-submit SEND` submit path without touching WeChat.
- The full frozen Dev Helper was built from the current source. A real
  manifest/token/socket round trip returned `readiness: ready`,
  `accessibility_trusted=true`, and selector-backed `accessibility_query` /
  `accessibility_action` operations. The service files were private and were
  removed on shutdown.
- The frozen entrypoint was verified against the package's actual
  `sys.executable -u -c` Accessibility worker launch contract and its
  `sys.executable -m computer_use_macos._coordinate_click` coordinate worker.
  The module path is allowlisted rather than treated as a general Python
  module launcher. Protocol JSON schemas are included as package data in the
  Helper bundle.
- A temporary Electron launcher directory successfully embedded
  `Plato Computer Use Helper.app` at `Contents/Library/LoginItems`. The
  release-assets checker reported `failureCount=0`, `externalSymlinks=0`, and
  the nested Helper passed `codesign --verify --deep --strict` with bundle id
  `com.taskweavn.plato.computer-use-helper`. The current local signature is
  ad-hoc; distribution signing and notarization remain release operations.
- Electron product startup now accepts only `helper` or `disabled`. The dev CLI
  rejects `--computer-use-backend macos`, and Electron main coerces a legacy
  direct value to the fixed Helper path on macOS. The sidecar direct backend is
  retained only for isolated package/CLI tests.
- The stable `~/Applications/Plato Computer Use Helper Dev.app` was rebuilt as
  version `0.3.0` and launched by `npm run electron:dev`. Electron started the
  full Helper service before the sidecar, and the live manifest reported the
  expected dev bundle id, service version, app path, pid, Unix socket, and
  private token path.
- The live Settings readiness projection reported `backend=helper`,
  `failureKind=missing_accessibility`, the exact Dev Helper path and bundle id,
  verified its ad-hoc signature, and returned bounded recovery actions. A
  no-submit smoke stopped at readiness and did not open or modify WeChat;
  evidence: `/tmp/plato-electron-helper-draft-20260719-1738.json`.
- Electron SIGINT shutdown was exercised against an isolated live product path
  (`PLATO_ELECTRON_USER_DATA_DIR=/tmp/plato-helper-lifecycle-verify-2`). The
  exercise first exposed a real duplicate-signal/stale-runtime-file gap. The
  shared signal handler now keeps `SIGINT` / `SIGTERM` listeners installed while
  requesting shutdown only once, and Electron removes the three private runtime
  paths it owns after signalling the Helper. The repeated live run proved that
  Helper PID `41066` stopped and the manifest, token, and socket were all absent
  one second after Ctrl-C.
- The managed WeChat send boundary now uses
  `.plato/sessions/<session_id>/tool_effects.sqlite`. Focused tests prove that a
  completed result is replayed across SQLite reopen without a second package
  call, changed content conflicts before execution, and `unknown` /
  `in_progress` records never replay. The package command receives the key
  derived from `session_id + TaskBus task_id`; the LLM action schema does not
  expose the key.
- Fresh temporary Dev and release Helper bundles were rebuilt from the current
  source at version `0.3.0`. Both passed `codesign --verify --deep --strict`;
  their bundle ids were respectively
  `com.taskweavn.plato.computer-use-helper.dev` and
  `com.taskweavn.plato.computer-use-helper`. Both frozen executables passed the
  `python -c` worker check and dispatched the exact allowlisted
  `computer_use_macos._coordinate_click` module. The module check used an
  invalid coordinate and exited during integer parsing before posting any
  mouse event.
- A bounded `--readiness-only` smoke path now queries the fixed Helper and
  exits before any WeChat operation. On 2026-07-19 it ran against
  `/Users/zhanghao/Applications/Plato Computer Use Helper Dev.app`; evidence
  `/tmp/plato-app-control-readiness-20260719.json` contains exactly one
  `readiness` observation, reports `readinessOnly=true`,
  `failure_kind=missing_accessibility`, `accessibility_trusted=false`, and no
  open/contact/draft/submit operation. The Helper was stopped and its temporary
  manifest, token, and socket were absent afterward.
- The latest migration-focused backend suite passed 92 tests. One Unix-socket
  round-trip required running outside the filesystem sandbox and then passed.
- Full frontend Vitest passed with 77 test files and 576 tests; ESLint completed
  with zero errors and two pre-existing Fast Refresh warnings; the TypeScript /
  Vite production build passed. Ruff passed for `src/taskweavn`, `tests`, and
  `scripts`; focused mypy passed for all 27 changed source modules. Full-source
  mypy still reports five pre-existing errors in three unrelated modules.
- Current fixed-Helper Smoke B passed through `open_contact`, `draft_message`,
  and `observe_current_chat` without submit. Evidence:
  `/tmp/plato-wechat-package-draft-20260721-215213.json`.
- One separately authorized Smoke C used
  `session_id=plato-wechat-smoke-20260721-222218`,
  `task_id=wechat-send-20260721-222218`, and exact message
  `Plato package-backed submit smoke 20260721-222218`. The package pressed
  Return once but returned `status=unknown` / `send_unverified`. No retry ran.
  Read-only inspection found exactly one matching outgoing message and an empty
  input, after which the exact scope/key/request/contact/message hashes were
  manually reconciled from `unknown` to `completed`. Original evidence:
  `/tmp/plato-wechat-package-submit-20260721-222218.json`; reconciliation:
  `/tmp/plato-wechat-package-submit-20260721-222218-reconciliation.json`.
- Separately authorized Smoke D reused the same session, task, contact, message,
  and effect database with new smoke id
  `plato-wechat-package-replay-20260721-225215`. It returned
  `replayed=true`, `submitAttempted=false`, and `submitted=false`; current-run
  events contained only readiness and no new send command. Evidence:
  `/tmp/plato-wechat-package-replay-20260721-225215.json`.

## 17. Completion Audit

This audit treats completion as unproven until every acceptance item has direct
current-state evidence.

| Requirement | Current evidence | Status |
|---|---|---|
| Remove old `macos-computer-use` dependency | `uv tree --depth 1` lists `app-control-protocol`, `computer-use-macos`, and `wechat-desktop-tool`; `pyproject.toml` / `uv.lock` do not contain `macos-computer-use`; `importlib.util.find_spec("macos_computer_use")` is false. | Done |
| Remove retired repo-local helper/runtime code | Old helper server/app builders, helper adapter, repo-local WeChat adapter, deterministic runtime, send execution, send boundary, and old smoke scripts are deleted from active source/tests. Active-source `rg` only finds one negative CLI assertion for the retired preflight command. | Done |
| Route WeChat send through TaskBus / Agent loop tools | Router tests cover `communication.wechat.send_message` publishing to Execution Plane and dispatch trigger. Runtime skills select package-backed `wechat_desktop` / `computer_use` tools instead of `WeChatSendRuntimeHandler`. | Done |
| Keep the package protocol/service boundary narrow | Router and TaskBus import no package implementation. The tool adapters build semantic package commands; `service_client.py` is the only sidecar `UnixSocketServiceClient` owner, while the direct `ComputerUseClient` is confined to the Helper host and isolated CLI/package paths. | Done |
| Use one semantic send call | The Agent schema exposes one `wechat_desktop.send_message` operation. Adapter tests assert one package call, and Smoke C's current event/evidence chain contains one semantic send whose lower contact/draft/submit sequence is package-owned. | Done |
| Preserve confirmation policy before intended submit | Router task draft requires `requiresHumanConfirmation=true`, `riskLevel=high`, and `communication.wechat_desktop_send`. Manual submit smoke requires `--allow-submit --confirm-submit SEND`. | Done |
| Durable send-boundary idempotency | `WeChatDesktopTool` receives a managed key derived from session/task identity and claims a SQLite effect record before package execution. Tests cover completed replay across reopen, changed-payload conflict, unknown no-replay, and interrupted `in_progress` persistence. Smoke D reused the exact reconciled identity and effect DB without another send attempt. | Done |
| Preserve package events / observations for debugging | `tests/test_wechat_desktop_tool.py` verifies redacted runtime log emission; diagnostic bundle tests cover app-control runtime evidence projection. | Done |
| Electron owns the complete Helper service lifecycle | `computerUseHelperManager.mjs` / `computerUseHelperProcess.mjs` own one launch attempt, private runtime paths, manifest validation, sidecar injection, and shutdown. `gracefulShutdown.mjs` absorbs duplicate terminal/CLI signals while requesting cleanup once. An isolated live Electron run launched the rebuilt fixed Dev Helper before sidecar startup; Ctrl-C stopped Helper PID `41066` and removed manifest/token/socket files. | Done |
| Helper exposes the complete selector service | Frozen Dev/release worker tests cover the package's `python -c` selector worker and allowlisted coordinate module. Real readiness advertised `accessibility_query` / `accessibility_action`, and current Smoke B completed package `open_contact` through the fixed Helper. | Done |
| Release embeds one stable Helper app | `package-electron-dir.mjs --with-launcher` built one Plato app with the release Helper under `Contents/Library/LoginItems`; release-assets returned `failureCount=0` / `externalSymlinks=0`, and nested deep codesign plus release bundle-id verification passed. | Done for migration; Developer ID signing/notarization remains release operations |
| Product uses the fixed Helper identity | Electron product startup accepts `helper` or `disabled`; the dev CLI rejects `macos`, and legacy direct input is forced to Helper on macOS. Sidecar direct mode remains available only for isolated package/CLI tests. | Done |
| Product failure path only explains the concrete failure | Live Settings readiness projected `missing_accessibility`, the exact Helper app identity/signature, and bounded recovery actions. `tests/test_app_control_migration_conversation.py` drives the real sidecar Router -> Execution Plane -> TaskBus -> asynchronous dispatcher -> summary/message-stream -> snapshot path and proves the user input plus concrete Helper permission reason reach Conversation while the scripted desktop backend receives zero actions. `MainPage.appControlFailure.test.tsx` renders that contract and proves the input, `missing_accessibility`, Helper identity, Open settings, and Retry command are visible. | Done |
| Preserve failure fields without automatic recovery | Adapter, TaskBus, Audit, diagnostic, and Conversation tests retain package `failureKind`, `message`, `recoveryHint`, `retryable`, `phase`, and evidence. Helper/service/permission and unknown-send paths do not restart Helper, create ordinary fallback work, or automatically replay a mutating command. | Done |
| Package import / CLI contract smoke | Smoke A passed on 2026-06-30 with `uv run python scripts/manual_wechat_desktop_tool_smoke.py --help`, exit code `0`, without opening WeChat. | Done |
| Full automated regression | Current verification: backend `1561 passed, 10 skipped`; frontend 77 files / 576 tests passed; production build passed; ESLint had zero errors and two pre-existing warnings; Ruff passed across source/tests/scripts; focused mypy passed all 27 changed source modules. Complete launcher packaging and release-assets passed. Full-source mypy still reports five pre-existing errors in three unrelated modules. | Done for migration scope |
| Real package-backed focus / draft / observe | Current fixed Dev Helper Smoke B passed `open_contact`, `draft_message`, and `observe_current_chat` with `submitAttempted=false` / `submitted=false`. Evidence: `/tmp/plato-wechat-package-draft-20260721-215213.json`. | Done |
| Real controlled submit-once | Authorized Smoke C pressed Return once. Package verification returned fail-closed `send_unverified`; no retry ran. Immediate read-only inspection found exactly one matching outgoing message and an empty input. Exact-hash manual reconciliation archived the boundary as `completed` while preserving the original unknown observation. Evidence: `/tmp/plato-wechat-package-submit-20260721-222218.json` and `/tmp/plato-wechat-package-submit-20260721-222218-reconciliation.json`. | Done through explicit reconciliation; automatic package verification remains an improvement |
| Same-key replay / no duplicate | Authorized Smoke D reused the exact session/task/contact/message/effect DB under a fresh smoke id. It returned `replayed=true`, `submitAttempted=false`, `submitted=false`; current events had no send command. Evidence: `/tmp/plato-wechat-package-replay-20260721-225215.json`. | Done |

Conclusion: the package migration is accepted for the current product scope.
Dependency migration, old-code removal, Router/TaskBus/Agent-loop routing,
package tools and skill loading, logging/failure projection, Electron-owned
fixed Helper hosting, sidecar-only service access, release embedding, real
no-submit, one controlled external send, and same-key no-duplicate replay all
have current evidence. Formal distribution signing/notarization remains a
release credential operation. Package post-submit parsing should still be
hardened to replace the demonstrated manual reconciliation path.
