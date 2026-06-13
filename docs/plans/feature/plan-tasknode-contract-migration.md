# Feature Plan: Plan / TaskNode Contract Migration

> Status: planned
>
> Last Updated: 2026-06-13
>
> Owner: Product Model / Backend / Frontend
>
> Related:
> [Plan / TaskNode Technical Design](plan-tasknode-model-technical-design.zh-CN.md),
> [Plato Contract Loop Product Model](../../product/plato-contract-loop-model.md),
> [Contract Revision And Execution Loops](../../architecture/contract-revision-and-execution-loops.md)

---

## 1. Gap

Current state still centers legacy `RawTask -> DraftTaskTree -> PublishedTask`
storage and projection. Product 1.1 needs a first-class `Plan -> TaskNode[]`
contract so runtime input, activity, inquiry, outcome review, and contract
revision commands have stable targets.

Current gap:

- Plan / TaskNode technical design is still draft.
- UI API contract does not yet expose `activePlan` as canonical.
- Backend does not yet project legacy DraftTaskTree into a formal PlanView.
- Collaborator still produces legacy task tree shapes.
- Plan store / TaskNode store and Plan publishing are not implemented.

---

## 2. Target

Product 1.1 first version uses:

```text
Session
  -> active Plan
      -> flat TaskNode list
```

No parent/child TaskNode hierarchy in the first version.

Plan is the contract boundary for one round of work. TaskNode is the execution
contract item inside the Plan.

---

## 3. Implementation Slices

### PTC-1. Decision Closure

- Review and accept `plan-tasknode-model-technical-design.zh-CN.md`.
- Resolve open questions for first implementation:
  - active Plan only vs visible history;
  - deterministic Plan finalization vs reviewer/Collaborator finalization;
  - projection-only vs backfill.

Acceptance:

- technical design status is accepted;
- Product 1.1 scope remains flat `Plan -> TaskNode[]`.

### PTC-2. Contract And ViewModel Alignment

- Update UI API contract with `PlanView`, `TaskNodeCardView`, `activePlan`,
  and compatibility `taskTreeProjection`.
- Update frontend ViewModel contract.
- Define safe migration fields and legacy aliases.

Acceptance:

- API and frontend contracts can represent active Plan without removing legacy
  TaskTree support.

### PTC-3. Projection-Only Backend

- Add backend projection from existing DraftTaskTree / published task facts to
  synthetic PlanView.
- Preserve current sessions and published task display.

Acceptance:

- existing sessions load as active Plan;
- no database migration required in this slice.

### PTC-4. Plan Proposal Schema

- Add `PlanProposal` and `PlanTaskNodeProposal` models.
- Validate flat TaskNode list, stable ordering, duplicate indexes, and rejected
  hierarchy output.
- Keep legacy DraftTaskTree compatibility input.

Acceptance:

- Collaborator proposal can produce a valid PlanView-compatible contract.

### PTC-5. Durable Plan Store

- Add Plan and TaskNode stores.
- Add reopen/migration/version conflict tests.
- Keep legacy DraftTaskTree read path.

Acceptance:

- new Plans persist and reopen without breaking legacy data.

### PTC-6. Publish Plan

- Add `PublishPlanCommand`.
- Map each TaskNode to a PublishedTask.
- Keep legacy publish path.

Acceptance:

- Plan publishing preserves order and task identity.

---

## 4. Non-Goals

- No parent/child TaskNode hierarchy.
- No multi-active Plan.
- No full Plan history UI in the first implementation.
- No hidden parent TaskNode for finalization.
- No broad Agent assignment changes.

---

## 5. Dependencies

This plan should land before:

- Runtime Input Router;
- Contract Revision Command Skills;
- Outcome Review;
- Result packaging;
- advanced Session/Plan context management.
