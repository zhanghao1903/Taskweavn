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
process:

```bash
uv run python scripts/manual_wechat_send_smoke.py \
  --base-url http://127.0.0.1:<sidecar-port> \
  --preflight-only \
  --evidence-output /tmp/plato-wechat-preflight-<run>.json
```

Required result:

- `sidecarOk=true`
- `computerUseBackend="helper"` for the preferred helper-backed path
- `computerUseStatus="ok"`
- `packageReadinessStatus="ready"`
- `helperStatus="ready"` for helper-backed path
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

### 6.3 Current Helper-Backed Reject/No-Send Blocker

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

No message was sent. The task did not reach the confirmation boundary. Before
the next reject/no-send attempt, manually open the WeChat main window and ensure
it is frontmost, then use a fresh idempotency key.

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
| helper preflight ready but WeChat not frontmost | Helper/TCC path is ready, but the app-specific contact driver cannot safely operate. | Manually open/focus WeChat main window and rerun reject/no-send with a fresh key. |
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
