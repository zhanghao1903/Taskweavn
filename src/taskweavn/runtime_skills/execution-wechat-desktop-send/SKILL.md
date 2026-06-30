---
skill_id: internal:execution-wechat-desktop-send
name: execution-wechat-desktop-send
description: Use when an execution task must operate WeChat Desktop to prepare and submit one confirmation-gated message.
context_requirements:
  - execution_agent
  - wechat_desktop_send
risk_tags:
  - external_message
  - computer_use
  - high_risk
output_contract: Operate WeChat through the package-backed wechat_desktop tool and preserve confirmation, idempotency, and evidence boundaries.
---

# Execution WeChat Desktop Send

Use this skill after a validated execution task already exists. Do not use this
skill for Router semantic parsing.

Execution rules:

1. Confirm macOS computer-use readiness before interacting with WeChat.
2. Use `wechat_desktop.focus_contact` for the requested contact. Do not
   reimplement WeChat search/focus through raw `computer_use` unless the
   semantic tool is unavailable.
3. Use `wechat_desktop.draft_message` for exactly the requested message text.
4. Verify input focus and drafted content through package observations before
   requesting confirmation.
5. Wait for Plato confirmation before submitting.
6. Use `wechat_desktop.submit_draft` only after confirmation.
7. Preserve idempotency, package command ids, ToolEvent progress, and
   ToolObservation evidence.
8. If readiness, contact resolution, input verification, or confirmation fails,
   stop without sending and report structured evidence.
