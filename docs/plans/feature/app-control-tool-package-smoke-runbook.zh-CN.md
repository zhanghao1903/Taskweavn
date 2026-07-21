# App-Control Tool Package Smoke Runbook

> Status: Active operator runbook for the Electron-owned Helper product path.
>
> Date: 2026-07-19
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
   the same TaskBus execution identity must not duplicate the message.

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
- Use a fresh TaskBus-style `session_id + task_id` identity for every intended
  send-once smoke. Plato derives the managed idempotency key from that identity.
- Reuse the same session, task, and effect database only for the
  replay/no-duplicate check.
- Every run must use `--allow-focus-select` so the script runs the package
  `open_contact` command. Smoke evidence must not assume the current WeChat
  chat already matches the target contact.

## 3. Preconditions

Run from the repository root:

```bash
pwd
# /Users/zhanghao/.codex/worktrees/e05a/Taskweavn
```

Package/runtime prerequisites:

- `app-control-protocol==0.3.0` is installed through `uv.lock`.
- `computer-use-macos[accessibility]==0.3.0` is installed on macOS; this
  installs the PyObjC modules needed by `accessibility_query`.
- `wechat-desktop-tool==0.3.0` is installed.
- The old `macos-computer-use` compatibility package is not installed as a
  Plato dependency.

macOS prerequisites:

- WeChat is installed and logged in.
- The WeChat main window is visibly open, not merely a running/frontmost app
  with its main window closed or hidden.
- The target contact `文件传输助手` exists.
- The current `Plato Computer Use Helper Dev.app` has been built into
  `~/Applications` and is authorized for Accessibility.
- Electron has launched the Helper and its endpoint manifest exists under the
  Electron `userData/computer-use-helper` directory. The smoke process is only
  a protocol client and does not own the TCC grant.
- `computer_use.allow_coordinate_click` is enabled for the Helper. Current
  WeChat conversation rows may require the package's verified current-frame
  fallback when they do not advertise `AXPress`.
- Screen Recording is not required by this smoke unless the package
  configuration is changed to require it.

Build or refresh the stable Dev Helper after package/service-host changes:

```bash
uv run --group packaging python \
  scripts/build_plato_computer_use_helper_dev.py --variant dev
```

Then launch Plato normally:

```bash
cd frontend
npm run electron:dev -- --workspace /path/to/workspace
```

Electron is the only Helper process owner. It starts the full package-backed
service, waits for the private manifest/token/socket, and passes the manifest
path to the sidecar. Do not start `computer-use-macos serve` separately and do
not launch a second Helper from the smoke script.

Resolve the manifest path from the Electron startup environment or its stable
`userData/computer-use-helper/app-control-service.json` location. Verify that
its `bundleId` is `com.taskweavn.plato.computer-use-helper.dev` before using it.

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
- `config.manifestPath`
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
- help text includes `--manifest-path`, `--contact`, `--message`,
  `--allow-focus-select`, `--allow-submit`, `--confirm-submit`, `--session-id`,
  `--task-id`, `--effect-db`, `--replay-only`, `--readiness-only`, and
  `--evidence-output`;
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

### 5.1 Helper Readiness-Only Check

Use this before Smoke B when the fixed Helper permission state is uncertain.
It queries the Helper and exits without opening or operating WeChat:

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py \
  --manifest-path /path/to/app-control-service.json \
  --message 'readiness only' \
  --readiness-only \
  --evidence-output /tmp/plato-app-control-readiness.json
```

Expected result:

- evidence contains exactly one `readiness` observation;
- `readinessOnly` is `true`;
- no `open_wechat`, `open_contact`, draft, observe-chat, or submit operation is
  present.

Current fixed Dev Helper results:

- initial 2026-07-19 evidence:
  `/tmp/plato-app-control-readiness-20260719.json` reported
  `missing_accessibility` without any WeChat operation;
- TCC diagnostics showed that the existing Accessibility row referenced an
  older ad-hoc code requirement;
- after deleting and re-adding the current fixed Helper app, evidence
  `/tmp/plato-app-control-readiness-after-tcc-readd-20260719.json` passed with
  exactly one `readiness` observation, `readinessOnly=true`, and
  `accessibility_trusted=true`;
- the first post-readiness Smoke B stopped safely at `open_contact` because the
  Helper still had coordinate click disabled; evidence:
  `/tmp/plato-wechat-package-draft-20260719-2255.json`, with
  `submitAttempted=false` and `submitted=false`.
- after enabling coordinate click, the next authorized Smoke B stopped even
  earlier at `open_wechat` because WeChat had no focused Accessibility window;
  evidence: `/tmp/plato-wechat-package-draft-20260719-2325.json`, with
  `failureKind=accessibility_query_no_focused_window`,
  `submitAttempted=false`, and `submitted=false`. Open the WeChat main window
  manually before a separately authorized rerun; do not retry automatically.
- after manually opening WeChat and enabling coordinate click by default, the
  single authorized 2026-07-20 rerun passed `readiness` and `open_wechat`, then
  stopped at `open_contact`; evidence:
  `/tmp/plato-wechat-package-draft-20260720-001726.json`. The contact control
  map found a visible candidate, but the package-backed coordinate `click`
  returned `action.available=false` with the generic
  `failureKind=failed`. No draft or submit operation ran:
  `submitAttempted=false` and `submitted=false`. Diagnose the package/service
  click failure before another app-operation retry.
- static diagnosis on 2026-07-21 found that `computer-use-macos 0.3.0` launches
  coordinate clicks with
  `sys.executable -m computer_use_macos._coordinate_click`, while the frozen
  Plato Helper entrypoint only implemented the package's `python -c` selector
  worker contract. The entrypoint now supports that exact allowlisted module
  worker and rejects every other `-m` module. A temporary PyInstaller bundle
  under `/tmp` passed both the existing `-c` worker check and a safe `-m`
  dispatch check that used an invalid coordinate and exited before posting a
  mouse event. The fixed Dev Helper was then installed at the stable app path,
  reauthorized, and passed readiness with `accessibility_trusted=true`.
- the single authorized 2026-07-21 Smoke B then passed the full no-submit flow;
  evidence: `/tmp/plato-wechat-package-draft-20260721-215213.json`. The
  package resolved `文件传输助手` through `open_contact`, drafted 48 characters,
  and observed the current chat with `submitAttempted=false` and
  `submitted=false`.

## 6. Smoke B: No-Submit Open / Draft / Observe

The script opens/focuses WeChat, resolves `文件传输助手` through package
`open_contact`, drafts a message, and observes the selected chat. It must not
submit.

Choose values:

```text
timestamp = YYYYMMDD-HHMMSS
smoke_id = plato-wechat-package-draft-<timestamp>
message = Plato package-backed draft smoke <timestamp>
```

Electron-owned Helper service:

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py \
  --manifest-path /path/to/app-control-service.json \
  --contact 文件传输助手 \
  --message 'Plato package-backed draft smoke <timestamp>' \
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

- 2026-07-21: the fixed, reauthorized Dev Helper passed the full current
  package path: `readiness -> open_wechat -> open_contact -> draft_message ->
  observe_current_chat`. Evidence:
  `/tmp/plato-wechat-package-draft-20260721-215213.json`.
- Contact resolution used `open_contact` with
  `openMethod=control_map_visible_action_ref`, verified current chat title
  `文件传输助手`, and reported confidence `0.95`.
- The test drafted `Plato package-backed draft smoke 20260721-215213` without
  submit permission. Evidence records `submitRequested=false`,
  `submitAttempted=false`, and `submitted=false`. The visible draft remains in
  the WeChat input until cleared manually.
- 2026-07-18: passed through the local app-control service, following the
  published package SDK example. Evidence:
  `/tmp/plato-wechat-service-draft-20260718-133314.json`. This is historical
  service evidence; it predates the fixed Electron-owned Dev Helper proof.
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

Choose a fresh product execution identity. Do not supply an arbitrary
idempotency key; Plato derives it from `session_id + task_id`:

```text
timestamp = YYYYMMDD-HHMMSS
smoke_id = plato-wechat-package-submit-<timestamp>
session_id = plato-wechat-smoke-<timestamp>
task_id = wechat-send-<timestamp>
effect_db = /path/to/workspace/.plato/sessions/<session_id>/tool_effects.sqlite
message = Plato package-backed submit smoke <timestamp>
```

Command:

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py \
  --manifest-path /path/to/app-control-service.json \
  --contact 文件传输助手 \
  --message 'Plato package-backed submit smoke <timestamp>' \
  --smoke-id plato-wechat-package-submit-<timestamp> \
  --session-id plato-wechat-smoke-<timestamp> \
  --task-id wechat-send-<timestamp> \
  --effect-db /path/to/workspace/.plato/sessions/plato-wechat-smoke-<timestamp>/tool_effects.sqlite \
  --allow-focus-select \
  --allow-submit \
  --confirm-submit SEND \
  --evidence-output /tmp/plato-wechat-package-submit-<timestamp>.json
```

Expected result:

- process exits `0`;
- `submitted` is `true`;
- the final Plato observation is a successful semantic `send_message`;
- package event summaries show the bounded internal contact, draft, submit,
  and verification phases;
- `send_boundary.state=completed` and `send_boundary.replayed=false`;
- WeChat shows exactly one sent message matching the smoke message;
- package events and observations are present in the evidence JSON.

If semantic `send_message` returns an unknown outcome, do not retry. Manually
inspect the chat and preserve the evidence file as failed/unknown evidence. If
the read-only inspection finds exactly one matching outgoing message and an
empty chat input, archive the boundary with the separate offline reconciliation
command. The command requires the original session/task identity, request hash,
contact, and message hash; it never connects to Helper or WeChat. It preserves
the original package observation and writes an independent reconciliation audit
record.

```bash
uv run python scripts/reconcile_wechat_send_boundary.py \
  --effect-db /path/to/tool_effects.sqlite \
  --session-id <original-session-id> \
  --task-id <original-task-id> \
  --request-hash <original-request-hash> \
  --contact 文件传输助手 \
  --message-sha256 <original-message-sha256> \
  --observed-at <timezone-aware-timestamp> \
  --operator <operator-id> \
  --note '<sanitized manual observation>' \
  --confirm-exact-outgoing-count 1 \
  --confirm-chat-input-empty \
  --confirm-reconciliation COMPLETE \
  --evidence-output /tmp/wechat-send-reconciliation.json
```

Current branch result:

- 2026-07-21: one separately authorized current Smoke C used fresh identity
  `session_id=plato-wechat-smoke-20260721-222218` and
  `task_id=wechat-send-20260721-222218`, with effect store
  `/tmp/plato-wechat-smoke-20260721-222218/tool_effects.sqlite`.
- The semantic package flow resolved `文件传输助手`, drafted
  `Plato package-backed submit smoke 20260721-222218`, and successfully pressed
  Return. Package post-submit parsing did not find the new text, so the final
  automated result was `status=unknown` and `failureKind=send_unverified`.
  No retry was performed.
- A separate read-only UI inspection immediately afterward found exactly one
  matching outgoing message at `22:24` and an empty chat input. This confirms
  the external effect succeeded exactly once despite the failed package
  verification.
- The new offline reconciliation path matched the exact scope, idempotency key,
  request hash, contact, and message hash, then atomically changed only the
  durable boundary from `unknown` to `completed`. A subsequent ledger-only
  claim returned `replay`; no Helper or WeChat action occurred. The original
  package observation remains `status=unknown` with `submitted=true`.
- Reconciliation evidence:
  `/tmp/plato-wechat-package-submit-20260721-222218-reconciliation.json`.
- Evidence:
  `/tmp/plato-wechat-package-submit-20260721-222218.json`. It was generated
  before the follow-up projection fix, so its top-level `submitAttempted` and
  `submitted` fields are false while the nested package observation correctly
  records `submitted=true`. The smoke projection now preserves
  `submitAttempted=true`, `submitted=true`, and `status=unknown` together; the
  regression is covered by the focused script test.
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

Replay must reuse the same `session_id`, `task_id`, exact contact/message, and
effect database as Smoke C. Use a new `smoke_id` and require `--replay-only`:

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py \
  --manifest-path /path/to/app-control-service.json \
  --contact 文件传输助手 \
  --message 'Plato package-backed submit smoke <timestamp>' \
  --smoke-id plato-wechat-package-replay-<timestamp> \
  --session-id plato-wechat-smoke-<timestamp> \
  --task-id wechat-send-<timestamp> \
  --effect-db /path/to/workspace/.plato/sessions/plato-wechat-smoke-<timestamp>/tool_effects.sqlite \
  --replay-only \
  --allow-focus-select \
  --allow-submit \
  --confirm-submit SEND \
  --evidence-output /tmp/plato-wechat-package-replay-<timestamp>.json
```

Expected result:

- no second identical WeChat message is sent;
- evidence reports `replayed=true`, `submitAttempted=false`, and
  `submitted=false` for the replay run;
- the cached final observation contains
  `metadata.send_boundary.replayed=true`;
- no second semantic `send_message` package command/event appears;
- if the effect record is missing, `--replay-only` exits before package
  execution instead of risking a new send.

Current branch result:

- 2026-07-21: separately authorized Smoke D reused the exact reconciled Smoke C
  identity, effect database, contact, and message with new smoke id
  `plato-wechat-package-replay-20260721-225215`.
- Result: `replayed=true`, `submitAttempted=false`, `submitted=false`, and the
  projected replay observation was `status=ok`, `success=true`.
- The current-run event stream contained only Helper readiness; it contained no
  new `wechat.desktop.send_message` command or event. The boundary remained
  `completed` with `resolution=manual_reconciliation` and retained
  `replay_original_status=unknown` for the original package result.
- Replay evidence:
  `/tmp/plato-wechat-package-replay-20260721-225215.json`. Nested historical
  message collections are redacted to counts.
- The temporary Helper was stopped and its manifest, token, and socket were
  removed after verification.

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
- [x] Historical Smoke B passes with `submitted=false` through a local service.
- [x] Current Smoke B passes through the Electron-owned fixed Dev Helper.
- [x] Smoke C is explicitly authorized and exactly one visible sent message is
      confirmed by read-only UI inspection.
- [x] The ambiguous Smoke C boundary is manually reconciled to `completed` with
      exact identity/hash checks and preserved original package evidence.
- [ ] Smoke C package verification and durable boundary complete automatically
      instead of ending in `send_unverified` / `state=unknown`.
- [x] Smoke D proves no duplicate send for the same TaskBus execution identity.
- [x] Evidence JSON files are referenced in this runbook and the migration
      completion audit; raw UI evidence remains local to avoid committing
      message-bearing diagnostic payloads.
- [x] Runtime logs, Audit, and diagnostics can project package
      `ToolEvent` / `ToolObservation` summaries without leaking secrets.

## 11. Current Branch Status

As of 2026-07-21:

- package dependencies and source migration are implemented on branch;
- Smoke A package import / CLI contract passed without opening WeChat;
- the current fixed Dev Helper path passed Smoke B through `open_contact`,
  `draft_message`, and `observe_current_chat`; evidence is
  `/tmp/plato-wechat-package-draft-20260721-215213.json`, with
  `submitAttempted=false` and `submitted=false`;
- the fixed Dev Helper is installed at
  `~/Applications/Plato Computer Use Helper Dev.app`, version `0.3.0`, bundle
  id `com.taskweavn.plato.computer-use-helper.dev`;
- Electron startup produced a private manifest/token/socket and sidecar
  readiness identified the exact Helper permission subject. An isolated live
  Ctrl-C regression run then stopped Helper PID `41066` and removed the
  manifest, token, and socket. This proof includes the duplicate-signal and
  stale-runtime-file fixes, not only a mocked `stop()` call;
- the frozen Helper worker incompatibility behind the earlier coordinate click
  failure is fixed in the installed bundle and validated by the successful
  current Smoke B;
- the authorized current Smoke C sent exactly one visible message. Package
  verification returned `send_unverified`; manual read-only inspection confirmed
  the send and no automatic retry occurred. The explicit offline reconciliation
  archived the durable effect as `completed`, and a ledger-only claim now
  returns `replay`. The original package evidence remains unknown and is stored
  at `/tmp/plato-wechat-package-submit-20260721-222218.json`; reconciliation
  evidence is stored at
  `/tmp/plato-wechat-package-submit-20260721-222218-reconciliation.json`;
- old repo-local helper/runtime code is retired from active source/tests;
- package event/observation projection, including unverified submitted sends,
  is covered by tests;
- the separately authorized real macOS Smoke D replay passed with no new send
  command, `submitAttempted=false`, and `submitted=false`. Evidence is
  `/tmp/plato-wechat-package-replay-20260721-225215.json`.
