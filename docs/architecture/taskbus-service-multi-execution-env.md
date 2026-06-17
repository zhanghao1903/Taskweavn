# TaskBus Service And Multi-Execution-Env Architecture Memo

> Status: exploratory architecture memo
> Last Updated: 2026-06-17
> Scope: Product 1.1+ direction; not current implementation fact
> Related: [task.md](task.md), [bus-v2.md](bus-v2.md), [agent.md](agent.md), [tool-capability-layer.md](tool-capability-layer.md), [workspace-communication-protocol.md](workspace-communication-protocol.md), [context-manager.md](context-manager.md), [ui-backend-communication.md](ui-backend-communication.md)

---

## 1. Core Thesis

Plato's strongest platform direction is not to replace every ecommerce,
communication, ERP, CRM, or analytics tool. The stronger direction is to make
work executable, traceable, and data-producing across tools that do not share a
clean API surface.

The key product capability is:

```text
TaskBus as a Service
  + multiple execution environments
  + env-scoped tools such as computer use, MCP, browser, email, and local apps
  + durable task evidence
  + business hooks / knowledge updates
```

In this model, external business systems publish tasks to Plato. Plato routes
tasks to capable execution environments. Those environments execute work through
available tools and return structured results, evidence, and follow-up events.

The business system does not need every upstream platform to expose APIs before
it can start building a data flywheel. The act of executing the workflow becomes
the data capture path.

---

## 2. Problem Context

Many ecommerce operations depend on tools that are not cleanly integrated:

- ecommerce back offices expose incomplete or restricted data;
- inventory or ERP systems may support exports but not the required API shape;
- WeChat and similar communication tools may not expose stable APIs;
- customer feedback, sales signals, product iteration notes, campaign costs,
  and communication history are scattered across platforms;
- existing automation tools can operate a desktop, but their data often does
  not become durable enterprise memory.

The business gap is not only "automate this action". The deeper gap is:

```text
Operational work happens, but the organization does not retain a structured,
auditable memory of what happened and why it matters.
```

---

## 3. Product Position

Plato should act as a workflow data layer:

```text
External product / CRM / workflow system
  -> publishes a task
  -> Plato TaskBus accepts and tracks it
  -> an execution environment claims it
  -> Agent uses tools to perform the work
  -> observations and evidence are captured
  -> business hooks update knowledge and downstream systems
```

This keeps Plato focused on task execution, evidence, and memory rather than
trying to own every vertical business screen.

### 3.1 What Plato Owns

- task publication boundary;
- task lifecycle and idempotency;
- execution environment registration and capability matching;
- claim / lease / heartbeat for distributed execution;
- tool capability and permission boundary;
- task-scoped evidence and audit;
- result and error summaries;
- business event emission;
- hook execution and knowledge update orchestration.

### 3.2 What Plato Should Not Own First

- full ecommerce ERP replacement;
- full CRM replacement;
- full influencer management SaaS;
- direct replacement for WeChat or ecommerce back offices;
- business-specific UI for every vertical workflow;
- unreviewed high-risk outbound communication.

---

## 4. System Shape

```text
                          +-------------------------+
                          | External Business Apps  |
                          | CRM / OMS / scripts     |
                          +-----------+-------------+
                                      |
                                      | Task Publish API
                                      v
+-------------------------------------------------------------------+
| Plato Control Plane                                                |
|                                                                   |
| - TaskBus API                                                      |
| - Execution Env Registry                                           |
| - Scheduler / capability matcher                                   |
| - Claim / lease / heartbeat                                        |
| - Audit and evidence store                                         |
| - Knowledge / business event store                                 |
| - Webhook and hook runtime                                         |
+----------------------+----------------------+---------------------+
                       |                      |
                       | claim / lease        | result / evidence
                       v                      ^
       +---------------+----------------------+-+
       | Execution Env Agent                    |
       |                                        |
       | - local sidecar                         |
       | - AgentLoop / runtime                   |
       | - computer use                          |
       | - browser / email / MCP / local apps    |
       | - local evidence capture                |
       | - heartbeat and lease renewal           |
       +-----------------------------------------+
```

---

## 5. Control Plane

The control plane is the service boundary for distributed task execution.

Responsibilities:

1. expose task publish APIs;
2. own canonical task lifecycle state;
3. maintain execution environment registry;
4. match tasks to environments by capability, permission, and availability;
5. issue leases for claimed tasks;
6. reject duplicate execution through idempotency and lease checks;
7. persist task result, error, evidence, and audit metadata;
8. run or dispatch business hooks after task lifecycle transitions;
9. expose query APIs for task, evidence, environment, and business-event state.

The control plane must remain the source of truth for task state. Execution
environments may cache local context and collect local evidence, but they must
not become independent task authorities.

---

## 6. Execution Environment

An execution environment is a real or virtual machine that can perform work.

Examples:

- an office Windows PC logged into WeChat and ecommerce back offices;
- a macOS machine with browser automation and local files;
- a cloud VM with email/API/MCP tools;
- a controlled browser profile with specific platform sessions;
- a local employee workstation that only performs user-confirmed actions.

Each environment registers:

```text
env_id
display_name
status: online | offline | draining | disabled
capabilities
tool_pool
permission_profile
workspace_roots
active_task_id
last_heartbeat_at
version / runtime metadata
```

Capabilities are not only abstract skills. They must reflect what the
environment can actually do:

```text
computer_use
browser_control
email_send
wechat_desktop
mcp.jushuitan
mcp.crm
file_read
file_write
workspace_search
```

---

## 7. Task Publish API

External systems should be able to publish tasks without coupling to Plato's
internal execution model.

Candidate request shape:

```json
{
  "idempotencyKey": "external-system:task:123",
  "externalRef": {
    "system": "ops-crm",
    "kind": "influencer",
    "id": "inf_123"
  },
  "taskType": "outreach.contact",
  "intent": "Contact this creator about a sample collaboration.",
  "requiredCapability": "outreach.email_contact",
  "constraints": {
    "channel": "email",
    "requiresHumanConfirmation": true
  },
  "callback": {
    "webhookUrl": "https://example.com/plato/task-events"
  }
}
```

The publish boundary should preserve:

- idempotency;
- requester identity;
- external reference;
- task type;
- required capability;
- permission constraints;
- callback or webhook policy;
- expected result contract;
- evidence retention policy.

---

## 8. Claim, Lease, And Recovery

Distributed execution requires stronger lifecycle semantics than a single local
loop.

Minimum state model:

```text
pending
claimed
running
waiting_for_user
done
failed
cancelled
lease_expired
```

Required mechanics:

1. environment asks for the next compatible task;
2. control plane grants a lease with expiry;
3. environment renews lease by heartbeat;
4. task execution writes progress events and evidence refs;
5. lease expiry returns task to recoverable state or marks it for review;
6. duplicate result submission is rejected or deduplicated;
7. recovery policies are explicit per task type.

This is the distributed version of current TaskBus lifecycle and idempotency
work. It should build on existing TaskBus semantics rather than replace them.

---

## 9. Tool Capability Boundary

Tools must be scoped by execution environment.

The system must not assume every Agent has every tool. Instead:

```text
Task.required_capability
  -> compatible env candidates
  -> env tool pool
  -> permission merge
  -> skill/context guidance
  -> execution
```

Example:

```text
outreach.email_contact
  requires: email_send, browser_control, knowledge_read
  optional: crm_update
  risk: medium
  confirmation: before send
```

```text
outreach.wechat_contact
  requires: computer_use, wechat_desktop, screenshot_capture
  optional: knowledge_read
  risk: high
  confirmation: before send, before batch action
```

Computer use is important because it turns otherwise closed local tools into a
workflow execution and data capture surface. It should be treated as a powerful
tool family with evidence, permission, and confirmation requirements.

---

## 10. Evidence And Audit

Task execution must produce durable evidence, not only final text.

Evidence candidates:

- tool call result;
- screenshot;
- copied text;
- exported file;
- sent email metadata;
- page URL and timestamp;
- operator confirmation;
- extracted business event;
- error trace;
- generated summary;
- source object refs.

Every structured business event should retain source evidence:

```text
BusinessEvent
  -> source_task_id
  -> agent_run_id
  -> env_id
  -> evidence_refs
  -> confidence
  -> human_review_status
```

This is how workflow execution becomes a data flywheel instead of another
opaque automation layer.

---

## 11. Hooks And Knowledge Maintenance

Business-specific maintenance should be outside the TaskBus core.

Preferred model:

```text
Task lifecycle event
  -> hook matcher
  -> business hook
  -> knowledge update task or direct write
  -> audit record
```

Example:

```text
TaskDone(outreach.contact)
  -> append CommunicationEvent
  -> update InfluencerProfile.last_contacted_at
  -> schedule FollowUpTask
```

Hooks can be implemented as:

1. deterministic functions for simple updates;
2. Agent tasks for summarization or fuzzy extraction;
3. external webhooks for customer-owned systems;
4. manual review queues for low-confidence updates.

The knowledge base must not accept untraceable Agent writes. Each update should
carry evidence refs, confidence, and review status.

---

## 12. MVP Direction

The first service-oriented MVP should not use WeChat as the primary path.
WeChat is valuable but high risk because of UI fragility, account risk, and
communication sensitivity.

Recommended MVP:

```text
Email outreach task over TaskBus service
```

MVP workflow:

1. external system publishes an outreach task through API;
2. one registered execution environment claims it;
3. Agent reads a target profile and product context;
4. Agent drafts an email;
5. human confirms send;
6. environment sends email or simulates send in test mode;
7. task records evidence;
8. hook writes communication event;
9. hook schedules a follow-up task;
10. external callback receives task status.

Acceptance:

- task can be published through API;
- env can register and claim;
- task cannot be double-claimed;
- result and evidence are queryable;
- hook updates a business object or emits a business event;
- human confirmation is required before outbound communication;
- failure and lease-expiry states are visible.

---

## 13. Later Vertical Scenarios

After the service substrate is proven, vertical workflows can be added as
packages:

- influencer outreach;
- customer feedback triage;
- product iteration issue detection;
- sample shipment follow-up;
- campaign cost reconciliation;
- sales result review;
- inventory risk monitoring;
- supplier communication.

Each vertical package should define:

1. task types;
2. required capabilities;
3. result contract;
4. evidence requirements;
5. hooks;
6. business object mappings;
7. human review rules.

---

## 14. Key Risks

| Risk | Mitigation |
|---|---|
| Distributed execution creates duplicate or stale work | Claim/lease/heartbeat, idempotency, explicit recovery states. |
| Computer use is unstable | Treat it as high-risk tool family; require evidence, screenshots, retries, and human review. |
| Closed platforms change UI or restrict automation | Start with email/browser/API-compatible workflows; keep WeChat as later local-assisted mode. |
| Task types become free-text queue items | Require task type schemas and result contracts for business workflows. |
| Knowledge base becomes polluted | Require evidence refs, confidence, and review status for Agent-written facts. |
| Core platform absorbs vertical business logic | Keep hooks and vertical packages outside TaskBus core. |
| Security and privacy boundaries blur across envs | Env-scoped permissions, workspace scoping, credential isolation, redacted diagnostics. |

---

## 15. Non-Goals

This memo does not propose:

- replacing ecommerce platforms;
- replacing ERP, CRM, or communication tools;
- fully autonomous WeChat outreach;
- distributed execution without leases;
- a global tool pool shared by every environment;
- unreviewed knowledge base mutation;
- a generalized BI platform;
- a Product 1.0 requirement.

---

## 16. Recommended Next Plan

Create a Product 1.1+ feature plan:

```text
TaskBus Service And Execution Env Registry
```

Suggested slices:

1. Task Publish API contract with idempotency and external refs.
2. Execution Env Registry model and heartbeat API.
3. Claim / lease / renewal protocol.
4. Env-scoped tool capability model.
5. Evidence upload/query contract.
6. Hook runtime contract.
7. Email outreach MVP as first vertical proof.

Implementation should not start until the API contract and recovery semantics
are explicit.
