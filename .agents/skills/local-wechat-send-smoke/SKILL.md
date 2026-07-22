---
name: local-wechat-send-smoke
description: Run and diagnose the Taskweavn/Plato Local macOS WeChat Send MVP smoke. Use when testing controlled WeChat sends to 文件传输助手 or another controlled contact, validating managed send-boundary identities, preflight readiness, draft-before-submit, keyboard Return submit, replay/no-duplicate behavior, or investigating unknown WeChat automation outcomes.
---

# Local WeChat Send Smoke

## Purpose

Use this repo-scoped skill for the local macOS WeChat send MVP only. It verifies
the package-backed `wechat_desktop` / `computer_use` app-control path with
explicit confirmation and evidence. It is not a bulk messaging, remote
ExecutionEnv, or LAN API workflow.

## Safety Rules

- Run `product-workflow-gate` first.
- Never submit without explicit user authorization and both `--allow-submit`
  and `--confirm-submit SEND`.
- Use only a controlled contact. The default smoke contact is `文件传输助手`.
- Always use a fresh `session_id + task_id` identity and a session-scoped
  `tool_effects.sqlite` database for a real submit attempt. Plato derives the
  idempotency key; do not invent one in the Agent or operator command.
- Reuse that exact identity and database only for `--replay-only` verification.
- Never automatically retry an unknown or failed submit; inspect evidence and
  start a new run only after manual review.
- Keep screenshot evidence disabled unless a separate redaction plan exists.
- Draft/no-submit smoke can still open WeChat and leave text in the input field;
  run it only when that visible local side effect is acceptable.
- New package smoke runs must use package contact selection through
  `--allow-focus-select`, which calls `open_contact`. Do not assume that the
  current WeChat chat already matches the target contact.

## Package-Backed Smoke Flow

Use
`docs/plans/feature/app-control-tool-package-smoke-runbook.zh-CN.md`
as the operator runbook.

### Smoke A: Package Import / CLI Contract

This check does not open WeChat:

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py --help
```

Accept only if the command exits 0 and the help includes `--manifest-path`,
`--contact`, `--message`, `--allow-focus-select`,
`--allow-submit`, `--confirm-submit`, `--session-id`, `--task-id`,
`--effect-db`, `--replay-only`, `--readiness-only`, and `--evidence-output`.

### Readiness-Only Check

This check talks to the fixed Helper but never opens or operates WeChat:

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py \
  --manifest-path /path/to/app-control-service.json \
  --message "readiness only" \
  --readiness-only \
  --evidence-output /tmp/plato-app-control-readiness.json
```

Accept only if the sole observation is `readiness`, `readinessOnly=true`, and
the evidence contains no WeChat open/contact/draft/submit operation.

### Smoke B: No-Submit Open / Draft / Observe

This opens/focuses WeChat, resolves `文件传输助手` through the package
`open_contact` flow, drafts the message, and observes the selected chat. It
must not submit:

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py \
  --manifest-path /path/to/app-control-service.json \
  --contact 文件传输助手 \
  --message "Plato package-backed draft smoke <timestamp>" \
  --smoke-id plato-wechat-package-draft-<timestamp> \
  --allow-focus-select \
  --evidence-output /tmp/plato-wechat-package-draft-<timestamp>.json
```

The Electron-owned Plato Computer Use Helper process owns the macOS TCC
identity and full package service; the smoke caller only consumes its manifest.
Accept only if observations include successful `readiness`, `open_wechat`,
`open_contact`, `draft_message`, and `observe_current_chat`, with
`submitted=false`.

### Smoke C: Controlled Submit Once

Run only after explicit user authorization for that exact run:

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py \
  --manifest-path /path/to/app-control-service.json \
  --contact 文件传输助手 \
  --message "Plato package-backed submit smoke <timestamp>" \
  --smoke-id plato-wechat-package-submit-<timestamp> \
  --session-id plato-wechat-smoke-<timestamp> \
  --task-id wechat-send-<timestamp> \
  --effect-db /path/to/workspace/.plato/sessions/plato-wechat-smoke-<timestamp>/tool_effects.sqlite \
  --allow-focus-select \
  --allow-submit \
  --confirm-submit SEND \
  --evidence-output /tmp/plato-wechat-package-submit-<timestamp>.json
```

Accept only if `submitted=true`, `replayed=false`, the semantic `send_message`
succeeds, the send-boundary record is `completed`, and manual inspection shows
exactly one sent message matching the smoke text.

### Smoke D: Replay / No Duplicate

Run only after Smoke C has a known successful outcome. Reuse its exact
`session_id`, `task_id`, effect database, contact, and message; use a new smoke
id and add `--replay-only`. The replay must report `replayed=true`,
`submitAttempted=false`, and `submitted=false`, and it must not emit a second
semantic package `send_message` call. If the managed record is missing, the
script must fail before package execution. Preserve evidence and manually
verify no duplicate message appears.

```bash
uv run python scripts/manual_wechat_desktop_tool_smoke.py \
  --manifest-path /path/to/app-control-service.json \
  --contact 文件传输助手 \
  --message "Plato package-backed submit smoke <timestamp>" \
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

## Code Invariants

- `wechat_desktop` builds semantic package commands; it does not decide whether
  a message should be sent.
- `computer_use` executes app-control commands through `computer-use-macos`.
- Product policy or explicit operator authorization controls submit.
- Plato derives and persists the send-boundary identity; it is not an
  Agent-visible tool argument and is not delegated to the package service.
- Submit must use the package command path, not a coordinate click fallback.
- Evidence should include `ToolObservation` rows and safe runtime metadata.
- Raw helper tokens, full accessibility trees, and unrelated chat history must
  not be persisted.

## Diagnostics

- Read package evidence JSON written by `--evidence-output`.
- Inspect `observations[*].failure_kind`, `observations[*].message`,
  `observations[*].recovery_hint`, and emitted `events`.
- Unknown or failed submit means no automatic retry.
- If contact resolution fails, diagnose `open_contact` / `accessibility_query`
  evidence. Do not bypass it by assuming the current chat.
- If draft text may be stale, clear WeChat input manually before rerunning
  Smoke B.

## Focused Checks

Run after changing this path:

```bash
uv run pytest \
  tests/test_manual_wechat_desktop_tool_smoke_script.py \
  tests/test_wechat_desktop_tool.py \
  tests/test_runtime_input_wechat_router.py

uv run ruff check \
  scripts/manual_wechat_desktop_tool_smoke.py \
  tests/test_manual_wechat_desktop_tool_smoke_script.py \
  tests/test_wechat_desktop_tool.py \
  src/taskweavn/tools/wechat_desktop.py
```

## Playbook

Use `docs/plans/feature/app-control-tool-package-smoke-runbook.zh-CN.md` for
the active operator runbook. `docs/plans/feature/local-macos-wechat-send-playbook.md`
is historical only.
