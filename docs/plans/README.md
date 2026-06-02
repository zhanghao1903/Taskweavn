# Plans

> Status: active planning entry
> Last Updated: 2026-06-01

Plans are executable work packages for selected gaps. They should contain
enough context, scope, APIs, slices, and acceptance criteria for another session
to execute without reopening major design questions.

Plans are not the global product structure. Global structure lives in roadmap,
architecture, product docs, and the gap registry.

---

## 1. Categories

| Directory / File | Purpose |
|---|---|
| [feature/](feature/) | Feature and system capability plans. |
| [ui/](ui/) | UI page, interaction, and frontend implementation plans. Some early files are concept seeds; check status headers. |
| [maintainability/](maintainability/) | Maintenance, refactor, large-file split, and architecture hygiene plans. |
| [configuration.md](configuration.md) | Configuration system plan. |
| [observability.md](observability.md) | Trace / metrics / debug observability plan. |
| [cost-quota.md](cost-quota.md) | Cost and quota plan. |
| [task-first-ui-interaction.md](task-first-ui-interaction.md) | Early Task-first UI concept seed. |
| [ux-interaction.md](ux-interaction.md) | HITL / autonomy UX plan. |
| [walkthrough.md](walkthrough.md) | End-to-end walkthrough plan. |
| [user-guide.md](user-guide.md) | User guide plan. |

---

## 2. When To Create A Plan

Create or update a plan when a gap is selected for execution and at least one
of these is true:

1. implementation crosses frontend/backend, storage, protocol, or agent boundaries;
2. detailed technical design is needed before code;
3. multiple implementation sessions or branches will share the work;
4. the work changes an architecture boundary or requires an ADR;
5. acceptance criteria cannot fit in a short issue.

Do not create plans for every known gap. Use [Gap Registry](../gaps/) to track
unplanned gaps until they become near-term work.

---

## 3. Required Plan Header

Each plan should start with:

```md
# <Plan Title>

> Status: planned | in_progress | done | blocked | superseded
> Last Updated: YYYY-MM-DD
> Gap: <link to docs/gaps/README.md row or section>
> Architecture: <links to architecture facts>
> Product: <links to product docs, if user-facing>
> Release Record: <link when done>
```

---

## 4. Required Sections

Use only the sections that fit the work, but substantial plans should cover:

```md
## 1. Problem / Gap
## 2. Architecture References Reviewed
## 3. Scope
## 4. Non-goals
## 5. Proposed Design
## 6. Implementation Slices
## 7. Frontend Work
## 8. Backend Work
## 9. Contract / API Changes
## 10. Tests And Validation
## 11. Acceptance Criteria
## 12. Completion Updates
```

For docs-only planning work, replace implementation sections with document
deliverables and review criteria.

---

## 5. Completion Rule

When a plan is completed:

1. mark the plan `done`;
2. update the related row in [Gap Registry](../gaps/);
3. update architecture docs if facts or boundaries changed;
4. update product docs if user-facing behavior changed;
5. add or update an ADR if a durable decision was made;
6. add a release record under [releases/](../releases/);
7. update roadmap only if priority, sequencing, or phase baseline changed.
