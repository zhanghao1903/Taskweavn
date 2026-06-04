# ADR-0015: Main Page Activity Overlay For Message History

> Status: accepted
> Date: 2026-06-05
> Related: [Main Page Visual Direction Summary](../design/main-page-visual-direction-summary.zh-CN.md), [Main Page Visual Direction Decision](../design/main-page-visual-direction-decision.md), [Main Screen States Visual Simplification Brief](../design/main-screen-states-visual-simplification-brief.md), [Main Screen States Recomposition Checklist](../design/main-screen-states-recomposition-checklist.md), [Current UI Review 2026-06-04](../design/main-screen-states-current-ui-review-2026-06-04.md), [Main Page UX Flow](../product/plato-main-page-ux-flow.md), [Interaction Control Taxonomy](ADR-0014-interaction-control-taxonomy-for-product-1-0.md)

---

## Context

The current Plato Main Page workbench has TaskTree, DetailPanel, InputDock, and
a persistent `Session messages` / `MessageStream` panel.

The persistent message panel creates two product problems:

- it competes visually with TaskTree even when it only contains process
  evidence;
- long messages and long TaskTree content can create multiple adjacent scroll
  areas, making the workbench feel noisy and hard to scan.

The page is task-first. Users should first understand:

```text
current task structure
  -> current required action
  -> result and changed files
  -> reviewable evidence
```

Message history remains important, but it is evidence and review context. It is
not the primary work surface and does not own execution control state. This is
consistent with ADR-0014: MessageStream may record communication/history, but
ASK, confirmation, interruption, and execution state have their own authority.

The product also needs a clean way to expose long result content, especially
`Result Summary`, without turning the UI back into a chat transcript.

---

## Decision

Plato Main Page will replace the default persistent message column with:

```text
Latest Activity strip
  -> Activity Overlay
  -> Result Artifact/Reader for long results
```

### 1. Default Workbench

The default Main Page layout does not include a persistent `Session messages` /
`MessageStream` peer column.

The default workbench keeps:

- TaskTree as the primary control object;
- DetailPanel as the selected-object and next-action surface;
- InputDock as the scoped command surface;
- Audit as a trust entry, not a default detail surface.

### 2. Latest Activity

Workspace may show one subtle, one-line Latest Activity strip.

Rules:

- show only the latest important productized update;
- do not show raw message body text;
- do not scroll or expand inline;
- hide the strip when there is no meaningful update;
- provide a compact `Activity` / `动态` entry point with count when useful.

Example:

```text
刚刚 · 结果摘要已生成 · 发现 3 个问题 · 查看
```

### 3. Activity Overlay

Clicking `Activity` / `动态` opens an independent Activity Overlay.

Rules:

- the overlay covers the DetailPanel region;
- it does not reuse DetailPanel as its component or information architecture;
- it does not leave DetailPanel half-visible as a stable state;
- TaskTree may remain visible behind or beside the overlay so task context is
  not lost;
- closing the overlay restores the previous selected TaskNode and DetailPanel
  state;
- the overlay is the only scrollable activity-history surface when open.

Minimum filters:

```text
Current task / All / Results / Errors
```

Optional filters:

```text
Needs confirmation / Tool records / Audit
```

### 4. Long Results

Long `Result Summary` content does not expand inside the activity timeline.

Activity shows a compact result entry:

```text
Result summary generated
View full result
```

Opening it displays a Result Artifact/Reader inside the overlay or a widened
reader state. The reader is a result-document surface, not a third-level
message list.

### 5. Routing Rules

Use this routing model:

| Content type | Primary surface |
|---|---|
| Ordinary progress | Latest Activity + Activity Overlay |
| Required confirmation | DetailPanel |
| Recoverable error | Inline near the affected control + Activity Overlay |
| Long Result Summary | Result Artifact/Reader |
| File changes | DetailPanel file summary + Audit entry |
| Raw tool/audit logs | Audit |

Summary:

```text
short messages become activity
long content becomes results
actions stay in DetailPanel
raw evidence stays in Audit
```

---

## Rejected Alternatives

### Keep MessageStream As A Persistent Peer Column

Rejected because it preserves the visual competition with TaskTree and keeps
the double-scroll problem.

### Collapse MessageStream Into A Narrow Rail

Rejected as the default model because it still reserves permanent layout space
for evidence and creates another surface that must be maintained at every
responsive breakpoint.

### Use Toasts Only

Rejected because toasts are transient and lossy. Users need a durable place to
review what happened.

### Reuse DetailPanel For Activity

Rejected because DetailPanel owns the selected object and next action.
Activity owns reviewable evidence. Reusing the same panel would blur the user's
mental model and complicate confirmation/result states.

### Leave DetailPanel Half-Visible Under The Overlay

Rejected as a stable state because the visible half has little interaction
value and makes the UI look unresolved. Covering DetailPanel is clearer and
easier to tune.

---

## Consequences

Positive:

- TaskTree remains the primary visual object.
- Main Page has fewer permanent columns and fewer adjacent scroll areas.
- Message history remains durable and filterable.
- Long results become readable artifacts instead of oversized chat bubbles.
- DetailPanel keeps a clean action/decision role.
- The overlay model is easier to adjust across desktop, wide desktop, and
  mobile because it does not reflow the whole workbench.

Trade-offs:

- Users must open Activity to inspect full message history.
- Latest Activity copy must be productized; raw backend/message text is not
  acceptable.
- Overlay state needs focus, close, keyboard, and scroll behavior.
- Frontend needs a separate Activity component instead of reusing DetailPanel.

Non-goals:

- no backend MessageStream lifecycle change;
- no change to ASK, confirmation, interruption, or audit authority;
- no Figma write in this ADR;
- no frontend implementation in this ADR;
- no guarantee that all tool records appear in Activity by default.

---

## Implementation Guidance

Future frontend work should introduce or adapt these UI concepts:

- `LatestActivityStrip`;
- `ActivityEntryButton`;
- `ActivityOverlay`;
- `ActivityFilterTabs`;
- `ActivityTimeline`;
- `ResultArtifactReader`.

Implementation should preserve these invariants:

- default workbench has no persistent message peer column;
- overlay open/close does not change selected TaskNode;
- overlay covers DetailPanel rather than pushing the main grid;
- long Result Summary opens in a reader state;
- required user actions remain in DetailPanel;
- raw ids, audit payloads, and tool traces stay hidden by default.

Visual QA must include:

- default desktop state with overlay closed;
- overlay open over DetailPanel;
- long Result Summary reader state;
- 1280px desktop no-clipping check;
- at least one running/progress state and one completed/result state.

---

## Related Documents

- [Main Page Visual Direction Summary](../design/main-page-visual-direction-summary.zh-CN.md)
- [Main Page Visual Direction Decision](../design/main-page-visual-direction-decision.md)
- [Main Screen States Visual Simplification Brief](../design/main-screen-states-visual-simplification-brief.md)
- [Main Screen States Recomposition Checklist](../design/main-screen-states-recomposition-checklist.md)
- [Current UI Review 2026-06-04](../design/main-screen-states-current-ui-review-2026-06-04.md)
- [ADR-0014: Interaction Control Taxonomy For Product 1.0](ADR-0014-interaction-control-taxonomy-for-product-1-0.md)
