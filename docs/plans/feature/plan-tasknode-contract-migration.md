# Feature Plan: Plan / TaskNode Contract Migration

> Status: in_progress
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

- Plan / TaskNode technical design is accepted.
- UI API contract now exposes `activePlan` and compatibility
  `taskTreeProjection`.
- Backend UI contract can derive a synthetic `PlanView` from the existing
  `taskTree` compatibility projection.
- Backend now has an explicit projection-only service from legacy TaskTree
  projection to synthetic `PlanView`.
- Collaborator still produces legacy task tree shapes.
- Plan proposal schema exists and validates Product 1.1 flat TaskNode
  proposals before converting them into the legacy DraftTaskTree compatibility
  path.
- Durable Plan / TaskNode store interfaces and SQLite implementation now exist.
- Backend Plan publishing adapter now exists and preserves legacy
  DraftTaskTree publish compatibility.
- UI/API publish gateway wiring now routes active durable Plans through
  `DefaultPlanPublisher` and falls back to legacy DraftTaskTree publish for old
  sessions. Read/query paths still use legacy projection compatibility.

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

Status: complete.

- Review and accept `plan-tasknode-model-technical-design.zh-CN.md`.
- Resolve open questions for first implementation:
  - active Plan only vs visible history;
  - deterministic Plan finalization vs reviewer/Collaborator finalization;
  - projection-only vs backfill.

Acceptance:

- technical design status is accepted;
- Product 1.1 scope remains flat `Plan -> TaskNode[]`.

### PTC-2. Contract And ViewModel Alignment

Status: complete for additive contract alignment.

- Update UI API contract with `PlanView`, `TaskNodeCardView`, `activePlan`,
  and compatibility `taskTreeProjection`.
- Update frontend ViewModel contract.
- Define safe migration fields and legacy aliases.

Acceptance:

- API and frontend contracts can represent active Plan without removing legacy
  TaskTree support.

Notes:

- `taskTree` remains the legacy field used by existing Main Page components.
- `activePlan` is the canonical Product 1.1 field for new Router, Activity, and
  command-skill work.
- `activePlan.taskTreeProjection` preserves the legacy TaskTree projection
  during migration.

### PTC-3. Projection-Only Backend

Status: complete for legacy TaskTree projection.

- Add backend projection from existing DraftTaskTree / published task facts to
  synthetic PlanView.
- Preserve current sessions and published task display.

Acceptance:

- existing sessions load as active Plan;
- no database migration required in this slice.

Notes:

- `DefaultPlanProjectionService` projects current legacy `TaskTreeView` into
  `PlanView`.
- `PlanView.taskNodes` is flattened for Product 1.1 semantics.
- `PlanView.taskTreeProjection` preserves the legacy TaskTree compatibility
  shape for existing Main Page components.
- Durable Plan storage and Collaborator Plan proposal output remain later
  slices.

### PTC-4. Plan Proposal Schema

Status: complete for schema validation and legacy compatibility input.

- Add `PlanProposal` and `PlanTaskNodeProposal` models.
- Validate flat TaskNode list, stable ordering, duplicate indexes, and rejected
  hierarchy output.
- Keep legacy DraftTaskTree compatibility input.

Acceptance:

- Collaborator proposal can produce a valid PlanView-compatible contract.

Notes:

- New Plan proposals reject hierarchy fields such as `children`,
  `parent_client_task_id`, `node_type`, `execution_role`, and
  `children_policy`.
- `depends_on` may reference proposal-local `client_task_id` or `task_index`
  strings and is rejected when unknown, self-referential, or cyclic.
- Existing legacy `DraftTaskTreeProposal` input remains accepted and is
  flattened before entering the current DraftTaskTree authoring store.

### PTC-5. Durable Plan Store

Status: complete for durable store foundation.

- Add Plan and TaskNode stores.
- Add reopen/migration/version conflict tests.
- Keep legacy DraftTaskTree read path.

Acceptance:

- new Plans persist and reopen without breaking legacy data.

Notes:

- Added storage-facing `Plan` and `PlanTaskNode` domain models.
- Added `PlanStore` / `PlanTaskNodeStore` protocols and
  `SqlitePlanStore`.
- SQLite tables are additive inside `authoring.sqlite`:
  `plans`, `plan_task_nodes`, and `plan_schema_meta`.
- Legacy `DraftTaskTree` tables and `SqliteDraftTaskStore` reads remain
  unchanged and are covered by same-database compatibility tests.
- PTC-5 does not migrate `authoring_active_sessions.active_plan_id` and does
  not switch UI gateways to stored Plan reads. The legacy `DraftTaskTree`
  projection remains the current read path until the next migration slice.

### PTC-6. Publish Plan

Status: complete for backend Plan publish adapter and command gateway wiring.

- Add `PublishPlanCommand`.
- Map each TaskNode to a PublishedTask.
- Route UI publish commands through `DefaultPlanPublisher` when a durable active
  Plan exists.
- Keep legacy DraftTaskTree publish fallback for old sessions.

Acceptance:

- Plan publishing preserves order and task identity.

Notes:

- Added `PublishPlanCommand`, `PublishPlanResult`, `PlanTaskPublishMapping`,
  and `DefaultPlanPublisher`.
- `DefaultPlanPublisher` adapts durable Plan / TaskNode rows to the existing
  `TaskPublisher` / `PublishRequest` boundary instead of replacing legacy
  publish logic.
- Each flat TaskNode publishes as a root `PublishedTask` in deterministic
  `order_index` order. The resulting `published_ref`, readiness, and execution
  state are written back to the TaskNode rows.
- Existing full-lineage publish calls replay without creating duplicate
  TaskBus rows. Partial lineage is rejected as unsafe.
- Legacy `PublishDraftTaskTreeCommand` and `publish_draft_tree` remain
  compatible.
- `DefaultUiCommandGateway.publish_task_tree` now checks the workspace
  `PlanStore.get_active_plan(session_id)` first. If a durable active Plan
  exists, the gateway publishes it and returns the same `CommandResponse`
  shape with `publishedTaskIds`; otherwise it uses the previous legacy
  DraftTaskTree path unchanged.
- Main Page sidecar runtime now wires `SqlitePlanStore` and
  `DefaultPlanPublisher` per workspace.

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
