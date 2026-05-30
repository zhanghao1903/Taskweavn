# Plato Typography System

> Status: draft baseline
> Last Updated: 2026-05-29
> Scope: font family, type scale, text color semantics, and usage rules for
> Plato / Taskweavn UI.
> Related:
> [Design System](design-system.md),
> [Component Spec](component-spec.md),
> [Figma UI Baseline](../product/plato-figma-ui-baseline.md),
> [Design Philosophy](../product/plato-design-philosophy-style-guide.md).

## 1. Purpose

Plato is a task-first intelligent workbench. Typography must support dense,
long-running work instead of decorative presentation. The system should feel
calm, precise, readable, and trustworthy.

This document defines:

- font family choices;
- type roles and scale;
- text color semantics;
- component usage rules;
- frontend and Figma token requirements.

It is a design-system contract. It should be updated before changing the
frontend text scale, Figma text styles, or reusable Text component variants.

## 2. Principles

1. **Readable before expressive.** Workbench text is functional. Brand
   character appears in controlled places, not in dense task panels.
2. **Chinese and English are both first-class.** The system must handle Chinese
   product copy, English technical labels, IDs, file paths, and mixed text.
3. **Compact but not cramped.** Plato shows TaskTrees, messages, file changes,
   and audit facts together. Typography should preserve density without forcing
   users to zoom.
4. **No viewport-scaled type.** Font sizes do not scale with viewport width.
   Layout adapts; text scale remains stable.
5. **No negative letter spacing.** Letter spacing stays `0` unless a future
   brand decision explicitly adds a separate display style.
6. **Use color semantically.** Text color should express hierarchy, status, or
   action affordance. Do not use ad hoc gray/blue/red literals.
7. **Overflow is a design problem.** Labels, titles, and cards must define wrap
   or truncation behavior before implementation.

## 3. Font Families

### 3.1 UI Sans

Primary workbench font:

```text
Inter, "Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif
```

Use for:

- all normal UI text;
- TaskTree, TaskNode, message, form, button, badge, navigation, and settings
  copy;
- English technical labels and UI numerals.

Rationale:

- `Inter` gives stable Latin metrics and UI numerals.
- `Noto Sans SC` / `PingFang SC` / `Microsoft YaHei` provide Chinese glyphs
  across common environments.
- `system-ui` keeps the interface usable when preferred fonts are unavailable.

Top bar context and compact control text can intentionally use the CJK-first UI
family when Chinese/English mixed labels need steadier metrics:

```text
"Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif
```

### 3.2 Brand Serif

Brand-only font:

```text
"Source Serif 4", "Noto Serif SC", "Source Han Serif SC", Georgia, serif
```

Use for:

- the Plato brand mark text in the top bar;
- occasional brand or document cover moments.

Do not use brand serif for:

- TaskTree contents;
- message streams;
- forms;
- status badges;
- audit facts;
- dense panels.

### 3.3 Mono

Technical text font:

```text
"JetBrains Mono", "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono",
"Courier New", monospace
```

Use for:

- file paths;
- command snippets;
- IDs when they must be exposed;
- logs and audit technical evidence.

## 4. Type Scale

The first production baseline is desktop workbench-first. Mobile may later add
layout-specific density rules, but it should not invent a separate type system.

| Role | CSS token prefix | Size | Weight | Line height | Default color | Use |
|---|---|---:|---:|---:|---|---|
| Brand title | `--plato-type-brand-title-*` | 24px | 700 | 1.1 | brand | Top bar brand text only. |
| Display | `--plato-type-display-*` | 28px | 700 | 1.15 | primary | Dialog title or rare page-level emphasis. |
| Page title | `--plato-type-page-title-*` | 22px | 600 | 1.25 | primary | Main workspace title, audit page title. |
| Title | `--plato-type-title-*` | 20px | 600 | 1.3 | primary | Dialog input title, major object title. |
| Panel title | `--plato-type-panel-title-*` | 18px | 500 | 1.3 | primary | Workspace panel, detail panel, message panel. |
| Card title | `--plato-type-card-title-*` | 15px | 500 | 1.35 | primary | TaskNode title, message title, result card title. |
| Body | `--plato-type-body-*` | 14px | 400 | 1.5 | primary | Normal readable copy. |
| Body strong | `--plato-type-body-strong-*` | 14px | 500 | 1.5 | primary | Inline emphasis or short important copy. |
| Body small | `--plato-type-body-sm-*` | 13px | 400 | 1.45 | secondary | Secondary descriptions, help text. |
| Label | `--plato-type-label-*` | 13px | 500 | 1.35 | primary | Field labels, compact control labels. |
| Control | `--plato-type-control-*` | 14px | 500 | 1.2 | action/primary | Buttons, select labels, menu items. |
| Caption | `--plato-type-caption-*` | 12px | 500 | 1.35 | tertiary | Metadata, small status context, counters. |
| Badge | `--plato-type-badge-*` | 12px | 500 | 1.2 | status text | Badge and pill text. |
| Code | `--plato-type-code-*` | 13px | 500 | 1.45 | primary | File path, command, log snippets. |

Supplemental workbench roles:

| Role | CSS token prefix | Size | Weight | Line height | Use |
|---|---|---:|---:|---:|---|
| Breadcrumb | `--plato-type-breadcrumb-*` | 14px | 500 | 1.35 | Top bar path labels. |
| Top bar context | `--plato-type-topbar-context-*` | 14px | 500 | 20px | Top bar project and session context. |
| Top bar action | `--plato-type-topbar-action-*` | 12px | 500 | 17px | Top bar action buttons. |
| Top bar badge | `--plato-type-topbar-badge-*` | 11px | 500 | 16px | Top bar workflow/status badges. |
| Navigation | `--plato-type-nav-*` | 15px | 400 | 1.35 | Sidebar session/workflow items. |
| Navigation active | `--plato-type-nav-active-*` | 15px | 500 | 1.35 | Active sidebar item. |

Compatibility aliases:

- `heading` maps to `page-title`;
- `subheading` maps to `panel-title`;
- `body`, `muted`, `label`, and `eyebrow` remain stable for current frontend
  code.

## 5. Text Color Semantics

### 5.1 Core Text Colors

| Semantic token | Current target | Use |
|---|---|---|
| `--plato-color-semantic-text-primary` | ink | Primary readable text and important object names. |
| `--plato-color-semantic-text-secondary` | muted | Supporting descriptions and less important metadata. |
| `--plato-color-semantic-text-tertiary` | placeholder | Quiet labels, counters, low-emphasis context. |
| `--plato-color-semantic-text-disabled` | placeholder | Disabled controls and unavailable actions. |
| `--plato-color-semantic-text-placeholder` | placeholder | Input placeholder text. |
| `--plato-color-semantic-text-link` | reason blue | Navigation links and inline drill-down actions. |
| `--plato-color-semantic-on-action-primary` | panel white | Text on primary action backgrounds. |

### 5.2 Status Text Colors

Use status text tokens when the text is part of a product state.

| Semantic token | Maps to | Use |
|---|---|---|
| `--plato-color-semantic-text-info` | reason blue | Informational state, selected state, live event hint. |
| `--plato-color-semantic-text-success` | success text | Done, ready, passed. |
| `--plato-color-semantic-text-warning` | warning text | Waiting user, running, needs attention. |
| `--plato-color-semantic-text-danger` | danger text | Failed, rejected, destructive action. |

Status text must not rely on color alone. Pair it with label copy or icon shape.

## 6. Scenario Rules

### 6.1 Top Bar

- Brand: brand serif, brand title role.
- Project and session context: top bar context role, CJK-first UI family.
- Workflow and status pills: top bar badge role, CJK-first UI family.
- Top bar action buttons: top bar action role, CJK-first UI family.
- Long breadcrumb items: single-line ellipsis.

### 6.2 Side Navigation

- Section title: caption or eyebrow, uppercase only for stable category labels.
- Session/workflow item: body strong when active, body small/body otherwise.
- Right-click menu item: control role.
- Double-click rename dialog title: display role; input: title role.

### 6.3 Workspace

- Workspace title: page title.
- Workbench panel title: panel title.
- TaskNode title: card title.
- TaskNode summary: body small.
- Task status: badge.
- Empty states: body and body small; avoid large empty-state hero type.

### 6.4 Detail Panel

- Detail object title: page title or title depending on density.
- Detail description: body small.
- Result and file-change cards: card title + body small.
- Technical paths: code role and mono family.

### 6.5 Message Stream

- Message kind/status badge: badge.
- Message title: card title.
- Message body: body or body small depending on card density.
- Message metadata and task-scoped projection labels: caption.
- User-provided long text must wrap; IDs and technical strings may use
  `overflow-wrap: anywhere`.

### 6.6 Context Input

- Scope label: label or caption.
- Guidance text: body small.
- Input text: body.
- Placeholder text: placeholder semantic color.
- Send button: icon-first; button label, if present, uses control role.

### 6.7 Audit And Logs

- Audit page title: display or page title depending on screen density.
- Evidence timeline title: panel title.
- Record metadata: caption.
- Log snippets and file paths: code role.
- Verdict text: status text semantic token.

## 7. Figma Requirements

The canonical Figma file should contain text styles that correspond to this
scale:

- `type/brand-title`
- `type/display`
- `type/page-title`
- `type/title`
- `type/panel-title`
- `type/card-title`
- `type/body`
- `type/body-strong`
- `type/body-small`
- `type/label`
- `type/control`
- `type/caption`
- `type/badge`
- `type/code`

Existing Figma styles may be renamed or mapped during the next governed Figma
pass. Do not create component-specific font sizes in Figma.

## 8. Frontend Requirements

Frontend rules:

- `frontend/src/shared/styles/tokens.css` is the source of code-side token
  names.
- Existing components should use type tokens instead of raw `font-size`,
  `font-weight`, or `line-height` literals.
- `Text` component variants may remain coarse initially, but future component
  work should either:
  - add variants that map to this document; or
  - keep the Text component small and expose role-specific CSS utility classes.
- Page CSS may use local layout variables, but not local type scales.
- Mono font usage must go through `--plato-font-mono`.

## 9. Accessibility And Readability

- Body text should not go below 14px in user-facing workbench copy.
- Caption text can be 12px only for metadata and short labels.
- Interactive labels should generally be 14px or larger.
- Long Chinese copy should prefer wrapping over single-line truncation unless
  the container is a nav item, breadcrumb, or compact TaskNode row.
- Important action text must pass normal contrast expectations on its
  background.
- Disabled text can be lower contrast, but unavailable state must also be
  conveyed by disabled behavior and affordance.

## 10. Open Questions

These are intentionally left open for later visual QA:

1. Whether Plato should bundle web fonts or rely on local/system fonts for the
   first desktop build.
2. Whether brand serif should prefer Chinese serif first for `柏拉图` or keep
   Latin-first serif for the mixed `柏拉图 Plato` mark.
3. Whether mobile should use the same 15px body baseline or increase line-height
   for long conversational copy.
4. Whether Audit Page needs a denser evidence-table type role after real data
   volume is tested.
