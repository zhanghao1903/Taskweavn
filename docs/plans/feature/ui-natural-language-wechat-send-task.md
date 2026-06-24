# Feature Plan: UI Natural-Language WeChat Send Task

Status: completed
Last updated: 2026-06-24

## Summary

This plan defines the first user-facing path for creating a local macOS WeChat
send task from Plato's own Main Page input. The user writes a clear natural
language request, Plato routes it through the Runtime Input Router, creates a
confirmation-gated Execution Plane task, and the existing local WeChat runtime
performs the send only after user confirmation.

This is not the remote Task API use case. It proves the product loop first:

```text
Main Page input -> Runtime Input Router -> Execution Plane task
-> WeChat draft -> user confirmation -> send -> result/evidence projection
```

## Source Documents

- `docs/plans/feature/runtime-input-router-contract.md`
- `docs/plans/feature/runtime-input-router-contract-technical-design.md`
- `docs/plans/feature/local-macos-wechat-send-mvp.md`
- `docs/plans/feature/local-macos-wechat-send-mvp-technical-design.zh-CN.md`
- `docs/plans/feature/execution-plane-service-task-api.md`
- `docs/plans/feature/execution-plane-service-task-api-technical-design.zh-CN.md`
- `docs/product/remote-wechat-message-task-prd.md`
- `docs/ux/confirmation-ui-spec.md`

## Problem

The local macOS WeChat send MVP has proven that Plato can execute a controlled
WeChat send through a task API and confirmation boundary. However, that path is
still API/manual-smoke oriented.

For the product, the next proof should be simpler for users:

1. The user enters a concrete task in the Plato UI.
2. Plato recognizes it as a WeChat send execution request.
3. Plato creates the proper execution task.
4. The high-risk send is gated by confirmation.
5. The result and evidence show up in the existing task/activity surfaces.

Without this path, computer-use remains a backend capability rather than a
usable Plato workflow.

## Product Decision

The first product path will use the existing Main Page input rather than a new
external Task API caller.

The initial router behavior should be deterministic and bounded. It should
support clear WeChat-send phrases and reject or clarify ambiguous input. It
must not let a general LLM planner freely decide to send external messages.

## Target User Flow

Example input:

```text
给微信文件传输助手发送一条消息：Plato 本地发送测试。发送前让我确认。
```

Expected flow:

1. The user submits the text from the Main Page input.
2. Runtime Input Router classifies it as an external communication execution
   request.
3. Router extracts:
   - contact: `文件传输助手`
   - message: `Plato 本地发送测试。`
4. Router creates a `communication.wechat.send_message` Execution Plane task.
5. WeChat runtime opens/focuses WeChat and prepares the draft.
6. Plato presents a high-risk confirmation.
7. If the user rejects, no send happens and evidence records no-send.
8. If the user confirms, the message is submitted once.
9. Task result/error/evidence is projected into Main Page activity and
   conversation surfaces.

## Goals

- Support a clear UI-origin natural-language WeChat send request.
- Route the request through Runtime Input Router instead of direct tool calls.
- Build a valid Execution Plane task request using the existing WeChat task
  type:
  - `taskType=communication.wechat.send_message`
  - `input.contactDisplayName`
  - `input.messageText`
  - `policy.requiredCapability=communication.wechat_desktop_send`
  - `policy.requiresHumanConfirmation=true`
  - `policy.riskLevel=high`
- Preserve the confirmation boundary before any send.
- Preserve one-primary-side-effect semantics for a single user input.
- Preserve idempotency for retries/replays of the same routed command.
- Surface result, error, and evidence through existing Main Page projections.
- Keep the design compatible with future remote Task API submission.

## Non-Goals

- No LAN/remote computer execution in this slice.
- No bulk messaging.
- No arbitrary contact discovery UI.
- No file attachment send.
- No automatic send without confirmation.
- No generic LLM-controlled WeChat automation.
- No new high-fidelity UI redesign.
- No replacement of the existing WeChat runtime.
- No production support for all Chinese natural-language variants in the first
  slice.

## Scope

In scope:

- Runtime Input Router intent and slot extraction for clear WeChat send
  requests.
- Structured handoff from router to Execution Plane task creation.
- Clarification or ASK behavior when required fields are missing.
- Confirmation-gated execution using existing WeChat runtime.
- Result/error/evidence projection checks.
- Fake-adapter tests plus one controlled local real smoke to `文件传输助手`.

Out of scope:

- External app authentication.
- Network-exposed Task API usage.
- Multi-user authorization.
- Enterprise contact registry.
- Durable business CRM record creation.
- Skill packaging for WeChat usage. That can follow after the flow is proven.

## Implementation Slices

Current implementation status:

- NLW1/NLW2 foundation is implemented:
  - deterministic WeChat-send intent resolver;
  - contact/message slot extraction for bounded phrase patterns;
  - missing-contact and missing-message clarification outcomes;
  - ambiguous/bulk send rejection without side effects.
- NLW3 runtime handoff foundation is implemented:
  - Runtime Input Router prefers the deterministic WeChat resolver before LLM
    planning;
  - when an Execution Plane service is available, Router publishes a
    `communication.wechat.send_message` `TaskRequest`;
  - when no Execution Plane service is available, Router can still fall back to
    creating a contract-revision execution TaskNode.
- HTTP route user-path coverage is implemented for workspace-scoped Main Page
  runtime input routing into an Execution Plane WeChat TaskRequest.
- Fake runtime integration coverage is implemented for reject/no-send and
  confirm/send-once using the same natural-language runtime-input route.
- NLW4 clarification completion is implemented:
  - missing contact/message returns a non-mutating pending clarification;
  - Main Page stores the pending clarification in local UI state and sends it
    back with the next runtime-input request;
  - the follow-up answer completes the slots and creates the same
    confirmation-gated WeChat send task path.
- Renderer/Electron user-path smoke is implemented and passed on 2026-06-24:
  - `npm run electron:smoke:runtime-input-wechat`;
  - submits the incomplete WeChat request through the Main Page input;
  - verifies the missing-message clarification;
  - submits the follow-up message;
  - verifies safe capability-disabled feedback when computer-use is not enabled
    in the seeded fixture.

Final validation:

- Controlled real local smoke to `文件传输助手` passed on 2026-06-24:
  - base URL: local sidecar `http://127.0.0.1:58027`;
  - session: `a436ec2f`;
  - execution: `exec_93d596a34767537297a69bd6502e2f10`;
  - confirmation: `d601fc72dc53417fa1fc96db9f0958c2`;
  - idempotency key: `manual-wechat-smoke-20260624-e05a-authorized-02`;
  - result kind: `wechat_send_result`;
  - send boundary: `sent`;
  - submit method: `keyboard_return`;
  - terminal same-key replay returned the same execution and `done`.

### NLW0 - Plan And Technical Design

Create this plan and the detailed technical design.

Acceptance:

- Product boundary is explicit.
- Technical route from Main Page input to Execution Plane task is defined.
- Gap registry references this work.

### NLW1 - Router Intent And Fixture Contract

Add router-level fixtures for clear WeChat send requests.

Status: implemented for bounded local patterns.

Acceptance:

- Clear WeChat-send input routes to execution handoff.
- Missing contact/message routes to clarification or ASK.
- Low-confidence input has no external side effect.

### NLW2 - Deterministic WeChat Slot Extraction

Implement a bounded extractor for the first supported phrase patterns.

Status: implemented for first Chinese phrase patterns.

Acceptance:

- Extracts contact and message for accepted patterns.
- Rejects bulk, ambiguous, or missing-slot input.
- Unit tests cover Chinese punctuation and whitespace normalization.

### NLW3 - Execution Plane Handoff

Build the WeChat `TaskRequest` from the routed command and submit it through the
existing Task API service boundary.

Status: foundation implemented; HTTP route user-path smoke implemented;
renderer/Electron smoke passed on 2026-06-24.

Acceptance:

- The task type, input, policy, metadata, and idempotency key are generated
  consistently.
- No UI code invents API payload shape.
- Replayed router command returns the same execution result.

### NLW4 - Clarification / ASK Fallback

When the user request is incomplete, ask for the missing contact or message
instead of creating a task.

Status: implemented for the current local UI route. The pending clarification
is held by the Main Page controller and is not durable across page refresh or
app restart. Durable ASK-backed clarification remains a follow-up only if this
flow needs restart recovery.

Acceptance:

- Missing contact/message creates no task.
- The follow-up answer can complete the pending request.
- The UX makes it clear that no message has been sent.

### NLW5 - Main Page Projection

Ensure the created WeChat send task appears in Main Page activity, conversation,
detail, result, and evidence surfaces.

Acceptance:

- Waiting-for-confirmation is visible.
- Reject/no-send is visible.
- Confirm/send-once is visible.
- Failure evidence includes phase and failure kind.

### NLW6 - Smoke Coverage

Run fake-adapter integration first, then one controlled real local smoke to
`文件传输助手`.

Status: fake-adapter integration implemented; renderer/Electron UI-path smoke
passed; controlled real local smoke passed on 2026-06-24.

Acceptance:

- Workspace-scoped HTTP runtime-input route publishes the expected
  confirmation-gated `TaskRequest`.
- `npm run electron:smoke:runtime-input-wechat` proves the Main Page input path
  can surface missing-slot clarification and safe capability-disabled feedback
  without sending a message.
- Reject/no-send smoke passes before confirm/send smoke.
- Confirm/send-once uses a fresh idempotency key.
- Evidence records draft, confirmation, submit, and final observation phases.

## Status And Failure Handling

The flow must represent these outcomes explicitly:

- unsupported input
- missing contact
- missing message
- ambiguous/bulk send request
- runtime readiness failed
- WeChat contact not found
- draft preparation failed
- confirmation rejected
- confirmation expired
- send submitted once
- send result unknown
- execution failed with structured error

Stale snapshot, retry, and resync behavior should reuse existing runtime and
Main Page patterns where possible.

## Acceptance Criteria

- A clear UI-origin WeChat send request creates exactly one
  `communication.wechat.send_message` task.
- The request never sends without user confirmation.
- Rejecting confirmation produces a no-send result.
- Confirming sends once and produces result/evidence.
- Missing slots do not create a side effect.
- Replay of the same routed command does not duplicate a send.
- The product path does not depend on Figma Auto Layout or a new visual design.
- The implementation remains compatible with future remote Task API exposure.

## Risks

- Natural language can be ambiguous. The first slice must prefer clarification
  over unsafe execution.
- Sending WeChat messages is high risk. Confirmation must remain mandatory even
  if the user wording says "直接发送".
- Duplicate send prevention depends on stable command idempotency.
- WeChat UI automation is sensitive to app state and macOS permissions.
- If result/evidence projection is weak, users cannot trust what happened.

## Open Questions

- Should the first UI path allow only `文件传输助手`, or any explicit contact
  name?
- Should the generated WeChat send task appear as a normal Plan task, an
  execution-only task, or both?
- Should repeated identical user text mean a deliberate second send or a replay?
  Proposed answer: a new user submit is a new command; transport retry of the
  same command must be idempotent.
- Should the follow-up missing-slot interaction use the ASK lifecycle or the
  Runtime Input Router clarification path first?

## Recommended Next Task Prompt

```text
Use the product-workflow-gate skill first.

Task:
Implement NLW1 for UI natural-language WeChat send routing.

Scope:
- Add Runtime Input Router fixtures/tests for clear WeChat send input.
- Add missing-contact and missing-message clarification cases.
- Do not execute WeChat.
- Do not change frontend UI.
- Do not send real messages.

Acceptance:
- Clear "给微信文件传输助手发送一条消息：..." routes to execution handoff.
- Missing slots create no side effect.
- Unsupported or ambiguous input remains non-mutating.
```
