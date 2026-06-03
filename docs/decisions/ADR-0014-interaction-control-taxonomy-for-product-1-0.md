# ADR-0014: Interaction Control Taxonomy For Product 1.0

> Status: accepted
> Date: 2026-06-03
> Related: [Task](../architecture/task.md), [TaskBus](../architecture/bus.md), [Interaction Layer](../architecture/interaction-layer.md), [UI / Backend Communication](../architecture/ui-backend-communication.md), [Cooperative Task Interruption](../plans/feature/cooperative-task-interruption.md), [ASK Lifecycle Contract](../engineering/ask-lifecycle-contract.md), [ASK User Interaction](../interaction-model/ask-user-interaction.md), [Gap Registry](../gaps/), [ADR-0011](ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0013](ADR-0013-cache-aware-append-only-context-rendering.md)

---

## Context

Product 1.0 still has two related P0 gaps:

- cooperative task interruption;
- Message, ASK, and confirmation UI integration.

They are related because both surface active user interaction during execution,
but they do not represent the same domain event.

If they are implemented as one generic "interaction pause" mechanism, Product
1.0 will likely inherit a broad control platform before the closed loop is
finished. That would mix stop intent, missing-information recovery, and
authorization into one state machine and make execution, UI projection, audit,
and retry harder to reason about.

---

## Decision

Product 1.0 separates three interaction control semantics and keeps
MessageStream as a history/communication substrate.

| Mechanism | Domain Meaning | State Authority | Product 1.0 Execution Effect | UI Surface |
|---|---|---|---|---|
| Interrupt | User or system asks active execution to stop. | TaskBus records interrupt intent; Agent/runtime acknowledges at safe points. | `pending` can fail immediately with `cancelled:`; `running` stays running and projects as stopping until terminal outcome. | Cancel/stop affordance, stopping projection, audit/message history. |
| ASK | Agent lacks required user-owned information. | Durable ASK request/answer store, later feature plan. | Blocking ASK pauses or yields execution until answered, cancelled, expired, or otherwise resolved. | ASK Dock and task/session waiting-for-user signals. |
| Confirmation | Agent knows the action but needs authorization. | Confirmation/actionable message lifecycle. | Authorization gates one known action; it is not a missing-information question. | Confirmation card/action surface and confirmation history. |
| Message | User-visible process history or communication. | MessageStream. | Does not by itself own execution control state. | Session/task message stream. |

MessageStream may record history for all three mechanisms, but MessageStream is
not the state authority for interrupt, ASK, or confirmation.

ASK and confirmation may reuse frontend primitives such as option groups,
buttons, pending states, and validation copy. They must not collapse into one
backend lifecycle.

---

## Product 1.0 Sequencing

The implementation order is:

1. Cooperative task interruption.
2. Message, ASK, and confirmation UI integration planning.
3. Confirmation UI hardening on existing confirmation/actionable facts.
4. Durable ASK backend/runtime and ASK Dock frontend slices.

Rationale:

- interruption has an accepted feature plan and technical design;
- interruption can close a useful control loop without adding `waiting_for_user`
  or a durable ASK store;
- ASK needs a larger backend/frontend contract: `ask_user` tool, durable
  request/answer records, answer commands, resume behavior, and restart
  recovery;
- confirmation already exists as an authorization lifecycle and should be
  hardened without becoming the ASK mechanism.

This ADR is docs-only alignment. It does not implement interruption, ASK,
confirmation UI, or MessageStream changes.

---

## Consequences

Positive:

- keeps Product 1.0 interruption small and honest;
- avoids adding `waiting_for_user` as a prerequisite for stop/cancel;
- preserves separate audit explanations for stop requests, missing
  information, and authorization;
- lets the ASK plan use the interruption safe-point and Context Manager delta
  work later without blocking the interruption slice.

Trade-offs:

- frontend may need similar controls in separate components before shared UI
  primitives are extracted;
- Message, ASK, and confirmation integration still needs a full feature plan
  before implementation;
- some user-facing copy must be precise so "stop", "answer", and "approve" are
  not confused.

Non-goals:

- no hard cancellation;
- no Product 1.0 `paused` or `cancelled` PublishedTask status;
- no durable ASK store in the interruption slice;
- no generic interaction-control state machine;
- no merger of ASK and confirmation semantics.
