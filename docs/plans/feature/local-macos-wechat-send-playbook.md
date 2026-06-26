# Local macOS WeChat Send Playbook

> Status: Accepted local smoke playbook
>
> Last Updated: 2026-06-27
>
> Related:
> [Local macOS WeChat Send MVP](local-macos-wechat-send-mvp.md),
> [technical design](local-macos-wechat-send-mvp-technical-design.zh-CN.md),
> [Remote WeChat Message Task PRD](../../product/remote-wechat-message-task-prd.md)

---

## 1. Scope

This playbook runs the local macOS WeChat send MVP through Plato's local
Execution Plane path:

```text
local sidecar -> Task API -> WeChatSendRuntimeHandler
  -> macOS computer-use adapter -> WeChat Desktop adapter
  -> draft -> confirmation -> keyboard Return submit
  -> result/evidence -> same-key terminal replay
```

It is only for controlled local smoke testing. It is not a bulk messaging,
remote ExecutionEnv, LAN API, Windows, or production contact-management
workflow.

## 2. Preconditions

- macOS Accessibility is granted to the Python/Terminal runtime that starts the
  sidecar.
- WeChat Desktop is installed, logged in, unlocked, and available on the local
  machine.
- The test contact is controlled. The default smoke contact is `文件传输助手`.
- The message is non-sensitive and unique per real send attempt.
- Screenshot evidence remains disabled unless a separate redaction plan exists.

## 3. Start The Sidecar

Preferred helper-backed path:

```bash
uv run taskweavn plato-sidecar \
  --workspace ./plato-workspace \
  --port 0 \
  --computer-use-backend helper \
  --computer-use-allowed-apps WeChat \
  --computer-use-helper-manifest "$HOME/Library/Application Support/PlatoDev/computer-use-helper.json"
```

If the helper app should be launched by Plato, add the explicit opt-in helper
path and auto-launch flag:

```bash
uv run taskweavn plato-sidecar \
  --workspace ./plato-workspace \
  --port 0 \
  --computer-use-backend helper \
  --computer-use-allowed-apps WeChat \
  --computer-use-helper-manifest "$HOME/Library/Application Support/PlatoDev/computer-use-helper.json" \
  --computer-use-helper-app-path "/Applications/Plato Computer Use Helper Dev.app" \
  --computer-use-helper-auto-launch
```

Legacy direct macOS backend path remains useful for package-level diagnosis
only. It does not validate the helper TCC identity:

```bash
uv run taskweavn plato-sidecar \
  --workspace ./plato-workspace \
  --port 0 \
  --computer-use-backend macos \
  --computer-use-allowed-apps WeChat
```

Record the printed local base URL.

## 4. Preflight

Run preflight before any real WeChat task. The script reads the running
sidecar's `/api/v1/settings/readiness` response, so it validates the configured
runtime path (`helper` or `macos`) instead of checking an unrelated local Python
process. For the preferred helper-backed path, pass the helper manifest as well;
this performs an explicit WeChat app/window readiness probe through the helper
and may open or focus WeChat:

```bash
uv run python scripts/manual_wechat_send_smoke.py \
  --base-url http://127.0.0.1:<sidecar-port> \
  --preflight-only \
  --helper-manifest "$HOME/Library/Application Support/PlatoDev/computer-use-helper.json" \
  --evidence-output /tmp/plato-wechat-preflight-<run>.json
```

Required result:

- `sidecarOk=true`
- `computerUseBackend="helper"` for the preferred helper-backed path
- `computerUseStatus="ok"`
- `packageReadinessStatus="ready"`
- `helperStatus="ready"` for helper-backed path
- `wechatAppSuccess=true` for helper-backed WeChat send smoke
- `wechatAppPhase="window_readiness"` for helper-backed WeChat send smoke
- `ready=true`

If preflight is not ready, do not run a send smoke.

## 5. Controlled Confirm/Send Once

Create or select a smoke session, then run one fresh idempotency key:

```bash
uv run python scripts/manual_wechat_send_smoke.py \
  --base-url http://127.0.0.1:<sidecar-port> \
  --session-id <session-id> \
  --contact 文件传输助手 \
  --message "Plato local WeChat smoke test <unique-run-id>" \
  --idempotency-key <fresh-key> \
  --response confirm \
  --allow-send \
  --timeout-seconds 90 \
  --poll-seconds 0.5 \
  --evidence-output /tmp/plato-wechat-confirm-smoke-<run>.json
```

The smoke is accepted only if all are true:

- `finalStatus=done`
- `resultKind=wechat_send_result`
- `errorCode=null`
- `terminalReplayStatus=done`
- `terminalReplaySameExecution=true`
- result query returns `sendBoundaryStatus=sent`
- evidence query includes `WeChat send observation` with:
  - `phase=keyboard_submit`
  - `send_method=keyboard_return`
  - `send_attempted=true`
  - `confirmation_required=true`
  - `confirmed_by_user=true`

## 6. Validated Smoke Record

### 6.1 Direct macOS Backend Confirm/Send

Validated on 2026-06-22 with the legacy direct `macos` backend:

- contact: `文件传输助手`
- idempotency key:
  `manual-wechat-smoke-20260622-keyboard-submit-e05a-03`
- execution id: `exec_c47432a39d1b5a0da94d15d16dd1827e`
- confirmation id: `217fddb7310f47b4968f852734457e64`
- result: `wechat_send_result`
- send boundary: `sent`
- replay: same execution, same `done` terminal status

### 6.2 Helper-Backed Preflight

Validated on 2026-06-27 with `computer-use-backend=helper`:

- helper manifest:
  `/tmp/plato-computer-use-smoke/computer-use-helper.json`
- helper readiness:
  - `status=ready`
  - `success=true`
  - `accessibility_trusted=true`
  - `helper.bundleId=com.taskweavn.plato.computer-use-helper.dev`
- sidecar preflight evidence:
  `/tmp/plato-computer-use-smoke/helper-preflight.json`
- preflight result:
  - `sidecarOk=true`
  - `computerUseBackend=helper`
  - `computerUseStatus=ok`
  - `packageReadinessStatus=ready`
  - `computerUseReady=true`
  - `helperStatus=ready`
  - `ready=true`

This validates the Plato sidecar -> helper backend readiness path. It does not
validate WeChat contact resolution, draft insertion, or send.

### 6.2.1 Helper-Backed WeChat App Readiness Preflight

Added on 2026-06-27:

- `scripts/manual_wechat_send_smoke.py --preflight-only --helper-manifest ...`
  now also calls helper `POST /v1/apps/wechat/readiness`.
- The app readiness probe validates that WeChat can be opened/focused and that
  its main window is automation-ready before publishing a task.
- If `wechatAppSuccess=false`, the smoke exits before task creation. This keeps
  known app/window blockers out of the send pipeline.

Validated negative preflight on 2026-06-27:

- helper manifest:
  `/tmp/plato-computer-use-smoke/computer-use-helper.json`
- evidence:
  `/tmp/plato-computer-use-smoke/helper-app-readiness-preflight-20260627.json`
- sidecar/helper readiness:
  - `computerUseBackend=helper`
  - `computerUseStatus=ok`
  - `packageReadinessStatus=ready`
  - `computerUseReady=true`
  - `helperStatus=ready`
- WeChat app readiness:
  - `wechatAppStatus=needs_user`
  - `wechatAppSuccess=false`
  - `wechatAppPhase=window_readiness`
  - `wechatAppSummary=WeChat main window is unavailable; open the main WeChat window before sending.`
- result: `ready=false`, and no task was published.

Validated recovery-action preflight on 2026-06-27:

- evidence:
  `/tmp/plato-computer-use-smoke/helper-app-readiness-preflight-recovery-actions-20260627.json`
- result:
  - `wechatAppSuccess=false`
  - `wechatAppPhase=window_readiness`
  - `wechatAppSetupHint=Open the WeChat main window or chat list, make sure WeChat is logged in and unlocked, then rerun helper-backed preflight before publishing a task.`
  - `wechatAppRecoveryActions=["open_wechat_main_window", "unlock_or_login_wechat", "rerun_helper_preflight"]`
- result: `ready=false`, and no task was published.

Validated structured window-count preflight on 2026-06-27:

- evidence:
  `/tmp/plato-computer-use-smoke/helper-app-readiness-preflight-window-count-20260627.json`
- result:
  - `wechatAppSuccess=false`
  - `wechatAppPhase=window_readiness`
  - `wechatAppDiagnostics.process_exists=true`
  - `wechatAppDiagnostics.window_count=0`
- interpretation: WeChat is running, but it has no automatable main window.
  Open the WeChat main window or chat list, then rerun helper-backed preflight
  before publishing a task.

Fresh helper/sidecar preflight repeated the same blocker on 2026-06-27:

- evidence:
  `/tmp/plato-computer-use-smoke/helper-app-readiness-preflight-current-20260627.json`
- helper/sidecar state:
  - `sidecarOk=true`
  - `computerUseBackend=helper`
  - `computerUseStatus=ok`
  - `packageReadinessStatus=ready`
  - `helperStatus=ready`
- WeChat app readiness:
  - `wechatAppSuccess=false`
  - `wechatAppFailureKind=needs_user`
  - `wechatAppPhase=window_readiness`
  - `wechatAppDiagnostics.process_exists=true`
  - `wechatAppDiagnostics.window_count=0`
- interpretation: this is not a Plato helper capability failure. The helper is
  ready, but WeChat has no automatable main window. Do not publish a WeChat send
  task until the operator opens/unlocks the main WeChat window and preflight
  returns `ready=true`.

Structured stale-helper-manifest preflight on 2026-06-27:

- evidence:
  `/tmp/plato-computer-use-smoke/helper-app-readiness-preflight-manifest-structured-20260627.json`
- result:
  - `sidecarOk=true`
  - `computerUseBackend=helper`
  - `computerUseStatus=failed`
  - `helperManifest.endpoint=http://127.0.0.1:57319`
  - `helperManifest.bundleId=com.taskweavn.plato.computer-use-helper.dev`
  - `helperManifest.pid=27864`
  - `wechatAppSuccess=false`
  - `wechatAppPhase=helper_app_readiness`
  - `wechatAppFailureKind=helper_app_unavailable`
  - `wechatAppSummary=Request failed for POST /v1/apps/wechat/readiness: <urlopen error [Errno 61] Connection refused>`
- interpretation: the sidecar can run, but the helper manifest points to a
  dead helper endpoint. No task should be published. Relaunch the helper or
  regenerate the manifest, then rerun helper-backed preflight. If the sidecar is
  started with both `--computer-use-helper-app-path` and
  `--computer-use-helper-auto-launch`, the helper backend can now relaunch the
  helper, refresh the stale manifest endpoint, rebuild the helper client, and
  retry the current helper request once. The preflight evidence preserves safe
  helper manifest identity while excluding `tokenRef` and token values.

Validated helper auto-launch preflight on 2026-06-27:

- generated dev helper app:
  `/tmp/plato-computer-use-autolaunch-20260627/Plato Computer Use Helper Dev.app`
- manifest:
  `/tmp/plato-computer-use-autolaunch-20260627/computer-use-helper.json`
- evidence:
  `/tmp/plato-computer-use-autolaunch-20260627/preflight-autolaunch-20260627.json`
- sidecar/helper state:
  - `sidecarOk=true`
  - `computerUseBackend=helper`
  - `computerUseStatus=ok`
  - `packageReadinessStatus=ready`
  - `computerUseReady=true`
  - `helperStatus=ready`
  - `computerUseHelper.path=/private/tmp/plato-computer-use-autolaunch-20260627/Plato Computer Use Helper Dev.app`
  - `helperManifest.endpoint=http://127.0.0.1:60557`
  - `helperManifest.pid=66418`
- runtime identity:
  - `computerUseDiagnostics.diagnostics.checkedByProcessPath=/Users/zhanghao/.codex/worktrees/e05a/Taskweavn/.venv/bin/python`
  - `computerUseDiagnostics.diagnostics.adapterProcessExecutable=/Users/zhanghao/.codex/worktrees/e05a/Taskweavn/.venv/bin/python`
- WeChat app readiness:
  - `wechatAppSuccess=false`
  - `wechatAppPhase=window_readiness`
  - `wechatAppSummary=WeChat main window readiness AppleScript failed.`
  - `wechatAppDiagnostics.stderr=osascript timed out after 10.0s`
- interpretation: helper auto-launch and manifest publication work in the dev
  path. The remaining blocker is WeChat window readiness, not helper discovery.
  The dev scaffold still delegates the actual macOS backend to the configured
  Python runtime; release packaging must replace this with a helper-owned
  packaged/embedded executable before treating Helper.app as the final TCC
  permission subject.

### 6.3 Helper-Backed Contact Resolution Progress

Attempted on 2026-06-27 with `response=reject` and no `--allow-send`:

- session id: `37272159`
- idempotency key:
  `manual-wechat-helper-reject-20260627-failure-evidence-01`
- execution id: `exec_b2caa66958ea5142be2e175d9327e1cd`
- failure evidence:
  `/tmp/plato-computer-use-smoke/helper-reject-nosend-failure.json`
- terminal status: `failed` before confirmation
- error code: `wechat_contact_needs_user`
- error message:
  `Target app is not frontmost: expected WeChat, got Codex.`

No message was sent. The task did not reach the confirmation boundary.

Mitigation added on 2026-06-27:

- When generic `observe` fails because the target app is not frontmost, the
  WeChat adapter now gives the bounded macOS WeChat search driver one recovery
  attempt before reporting contact resolution as blocked.
- The driver window readiness script now activates WeChat and performs one
  bounded window-readiness retry before returning `needs_user`.
- The driver also sends a bounded macOS `reopen` event before activation so a
  running app has a chance to restore its main window.
- The helper-backed WeChat runtime now calls the helper generic `open_app`
  operation during `open_or_focus`, so task evidence records the real helper
  open/focus result instead of a fixed delegated placeholder.

Validated checks:

- `uv run pytest tests/test_wechat_macos_driver.py tests/test_wechat_desktop_adapter.py tests/test_wechat_send_execution.py tests/test_wechat_send_runtime.py tests/test_manual_wechat_send_smoke_script.py`
- helper-backed preflight evidence:
  `/tmp/plato-computer-use-smoke/helper-preflight-after-real-open.json`

Current helper-backed reject/no-send blocker after mitigation:

- session id: `38ddf4e3`
- idempotency key:
  `manual-wechat-helper-reject-20260627-real-open-01`
- execution id: `exec_ed27daff35ba5f829bc69c699f1837a9`
- failure evidence:
  `/tmp/plato-computer-use-smoke/helper-reject-nosend-real-open.json`
- terminal status: `failed` before confirmation
- open/focus evidence: `Opened app: WeChat`, status `ok`
- error code: `wechat_contact_needs_user`
- error message:
  `WeChat main window is unavailable; open the main WeChat window before sending.`
- diagnostics:
  `System Events` could not get `window 1 of process "WeChat"`.

No message was sent. The task did not reach the confirmation boundary. Before
the next reject/no-send attempt, manually open the WeChat main window and ensure
it has a visible chat/search window, then use a fresh idempotency key.

## 7. Implementation Invariants

- Clear existing input before typing a fresh draft.
- Do not click the WeChat send button in the accepted MVP path.
- Final submit uses keyboard Return after confirmation.
- Unknown submit failures are manual-review states and must not be retried
  automatically.
- Do not store raw unrelated WeChat chat history.
- Use a fresh idempotency key for every new real send attempt.

## 8. Failure Handling

| Failure | Meaning | Rule |
|---|---|---|
| preflight not ready | Runtime or permissions unavailable. | Fix setup before any task. |
| helper preflight ready but WeChat not frontmost | Helper/TCC path is ready, but generic observe lost the focus race. | The adapter falls back to the bounded WeChat driver. If it still fails, inspect contact-resolution evidence. |
| WeChat process has no window 1 | WeChat is running, but no automatable main window is visible. | Manually open the WeChat main window/chat list and rerun reject/no-send with a fresh key. |
| contact resolution failed | Controlled contact was not selected. | Open WeChat main window and rerun reject/no-send first. |
| draft failed | Input was not safely written. | Do not confirm; inspect evidence. |
| `wechat_send_unknown` | Send boundary may have side effects. | No automatic retry; manual review only. |
| terminal replay differs | Idempotency is broken. | Stop; fix boundary before another send. |

## 9. Focused Checks

Run after changing this path:

```bash
uv run ruff check \
  src/taskweavn/integrations/wechat_desktop/macos_driver.py \
  tests/test_wechat_macos_driver.py

uv run mypy \
  src/taskweavn/integrations/wechat_desktop/macos_driver.py \
  tests/test_wechat_macos_driver.py

uv run pytest \
  tests/test_wechat_macos_driver.py \
  tests/test_wechat_desktop_adapter.py \
  tests/test_wechat_send_execution.py \
  tests/test_wechat_send_runtime.py \
  tests/test_manual_wechat_send_smoke_script.py
```
