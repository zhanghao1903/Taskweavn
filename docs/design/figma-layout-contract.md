# Plato Figma Layout Contract

> Status: active governance contract
> Last Updated: 2026-05-25
> Scope: Required layout rules for governed Screen State frames and Dev Handoff
> sections in the canonical Figma file.

This contract prevents future Main Page, Audit Page, Prototype Flow, and Dev
Handoff frames from becoming unreadable because of overlapping metadata,
clipped text, mixed component proof galleries, or unconstrained long notes.

Canonical Figma file:

```text
Plato Product Design System and Prototype
```

Use this contract with:

- `.agents/skills/plato-figma-governance/SKILL.md`
- `docs/design/figma-readiness-checklist.md`
- `docs/design/dev-handoff.md`
- `docs/ux/screen-state-spec.md`
- `docs/ux/prototype-state-map.md`

## 1. Required Gate Usage

Before any future Figma write that creates or edits Screen State frames,
Prototype Flow handoff frames, or Dev Handoff sections, the Figma Operation Gate
must confirm:

- this contract was read;
- the target work uses the standard layout zones below;
- metadata is summary-length only in Figma;
- full metadata lives in repo docs;
- component usage proof is not inside the screen preview zone;
- structural, readability, screenshot-width, and metadata overflow checks are
  included in the verification plan;
- node ID preservation is planned for hygiene passes.

If those conditions are not met, block the Figma write and perform the smallest
layout-governance or documentation task that unblocks it.

## 2. Standard Screen State Frame Layout

Every governed Screen State frame must be divided into four zones.

| Zone | Required content | Rules |
|---|---|---|
| Header zone | State ID, state name, short canonical mapping summary, readiness marker | Keep to one compact row or stacked title block. Do not place long state metadata here. |
| Screen preview zone | The page composition for the state, built from approved Base, Layout, and Domain component instances | This is the product-state preview only. Do not place component proof galleries or long handoff notes inside this zone. |
| Metadata summary zone | Trigger, route/entry context, canonical backend state dimensions, required data summary, actions, disabled behavior, exit condition | Summary only. Use bullets or short table rows. Long field-by-field metadata moves to `docs/design/dev-handoff.md`. |
| Implementation notes zone | Source docs, component usage summary, implementation caveats, recovery behavior, open gaps | Use concise references and links. Do not duplicate full handoff tables from docs. |

Recommended frame structure:

- Minimum desktop width: `1440`.
- Governed screen composition preview slot: `1440x1024`.
- Canonical reusable Figma template: `Template / P4.10 Screen composition
  preview` in `11 - Dev Handoff / Layout Templates`.
- When metadata is shown beside the preview, widen the outer state/template
  frame instead of shrinking the preview. The preview remains the fixed product
  composition reference; metadata and implementation notes must sit outside it.
- Main screen state frame height: at least `1340` when component usage and
  metadata are present.
- Audit screen state frame height: at least `1580` when evidence, permission,
  stale, or error metadata is present.
- Outer margin: at least `32`.
- Zone gutter: at least `24`.
- Metadata summary zone width: at least `360`; use wider side panels for Audit
  permission, evidence, stale, and error states.
- If the metadata summary cannot fit within the zone, shorten the Figma copy
  and move the full text to `docs/design/dev-handoff.md`.

Screen State frames must stay readable as development references. They are not
allowed to become full product-spec documents pasted into Figma.

## 3. Standard Dev Handoff Section Layout

Every governed Dev Handoff section must use a consistent structure:

| Zone | Required content | Rules |
|---|---|---|
| Section header | Section title, scope, readiness status | One concise title and one concise scope note. |
| Mapping table or list | Figma node ID, code path, props/ViewModel fields, backend source, state coverage | Prefer tables or short rows. Do not use paragraph blocks for dense mappings. |
| Gaps and blockers | Missing API, ViewModel, route, test, responsive, or accessibility work | Keep each blocker actionable and traceable to the source doc. |
| Source references | Repo doc paths and relevant Figma page names | Use doc path references instead of duplicating full text. |

Dev Handoff pages in Figma are navigation and inspection surfaces. The repo
document `docs/design/dev-handoff.md` remains the complete engineering handoff
source.

## 4. Max Text Rules For Figma Metadata

Figma metadata must remain summary-length. Use these limits unless a future
contract revision changes them:

| Text kind | Maximum |
|---|---:|
| State title | 80 characters |
| Canonical mapping summary | 140 characters |
| Metadata bullet | 120 characters |
| Metadata table cell | 160 characters |
| Metadata summary zone total visible copy | 900 characters |
| Implementation note bullet | 140 characters |
| Implementation notes zone total visible copy | 700 characters |
| Dev Handoff section paragraph | 220 characters |
| Dev Handoff mapping row note | 160 characters |

When content exceeds these limits:

1. replace the Figma text with a concise summary;
2. move the full content to `docs/design/dev-handoff.md` or the relevant
   contract doc;
3. add the doc path and section name in Figma;
4. record the move in the Figma Change Report.

Do not solve overflow by shrinking text below the tokenized readable size.

## 5. Full Metadata Lives In Repo Docs

Figma frames should contain:

- state identity;
- route or entry context;
- canonical status dimension summary;
- visible component summary;
- primary and secondary action summary;
- recovery behavior summary;
- source document references.

Repo docs should contain:

- complete route and ViewModel mapping;
- full backend-to-UI mapping;
- exhaustive state field lists;
- API/event dependencies;
- complete error, permission, stale, and recovery behavior;
- migration notes and implementation risks.

For the canonical handoff, `docs/design/dev-handoff.md` is the full metadata
source. Figma frames must point to it instead of duplicating it.

## 6. Component Usage Rules

- Do not place component usage proof galleries inside the screen preview zone.
- Do not use screen states as component inventory pages.
- Use a textual component usage summary in the implementation notes zone, or
  create a separate Dev Handoff section when detailed proof is needed.
- Base/Layout/Domain component galleries belong on their component pages.
- Screen preview zones should show only the components needed to communicate
  the target state.
- Placeholder labels used inside component instances must be clearly marked as
  non-production copy when there is a risk of confusion.

## 7. No-Overlap Verification

Every Screen State or Dev Handoff Figma write must verify:

- required zones exist;
- visible text nodes do not overlap other visible text or components;
- metadata panels do not overlap the screen preview;
- component usage summaries do not cover product-state preview content;
- no important content is clipped by the frame boundary;
- hidden legacy metadata overlays are not the handoff source;
- permission, stale, error, partial, and hidden-evidence states remain visible
  and distinct.

Structural verification is not enough. A pass can be structurally complete but
still fail layout readability if humans cannot inspect the frame at normal zoom.

## 8. Screenshot-Width Verification

Future Figma work that affects Screen State or Dev Handoff readability must
attempt screenshot verification at a common handoff width.

Minimum requirement:

- target screenshot width: `1600` px or the closest supported transport width;
- verify at least one normal Main state;
- verify at least one normal Audit state;
- verify the most complex permission/error state touched by the task;
- verify the Dev Handoff section touched by the task when applicable.

If screenshot transport fails:

- record screenshot verification as pending or blocked;
- keep structural and layout-readability verification separate;
- do not mark screenshot verification as passed;
- do not fail the entire task if structural and local layout inspection pass,
  but report the residual risk.

## 9. Metadata Overflow Verification

Every future Screen State and Dev Handoff write must verify:

- Figma metadata copy respects the max text rules in this contract;
- any full metadata moved to docs has a doc path reference in Figma;
- long labels wrap inside their zone instead of extending into adjacent zones;
- metadata zones are wide and tall enough for their visible summary;
- text remains readable without reducing type size below the design-system text
  token intended for notes or labels.

Overflow must be fixed by shortening and referencing docs, not by hiding text or
placing it outside the frame.

## 10. Node ID Preservation During Hygiene Passes

Hygiene passes must preserve existing state frame and component node IDs where
possible.

Allowed:

- move nodes;
- resize frames;
- reflow section contents;
- add labels or summary panels;
- hide stale generated metadata overlays only when they are clearly superseded
  and retained for traceability.

Avoid:

- deleting and recreating state frames;
- renaming state IDs;
- replacing component instances with hand-drawn copies;
- changing semantic state mappings;
- changing route/API/ViewModel mappings during visual cleanup.

If a node ID must change, the task must record:

- old node ID;
- new node ID;
- reason;
- affected registry/checklist/dev-handoff rows.

## 11. Auto Layout And Section Frame Rules

Use Auto Layout or labeled section frames wherever possible:

- use Auto Layout for metadata summary panels, implementation notes, and Dev
  Handoff mapping rows;
- use fixed or bounded dimensions for zones that must remain screenshot-safe;
- avoid unconstrained horizontal rows for large variant or state collections;
- wrap long rows into grids;
- keep notes adjacent to the component or state they describe;
- avoid using absolute-positioned overlay text inside auto-layout frames unless
  its behavior has been verified after resizing;
- keep `clipsContent` behavior intentional and verified.

If Auto Layout would expand content beyond the screenshot-safe width, use
bounded section frames and wrap content into multiple rows.

## 12. Definition Of Dev Handoff Readable

A Figma frame or section is dev-handoff readable only when a reviewer can, at a
standard screenshot width, identify:

- the state or section name;
- the relevant route or entry context;
- the separated canonical status dimensions;
- the visible components and their role;
- primary and secondary actions;
- disabled, permission, stale, error, partial, and hidden-evidence behavior when
  applicable;
- recovery or return behavior;
- the source doc path for full metadata;
- open blockers or readiness status.

It must also have:

- no visible text overlap;
- no clipped required metadata;
- no component proof covering the preview;
- no hidden overlay used as the handoff source;
- no placeholder copy that could be mistaken for approved product copy without
  an adjacent warning.

## 13. Required Report Fields For Future Figma Work

Future Figma Operation Gate Reports for Screen State or Dev Handoff work must
include:

- layout contract checked: yes/no;
- target layout template: ScreenState or DevHandoff;
- full metadata storage: Figma summary plus repo doc path;
- planned no-overlap verification;
- planned screenshot-width verification;
- planned metadata overflow verification;
- node ID preservation plan.

Future Figma Change Reports for Screen State or Dev Handoff work must include:

- layout template used;
- zones created or updated;
- metadata moved to docs;
- text over-limit findings;
- no-overlap verification result;
- screenshot-width verification result;
- metadata overflow verification result;
- node IDs preserved or changed.

## 14. Non-Goals

This contract does not:

- define final visual polish;
- replace the design system;
- create new product states;
- change the canonical status model;
- implement frontend code;
- approve the Figma file as frontend implementation complete.
