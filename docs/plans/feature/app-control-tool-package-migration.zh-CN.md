# App-Control Tool Package Migration Plan

> Status: Package migration cleanup implemented on branch: M0-M2 complete,
> M3 package tool adapter present, M4 routed through TaskBus/Agent loop, and
> M5-M6 repo-local helper/runtime retirement completed for production and
> test code. Package `ToolEvent` / `ToolObservation` projection is now present
> in runtime logs, Audit records, and diagnostic bundles. Remaining work is
> package-backed macOS smoke evidence.
>
> Date: 2026-06-30
>
> Phase: P8 Backend Integration / P9 QA Readiness
>
> Scope: Migrate Plato/Taskweavn from the repo-owned macOS computer-use and
> WeChat runtime path to the published app-control tool package suite.

## 1. Decision Summary

Plato should consume the new package suite as external tool capabilities:

- `app-control-protocol>=0.1.1,<0.2.0` (current lock: `0.1.1`)
- `computer-use-macos[accessibility]>=0.1.1,<0.2.0; sys_platform == "darwin"`
  (current lock: `0.1.1`)
- `wechat-desktop-tool>=0.1.1,<0.2.0` (current lock: `0.1.1`)

The old compatibility package `macos-computer-use` is not part of the active
integration path.

The migration should not continue expanding `WeChatSendRuntime` or the
repo-local helper protocol. The target model is:

```text
Router / user intent
  -> TaskBus as source of truth
  -> Agent loop
  -> Tool registry
  -> wechat-desktop-tool
  -> app-control-protocol ToolCommand / ToolObservation / ToolEvent
  -> computer-use-macos direct or helper backend
  -> macOS desktop APIs
```

The package suite provides execution capability. It does not decide product
authorization, task lifecycle, conversation projection, audit persistence, or
LLM behavior. Those remain Plato responsibilities.

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
  - keeps `app-control-protocol` and `computer-use-macos` imports out of Router
    and TaskBus code.
- `src/taskweavn/tools/computer_use_macos_adapter.py`
  - now builds `ToolCommand` envelopes with `computer-use-macos`;
  - executes through `AppControlClient.run_command`;
  - maps `ToolObservation` into Plato `ComputerUseObservation`;
  - preserves the existing `ComputerUseTool` API during migration.
- `src/taskweavn/tools/wechat_desktop.py`
  - exposes the package-backed semantic WeChat Agent tool;
  - maps package `ToolObservation` into Plato tool observations;
  - records package observer events for runtime diagnostics.
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

2026-07-18 doc/API refresh:

- `uv.lock` now resolves `app-control-protocol==0.1.1`,
  `computer-use-macos==0.1.1`, and `wechat-desktop-tool==0.1.1` under the
  active `<0.2.0` constraints.
- The active macOS dependency uses the `computer-use-macos[accessibility]`
  extra so `objc`, `ApplicationServices`, `Cocoa`, and `Quartz` are available
  for real `accessibility_query` operations.
- The installed `computer-use-macos==0.1.1` exposes
  `accessibility_query_command`, but not `accessibility_action_command`.
- The installed `wechat-desktop-tool==0.1.1` exposes the read-model builders:
  `inspect_window_command`, `list_contacts_command`,
  `list_conversations_command`, `open_contact_command`,
  `read_visible_messages_command`, and `read_contact_messages_command`.
  It does not expose `execute_action_command` yet.
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

- direct mode for local development;
- helper mode for stable macOS TCC permission identity;
- local Unix socket service mode when a non-Python process needs the same
  protocol.

Plato should use Python embedding first:

```python
from computer_use_macos import ComputerUseClient

app_control = ComputerUseClient.from_config("app-control.toml")
```

Local socket service is optional and should be treated as a transport option,
not as Plato's main integration path.

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
from computer_use_macos import ComputerUseClient
from wechat_desktop_tool import WeChatDesktopTool

app_control = ComputerUseClient.from_config("app-control.toml")
wechat = WeChatDesktopTool.from_config(app_control, "app-control.toml")
```

Plato should prefer granular calls over one-shot `send_message` for product
flows:

```text
open_wechat
focus_contact
draft_message
product confirmation / authorization
submit_draft
observe_current_chat or read_visible_messages
```

This keeps the side-effect boundary visible and lets Plato own confirmation,
audit, and retry policy.

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

- translate Plato runtime config into `app-control.toml`-compatible objects or
  a generated temp config file;
- create `ComputerUseClient`;
- create `WeChatDesktopTool`;
- map `ToolObservation` into Plato tool observations, activity logs, audit
  evidence, and diagnostic-safe summaries;
- map `ToolEvent` into structured runtime logs;
- keep package-specific imports out of Router and TaskBus code.

### 7.2 Agent Loop Tool Surface

Expose app-control capabilities as Agent loop tools:

```text
tool: app_control
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
```

`wechat_desktop.submit_draft` must be treated as side-effecting by Plato.
The package-backed tool exposes the capability; it does not decide product
authorization. Plato owns the authorization boundary through task policy,
runtime skill guidance, `request_confirmation`, and operator-only smoke flags.

### 7.3 TaskBus And Agent Loop

TaskBus remains the single source of truth for task state. The migration should
not introduce a separate durable execution plane for WeChat.

For `communication.wechat.send_message`:

1. Router publishes or updates a TaskBus task.
2. Agent loop receives the task.
3. Runtime skills explain how to use `wechat_desktop` and `app_control`.
4. Agent loop calls package-backed tools.
5. Tool observations become task evidence.
6. Product confirmation gates `submit_draft`.
7. Agent loop finalizes the task result.

`WeChatSendRuntime` is not part of the target route. The migrated path should
fail closed if no package-backed tool/runtime handler is configured, instead
of falling back to the retired deterministic runtime.

## 8. Configuration Model

### 8.1 App-Level Config

Current Plato settings are app-level. The first migration slice should keep
that behavior and map app-level settings to app-control config.

Recommended config keys:

```toml
[computer_use]
enabled = true
backend = "direct" # direct | helper | disabled
allowed_apps = ["WeChat", "TextEdit"]
timeout_ms = 10000
allow_coordinate_click = false

[computer_use.allowed_app_bundle_ids]
WeChat = "com.tencent.xinWeChat"
TextEdit = "com.apple.TextEdit"

[helper]
transport = "unix_socket"
helper_app_path = "/Applications/Your App Control Helper.app"
manifest_path = ""
bundle_id = "com.example.yourapp.app-control-helper"
auto_launch = true

[wechat]
app_name = "WeChat"
bundle_id = "com.tencent.xinWeChat"
submit_key = "return"
max_message_chars = 4000
default_timeout_ms = 30000
```

Existing CLI/env flags can remain as compatibility aliases, but the new
internal source should be app-control config.

### 8.2 Dev Mode

Development can use direct mode:

```toml
[computer_use]
backend = "direct"
allowed_apps = ["WeChat", "TextEdit"]
```

The macOS permission subject is the Python host process, terminal, IDE, or
Electron-owned sidecar that actually performs GUI control.

### 8.3 Release Mode

Production should use helper mode:

```toml
[computer_use]
backend = "helper"

[helper]
helper_app_path = "/Applications/Your App Control Helper.app"
bundle_id = "com.example.yourapp.app-control-helper"
```

The helper app is the stable TCC permission subject. Each embedding product
owns its helper app identity, signing, notarization, installation, and user
setup. Plato may ship a Plato-branded helper in its release packaging, but the
implementation should be generated or built through
`computer-use-macos helper init/build/doctor`, not through the retired
repo-local helper server protocol.

## 9. Side-Effect And Authorization Policy

Tool packages do not own business authorization. Plato must gate side effects.

Policy:

- `open_wechat`, `focus_contact`, `draft_message`, and read operations may run
  under normal task execution policy.
- `submit_draft` requires explicit product authorization.
- If `submit_draft` or verified send returns `unknown`, Plato must not auto
  retry. The task should require manual review.
- Future "automatic chat" can be enabled by a product-level authorization
  policy, not by making the tool package decide.

This keeps automation useful while preserving a clear action boundary.

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

Status: completed on branch for the generic app-control bridge.

Add `taskweavn.integrations.app_control`.

Implementation:

- `AppControlClientFactory`
  - builds `ComputerUseClient.from_config(...)`;
  - supports direct/helper mode;
  - accepts existing runtime config as input.
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
from production and test code.

Route `communication.wechat.send_message` to normal Agent loop execution using
runtime skills.

Implementation:

- update `execution-wechat-desktop-send` skill to use `wechat_desktop` tool
  commands;
- ensure Router creates a task, not a special runtime-only execution object;
- let Agent loop call `focus_contact` and `draft_message`;
- create confirmation before `submit_draft`;
- resume Agent loop after confirmation to call `submit_draft`.

Acceptance:

- UI natural-language request creates a TaskBus task.
- Conversation shows user input immediately.
- Task activity shows tool command progress.
- No ordinary Default Agent fallback claims WeChat is unavailable when the
  package tool is configured.

### M5. Helper Migration

Status: implemented on branch for Plato-owned code retirement. Helper mode
remains as a package-backed `computer-use-macos` transport configuration.

Stop expanding repo-local helper APIs.

Implementation:

- use `computer-use-macos helper init/build/doctor` for helper app lifecycle;
- read app-control helper manifests with `app_control.helper.v1`;
- deprecate `plato.computer_use_helper.v1`;
- replace helper CLI docs with package helper docs.

Acceptance:

- helper readiness uses package manifest/socket protocol;
- Settings readiness reports package helper status;
- helper app path and manifest path are visible in diagnostics;
- old helper HTTP endpoints are not required for new WeChat smoke.

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
- product-level task policy requires confirmation before routes that intend to
  call `wechat_desktop.submit_draft`; the package-backed tool remains a
  command executor and does not make business authorization decisions.

### Integration Tests Without macOS

- Router publishes `communication.wechat.send_message` task.
- Agent loop sees `wechat_desktop` tool availability.
- fake package client completes focus/draft path.
- confirmation answer resumes execution.
- `unknown` submit observation fails closed and does not retry.

### macOS Manual Smokes

Follow `docs/plans/feature/app-control-tool-package-smoke-runbook.zh-CN.md`
for operator commands, evidence paths, safety rules, and pass/fail
classification.

1. `computer-use-macos` readiness.
2. TextEdit direct smoke.
3. WeChat focus/draft smoke, no submit.
4. Controlled confirm/submit-once smoke to `文件传输助手`.
5. Same idempotency key replay must not send again.

### Release Checks

- helper doctor JSON archived;
- helper signature/notarization evidence when release helper exists;
- diagnostic bundle includes safe package command evidence;
- Electron smoke verifies UI projection of user input, task progress,
  confirmation, failure, and result.

## 13. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Package API changes before `0.2` | Adapter churn | Keep all package imports behind `integrations/app_control` and `integrations/wechat_tool`. |
| macOS TCC subject confusion | Readiness false negatives | Use helper mode for production; direct mode only for dev. |
| `submit_draft` returns `unknown` after key press | Duplicate message risk | Fail closed; require manual review before retry. |
| WeChat UI changes | Contact focus/draft failures | Preserve failureKind/recoveryHint and keep package smoke current. |
| Old runtime re-enters active code | Confusing behavior | Keep retired modules deleted and scan for old imports in migration checks. |
| Logs leak message content | Privacy risk | Redact tool events; keep preview/hash only where product explicitly displays user-provided text. |

## 14. Implementation Order

Recommended PR order:

1. `app-control` client bridge and observation mapper.
2. `computer_use` backend replacement using `computer-use-macos`.
3. `wechat_desktop` package adapter and fake-client tests.
4. Agent loop tool registration and skill update.
5. UI/evidence/log projection for package `ToolEvent` and `ToolObservation`.
6. Helper manifest migration to `app_control.helper.v1`.
7. Old runtime/helper removal.

Do not combine steps 1-7 into one PR. The first three can be verified entirely
with fake clients and package import tests. Real macOS smokes should start only
after the package-backed focus/draft path is observable from Plato logs.

## 15. Acceptance Criteria

The migration is accepted when:

- `macos-computer-use` is not declared as a dependency.
- production source no longer imports `macos_computer_use`.
- Plato creates package-backed `app_control` and `wechat_desktop` tools.
- WeChat send task runs through Agent loop tool calls, not hardcoded
  `WeChatSendRuntime` sequencing.
- Product WeChat send routes require human-confirmation policy before intended
  submit; manual submit smoke additionally requires `--allow-submit` and
  `--confirm-submit SEND`.
- `ToolEvent` and `ToolObservation` are visible in logs/audit/diagnostics.
- real package-backed focus/draft smoke passes without sending.
- one real controlled confirm/send-once smoke to `文件传输助手` passes.
- real replay with the same product idempotency key does not send again.

## 16. Verification Snapshot

Date: 2026-07-18.

Verified in the current worktree:

- `uv tree --depth 1` and `uv.lock` resolve `app-control-protocol==0.1.1`,
  `computer-use-macos==0.1.1`, and `wechat-desktop-tool==0.1.1`; it does not
  list `macos-computer-use`.
- Package import probing confirms `computer-use-macos==0.1.1` exports
  `accessibility_query_command`, and `wechat-desktop-tool==0.1.1` exports
  `inspect_window_command`, `list_contacts_command`,
  `list_conversations_command`, `open_contact_command`, and
  `read_contact_messages_command`.
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
- `uv run pytest` passed with `1515 passed, 10 skipped`.
- `uv run python scripts/manual_wechat_desktop_tool_smoke.py --help` passed
  without opening WeChat.
- `tests/test_manual_wechat_desktop_tool_smoke_script.py` verifies the
  replacement smoke script's no-submit path, explicit submit guard, and
  `--allow-submit --confirm-submit SEND` submit path without touching WeChat.

Not yet verified:

- controlled submit-once smoke to `文件传输助手` after successful contact
  verification;
- same-key replay/no-duplicate evidence.

Those checks require explicit operator authorization and should follow
`docs/plans/feature/app-control-tool-package-smoke-runbook.zh-CN.md`.

## 17. Completion Audit

This audit treats completion as unproven until every acceptance item has direct
current-state evidence.

| Requirement | Current evidence | Status |
|---|---|---|
| Remove old `macos-computer-use` dependency | `uv tree --depth 1` lists `app-control-protocol`, `computer-use-macos`, and `wechat-desktop-tool`; `pyproject.toml` / `uv.lock` do not contain `macos-computer-use`; `importlib.util.find_spec("macos_computer_use")` is false. | Done |
| Remove retired repo-local helper/runtime code | Old helper server/app builders, helper adapter, repo-local WeChat adapter, deterministic runtime, send execution, send boundary, and old smoke scripts are deleted from active source/tests. Active-source `rg` only finds one negative CLI assertion for the retired preflight command. | Done |
| Route WeChat send through TaskBus / Agent loop tools | Router tests cover `communication.wechat.send_message` publishing to Execution Plane and dispatch trigger. Runtime skills select package-backed `wechat_desktop` / `computer_use` tools instead of `WeChatSendRuntimeHandler`. | Done |
| Preserve confirmation policy before intended submit | Router task draft requires `requiresHumanConfirmation=true`, `riskLevel=high`, and `communication.wechat_desktop_send`. Manual submit smoke requires `--allow-submit --confirm-submit SEND`. | Done |
| Preserve package events / observations for debugging | `tests/test_wechat_desktop_tool.py` verifies redacted runtime log emission; diagnostic bundle tests cover app-control runtime evidence projection. | Done |
| Package import / CLI contract smoke | Smoke A passed on 2026-06-30 with `uv run python scripts/manual_wechat_desktop_tool_smoke.py --help`, exit code `0`, without opening WeChat. | Done |
| Full automated regression | 2026-06-30 baseline: `uv run pytest` passed with `1515 passed, 10 skipped`; `uv run ruff check src scripts tests` passed; `git diff --check` passed. 2026-07-18 package refresh requires a focused rerun after adapter updates. | Needs current rerun |
| Real package-backed focus / draft / observe | Smoke B passed on 2026-07-18 through the local app-control service, following the published SDK example. Evidence file: `/tmp/plato-wechat-service-draft-20260718-133314.json`; `readiness`, `open_wechat`, `open_contact`, `draft_message`, and `observe_current_chat` all succeeded; `submitted=false`. The prior direct-process run failed with `accessibility_query_timeout`, confirming the smoke caller must use the Accessibility-authorized service process. | Done |
| Real controlled submit-once | First authorized Smoke C attempt ran on 2026-06-30 with direct backend and fresh key `plato-wechat-package-submit-20260630-smoke-c-submit-001`, but failed before submit: historical `focus_contact` returned `contact_not_found` because the verified chat title was `微信 (聊天)`. Evidence file: `/tmp/plato-wechat-package-submit-20260630-smoke-c-submit-001.json`. The run did not reach `draft_message` or `submit_draft`; no automatic retry was performed. Current 0.1.1 path must use `open_contact` through `--allow-focus-select`. | Failed before submit / missing send-once evidence |
| Same-key replay / no duplicate | Not run. Must follow a known Smoke C outcome and verify no duplicate message appears. | Missing external evidence |

Conclusion: implementation and old-code removal are complete for source,
dependency, CLI, router, tool, automated-test evidence, and real no-submit
WeChat draft/observe evidence. The full MVP cannot be marked accepted until
Smoke C/D provide real submit-once and replay/no-duplicate evidence.
