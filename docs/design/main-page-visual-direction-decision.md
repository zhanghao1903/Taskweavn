# Main Page Visual Direction Decision

> Status: accepted direction, implementation not complete
> Decision date: 2026-06-04
> Scope: Product visual direction and interaction hierarchy for Plato Main
> Page.
> Non-goals: no frontend code, no Figma write, no API contract change, no old
> Figma frame migration.

## 1. Decision

Plato Main Page will use a `Modern Classical Workbench` visual direction.

This means:

- modern, calm, rational, and restrained;
- task-first, not chat-first;
- structured workbench, not marketing page;
- information-dense enough for real work, but not noisy;
- TaskTree is the primary control object;
- DetailPanel owns the current decision or selected object;
- MessageStream is evidence and recent process context, not the main
  experience;
- Audit is a trust entry from Main Page, not a default workflow surface.

The design goal is:

```text
Let users see the task structure, understand the next action, and trust the
result without reading repeated explanations or internal system detail.
```

## 2. Why This Direction

Plato is not trying to feel magical, autonomous, or decorative. Its product
value is legibility:

```text
unclear user intent
  -> visible TaskTree
  -> scoped guidance and confirmation
  -> controlled execution
  -> reviewable result and audit trail
```

The page should therefore feel like a reliable control surface for structured
work, not a chatbot timeline or a traditional task manager.

## 3. Rejected Directions

The following directions are explicitly rejected for Main Page:

| Rejected direction | Reason |
|---|---|
| Chat-first AI assistant | Hides task structure and makes work feel linear instead of controllable. |
| Todo/task-manager UI | Undersells confirmation, execution, result, file, and audit semantics. |
| IDE/terminal UI | Over-indexes on developer mental models and raw system detail. |
| Marketing/landing-page composition | Makes the app feel explanatory rather than operational. |
| Cyber/neon/magical AI visual style | Conflicts with calm trust and legibility. |
| Ancient Greek decorative theme | Turns Plato into surface metaphor instead of usable workbench. |
| Heavy glassmorphism or large-radius card UI | Adds visual noise and weakens the precise workbench tone. |

## 4. Surface Ownership

Each surface has a single owner role.

| Surface | Owns | Does not own |
|---|---|---|
| TopBar | Product identity, route context, one primary state, optional live/stale indicator | dev state picker, product education, repeated workflow copy |
| Sidebar | Workflow/session navigation | task status, audit evidence, onboarding |
| Workspace header | session title and primary command | broad explanation repeated elsewhere |
| TaskTree | structure, selection, readiness, execution, task-level status | long explanations, raw logs, audit evidence |
| MessageStream | evidence, recent process updates, task-related updates | primary action, repeated state summaries |
| DetailPanel | selected object, next action, confirmation, result, file summary | generic duplicated state notes |
| InputDock | command mode, target scope, disabled/read-only reason | long help text, contradictory placeholders |
| Audit entry | verification path | default detail dump or workflow instruction |

If a piece of content does not fit the owner role of its surface, it should be
moved, hidden, or removed.

## 5. Visual Hierarchy

The accepted hierarchy is:

```text
1. Active TaskTree / selected TaskNode
2. Required user action: confirm, publish, retry, resync, or scoped input
3. Result and file review after execution
4. Message evidence
5. Audit and log detail
```

Consequences:

- MessageStream may never visually dominate TaskTree.
- DetailPanel may visually dominate only when a decision is required.
- Result/File/Audit must be a review path, not three competing panels.
- Empty, loading, stale, permission, and error states should each have one
  primary explanation.

## 6. Style Contract

Use the existing Plato token direction:

- palette: reason blue, clear blue, wisdom gold, success green, danger red,
  warm neutral surface, graphite/ink text;
- typography: compact readable UI type, no hero-scale panel text;
- radius: 8px or below for cards and panels;
- borders: fine, low-contrast dividers;
- shadows: subtle and functional only;
- motion: light and state-oriented;
- no decorative gradients, orbs, bokeh, or persistent philosophical motifs.

Style should make the interface feel precise and usable, not ornamental.

## 7. Copy Contract

Main Page copy must answer one of these questions:

- Where am I?
- What is happening?
- What needs my decision?
- What can I change?
- What was produced?
- What changed?
- Where can I verify it?

If copy does not answer one of those questions, remove it from Main Page.

Default copy changes now accepted:

| Existing tendency | Direction |
|---|---|
| `Task-scoped projection` | `Related updates`, `This task`, or equivalent user-facing language |
| `Full session stream` | `Session updates` |
| `State note` that repeats header/body | remove |
| `Owner TaskNode: task-...` | hide by default; expose in audit or expanded detail |
| completed-state edit placeholder | use read-only or follow-up language only when command mode supports it |

## 8. Responsive Decision

Wide desktop keeps the full workbench.

At constrained widths, collapse in this order:

```text
MessageStream
  -> secondary metadata
  -> sidebar density
```

Do not clip these before MessageStream is demoted:

- TaskTree;
- DetailPanel next action;
- InputDock;
- TopBar route/status context.

The 1280px desktop review target is mandatory. A page that requires 1360px to
avoid clipping is not visually accepted.

## 9. P0 Gates Before Visual Acceptance

The current runtime review on 2026-06-04 identified these P0 gates:

| Gate | Required outcome |
|---|---|
| Production state picker | Hidden from production/Figma-ready screen states or moved outside product shell. |
| Raw TaskNode owner ids | Removed from default file summary; moved to audit or expanded detail. |
| Constrained-width layout | 1280px desktop has no primary content clipping. |

These must be addressed before the Main Page can be called visually simplified.

## 10. P1 Gates Before Polish

These must be addressed before spending time on fine visual polish:

| Gate | Required outcome |
|---|---|
| Duplicate `State note` in S1/S3 | Removed or replaced with one concrete next-step sentence. |
| MessageStream visual weight | Demoted to evidence/recent updates, not a peer to TaskTree. |
| Brand tagline in dense shell | Removed or demoted in normal app states. |
| Confirmation copy repetition | Reduced to action + impact + options. |
| File summary density | Paths and change types stay visible; lineage metadata moves behind expansion/audit. |

## 11. Acceptance Checklist

A future Figma or frontend pass is accepted only if:

- TaskTree is the primary visual object whenever it exists;
- user-required action is immediately visible and scoped;
- InputDock target matches selected object and permissions;
- MessageStream is visibly subordinate;
- TopBar has route context and no visible dev state picker;
- S1/S3 do not repeat empty or draft explanations across surfaces;
- S7 has one clear primary confirmation action;
- S8/S9 show result/file/audit as a single review path;
- raw ids and audit evidence are hidden by default;
- 1280px desktop has no primary content clipping;
- the page still feels calm, precise, and work-oriented.

## 12. Source Documents

This decision is grounded in:

- `docs/product/plato-design-philosophy-style-guide.md`
- `docs/product/plato-main-page-ux-flow.md`
- `docs/design/design-system.md`
- `docs/design/main-screen-states-visual-simplification-brief.md`
- `docs/design/main-screen-states-recomposition-checklist.md`
- `docs/design/main-screen-states-current-ui-review-2026-06-04.md`

## 13. Current Completion Status

Direction is accepted.

Implementation is not complete.

The current runtime remains below visual acceptance until the P0 and P1 gates
above are resolved and verified against the acceptance checklist.
