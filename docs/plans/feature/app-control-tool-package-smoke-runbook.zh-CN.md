# App-Control Tool Package Smoke Runbook

> Status: Draft operator runbook for package-backed macOS evidence.
>
> Date: 2026-06-30
>
> Scope: Validate the published `app-control-protocol`,
> `computer-use-macos`, and `wechat-desktop-tool` package path from Plato's
> repository without using the retired repo-local helper/runtime code.

## 1. Purpose

This runbook captures the required manual smoke evidence for the package-backed
WeChat desktop tool migration.

The smoke sequence proves three things:

1. Plato can import and invoke the published packages.
2. The package path can open WeChat, use an explicit contact-selection mode,
   draft a message, and observe the current chat without submitting.
3. A separately authorized submit path can send exactly once, and replay with
   the same idempotency key must not duplicate the message.

This runbook does not replace automated unit/integration tests. It is the
manual macOS evidence gate for the real desktop boundary.

## 2. Safety Rules

- Do not run submit smoke without explicit user authorization for that run.
- Draft smoke is not side-effect free: it can open WeChat and leave text in the
  chat input field. Clear the draft manually after the no-submit check if
  needed.
- Submit smoke requires both flags:
  - `--allow-submit`
  - `--confirm-submit SEND`
- Do not automatically retry a failed or unknown submit.
- If submit returns `unknown`, inspect WeChat manually before any retry.
- Use a fresh idempotency key for every intended send-once smoke.
- Reuse the same idempotency key only for the replay/no-duplicate check.
- Every run must use `--allow-focus-select` so the script runs the package
  contact-selection command. With `wechat-desktop-tool==0.1.1`, this uses
  `open_contact`. Smoke evidence must not assume the current WeChat chat
  already matches the target contact.

## 3. Preconditions

Run from the repository root:

```bash
pwd
# /Users/zhanghao/.codex/worktrees/e05a/Taskweavn
```

Package/runtime prerequisites:

- `app-control-protocol==0.1.1` is installed through `uv.lock`.
- `computer-use-macos[accessibility]==0.1.1` is installed on macOS; this
  installs the PyObjC modules needed by `accessibility_query`.
- `wechat-desktop-tool==0.1.1` is installed.
- The old `macos-computer-use` compatibility package is not installed as a
  Plato dependency.

macOS prerequisites:

- WeChat is installed and logged in.
- The target contact `文件传输助手` exists.
- A local `computer-use-macos serve` process is running on a Unix socket.
- Accessibility permission is granted to the process hosting that service.
  The smoke process is only a protocol client and does not own the TCC grant.
- Screen Recording is not required by this smoke unless the package
  configuration is changed to require it.

Start the service from the environment that contains the published packages:

```bash
computer-use-macos serve \
  --config /path/to/app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file /path/to/app-control.token
```

The service configuration owns direct/helper backend selection, app allowlists,
timeouts, and the macOS permission identity. The smoke caller must not select a
backend independently.

## 4. Evidence Location

Use a unique smoke id and keep JSON evidence under `/tmp`:

```text
/tmp/plato-wechat-package-draft-<timestamp>.json
/tmp/plato-wechat-package-submit-<timestamp>.json
/tmp/plato-wechat-package-replay-<timestamp>.json
```

Each evidence file must include:

- `kind = wechat_desktop_tool_manual_smoke`
- `smokeId`
- `contact`
- `messagePreview`
- `messageHash`
- `allowFocusSelect`
- `contactSelectionMode`
- `submitRequested`
- `submitConfirmed`
- `submitAttempted`
- `submitted`
- `config.transport = unix_socket`
- `config.socketPath`
- package `events`
- final `observations`

The evidence must not contain raw helper tokens, full accessibility trees, or
unbounded message history.

## 5. Smoke A: Package Import / CLI Contract

This check does not open WeChat.

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py --help
```

Expected result:

- command exits `0`;
- help text includes `--config`, `--socket-path`, `--token-file`, `--contact`,
  `--message`, `--allow-focus-select`, `--allow-submit`, `--confirm-submit`,
  and `--evidence-output`;
- no retired helper script is invoked.

Current branch result:

- 2026-06-30: passed in the current worktree with
  `uv run python scripts/manual_wechat_desktop_tool_smoke.py --help`.
- Exit code: `0`.
- Historical help exposed `--backend`; the current service-backed smoke exposes
  `--config`, `--socket-path`, and `--token-file` instead.
- 2026-07-02 refresh: help also includes `--allow-focus-select`,
  `--search-hotkey`, and `--search-clear-hotkey`.
- No WeChat UI was opened and no JSON evidence file is expected for Smoke A.

## 6. Smoke B: No-Submit Open / Draft / Observe

The script opens/focuses WeChat, resolves `文件传输助手` through package
`open_contact`, drafts a message, and observes the selected chat. It must not
submit.

Choose values:

```text
timestamp = YYYYMMDD-HHMMSS
smoke_id = plato-wechat-package-draft-<timestamp>
idempotency_key = plato-wechat-package-draft-<timestamp>
message = Plato package-backed draft smoke <timestamp>
```

Local service:

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py \
  --config /path/to/app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file /path/to/app-control.token \
  --contact 文件传输助手 \
  --message 'Plato package-backed draft smoke <timestamp>' \
  --idempotency-key plato-wechat-package-draft-<timestamp> \
  --smoke-id plato-wechat-package-draft-<timestamp> \
  --allow-focus-select \
  --evidence-output /tmp/plato-wechat-package-draft-<timestamp>.json
```

Expected result:

- process exits `0`;
- `submitted` is `false`;
- observations include successful:
  - `readiness`
  - `open_wechat`
  - `open_contact`
  - `draft_message`
  - `observe_current_chat`
- WeChat input contains the draft message;
- no message appears in the chat history as sent.

After recording evidence, manually clear the draft from WeChat.

Current branch result:

- 2026-07-18: passed through the local app-control service, following the
  published package SDK example. Evidence:
  `/tmp/plato-wechat-service-draft-20260718-133314.json`.
- The successful path was `readiness -> open_wechat -> open_contact ->
  draft_message -> observe_current_chat`; `submitted=false` and no submit
  command was attempted.
- The immediately preceding direct-process smoke failed in
  `accessibility_query_timeout`. This service-backed pass confirms that the
  smoke caller must use the long-lived, Accessibility-authorized service
  process rather than instantiate `ComputerUseClient` directly.
- 2026-06-30: passed with direct backend using the previous default
  `focus_contact` behavior. Current runs must pass `--allow-focus-select`.
  After the 2026-07-18 package refresh, contact selection uses `open_contact`.
- Command:
  `uv run python scripts/manual_wechat_desktop_tool_smoke.py --backend direct --contact 文件传输助手 --message 'Plato package-backed draft smoke 2026-06-30 smoke-b-no-submit-001' --idempotency-key plato-wechat-package-draft-20260630-smoke-b-no-submit-001 --smoke-id plato-wechat-package-draft-20260630-smoke-b-no-submit-001 --evidence-output /tmp/plato-wechat-package-draft-20260630-smoke-b-no-submit-001.json`
- Evidence:
  `/tmp/plato-wechat-package-draft-20260630-smoke-b-no-submit-001.json`
- Exit code: `0`.
- Verified evidence:
  - `submitted=false`
  - `open_wechat`: `ok`, `success=true`
  - `focus_contact`: `ok`, `success=true` in the historical run; current runs
    use `open_contact`
  - `draft_message`: `ok`, `success=true`
  - `observe_current_chat`: `ok`, `success=true`
  - events recorded: `20`
- The draft text may remain in the WeChat input and should be cleared manually
  before any later submit smoke.

## 7. Smoke C: Controlled Confirm / Submit Once

This smoke requires explicit authorization before running.

Choose a fresh send key:

```text
timestamp = YYYYMMDD-HHMMSS
smoke_id = plato-wechat-package-submit-<timestamp>
idempotency_key = plato-wechat-package-submit-<timestamp>
message = Plato package-backed submit smoke <timestamp>
```

Command:

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py \
  --config /path/to/app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file /path/to/app-control.token \
  --contact 文件传输助手 \
  --message 'Plato package-backed submit smoke <timestamp>' \
  --idempotency-key plato-wechat-package-submit-<timestamp> \
  --smoke-id plato-wechat-package-submit-<timestamp> \
  --allow-focus-select \
  --allow-submit \
  --confirm-submit SEND \
  --evidence-output /tmp/plato-wechat-package-submit-<timestamp>.json
```

Expected result:

- process exits `0`;
- `submitted` is `true`;
- observations include successful:
  - `open_wechat`
  - `open_contact`
  - `draft_message`
  - `observe_current_chat`
  - `submit_draft`
- WeChat shows exactly one sent message matching the smoke message;
- package events and observations are present in the evidence JSON.

If `submit_draft` returns `unknown`, do not retry. Manually inspect the chat
and preserve the evidence file as failed/unknown evidence.

Current branch result:

- 2026-06-30: first authorized Smoke C attempt failed before submit.
- Command:
  `uv run python scripts/manual_wechat_desktop_tool_smoke.py --backend direct --contact 文件传输助手 --message 'Plato package-backed submit smoke 2026-06-30 smoke-c-submit-001' --idempotency-key plato-wechat-package-submit-20260630-smoke-c-submit-001 --smoke-id plato-wechat-package-submit-20260630-smoke-c-submit-001 --allow-submit --confirm-submit SEND --evidence-output /tmp/plato-wechat-package-submit-20260630-smoke-c-submit-001.json`
- Evidence:
  `/tmp/plato-wechat-package-submit-20260630-smoke-c-submit-001.json`
- Exit code: `1`.
- Verified evidence:
  - `open_wechat`: `ok`, `success=true`
  - `focus_contact`: `not_found`, `success=false` in the historical run
  - `failure_kind=contact_not_found`
  - message: `Verified WeChat chat title does not match requested contact: 微信 (聊天)`
  - reached operations: `open_wechat`, `focus_contact`
  - not reached: `draft_message`, `observe_current_chat`, `submit_draft`
- The script evidence schema was corrected after this run because the previous
  top-level `submitted` field was computed from CLI flags instead of an actual
  successful `submit_draft` observation.
- On 2026-07-18 the script was updated to remove the current-chat assumption
  path. Current runs must use `--allow-focus-select` and package
  `open_contact`.
- No automatic retry was performed.

## 8. Smoke D: Replay / No Duplicate

Run this only after Smoke C has a known outcome.

Replay must reuse the same `idempotency_key` as Smoke C and should use a new
`smoke_id`:

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py \
  --config /path/to/app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file /path/to/app-control.token \
  --contact 文件传输助手 \
  --message 'Plato package-backed submit smoke <timestamp>' \
  --idempotency-key plato-wechat-package-submit-<timestamp> \
  --smoke-id plato-wechat-package-replay-<timestamp> \
  --allow-focus-select \
  --allow-submit \
  --confirm-submit SEND \
  --evidence-output /tmp/plato-wechat-package-replay-<timestamp>.json
```

Expected result:

- no second identical WeChat message is sent;
- evidence shows the package's idempotency/replay behavior, or the operator
  records manual evidence that no duplicate appeared;
- if the package cannot enforce replay yet, this is a release-blocking gap for
  the send-once acceptance criterion.

## 9. Failure Classification

Use these labels when filing a failure:

| Failure | Meaning | Retry rule |
|---|---|---|
| `not_ready` | backend or helper is unavailable | Fix readiness, then rerun no-submit first |
| `permission_missing` | macOS Accessibility/TCC is not granted | Grant permission, restart subject process |
| `contact_not_found` | target contact cannot be focused | Verify WeChat state/contact spelling |
| `input_not_focused` | draft target was not verified | Do not submit; inspect focus evidence |
| `submit_not_confirmed` | submit flags were incomplete | Expected guard behavior |
| `submit_unknown` | key press happened but result is unclear | Manual inspection required before any retry |
| `timeout` | operation exceeded timeout | Increase timeout only after checking UI state |

## 10. Acceptance Checklist

- [x] Smoke A passes.
- [x] Smoke B passes with `submitted=false` through the local service.
- [ ] Smoke C is explicitly authorized and passes with one visible sent
      message.
- [ ] Smoke D proves no duplicate send for the same idempotency key.
- [ ] Evidence JSON files are attached or referenced in the PR/release note.
- [ ] Runtime logs, Audit, or diagnostics can project package
      `ToolEvent` / `ToolObservation` summaries without leaking secrets.

## 11. Current Branch Status

As of 2026-07-18:

- package dependencies and source migration are implemented on branch;
- Smoke A package import / CLI contract passed without opening WeChat;
- Smoke B passed through the local app-control service with verified
  `open_contact` and `submitted=false`;
- old repo-local helper/runtime code is retired from active source/tests;
- package event/observation projection is covered by tests;
- real macOS Smoke C/D evidence remains pending and requires separate explicit
  operator authorization.
