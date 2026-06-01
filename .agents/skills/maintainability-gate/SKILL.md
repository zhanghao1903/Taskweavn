---
name: maintainability-gate
description: Use before Taskweavn maintenance, refactor, architecture hygiene, large-file review, module boundary cleanup, test-only restructuring, or any implementation that touches files with high complexity. Produces a Maintainability Gate Report and decides whether to refactor first, proceed narrowly, or block broad changes.
---

# Maintainability Gate Skill

Use this skill after `product-workflow-gate` whenever the task is about
maintenance, refactoring, architecture hygiene, large files, module boundaries,
test structure, or cumulative code health.

Also use it before adding non-trivial behavior to a file that is already large
or carries multiple responsibilities.

## Gate Report

Before editing code for a maintenance-sensitive task, produce:

```text
Maintainability Gate Report:
- Requested change:
- Files/modules inspected:
- Trigger:
- Current risk level:
- Responsibility count:
- Size/complexity signals:
- Coupling signals:
- Tests covering the area:
- Refactor required first: yes/no
- Allowed change type:
- Proposed slice:
- Acceptance criteria:
- Validation commands:
- Risks and assumptions:
```

## Triggers

Run this gate when any of these are true:

- User asks for refactor, cleanup, architecture hygiene, maintainability, or
  "是否合理".
- A file is over 800 lines and the task would add more production behavior.
- A file is over 1200 lines and is not generated code.
- A file is over 2000 lines, regardless of task size.
- A file mixes three or more responsibility groups:
  - public Protocol / interface definitions
  - concrete implementations
  - storage or filesystem IO
  - HTTP/transport parsing
  - projection/mapping logic
  - rendering/UI composition
  - runtime orchestration
  - sanitization/security policy
  - test fixtures or mock data
- A change crosses frontend, transport, contract, and backend assembly in one
  slice.
- A merge conflict happened in the same file repeatedly.

## Risk Levels

- `low`: under 800 lines, one clear responsibility, direct tests exist.
- `medium`: 800-1200 lines, or two responsibility groups, or weak tests.
- `high`: 1200-2000 lines, or three-plus responsibilities, or broad coupling.
- `blocked`: over 2000 lines, or adding behavior would deepen an already
  tangled boundary without a refactor plan.

Generated files, vendored code, and data snapshots can be exempt, but say so
explicitly.

## Allowed Change Types

Choose one:

- `narrow_fix`: small bug fix with tests; no broad movement.
- `zero_behavior_refactor`: move/rename/split only; public API preserved.
- `adapter_extraction`: introduce thin delegation to reduce file size.
- `boundary_redesign_plan`: docs/design only; implementation blocked until
  plan is accepted.
- `feature_after_refactor`: split first, then add behavior in a later slice.

Do not mix broad refactor and new product behavior unless the user explicitly
accepts that risk.

## Refactor Slicing Rules

Prefer small slices:

1. Extract pure helpers and tests first.
2. Extract source/provider or IO adapters next.
3. Extract transport/request parsing separately from gateway dispatch.
4. Extract UI presentational components separately from runtime hooks.
5. Keep re-export compatibility through the old module during migration.
6. Delete compatibility wrappers only after imports have moved and tests pass.

For Taskweavn UI/backend boundary files, default split targets are:

- `protocols.py` for Protocols and public gateway interfaces.
- `providers.py` for workspace/source providers.
- `query_gateway.py` for read gateway orchestration.
- `command_gateway.py` for command gateway orchestration.
- `audit_projection.py` for Audit record projection and detail assembly.
- `audit_disclosure.py` for sanitized payload and redaction policy.
- `routes.py` or `transport_routes.py` for HTTP route matching.
- React page files should compose smaller components and helpers.

## Validation Requirements

For `zero_behavior_refactor`, require at least:

- `git diff --check`
- targeted lint/typecheck for moved files
- targeted tests for all moved public behavior
- import compatibility check when public modules are re-exported

When the refactor touches UI and backend contract together, add:

- frontend targeted tests
- backend contract/transport tests
- one smoke path or build if feasible

## Current Taskweavn Hotspots

Known files that should not receive more broad behavior without this gate:

- `src/taskweavn/server/ui_contract/gateways.py`
- `frontend/src/pages/audit-page/AuditPage.tsx`
- `src/taskweavn/server/ui_http.py`
- `src/taskweavn/server/main_page.py`

Current preferred order:

1. Split `ui_contract/gateways.py`.
2. Split `ui_http.py`.
3. Split `AuditPage.tsx`.
4. Slim `main_page.py` back toward an assembly root.

## Maintenance Lessons

Append future maintenance lessons here when they are concrete and reusable.
Keep each lesson short, actionable, and tied to a trigger.

- If a file crosses 1200 lines because multiple slices kept adding small
  features, stop treating size as cosmetic; it is now a delivery-risk signal.
- If a file mixes Protocols, implementation, projection, IO, and policy, split
  by responsibility before adding another source or state.
- Broad refactors are safer after a small accepted loop exists. Do not let
  architecture cleanup outrun the verifiable product path.
- For high-risk refactors, preserve old imports with re-export wrappers first;
  remove wrappers only in a later cleanup slice.
