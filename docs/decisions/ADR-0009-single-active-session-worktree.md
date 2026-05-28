# ADR-0009: Single Active Session Work Tree

> Status: accepted
> Date: 2026-05-28
> Related: [Workflow, Session, And Task UX Model](../product/workflow-session-task-ux-model.md), [Authoring Domain](../architecture/authoring-domain.md), [Task Domain/UI Model Separation](../architecture/task-domain-ui-model-separation.md), [Plato UI API Contract](../product/plato-ui-api-contract.md), [ADR-0008](ADR-0008-authoring-domain-execution-boundary.md)

---

## Context

The product originally left room for a Session to contain a forest of draft or
published work trees. That model is too expensive for the current product
surface:

- the user-facing product is a personal workbench, not a team orchestration
  console;
- most LLM-generated task plans are naturally linear or lightly hierarchical;
- real usage often advances one current step at a time;
- multiple active trees inside one Session make draft persistence, publish
  identity, task selection, audit entry, and recovery behavior harder to
  explain and test;
- multi-agent execution remains useful, but it should not force the user model
  to expose parallel orchestration as the default workflow.

The current architecture already separates Authoring Domain objects from
Execution TaskBus. However, it does not yet state a product-level rule for how
many active RawTask, DraftTaskTree, or published work-tree projections may be
effective in one Session.

This ambiguity also affects recovery after restart. If RawTask and DraftTaskTree
are not durable, a user can lose unpublished work after the system restarts.
That breaks the expected behavior that a Session can be resumed into the last
meaningful work state.

---

## Decision

Adopt a **single active work tree per Session** rule for the MVP product model.

For one Session:

- there is at most one active user intent represented by the current RawTask;
- there is at most one active DraftTaskTree before publication;
- there is at most one effective published work-tree projection after
  publication;
- the Main Page presents that active tree as the primary control surface;
- additional historical or abandoned authoring attempts may exist as internal
  trace data, but they are not competing active trees in the product UI.

The Session remains the user-facing work boundary:

```text
Project
  -> Workflow
      -> Session
          -> active RawTask
          -> active DraftTaskTree before publish
          -> active work-tree projection after publish
```

Multi-agent or parallel execution is preserved as an internal execution
capability. It should degrade cleanly to a single ordered execution stream in
the product UI. The default user-facing workflow is:

```text
understand goal
  -> produce one draft task tree
  -> user reviews or edits
  -> publish
  -> execute current ordered work
  -> ask confirmation when needed
  -> continue or recover
```

RawTask and DraftTaskTree must be durable enough that a restarted system can
resume the active Session without losing the user's current draft plan.

`TaskTreeView` remains a UI projection. Commands that need domain identity must
use, or be resolved by the gateway to, real domain ids such as `draft_tree_id` or
`TaskRef`. A synthetic projection id must not be treated as a domain primary
key.

---

## Consequences

Positive:

- The user model is simpler: one Session shows one current plan and one current
  execution surface.
- Main Page, Audit Page, route state, and selected task behavior become easier
  to reason about.
- Restart recovery has a clear target: restore the active Session, active
  RawTask, active DraftTaskTree, or active published work-tree projection.
- Existing multi-agent architecture can remain, but the MVP does not need to
  expose parallel orchestration controls.
- Publish command identity becomes easier to validate because there is one
  active draft tree per Session.

Trade-offs:

- The product no longer treats a Session as a first-class forest manager.
- Experiments with alternative draft trees must be represented as replacement,
  regeneration, abandoned trace, or a new Session, not multiple active trees.
- Advanced parallel scheduling is hidden behind the ordered work surface.
- Some existing store APIs such as `list_trees(session_id)` may still exist, but
  MVP product logic must select or enforce one active tree.

Required follow-up:

- Persist active RawTask and DraftTaskTree state.
- Clarify or fix publish command identity so publish uses the active real
  DraftTaskTree id, not a synthetic `TaskTreeView.id`.
- Make the UI/API contract explicit about active authoring state.
- Ensure snapshot assembly returns the active tree consistently after restart.

---

## Post-Publish Editing Direction

Post-publish editing is intentionally not fully specified in this ADR.

The direction is:

- completed execution facts, confirmations, file changes, and audit records
  should remain traceable;
- not-started or queued work may be editable through controlled commands;
- running work should prefer guidance or revision-request commands instead of
  direct mutation;
- completed work should be read-only except for follow-up or retry flows;
- any broader edit policy must be specified separately before implementation.

This keeps the current ADR focused on the Session/work-tree cardinality and
authoring persistence decision.

---

## Rejected Alternatives

| Alternative | Reason Rejected |
|---|---|
| Allow multiple active draft trees in one Session | Creates forest management in the primary UI and complicates publish, recovery, and audit semantics. |
| Expose multi-agent parallelism as the default work model | Does not match the dominant linear user workflow and increases product complexity before there is demand. |
| Treat RawTask and DraftTaskTree as transient only | Loses user work after restart and makes unpublished sessions unreliable. |
| Introduce a new full WorkTree domain now | Too large for the current convergence phase; existing Authoring Domain, TaskPublisher, TaskBus, and projection boundaries can carry the MVP. |

---

## Implementation Guidance

Do next:

1. Update product/API docs to state the single active Session work-tree rule.
2. Add or harden persistence for active RawTask and DraftTaskTree.
3. Align publish route/gateway behavior with real draft tree identity.
4. Keep Main Page UI focused on the single active tree.
5. Keep multi-agent scheduling internal unless a future product requirement
   explicitly needs user-facing parallel controls.

Do not do yet:

- do not build a multi-tree Session UI;
- do not implement full post-publish editing semantics in this ADR;
- do not rewrite the execution domain;
- do not expose agent orchestration controls as MVP workflow features.
