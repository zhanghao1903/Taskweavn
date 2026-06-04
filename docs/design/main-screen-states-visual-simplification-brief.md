# Main Screen States Visual Simplification Brief

> Status: draft for P4 Main Page visual recomposition
> Last Updated: 2026-06-04
> Scope: Visual direction, information reduction, and state-level
> simplification rules for Plato Main Page screen states.
> Non-goals: no frontend code, no Figma write, no API contract change, no old
> Figma frame migration.

## 1. Purpose

This brief turns the current UI review into a concrete visual direction for
Main Page recomposition.

The goal is not to add more visual treatment. The goal is to make the existing
workbench easier to read:

- keep the page calm, structured, and task-first;
- remove repeated explanatory content;
- make the next user action obvious;
- keep TaskTree as the primary control object;
- make the input target explicit without over-explaining it;
- preserve Audit as a trust entry, not a main workflow surface.

Source inputs:

- `docs/product/plato-design-philosophy-style-guide.md`
- `docs/product/plato-main-page-ux-flow.md`
- `docs/design/design-system.md`
- `docs/design/visual-baseline-alignment.md`
- `docs/design/layout-components-visual-upgrade-brief.md`
- `docs/design/domain-components-visual-upgrade-brief.md`
- `docs/ux/screen-state-spec.md`
- `docs/ux/prototype-state-map.md`
- `frontend/src/pages/main-page/mainPageStateCatalog.ts`

Companion review artifact:

- `docs/design/main-screen-states-recomposition-checklist.md`

## 2. Workflow Gate Position

This is a design-planning artifact.

| Gate item | Decision |
|---|---|
| Detected phase | P4 static screen-state recomposition and P10 feedback iteration |
| Task type | Visual direction and interaction simplification |
| Frontend implementation allowed | No |
| Figma write allowed | Not by this brief alone; run Figma governance first |
| Artifact created | Current visual simplification brief |
| Required before implementation | Accepted screen-state visual direction and visual QA checklist |

This brief may guide future Figma work or frontend implementation, but it is
not itself a code or Figma handoff.

## 3. North Star

The Main Page should read as a modern rational workbench:

```text
+--------------------------------------------------------------+
| Where am I? What is the current session state?               |
+--------------------+-------------------------+---------------+
| Which session?     | What is the task plan?  | What now?     |
|                    | Which node is active?   | Why/confirm?  |
+--------------------+-------------------------+---------------+
| Applies to: current scope                         input/send |
+--------------------------------------------------------------+
```

Each region owns one job:

| Region | Owns | Must not own |
|---|---|---|
| TopBar | route context and one primary session state | product education, dev state picker, repeated workflow explanation |
| Sidebar | workflow/session navigation | task status, audit summaries, broad onboarding copy |
| Workspace header | session title and primary command | duplicate state prose |
| TaskTree | plan, hierarchy, selection, execution/readiness signals | long task explanations or raw logs |
| Message stream | process evidence and recent updates | primary decision-making or repeated state summaries |
| Detail panel | selected object, next action, confirmation/result/file summary | generic notes that duplicate header or messages |
| Input dock | input mode, target scope, disabled reason | long help text or contradictory placeholder copy |
| Audit entry | trust-plane link | routine workflow guidance |

## 4. Keep, Remove, Merge, Demote

### 4.1 Keep

- Stable workbench frame: sidebar, central task area, right context inspector,
  bottom input dock.
- TaskTree as the main visual object.
- Context-aware input scope.
- A visible but secondary Audit entry.
- Restrained blue, gold, green, red, gray, and cream status tones.
- Fine borders, low shadows, compact type, and radius no greater than 8px.

### 4.2 Remove

- Production-visible state picker controls.
- Repeated state notes when the header/body already explain the same fact.
- Generic skeleton labels such as `Default panel`, `Neutral`, `Primary`, or
  `Panel container skeleton`.
- Raw object ids in the default view, such as `Owner TaskNode: task-...`.
- Empty-state duplication where TaskTree, MessageStream, and DetailPanel all
  explain the same absence.
- Branding tagline inside the dense workbench top bar when it competes with
  route context.

### 4.3 Merge

- Result and file review into a single review flow:
  `Result summary -> changed files -> audit`.
- MessageStream and DetailPanel state explanations:
  MessageStream shows evidence; DetailPanel shows what to do.
- Multiple top-level status chips into one primary session status plus one
  optional live/stale indicator.
- Confirmation copy and task attachment copy into one concrete impact block.

### 4.4 Demote

- MessageStream becomes a supporting column or collapsible region when space is
  tight.
- Audit remains a link/card, not a full detail surface on Main Page.
- Workspace isolation appears as metadata, not as a main object.
- Agent/capability labels appear only when they help explain ownership or
  risk.

## 5. Visual Hierarchy Rules

1. The first visual weight goes to the active TaskTree or selected TaskNode.
2. The second visual weight goes to user-required action:
   confirmation, publish, retry, resync, or input.
3. The third visual weight goes to result/file review after execution.
4. Process messages should never look more important than the TaskTree.
5. Audit and logs should be discoverable but visually quiet.
6. A state should have one primary explanatory sentence, not one sentence per
   surface.
7. Selection must be visible by structure and border treatment, not color
   alone.
8. Disabled/read-only states must explain why, but only at the action surface
   where the user tries to act.

## 6. Layout And Responsive Rules

Desktop target:

- Use 1440 x 1024 as the primary design review frame.
- The page must also remain readable at 1280px width without horizontal
  clipping.
- If 1280px is tight, collapse or narrow MessageStream before clipping
  DetailPanel.
- TopBar should not require all route fields to have equal width.
- DetailPanel should scroll internally; it should not force the page wider.
- The input dock should align with the main workbench and detail region, but it
  should not look heavier than the TaskTree.

Priority at constrained width:

```text
TopBar context
  -> TaskTree
  -> DetailPanel next action
  -> Input dock
  -> MessageStream
  -> secondary metadata
```

Tablet/mobile rules remain design requirements, even if final mobile design is
deferred:

- sidebar collapses before TaskTree loses readability;
- detail becomes a secondary stacked inspector or tabbed region;
- input dock stays reachable and clearly scoped;
- no horizontal scroll for primary action paths.

## 7. Copy Rules

Use direct product language. Avoid internal model language unless the user is
already in an inspection or audit surface.

| Current tendency | Preferred direction |
|---|---|
| `Task-scoped projection` | `Related updates` or `This task` |
| `Full session stream` | `Session updates` |
| `State note` | remove or replace with a concrete next step |
| `Owner TaskNode: task-...` | hide by default; expose in audit/detail |
| `Add guidance...` in read-only state | explain read-only or offer follow-up |
| Multiple `View audit` placements | one stable audit entry per context |

Copy must answer one of these questions:

- Where am I?
- What is happening?
- What needs my decision?
- What can I change?
- What was produced?
- What changed?
- Where can I verify it?

If copy does not answer one of those questions, remove it from the Main Page.

## 8. State-Level Simplification Targets

The current frontend mock catalog uses S1-S13 labels that do not perfectly
match `docs/ux/screen-state-spec.md`. This table uses the current frontend
catalog labels for immediate review, while preserving the canonical state
separation from the UX spec.

| Frontend state | Primary focus | Simplification target |
|---|---|---|
| S1 Empty | Start a session | Show one clear input path. Keep TaskTree empty state. Demote MessageStream and DetailPanel empty explanations. |
| S2 Understanding | Make planning progress legible | Show TaskTree skeleton or progress region. Keep one recent update. Avoid "AI thinking" language. |
| S3 Draft Ready | Review task structure | Make TaskTree dominant. Publish action is primary. DetailPanel should not repeat draft-ready body copy. |
| S4 Task Selected | Narrow focus to one task | Selection, DetailPanel title, and input scope should all agree on the same task. MessageStream becomes related updates. |
| S5 Editing | Show task-scoped edit intent | Input dock and DetailPanel should explain that changes affect only the selected draft task. Hide unrelated session-wide copy. |
| S6 Running | Monitor execution | Running task is visually prominent. MessageStream shows live evidence. DetailPanel exposes stop/guidance only if allowed. |
| S7 Confirmation | Resolve a concrete decision | DetailPanel owns the confirmation. TaskTree shows the waiting node. MessageStream should not compete with the action buttons. |
| S8 Completed | Review result | Result summary becomes the main detail content. Input copy must not conflict with read-only completed state. |
| S9 File Changes | Review concrete changes | File summary appears after result. Hide raw task ids by default. Audit link appears as verification path. |
| S10 Permission Denied | Preserve context, explain boundary | Keep selected task visible. Disable input with one clear reason. Do not show unavailable controls as primary. |
| S11 Stale Snapshot | Make resync the next safe action | Keep last-known content visible but visually mark stale. Disable high-risk actions. Show one resync action. |
| S12 Backend Busy | Prevent duplicate action | Keep the current state readable. Show pending command near the control that caused it. Avoid global busy overlays. |
| S13 Command Failed | Recover without losing context | Keep TaskTree and selected object stable. Show inline error and retry/revise path. Do not redirect to a generic error page. |

## 9. Screen Composition Rules By Surface

### 9.1 TopBar

Target:

```text
Plato | Project | Workflow | Session | Primary status | Live/Stale | Audit | Settings
```

Rules:

- product mark and `Plato` are enough inside the app shell;
- remove or demote tagline text in dense states;
- show no more than two status chips;
- hide development state picker outside prototype/dev mode;
- route context should truncate gracefully and never force page overflow.

### 9.2 Sidebar

Rules:

- show workflow/session hierarchy;
- keep selected session visually clear;
- avoid explaining product concepts in the sidebar;
- session context menu should follow the same 8px radius and low-shadow
  workbench style;
- destructive actions stay visually secondary until the menu is open.

### 9.3 TaskTree

Rules:

- TaskNode title should be readable before secondary summary.
- One-line truncation is acceptable for summary, not for the core task title
  in normal desktop width.
- Status badges should be compact and stable in width.
- Selected state should use border, background, and maybe a left rail; not only
  blue fill.
- Inline stop/retry actions appear only when immediately relevant.

### 9.4 MessageStream

Rules:

- use it as evidence, not as the main narrative;
- show recent related updates when a task is selected;
- use compact rows rather than card-heavy blocks when density is high;
- hide count badges unless the count changes user interpretation;
- collapse first at constrained widths.

### 9.5 DetailPanel

Rules:

- title names the current object or required action;
- body explains the decision/action, not the whole session;
- remove generic `State note` when it repeats the header;
- confirmation, result, and file summary are mutually focused modes;
- long details should scroll inside the panel.

### 9.6 InputDock

Rules:

- leading scope should be compact: `Applies to: selected task / Visual direction`;
- label `Message` can be removed if placeholder and accessible label are
  clear;
- disabled/read-only reason replaces placeholder, not adds another paragraph;
- send button should stay icon-first with accessible label;
- placeholder must match the actual command mode.

## 10. Visual QA Checklist

Before accepting a future Figma or frontend simplification pass:

- no horizontal clipping at 1280px desktop width;
- no visible production state picker;
- no repeated `State note` content;
- no generic skeleton labels in screen states;
- TaskTree is the most prominent central object in planning/execution states;
- MessageStream is visually subordinate to TaskTree and DetailPanel actions;
- completed/read-only input copy does not invite unavailable edits;
- file summaries hide raw task ids by default;
- confirmation state has one clear primary action;
- audit entry is visible but not dominant;
- top bar has no more than two status chips;
- all cards/panels use radius at or below 8px unless the design-system changes;
- empty, loading, error, permission, stale, and success states are represented
  without overlapping text or controls.

## 11. Acceptance Criteria

This brief is accepted when it can guide a future screen-state recomposition
without additional interpretation:

- each Main Page state has a named visual focus and simplification target;
- each major surface has ownership rules;
- duplicate information sources are identified for removal, merge, or demotion;
- responsive priority is explicit;
- future work can verify screenshots against the QA checklist;
- no frontend behavior, API shape, or Figma write is implied as already done.
