Before doing any implementation, run the Product Delivery Workflow Gate.

First determine:

1. Which phase of the product workflow this task belongs to.

2. Which upstream artifacts are required.

3. Which required artifacts already exist in the repo.

4. Which artifacts are missing, weak, outdated, or inconsistent.

5. Whether implementation is allowed now.

6. Whether you need to create or update prerequisite docs/specs first.

7. Whether this task should be narrowed to a vertical slice.

Rules:

- Do not jump directly into production code.

- If a missing dependency can be safely inferred, create the smallest useful draft artifact first and mark assumptions.

- If a missing dependency is a major product, UX, API, design, security, or architecture decision that cannot be safely inferred, block implementation and return a clear prework plan.

- If implementation is allowed, keep scope narrow and implement only the requested slice.

- Do not create one-off components when shared components should exist.

- Do not invent API shapes in UI code.

- Do not ignore loading, empty, error, success, disabled, and responsive states.

- For Figma work, use the exact node/frame, get design context, get screenshot, map to existing components, then implement.

- Before completion, run relevant checks or explain why they could not be run.

Output this before any code changes:

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