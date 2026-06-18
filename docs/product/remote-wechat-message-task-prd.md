# PRD: Remote WeChat Message Task Via Execution Plane

> Status: product exploration / not an implementation plan
>
> Last Updated: 2026-06-18
>
> Related:
> [Product 1.1 Plan](plato-1-1-product-plan.md),
> [Product 1.1 Technical Design](plato-1-1-technical-design.zh-CN.md),
> [ADR-0020 Execution Plane As Service / Task API Boundary](../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md),
> [TaskBus Service And Multi-Execution-Env Memo](../architecture/taskbus-service-multi-execution-env.md),
> [Execution Plane Service And Task API Plan](../plans/feature/execution-plane-service-task-api.md)

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

## 6. Primary Flow

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

## 7. Required Screen / API States

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

## 8. Safety And Permission Requirements

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

## 9. Evidence Requirements

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

## 10. Capability Gap Summary

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

Minimum lab demo requires roughly these blockers:

1. network Task API access with local auth;
2. remote ExecutionEnv registration;
3. claim / lease / heartbeat;
4. computer-use tool baseline;
5. WeChat Desktop adapter;
6. confirmation + evidence capture.

Production use additionally requires:

- operator management;
- audit/redaction hardening;
- exactly-once evidence proof;
- callback/business hook;
- Windows packaging and reliability;
- security review.

## 11. Suggested Phasing

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

## 12. Open Questions

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

## 13. Product Decision

This PRD should not be treated as a Product 1.1 release blocker.

It is a strong Product 1.1+ vertical proof for the Execution Plane direction,
but it requires several platform capabilities that are currently missing.

Recommended stance:

```text
Use this PRD to validate Execution Plane + remote env + computer-use direction.
Do not implement WeChat send before remote execution safety, confirmation,
idempotency, and evidence capture are in place.
```
