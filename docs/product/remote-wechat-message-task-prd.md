# PRD: Remote WeChat Message Task Via Execution Plane

> Status: product exploration / not an implementation plan
>
> Last Updated: 2026-06-22
>
> Related:
> [Product 1.1 Plan](plato-1-1-product-plan.md),
> [Product 1.1 Technical Design](plato-1-1-technical-design.zh-CN.md),
> [ADR-0020 Execution Plane As Service / Task API Boundary](../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md),
> [TaskBus Service And Multi-Execution-Env Memo](../architecture/taskbus-service-multi-execution-env.md),
> [Execution Plane Service And Task API Plan](../plans/feature/execution-plane-service-task-api.md),
> [Local macOS WeChat Send MVP](../plans/feature/local-macos-wechat-send-mvp.md),
> [Local macOS WeChat Send MVP Technical Design](../plans/feature/local-macos-wechat-send-mvp-technical-design.zh-CN.md),
> [Local macOS WeChat Send Playbook](../plans/feature/local-macos-wechat-send-playbook.md)

---

## 1. Requirement Summary

User story:

```text
A computer publishes a task through API.
The task is routed to another computer on the same network.
That computer executes the task:
send a message to a specific WeChat contact.
The requester can query task status, result, and evidence.
```

Example:

```json
{
  "idempotencyKey": "crm:wechat-message:contact-123:2026-06-18T10:00",
  "requester": {
    "kind": "external_app",
    "id": "ops-crm"
  },
  "externalRef": {
    "system": "ops-crm",
    "kind": "contact",
    "id": "contact-123"
  },
  "taskType": "communication.wechat.send_message",
  "intent": "Send the approved sample follow-up message to this WeChat contact.",
  "input": {
    "contactDisplayName": "张三",
    "messageText": "你好，样品已寄出，麻烦查收。"
  },
  "policy": {
    "requiredCapability": "communication.wechat_desktop_send",
    "allowedTools": ["computer_use", "wechat_desktop"],
    "requiresHumanConfirmation": true,
    "riskLevel": "high"
  },
  "evidence": {
    "required": ["tool_observation", "screenshot", "result_summary"],
    "optional": ["audit_record"]
  }
}
```

## 2. Product Value

The core value is not "sending a WeChat message". The core value is a workflow
data bridge for tools that do not expose stable APIs.

If the system can safely execute a WeChat desktop action on another machine,
then the action itself becomes a structured operational event:

- who requested the contact;
- which contact was targeted;
- what message was approved;
- which environment performed the action;
- whether it succeeded;
- what evidence proves the action;
- which business record should be updated afterward.

This is the same product direction as Execution Plane as a service:

```text
External business app
  -> Task API
  -> capability-matched execution environment
  -> Agent + tools
  -> result / evidence / business hook
```

## 3. Users And Actors

| Actor | Role |
|---|---|
| External requester | CRM, operations tool, script, or Plato client that publishes the task. |
| Control Plane | Accepts task, validates policy, matches execution environment, tracks lifecycle. |
| Execution computer | Network-local machine logged into WeChat Desktop and registered as an ExecutionEnv. |
| Execution Agent | Short-lived agent process that runs the task on the execution computer. |
| Human operator | May approve final send, resolve contact ambiguity, unlock WeChat, or intervene on failure. |
| Auditor / reviewer | Reviews evidence, result, and business trace after execution. |

## 4. Goals

1. Allow a trusted local-network client to publish a typed WeChat-send task.
2. Route the task to a registered execution environment with WeChat Desktop
   capability.
3. Let the execution environment claim and run exactly one task lease.
4. Use computer-use / desktop automation to locate the contact and prepare the
   message.
5. Require explicit confirmation before the message is actually sent.
6. Capture safe evidence before and after the send.
7. Return a durable `TaskResult` or `TaskError`.
8. Preserve idempotency so retries do not send duplicate messages.
9. Expose task status, events, result, error, and evidence through Task API.

## 5. Non-Goals

- No public internet task execution API.
- No bypassing WeChat terms, login, device trust, or platform restrictions.
- No mass messaging / spam automation.
- No silent high-risk send without confirmation in the first version.
- No full CRM or influencer management product.
- No business-specific ecommerce schema in Execution Plane core.
- No guarantee that WeChat provides a reliable programmatic delivery receipt.
- No production rollout without security, audit, and operator policy.

## 6. MVP Slice: Local macOS WeChat Send

The first executable slice should validate the highest-risk product behavior on
one trusted local macOS machine before adding remote execution.

MVP statement:

```text
On the local macOS machine, Plato receives a typed WeChat-send task,
opens/focuses WeChat Desktop, resolves the target contact, drafts the exact
message, asks the user for explicit confirmation, sends only after approval,
and records a durable result/error summary with safe evidence.
```

This slice proves:

- real `computer_use` can operate a user desktop safely enough for a narrow
  external-message task;
- high-risk outbound communication can enter `waiting_for_user` instead of
  being executed silently;
- result, error, and evidence records can distinguish drafted, sent, failed,
  rejected, and unknown send-boundary states;
- the later remote Execution Plane use case has a credible local execution
  primitive.

### 6.1 MVP Scope

In scope:

1. **Single local macOS execution environment**
   - No Computer A / Computer B split.
   - No LAN task routing.
   - The same Plato sidecar owns task intake, execution, confirmation, and
     result projection.
2. **WeChat Desktop on macOS**
   - WeChat is installed by the user.
   - WeChat login, device trust, and unlock are user responsibilities.
   - Plato may detect not-ready states but must not handle credentials.
3. **Typed send-message task**
   - `taskType`: `communication.wechat.send_message`.
   - Required input:
     - `contactDisplayName`;
     - `messageText`.
   - Optional input:
     - contact remark / alias;
     - external business ref;
     - operator note.
4. **Computer-use backend**
   - Plato consumes the neutral macOS computer-use package through an adapter.
   - Required operations:
     - readiness;
     - open/focus app;
     - observe bounded UI state;
     - click/select safe UI target;
     - type text into focused editable field.
   - Raw coordinate clicks are disabled by default.
5. **WeChat adapter behavior**
   - Open or focus WeChat Desktop.
   - Search the target contact.
   - Detect missing or ambiguous contacts.
   - Select exactly one contact only when confidence is sufficient.
   - Draft the exact `messageText` without sending.
   - Represent the final send action as high risk.
6. **Human confirmation before send**
   - The task enters `waiting_for_user` after the draft is prepared.
   - UI shows exact contact, message, and risk summary.
   - Sending is allowed only after durable confirmation is resolved as approved.
   - Reject/cancel leaves the message unsent and records a terminal result.
7. **Result and evidence**
   - Store final `TaskResult` or `TaskError`.
   - Store safe observation summaries.
   - Store confirmation metadata.
   - Store send-boundary status:
     - `not_started`;
     - `drafted`;
     - `confirmed`;
     - `sent`;
     - `not_sent`;
     - `unknown`.

### 6.2 MVP Non-Goals

Out of scope for this slice:

- remote ExecutionEnv registration;
- LAN auth, claim, lease, heartbeat, and remote result upload;
- Windows WeChat support;
- group chat, broadcast, batch messaging, or campaign automation;
- file, image, video, voice, or emoji sending;
- generated marketing copy;
- automatic CRM / business hook updates;
- public API exposure outside local trusted development;
- screenshot storage unless a redaction policy is explicitly implemented;
- reliable WeChat delivery/read receipt guarantees;
- automatic retry after an unknown send boundary.

### 6.3 MVP User Flow

1. User or local API submits a typed WeChat-send task.
2. Plato validates:
   - computer-use is enabled;
   - macOS Accessibility readiness is available;
   - WeChat Desktop is allowlisted;
   - task policy requires confirmation.
3. Agent opens or focuses WeChat Desktop.
4. Agent searches for the target contact.
5. If WeChat is locked, not logged in, contact is missing, or contact is
   ambiguous, Agent emits ASK / intervention and does not draft/send.
6. Agent selects the resolved contact.
7. Agent drafts the exact message in the input box.
8. Agent emits a confirmation request with:
   - resolved contact summary;
   - message preview;
   - send-boundary status `drafted`;
   - risk level `high`.
9. UI shows confirmation above the input/workspace area and blocks the send.
10. If user rejects, Agent records `not_sent` and completes safely.
11. If user approves, Agent verifies the confirmation belongs to the same
    contact/message/action fingerprint.
12. Agent performs the send action once.
13. Agent records `sent` or `unknown` with result/error evidence.
14. Main Page and Activity show the final user-readable outcome.

### 6.4 MVP Acceptance Criteria

The MVP is accepted when all criteria below pass on a local macOS development
machine:

1. **Readiness**
   - When Accessibility is missing, the task is rejected or blocked with a
     user-readable setup reason.
   - When WeChat Desktop is missing, not logged in, locked, or not observable,
     the task enters intervention or fails safely before drafting.
2. **Draft-only boundary**
   - Given a valid contact and message, Plato can open/focus WeChat, select the
     contact, and draft the exact message without sending.
   - The task must not send while confirmation is unresolved.
3. **Confirmation**
   - The confirmation UI shows exact contact and exact message text.
   - Reject/cancel records `not_sent`.
   - Approve resumes the same task and authorizes only the matching action
     fingerprint.
4. **Send**
   - After approval, exactly one send action is attempted.
   - Re-running the same idempotency key after `sent` does not send again.
   - If send status is `unknown`, automatic retry is blocked until human review.
5. **Result and evidence**
   - Success produces a durable `TaskResult` with contact summary, message
     summary, send-boundary status, and evidence refs.
   - Failure produces a durable `TaskError` with phase, retryability,
     operator action needed, and send-boundary status.
   - Raw unrelated WeChat chat history is not stored by default.
6. **UI projection**
   - Main Page shows `running`, `waiting_for_user`, `done`, `failed`, or
     `rejected` accurately.
   - Activity shows progress, confirmation, and result/error events.
   - Audit/evidence entry may be minimal but must not claim unavailable proof.

### 6.5 MVP Risk Boundaries

This slice is allowed only under these boundaries:

- High-risk send is confirmation-gated.
- Agent cannot silently send based on prompt text alone.
- Unknown send status blocks automatic retry.
- Contact ambiguity blocks execution and asks the user.
- WeChat credentials are never requested or stored.
- Screenshots are disabled by default unless redaction is implemented.
- Local API is treated as trusted development only, not production LAN exposure.
- Business use requires a later security, audit, abuse, and deployment review.

### 6.6 MVP Follow-Up Decisions

Before moving from local MVP to remote execution, decide:

1. Whether the first supported business machine is macOS, Windows, or both.
2. Whether confirmation is performed by the requester, local operator, or both.
3. How contact identity should be made stable beyond display name.
4. Whether screenshot evidence is required or observation-only evidence is
   sufficient for the first business pilot.
5. What rate limits and abuse controls apply to outbound messaging.

## 7. Remote Primary Flow

1. Computer A calls `POST /api/v1/tasks` on the Control Plane.
2. Control Plane validates:
   - requester identity;
   - idempotency key;
   - task type;
   - capability policy;
   - high-risk confirmation requirement;
   - evidence requirements.
3. Control Plane creates `TaskExecution(status=pending)`.
4. Computer B is registered as an `ExecutionEnv` with:
   - `communication.wechat_desktop_send`;
   - `computer_use`;
   - WeChat Desktop session availability.
5. Computer B claims the task and obtains a lease.
6. Agent starts on Computer B and assembles context:
   - task input;
   - contact hint;
   - message text;
   - policy;
   - evidence requirement.
7. Agent opens or focuses WeChat Desktop.
8. Agent searches for the target contact.
9. If the contact is ambiguous, missing, or WeChat is not ready, Agent creates
   an ASK / intervention event.
10. Agent drafts the message in WeChat but does not send yet.
11. Human operator confirms the exact contact and message.
12. Agent sends the message.
13. Agent captures result summary and evidence.
14. Control Plane marks task done and exposes result/evidence to Computer A.

## 8. Required Screen / API States

| State | Meaning | Required Behavior |
|---|---|---|
| `pending` | Task accepted, waiting for compatible execution env. | Queryable through Task API. |
| `claimed` | Computer B leased the task. | Prevent duplicate execution. |
| `running` | Agent is operating WeChat. | Emit progress events. |
| `waiting_for_user` | Needs confirmation or ASK answer. | Do not send until resolved. |
| `done` | Message sent and evidence captured. | Return `TaskResult`. |
| `failed` | Could not complete safely. | Return `TaskError` with retryability. |
| `lease_expired` | Computer B disappeared mid-task. | Allow safe retry only if no send occurred. |
| `rejected` | Request violates policy or capability requirements. | Return structured error. |

## 9. Safety And Permission Requirements

This task is high risk because it sends an external message as a real user.

Minimum safety requirements:

1. **Requester authorization**: only trusted local-network clients can publish.
2. **Execution environment authorization**: only approved machines can claim
   WeChat-send tasks.
3. **Human confirmation**: first version must require confirmation before send.
4. **Contact disambiguation**: if more than one contact matches, stop and ask.
5. **Message preview**: show exact message before sending.
6. **Idempotency**: repeated publish or retry must not duplicate-send.
7. **Send boundary tracking**: the system must record whether the message was
   only drafted, confirmed, sent, or unknown.
8. **Evidence redaction**: screenshots may contain unrelated chat content and
   must be redacted or permission-limited.
9. **No raw credential handling**: the system must not ask for or store WeChat
   credentials.
10. **Rate / abuse controls**: bulk or repeated sends require additional policy.

## 10. Evidence Requirements

Required evidence for a successful task:

- task request metadata;
- execution environment id;
- contact resolution summary;
- confirmation event;
- sent-message result summary;
- safe screenshot or redacted visual proof;
- tool observations;
- final `TaskResult`.

Required evidence for failed tasks:

- failure phase;
- retryability;
- whether the message was sent, not sent, or unknown;
- operator action needed;
- safe screenshot if available;
- final `TaskError`.

Evidence must be queryable through Execution Plane / Audit surfaces without
exposing raw unrelated WeChat chat history by default.

## 11. Capability Gap Summary

Current repository foundation already covers part of the requirement:

| Existing / Partial Capability | Status |
|---|---|
| Task-first product model | exists |
| TaskBus lifecycle | exists for local execution |
| AgentLoop execution | exists for local fixed-route tasks |
| Execution Plane DTO / embedded Task API foundation | foundation in progress |
| Local sidecar task API shell | foundation in progress |
| Result / error / evidence references | foundation in progress |
| ASK / confirmation product model | exists locally |
| Context Manager | exists locally |
| Skill governance backend foundation | exists locally |

Major missing capabilities:

| Gap | Severity | Why It Matters |
|---|---:|---|
| Network-exposed Control Plane API | P0 | Computer A must securely reach the Control Plane or Computer B. Current sidecar is local-first. |
| Local-network auth / trust model | P0 | Task publish and task claim must not be open to any LAN device. |
| ExecutionEnv registration over network | P0 | Computer B must register capabilities and availability. |
| Claim / lease / heartbeat | P0 | Prevent duplicate execution and recover when Computer B disappears. |
| Remote task event/result upload | P0 | Computer B must report progress, ASK, result, error, and evidence. |
| Computer-use runtime tool | P0 | Agent needs controlled desktop perception/action. |
| WeChat Desktop capability adapter | P0 | Need app focus, search, contact selection, compose, send, and failure detection. |
| Contact identity resolver | P0 | Display names are ambiguous; need stable matching and ASK fallback. |
| Human confirmation before send | P0 | Required for high-risk outbound communication. |
| Exactly-once send semantics | P0 | Retry must not accidentally send duplicate messages. |
| Evidence capture/redaction | P0 | Screenshots and chat content are sensitive. |
| Windows support | P0/P1 | Real WeChat Desktop business use likely runs on Windows. |
| Operator intervention UI | P1 | Unlock/login/contact ambiguity needs human resolution. |
| Callback / webhook / polling contract | P1 | Computer A needs task completion notification. |
| Business hook / CRM update | P1 | Value comes from writing structured workflow memory back to business systems. |
| Audit Page deep evidence view | P1 | Reviewer needs traceability after execution. |
| Abuse/rate policy | P1 | Prevent mass messaging or unintended spam. |
| Deployment/install/update for execution computer | P1 | Computer B needs stable sidecar/runtime distribution. |

Minimum local macOS MVP requires roughly these blockers:

1. macOS computer-use package adapter inside Plato;
2. WeChat Desktop readiness detection;
3. contact search / selection / ambiguity handling;
4. draft-only workflow before send;
5. high-risk confirmation before send;
6. send-boundary idempotency;
7. result/error/evidence projection.

Minimum remote lab demo additionally requires:

1. network Task API access with local auth;
2. remote ExecutionEnv registration;
3. claim / lease / heartbeat;
4. remote task event/result/evidence upload;
5. remote operator intervention behavior.

Production use additionally requires:

- operator management;
- audit/redaction hardening;
- exactly-once evidence proof;
- callback/business hook;
- Windows packaging and reliability;
- security review.

## 12. Suggested Phasing

### Phase 0: Local macOS MVP

- Plato adapter for the neutral macOS computer-use package;
- local sidecar readiness projection;
- WeChat Desktop readiness and allowlist;
- contact search / select / ambiguity detection;
- draft-only message preparation;
- confirmation-gated send;
- send-boundary idempotency;
- result/error/evidence projection.

Acceptance:

- A local task can draft a WeChat message to one resolved contact;
- the message is not sent before confirmation;
- approval sends at most once;
- reject/cancel records `not_sent`;
- unknown send status blocks automatic retry;
- Main Page / Activity expose the final outcome.

### Phase A: Remote Execution Substrate

- network-safe Task API;
- local-network auth;
- ExecutionEnv registration;
- claim / lease / heartbeat;
- remote event/result/evidence upload.

Acceptance:

- Computer A can publish a no-op or file-read task;
- Computer B claims and completes it;
- duplicate claim is rejected;
- result is queryable from Computer A.

### Phase B: Computer-Use Tool Baseline

- screen observation;
- mouse/keyboard action;
- app focus;
- screenshot capture;
- safe action policy;
- human stop/intervention.

Acceptance:

- Computer B can perform a harmless local desktop task and return evidence.

### Phase C: WeChat Draft-Only Workflow

- launch/focus WeChat;
- search contact;
- compose message;
- stop before sending;
- ask for confirmation or report ambiguity.

Acceptance:

- Message is drafted but not sent until confirmation.

### Phase D: Confirmed Send Workflow

- confirmation lifecycle;
- send action;
- result/evidence capture;
- retry protection.

Acceptance:

- One approved message is sent once;
- retry after completion does not duplicate-send.

### Phase E: Business Memory Hook

- write structured result back to CRM / knowledge store;
- record conversation outcome;
- expose audit/evidence.

Acceptance:

- Business system can query status and update contact history.

## 13. Open Questions

1. Is Computer B expected to be Windows, macOS, or both?
2. Is WeChat Desktop already logged in and unlocked?
3. Who confirms the send: Computer A user, Computer B operator, or both?
4. How is the contact identified: display name, remark, phone, WeChat ID, CRM
   mapping, or manual selection?
5. Is the message pre-approved text or generated by Agent?
6. Are screenshots allowed to be stored? If yes, what redaction policy applies?
7. Should the first version support only draft mode, not send mode?
8. How should the system prove "not sent" after failure or lease expiration?
9. Should business hooks update CRM automatically or require review?
10. What rate limits and abuse controls are required for outreach scenarios?

## 14. Product Decision

This PRD should not be treated as a Product 1.1 release blocker.

It is a strong Product 1.1+ vertical proof for the Execution Plane direction,
but it requires several platform capabilities that are currently missing.

Recommended stance:

```text
Use the Local macOS MVP slice to validate the real desktop execution primitive
first.

Do not implement remote WeChat execution before remote auth, env registration,
claim/lease, confirmation, idempotency, and evidence capture are in place.

Do not allow any local or remote WeChat send path to bypass high-risk
confirmation and send-boundary tracking.
```
