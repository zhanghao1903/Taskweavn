# Feature Plan: Contract Revision Command Skills

> Status: planned
>
> Last Updated: 2026-06-13
>
> Owner: Product / Backend Commands / Authoring Domain / TaskBus
>
> Related:
> [Contract Revision And Execution Loops](../../architecture/contract-revision-and-execution-loops.md),
> [Plato Contract Loop Product Model](../../product/plato-contract-loop-model.md),
> [Runtime Input Router Contract](runtime-input-router-contract.md),
> [Plan / TaskNode Contract Migration](plan-tasknode-contract-migration.md)

---

## 1. Gap

The Contract Revision Loop needs command-backed capabilities for user requests
that change Plato product state:

- record guidance;
- patch TaskNode properties;
- create TaskNode;
- delete TaskNode;
- create workspace-changing execution work;
- resolve ASK or confirmation through the same routed input surface.

Product 1.0 has several separate command paths, but not a unified internal
skill/capability layer for Router-dispatched contract revisions.

---

## 2. Target

Internal command skills expose reusable, auditable product-state operations:

```text
Router decides
  -> command skill validates
  -> command handler persists facts
  -> event + activity projection
```

Workspace-changing requests do not write files. They create or update
executable Plan/TaskNode contract and enter TaskBus after publication or user
confirmation.

---

## 3. First Skill Set

### CRS-1. `record_guidance`

- Scope: Session, Plan, or Task.
- Persists guidance as typed contract/context fact.
- Creates Activity item.

### CRS-2. `patch_task_node`

- Updates TaskNode title, instructions, constraints, acceptance criteria, or
  status within allowed Plan states.
- Requires version/idempotency guard.

### CRS-3. `create_task_node`

- Adds a new TaskNode to active Plan.
- Preserves stable ordering.
- May require user confirmation when Plan is running or published.

### CRS-4. `delete_task_node`

- Removes or archives a not-yet-executed TaskNode.
- Requires explicit confirmation for destructive contract changes.

### CRS-5. `create_execution_task`

- Converts a workspace-changing request into executable work.
- Does not run workspace tools directly.
- Handoff to TaskBus happens through publish/execute path.

### CRS-6. `resolve_ask` / `resolve_confirmation`

- Bridges runtime input to existing ASK and confirmation command lifecycles.
- Keeps ASK and confirmation as separate domain mechanisms.

---

## 4. Implementation Slices

### CRS-A. Command Skill Protocol

- Define internal skill interface and result shape.
- Include required audit/activity metadata.
- Distinguish read-only interpretation tools from side-effect command skills.

### CRS-B. Guidance Command

- Implement guidance persistence and projection.
- Add context inclusion rules.

### CRS-C. Plan/TaskNode Mutation Commands

- Implement patch/create/delete operations after Plan/TaskNode contract
  migration.

### CRS-D. Execution Request Handoff

- Convert workspace-changing natural-language requests into executable work.
- Keep TaskBus as the only workspace mutation authority.

### CRS-E. Tests

- Command idempotency.
- Version conflict.
- invalid state rejection.
- Activity projection.
- Audit/event projection.
- no direct workspace writes.

---

## 5. Non-Goals

- No direct file writes.
- No direct shell execution.
- No generic Router Agent with unrestricted tools.
- No public skill marketplace.
- No replacement of TaskBus.
