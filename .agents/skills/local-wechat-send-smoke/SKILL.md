---
name: local-wechat-send-smoke
description: Run and diagnose the Taskweavn/Plato Local macOS WeChat Send MVP smoke. Use when testing confirmation-gated WeChat sends to 文件传输助手 or another controlled contact, validating fresh idempotency keys, preflight readiness, draft-before-confirmation, keyboard Return submit, replay/no-duplicate behavior, or investigating wechat_send_unknown / WeChat automation evidence.
---

# Local WeChat Send Smoke

## Purpose

Use this repo-scoped skill for the local macOS WeChat send MVP only. It verifies
the Execution Plane -> WeChat Desktop path with explicit confirmation and
evidence. It is not a bulk messaging, remote ExecutionEnv, or LAN API workflow.

## Safety Rules

- Run `product-workflow-gate` first.
- Never send without explicit user authorization and `--allow-send`.
- Use only a controlled contact. The default smoke contact is `文件传输助手`.
- Always use a fresh idempotency key for a real send attempt.
- Never automatically retry a boundary in `unknown` or after a failed submit;
  inspect evidence and start a new task only after manual review.
- Keep screenshot evidence disabled unless a separate redaction plan exists.

## Deterministic Flow

1. Start the local sidecar. Prefer the helper-backed path when validating the
   macOS backend product path:

   ```bash
   uv run taskweavn plato-sidecar \
     --workspace ./plato-workspace \
     --port 0 \
     --computer-use-backend helper \
     --computer-use-allowed-apps WeChat \
     --computer-use-helper-manifest "$HOME/Library/Application Support/PlatoDev/computer-use-helper.json"
   ```

   Use direct `macos` backend only for package-level diagnosis:

   ```bash
   uv run taskweavn plato-sidecar \
     --workspace ./plato-workspace \
     --port 0 \
     --computer-use-backend macos \
     --computer-use-allowed-apps WeChat
   ```

2. Run preflight:

   ```bash
   uv run python scripts/manual_wechat_send_smoke.py \
     --base-url http://127.0.0.1:<sidecar-port> \
     --preflight-only \
     --helper-manifest "$HOME/Library/Application Support/PlatoDev/computer-use-helper.json" \
     --evidence-output /tmp/plato-wechat-preflight-<run>.json
   ```

   Required for helper-backed path: `ready=true`,
   `computerUseBackend="helper"`, `computerUseStatus="ok"`,
   `packageReadinessStatus="ready"`, `helperStatus="ready"`,
   `wechatAppSuccess=true`, and `wechatAppPhase="window_readiness"`.
   The helper manifest check may open or focus WeChat; it must pass before
   publishing a WeChat task.

3. Create or select a smoke session.

4. Run confirm/send once with a fresh idempotency key:

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

5. Accept only if the smoke reports `finalStatus=done`,
   `resultKind=wechat_send_result`, `terminalReplayStatus=done`, and
   `terminalReplaySameExecution=true`.

## Code Invariants

- The WeChat focus phase must clear existing input before typing the new draft.
- The confirmation-gated submit phase must use keyboard Return, not a click on
  the send button.
- Submit evidence should include `send_method=keyboard_return` and
  `send_attempted=true` on success.
- Pre-submit failures should become `not_sent`; attempted or unknown submit
  failures require manual review.

## Diagnostics

- Read `/api/v1/tasks/<executionId>/result` and
  `/api/v1/tasks/<executionId>/evidence` for terminal evidence.
- `wechat_send_unknown` means no automatic retry.
- If contact resolution fails, confirm WeChat main window is open, logged in,
  and Accessibility permissions are ready.
- If draft text may be stale, verify the focus script clears input before
  `type_text`.

## Focused Checks

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

## Playbook

Use `docs/plans/feature/local-macos-wechat-send-playbook.md` for the operator
runbook and latest validated smoke evidence.
