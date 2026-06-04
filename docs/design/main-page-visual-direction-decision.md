# Main Page Visual Direction Decision

> Status: accepted direction, implementation not complete
> Decision date: 2026-06-04
> Activity decision update: 2026-06-05
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
- the persistent MessageStream column is not part of the accepted default Main
  Page layout;
- process messages are represented by a one-line Latest Activity strip and an
  on-demand Activity Overlay;
- long result messages become Result Artifacts/Readers, not expanded chat
  messages;
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
| Latest Activity | one productized latest important update | raw message body, long content, scrollable history |
| Activity Overlay | message history, task/session filters, result links | default persistent column, primary action, half-visible DetailPanel compromise |
| DetailPanel | selected object, next action, confirmation, result, file summary | generic duplicated state notes |
| Result Artifact/Reader | long result summaries and structured output | routine progress messages or audit logs |
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
4. Latest Activity and reviewable Activity Overlay evidence
5. Audit and log detail
```

Consequences:

- A persistent MessageStream column may never visually dominate TaskTree
  because it should not be present in the default layout.
- DetailPanel may visually dominate only when a decision is required.
- Result/File/Audit must be a review path, not three competing panels.
- Empty, loading, stale, permission, and error states should each have one
  primary explanation.

## 6. Activity And Long Result Decision

The accepted message model is:

```text
Latest Activity strip
  -> Activity Overlay
  -> Result Artifact/Reader for long results
```

Implementation rules:

- Default Main Page removes the persistent `Session messages` /
  `MessageStream` column.
- Workspace may show one subtle, one-line Latest Activity strip.
- The strip shows a productized update, not the raw last message.
- `Activity` / `动态` opens an independent overlay above the workbench.
- The overlay covers the DetailPanel region; it does not reuse DetailPanel and
  does not leave DetailPanel half-visible as a stable state.
- Closing the overlay returns to the previous DetailPanel state and selected
  TaskNode.
- The overlay supports at least `Current task`, `All`, `Results`, and `Errors`
  filters.
- Long `Result Summary` content opens as a Result Artifact/Reader inside the
  overlay or a widened reader state.
- Actionable confirmations are promoted to DetailPanel, not hidden in
  Activity.
- Raw tool and audit logs remain in Audit unless explicitly needed as compact
  evidence.

## 7. Style Contract

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

## 8. Copy Contract

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
| `Full session stream` | `Activity`, `Updates`, or `Session updates` inside the overlay |
| `Session messages` column | remove from default layout; replace with Latest Activity + Activity Overlay |
| `State note` that repeats header/body | remove |
| `Owner TaskNode: task-...` | hide by default; expose in audit or expanded detail |
| completed-state edit placeholder | use read-only or follow-up language only when command mode supports it |

## 9. Responsive Decision

Wide desktop keeps the workbench, but not a persistent message column.

At constrained widths, collapse in this order:

```text
Activity Overlay closed by default
  -> secondary metadata
  -> sidebar density
```

Do not clip these:

- TaskTree;
- DetailPanel next action;
- InputDock;
- TopBar route/status context.

The 1280px desktop review target is mandatory. A page that requires 1360px to
avoid clipping is not visually accepted.

## 10. P0 Gates Before Visual Acceptance

The current runtime review on 2026-06-04 identified these P0 gates:

| Gate | Required outcome |
|---|---|
| Production state picker | Hidden from production/Figma-ready screen states or moved outside product shell. |
| Raw TaskNode owner ids | Removed from default file summary; moved to audit or expanded detail. |
| Constrained-width layout | 1280px desktop has no primary content clipping. |
| Persistent MessageStream column | Removed from default Main Page and replaced with Latest Activity + Activity Overlay. |

These must be addressed before the Main Page can be called visually simplified.

## 11. P1 Gates Before Polish

These must be addressed before spending time on fine visual polish:

| Gate | Required outcome |
|---|---|
| Duplicate `State note` in S1/S3 | Removed or replaced with one concrete next-step sentence. |
| Activity Overlay behavior | Filtering, close behavior, and long-result reader state are specified and visually checked. |
| Brand tagline in dense shell | Removed or demoted in normal app states. |
| Confirmation copy repetition | Reduced to action + impact + options. |
| File summary density | Paths and change types stay visible; lineage metadata moves behind expansion/audit. |

## 12. Acceptance Checklist

A future Figma or frontend pass is accepted only if:

- TaskTree is the primary visual object whenever it exists;
- user-required action is immediately visible and scoped;
- InputDock target matches selected object and permissions;
- no persistent MessageStream/Session messages column appears in the default
  workbench;
- Latest Activity is one line and non-scrolling;
- Activity Overlay opens above DetailPanel, not as a peer column;
- long Result Summary opens as a Result Artifact/Reader;
- TopBar has route context and no visible dev state picker;
- S1/S3 do not repeat empty or draft explanations across surfaces;
- S7 has one clear primary confirmation action;
- S8/S9 show result/file/audit as a single review path;
- raw ids and audit evidence are hidden by default;
- 1280px desktop has no primary content clipping;
- the page still feels calm, precise, and work-oriented.

## 13. Source Documents

This decision is grounded in:

- `docs/product/plato-design-philosophy-style-guide.md`
- `docs/product/plato-main-page-ux-flow.md`
- `docs/design/design-system.md`
- `docs/design/main-screen-states-visual-simplification-brief.md`
- `docs/design/main-screen-states-recomposition-checklist.md`
- `docs/design/main-screen-states-current-ui-review-2026-06-04.md`

## 14. Current Completion Status

Direction is accepted.

Implementation is not complete.

The current runtime remains below visual acceptance until the P0 and P1 gates
above are resolved and verified against the acceptance checklist.
