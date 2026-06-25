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
output_contract: Operate WeChat only through the approved computer-use adapter and preserve confirmation, idempotency, and evidence boundaries.
---

# Execution WeChat Desktop Send

Use this skill after a validated execution task already exists. Do not use this
skill for Router semantic parsing.

Execution rules:

1. Confirm macOS computer-use readiness before interacting with WeChat.
2. Open or focus WeChat through the allowed app boundary.
3. Resolve exactly one contact.
4. Draft exactly the requested message text.
5. Verify input focus and drafted content before requesting confirmation.
6. Wait for Plato confirmation before submitting.
7. Submit using the approved send method for the current WeChat adapter.
8. Preserve send-boundary idempotency and evidence.
9. If readiness, contact resolution, input verification, or confirmation fails,
   stop without sending and report structured evidence.
