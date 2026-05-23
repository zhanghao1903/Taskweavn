---
name: product-workflow-gate
description: Use this skill before any product, UX, frontend, backend, API, integration, Figma, or testing task. It determines the current product delivery phase, checks upstream artifacts, detects missing dependencies, and decides whether implementation is allowed.
---

# Product Workflow Gate Skill

Before doing implementation work, always determine where the task sits in the product delivery workflow.

Canonical workflow:

P0. Repository and task intake
P1. Product Contract
P2. UX Flow and Screen State Spec
P3. Design System and Component Spec
P4. Figma static design and interactive prototype
P5. Frontend Architecture
P6. API Contract and Mock Data
P7. Vertical Slice Implementation
P8. Backend Integration
P9. QA, Visual Regression, E2E, Release Readiness
P10. Feedback and Iteration

## Required output before file edits

Workflow Gate Report:
- User request:
- Detected phase:
- Task type:
- Required upstream artifacts:
- Found artifacts:
- Missing/weak artifacts:
- Implementation allowed now: yes/no
- Prework required:
- Execution scope:
- Acceptance criteria:
- Risks/assumptions:

## Rules

- Do not jump directly into production code.
- If a missing dependency can be safely inferred, create the smallest useful draft artifact first and mark assumptions.
- If a missing dependency is a major product, UX, API, design, security, or architecture decision that cannot be safely inferred, block implementation.
- If implementation is allowed, keep scope narrow and implement only the requested vertical slice.
- Do not create one-off frontend components when shared components should exist.
- Do not invent API shapes in UI code.
- Do not ignore loading, empty, error, success, disabled, permission, and responsive states.
- For Figma tasks, require exact frame/component/variant links and map Figma elements to existing components before coding.

## Final response format

At the end, return:
- Workflow phase
- Dependency status
- What was done
- Files changed
- Tests/checks run
- Remaining gaps
- Recommended next step