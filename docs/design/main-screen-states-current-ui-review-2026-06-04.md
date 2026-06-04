# Main Screen States Current UI Review - 2026-06-04

> Status: current-runtime visual review notes
> Review date: 2026-06-04
> Scope: Read-only review of current Main Page runtime states against
> `main-screen-states-visual-simplification-brief.md` and
> `main-screen-states-recomposition-checklist.md`.
> Non-goals: no frontend code, no Figma write, no API contract change.

## 0. Follow-Up Decision - 2026-06-05

This document records runtime evidence from 2026-06-04. It is not the latest
implementation spec.

The later accepted direction is:

- remove the persistent `Session messages` / `MessageStream` column from the
  default Main Page;
- show one subtle Latest Activity strip in the workspace when a meaningful
  update exists;
- open full message history through an independent Activity Overlay;
- Activity Overlay covers DetailPanel instead of leaving DetailPanel half
  visible as a stable state;
- long `Result Summary` content opens as a Result Artifact/Reader, not as an
  expanded message.

Use `docs/design/main-page-visual-direction-summary.zh-CN.md` as the
implementation entry point.

## 1. Workflow Gate Report

| Gate item | Finding |
|---|---|
| User request | Guide Plato's visual direction so the page becomes more beautiful, concise, intuitive, less repetitive, and stylistically coherent. |
| Detected phase | P4 Main Page screen-state visual refinement and P10 feedback iteration. |
| Task type | Read-only runtime visual review and design note creation. |
| Required upstream artifacts | Visual simplification brief, recomposition checklist, current Main Page mock states. |
| Found artifacts | `docs/design/main-screen-states-visual-simplification-brief.md`, `docs/design/main-screen-states-recomposition-checklist.md`, `frontend/src/pages/main-page/mainPageStateCatalog.ts`. |
| Missing or weak artifacts | No accepted Figma/frontend recomposition pass yet; current runtime still reflects earlier visual structure. |
| Implementation allowed now | No frontend implementation in this task. |
| Prework required | Record runtime evidence and prioritize visual changes. |
| Execution scope | Review S1, S3, S7, S8, and S9 in the running app. |
| Acceptance criteria | Findings identify visible duplication, hierarchy issues, interaction ambiguity, and next review priorities. |
| Risks and assumptions | Browser viewport in Codex app was narrower than desktop; runtime page still reported fixed 1360px layout width, which is relevant to the 1280px no-clipping target. |

## 2. Evidence Captured

Runtime:

- Local frontend: `http://127.0.0.1:5174/`
- Tooling: in-app browser read-only DOM/screenshot review
- States sampled: S1 Empty, S3 Draft Ready, S7 Confirmation, S8 Completed,
  S9 File Changes

Runtime layout metrics:

| Metric | Observed |
|---|---:|
| Runtime page width | 1360px |
| Visible browser viewport width | 746px |
| Horizontal overflow | yes |
| TopBar width | 1328px |
| Workspace width | 756px |
| DetailPanel width | 320px |
| InputDock width | 1092px |

Important note:

- The current shell still behaves as a fixed-width 1360px workbench. This
  contradicts the simplification target that the page remain usable at 1280px
  without primary content clipping.

## 3. Cross-State Findings

### P0 - Horizontal Overflow Persists

All sampled states reported horizontal overflow. The page root was 1360px wide
while the active browser viewport was narrower.

Why this matters:

- The user loses the right side of the workbench before interacting.
- DetailPanel and TopBar controls are vulnerable to clipping.
- The later accepted direction removes the persistent MessageStream column
  before allowing DetailPanel or TaskTree to be clipped; the reviewed runtime
  still preserved the full three-column shell.

Design decision:

- Keep the workbench centered on TaskTree and DetailPanel.
- Replace the persistent MessageStream column with Latest Activity plus
  Activity Overlay before allowing the shell to overflow.
- Treat 1280px no-clipping as a P0 visual acceptance check.

### P0 - Development State Picker Is Still Visible

TopBar text includes the full state picker options in every sampled state:

```text
S1 Empty ... S13 Command Failed
```

Why this matters:

- It is not a user-facing control.
- It steals TopBar space from route context and status.
- It makes the product feel like a prototype rather than a polished workbench.

Design decision:

- Hide state picker in production and Figma-ready screen states.
- If kept for demos, isolate it in a dev-only toolbar outside the product
  shell.

### P1 - Brand Area Competes With Route Context

TopBar still shows:

```text
Plato
Task-first Intelligent
Workbench
```

Why this matters:

- The tagline is useful in docs or onboarding, but too heavy in the dense app
  shell.
- The brand block consumes width while the right-side controls already clip.

Design decision:

- Keep product mark + `Plato`.
- Remove or demote the tagline in normal workbench states.

### P1 - MessageStream Still Reads Like A Peer Panel

In S3/S7/S8/S9, MessageStream remains a full-height panel beside TaskTree.

Why this matters:

- It competes visually with TaskTree even when it only contains one or two
  supporting updates.
- It repeats facts also shown in DetailPanel or TaskTree.

Design decision:

- Remove the persistent MessageStream column from the default layout.
- Replace it with one-line Latest Activity plus an on-demand Activity Overlay.
- The overlay should cover DetailPanel when open rather than become a peer
  column or half-cover compromise.

## 4. State Findings

### S1 Empty

Observed surfaces:

- Workspace: `No TaskTree yet`
- MessageStream: `No messages yet`
- DetailPanel: workflow explanation plus `State note` with the same message
- InputDock: `Scope: workflow`

Issues:

- Empty-state explanation appears in three places.
- DetailPanel `State note` repeats the workflow body.
- MessageStream empty panel is visually too strong for a state where messages
  do not exist yet.

Decision:

- Keep one empty TaskTree explanation.
- Keep InputDock as the primary action path.
- Hide empty activity details; do not show an empty MessageStream panel.
- Remove the duplicate `State note`.

Priority: P1.

### S3 Draft Ready

Observed surfaces:

- TaskTree is present and central.
- Publish action is visible.
- MessageStream says draft task tree is ready.
- DetailPanel says `Review the generated structure` and repeats the same body
  inside `State note`.

Issues:

- TaskTree is correctly central, but MessageStream remains too visually equal.
- DetailPanel duplicates its own message with `State note`.
- TopBar state picker remains visible and clipped.

Decision:

- Keep TaskTree as primary.
- Remove duplicate `State note`.
- Put the generated-draft evidence in Latest Activity and Activity Overlay.
- Hide state picker.

Priority: P0 for state picker, P1 for duplicated note.

### S7 Confirmation

Observed surfaces:

- DetailPanel owns `Confirm visual baseline`.
- Confirmation buttons are visible.
- TaskTree shows waiting/running context.
- MessageStream includes an actionable confirmation-related update.

What works:

- This state is closer to the target model than S1/S3.
- DetailPanel correctly owns the decision.
- No `State note` duplication was observed.

Issues:

- MessageStream still competes with the confirmation card.
- Copy repeats that the confirmation is attached to the selected TaskNode.
- The secondary `Skip` action has enough visual weight to compete in a narrow
  panel.

Decision:

- Keep confirmation in DetailPanel.
- Keep one primary action dominant.
- Move confirmation-related evidence to Activity Overlay; the decision itself
  stays in DetailPanel.
- Demote revise/skip.
- Reduce repeated task-attachment copy to one impact block.

Priority: P1.

### S8 Completed

Observed surfaces:

- DetailPanel shows result summary and result sections.
- TaskTree shows done states.
- InputDock says completed tasks are read-only.
- MessageStream includes `Result ready`.

What works:

- The read-only copy is now aligned with the completed state.
- Result appears before file/audit detail.
- No `State note` duplication was observed.

Issues:

- MessageStream still repeats `Result ready`.
- Result card and detail heading both summarize the same result.
- InputDock still shows the generic `Message` label even when the task is
  read-only.

Decision:

- Keep result in DetailPanel as primary.
- Put result-ready evidence in Latest Activity / Activity Overlay.
- Open long Result Summary content as a Result Artifact/Reader.
- Replace generic input label with either follow-up affordance or a readonly
  explanation, depending on actual command mode.

Priority: P2.

### S9 File Changes

Observed surfaces:

- DetailPanel shows file summary.
- File cards show paths, change badges, and summaries.
- Raw owner ids are visible:

```text
Owner TaskNode: task-implementation
```

Issues:

- Raw TaskNode owner ids violate the default-view simplification rule.
- File list is useful but dense for a 320px panel.
- MessageStream repeats file-change summary.

Decision:

- Hide raw owner ids by default.
- Keep paths and change types visible.
- Put owner/task lineage into Audit or an expanded file detail.
- Put file-change evidence in Latest Activity / Activity Overlay only as a
  compact update.
- Keep Audit as the verification path, not another default content block.

Priority: P0 for raw ids in default view, P1 for density.

## 5. Prioritized Design Actions

| Priority | Action | Reason |
|---|---|---|
| P0 | Hide production-visible state picker | It makes the product surface feel like a prototype and consumes TopBar width. |
| P0 | Remove raw TaskNode owner ids from default file summary | Raw ids are not useful for most users and break the clean review surface. |
| P0 | Fix constrained-width overflow strategy | Current fixed 1360px shell contradicts the 1280px no-clipping acceptance target. |
| P0 | Replace persistent MessageStream with Latest Activity + Activity Overlay | It removes the peer-column competition and avoids double-scroll behavior. |
| P1 | Remove duplicate `State note` in S1/S3 | It repeats header/body copy and adds visual noise. |
| P1 | Specify Activity Overlay filters and long-result reader | It keeps history reviewable without turning long results into chat bubbles. |
| P1 | Demote brand tagline in dense workbench mode | Route context and status are more important in app usage. |
| P2 | Simplify completed-state input presentation | Completed state is read-only; input should not look like normal edit guidance. |
| P2 | Reduce file summary density inside 320px DetailPanel | File paths and change types matter; owner metadata can move behind expansion. |

## 6. Current Direction Assessment

The current runtime is directionally aligned with Plato's workbench model:

- stable workbench shell exists;
- TaskTree is present and central;
- DetailPanel changes by state;
- InputDock has scope awareness;
- confirmation and result states are understandable.

But it is not yet visually simplified enough:

- the shell still overflows constrained widths;
- dev controls remain visible;
- S1/S3 repeat explanatory content;
- MessageStream competes with primary surfaces;
- S9 exposes backend-like ids.

Overall readiness:

```text
Structural direction: good
Interaction direction: partially good
Visual simplification: not yet accepted
Production polish: not yet accepted
```

## 7. Recommended Next Task

Run a docs/Figma review pass using this order:

1. TopBar simplification.
2. 1280px layout behavior.
3. MessageStream replacement with Latest Activity + Activity Overlay.
4. S1/S3 duplicate-copy removal.
5. S9 file-summary metadata reduction.

Only after those P0/P1 issues are addressed should the visual review move to
fine styling such as color, shadow, radius, and spacing polish.
