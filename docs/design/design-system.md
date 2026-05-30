# Plato Design System

> Status: minimal production-grade contract
> Last Updated: 2026-05-24
> Scope: Design tokens and component-layer rules required before production
> Figma component work and frontend architecture.
> Non-goals: no Figma component creation, no frontend code, no old Figma
> migration, no high-fidelity screen redesign.

## 1. Purpose

This document defines the minimum design-system contract for Plato. It binds:

- the canonical Figma file:
  [Plato Product Design System and Prototype](https://www.figma.com/design/CTK1yALdNEFo2zL8ZcEJIA);
- current frontend token names in `frontend/src/shared/styles/tokens.css`;
- canonical product state dimensions in
  `docs/product/canonical-status-model.md`;
- component and prototype readiness gates in `docs/design/`.

Figma component work must not create detached visual values. Tokens come first,
then base components, then layout components, then domain components, then page
states, then prototype flows.

## 2. Token Naming

Token names must map cleanly between Figma variables and frontend CSS
variables.

| Layer | Figma naming | CSS variable naming |
|---|---|---|
| primitive | `color/primitive/reason-blue` | `--plato-color-reason-blue` |
| semantic | `color/semantic/text-primary` | `--plato-color-text-primary` |
| component | `component/button/primary-bg` | `--plato-button-primary-bg` |
| status | `color/status/execution-running-bg` | `--plato-status-execution-running-bg` |

Current frontend CSS variables are a baseline, not a full token system. When
adding semantic/component tokens, keep existing primitive token names stable
where possible.

## 3. Color Tokens

### 3.1 Primitive Colors

| Token | Current CSS variable | Value | Use |
|---|---|---|---|
| `color/primitive/reason-blue` | `--plato-color-reason-blue` | `#2b5caa` | Brand, primary action, focus anchor. |
| `color/primitive/cave-blue` | `--plato-color-cave-blue` | `#5b8fd9` | Selected or active accents. |
| `color/primitive/clear-blue` | `--plato-color-clear-blue` | `#e8f1fb` | Selected or hover surface. |
| `color/primitive/wisdom-gold` | `--plato-color-wisdom-gold` | `#d4af37` | Attention, running, warning accent. |
| `color/primitive/classic-cream` | `--plato-color-classic-cream` | `#f5f2ec` | Gentle empty states. |
| `color/primitive/marble` | `--plato-color-marble` | `#fbfaf7` | Warm page/surface option. |
| `color/primitive/ink` | `--plato-color-ink` | `#182033` | Primary text. |
| `color/primitive/muted` | `--plato-color-muted` | `#697386` | Secondary text. |
| `color/primitive/line` | `--plato-color-line` | `#dce3ee` | Borders and dividers. |
| `color/primitive/panel` | `--plato-color-panel` | `#ffffff` | Panels and contained surfaces. |

### 3.2 Semantic Colors

Semantic tokens are required before Figma components become production-ready.

| Semantic token | Maps to baseline | Use |
|---|---|---|
| `color/semantic/page-bg` | `marble` or neutral page background | App background. |
| `color/semantic/surface` | `panel` | Panels, cards, drawers. |
| `color/semantic/surface-muted` | `classic-cream` or light blue | Empty/quiet supporting surfaces. |
| `color/semantic/text-primary` | `ink` | Primary readable text. |
| `color/semantic/text-secondary` | `muted` | Secondary copy and metadata. |
| `color/semantic/border` | `line` | Standard borders. |
| `color/semantic/focus-ring` | `reason-blue` with alpha | Focus-visible ring. |
| `color/semantic/action-primary` | `reason-blue` | Primary commands. |

### 3.3 Status And Verdict Colors

Do not use one generic status token for all product states. The visual tone may
share colors, but the token name must preserve the state dimension.

| Dimension | Values | Required semantic tones |
|---|---|---|
| planning | `empty`, `capturing_input`, `assessing`, `awaiting_user`, `ready_to_plan`, `draft_ready`, `published`, `rejected`, `cancelled`, `unknown` | neutral, info, warning, success, danger |
| task readiness | `draft`, `accepted`, `published`, `cancelled`, `unknown` | neutral, info, success, danger |
| execution | `not_started`, `pending`, `running`, `done`, `failed`, `cancelled`, `unknown` | neutral, info, warning, success, danger |
| confirmation | `pending`, `resolved`, `expired`, local `resolving`, local `resolve_failed` | warning, success, neutral, danger |
| audit verdict | `not_available`, `passed`, `warning`, `failed`, `inconclusive` | neutral, success, warning, danger, info |

## 4. Typography Tokens

Detailed typography rules live in
[Typography System](typography-system.md). This section records the minimum
token contract and current frontend compatibility mapping.

Font family baseline:

| Token | Value |
|---|---|
| `typography/family/ui` | `Inter`, `Noto Sans SC`, `PingFang SC`, `Microsoft YaHei`, system sans |
| `typography/family/brand` | `Source Serif 4`, `Noto Serif SC`, `Source Han Serif SC`, Georgia |
| `typography/family/mono` | `JetBrains Mono`, `SFMono-Regular`, Menlo, Monaco, Consolas, monospace |

Core text roles:

| Role | Size | Weight | Intended use |
|---|---:|---:|---|
| `type/brand-title` | 24px | 700 | Top bar brand text only. |
| `type/display` | 28px | 700 | Dialog title or rare page-level emphasis. |
| `type/page-title` | 22px | 600 | Main workspace or audit page title. |
| `type/title` | 20px | 600 | Major object title or dialog input title. |
| `type/panel-title` | 18px | 500 | Panel and section headings. |
| `type/card-title` | 15px | 500 | TaskNode, message, and result card titles. |
| `type/body` | 14px | 400 | Normal readable text. |
| `type/body-small` | 13px | 400 | Secondary descriptions and help text. |
| `type/label` | 13px | 500 | Field labels and compact labels. |
| `type/control` | 14px | 500 | Buttons, menus, and select controls. |
| `type/caption` | 12px | 500 | Metadata, counters, compact context. |
| `type/badge` | 12px | 500 | Badge and pill text. |
| `type/code` | 13px | 500 | File paths, commands, and logs. |

Current compatibility aliases:

| Existing role | Maps to |
|---|---|
| `type/heading` | `type/page-title` |
| `type/subheading` | `type/panel-title` |
| `type/muted` | `type/body-small` + secondary text color |
| `type/eyebrow` | `type/caption` + uppercase transform |

Rules:

- Do not scale type with viewport width.
- Letter spacing stays `0` unless a specific text style requires otherwise.
- Panel/card headings must not use hero-scale type.
- Do not add page-local type scales in CSS. Extend token roles first.

## 5. Spacing, Radius, Shadow, Motion, Breakpoint, Z-Index

### 5.1 Spacing

Use the existing 4px-based spacing scale.

| Token | CSS variable | Value |
|---|---|---:|
| `space/1` | `--plato-space-1` | 4px |
| `space/2` | `--plato-space-2` | 8px |
| `space/3` | `--plato-space-3` | 12px |
| `space/4` | `--plato-space-4` | 16px |
| `space/5` | `--plato-space-5` | 20px |
| `space/6` | `--plato-space-6` | 24px |
| `space/8` | `--plato-space-8` | 32px |
| `space/10` | `--plato-space-10` | 40px |

### 5.2 Radius

| Token | CSS variable | Value | Rule |
|---|---|---:|---|
| `radius/sm` | `--plato-radius-sm` | 4px | Inputs, compact controls. |
| `radius/md` | `--plato-radius-md` | 6px | Buttons, badges. |
| `radius/lg` | `--plato-radius-lg` | 8px | Panels and cards. |

Cards must stay at 8px radius or less unless a future design decision changes
the system.

### 5.3 Shadow

| Token | CSS variable | Use |
|---|---|---|
| `shadow/panel` | `--plato-shadow-panel` | Elevated panels/drawers only. |
| `shadow/focus` | `--plato-shadow-focus` | Focus-visible affordance. |

Avoid decorative heavy shadows. Use borders and layout first.

### 5.4 Motion

Motion is restrained and functional.

| Token | Value | Use |
|---|---:|---|
| `motion/duration/fast` | 120ms | Hover/focus. |
| `motion/duration/base` | 180ms | Panel and state transitions. |
| `motion/duration/slow` | 240ms | Drawer/sheet transitions. |
| `motion/easing/standard` | `cubic-bezier(0.2, 0, 0, 1)` | Standard UI motion. |

Loading shimmer/skeleton motion is allowed only for data loading or generation
progress and must be removable when state resolves.

### 5.5 Breakpoints

| Token | Range | Required behavior |
|---|---|---|
| `breakpoint/mobile` | 0-767px | Single-column or stacked primary workflow. |
| `breakpoint/tablet` | 768-1199px | Condensed sidebar/panels. |
| `breakpoint/desktop` | 1200px+ | Full workbench layout. |
| `breakpoint/wide` | 1440px+ | Full desktop density. |

Desktop is the first production target, but component specs must not assume
fixed desktop-only sizing.

### 5.6 Z-Index

Z-index tokens are reserved for functional layering only.

| Token | Use |
|---|---|
| `z/base` | Normal document flow. |
| `z/sticky` | Sticky top bar or input dock. |
| `z/popover` | Tooltip, menu, popover. |
| `z/dialog` | Modal dialog and blocking overlays. |
| `z/toast` | Non-blocking global notifications. |

## 6. Component Layer Contract

Component layers:

1. Base components: product-neutral primitives.
2. Layout components: workbench structure and responsive containers.
3. Domain components: product object views backed by ViewModels.
4. Page states: composed screens from approved states.
5. Prototype flows: transitions between approved states.

Every component must map to:

- Figma component name;
- code component path or `new component required`;
- props or ViewModel source;
- required states and variants;
- accessibility and responsive requirements;
- readiness status.

Detailed component inventory lives in `docs/design/component-spec.md`.

## 7. Readiness Criteria

A token/component is ready for actual Figma creation only when:

- token names and layer are defined here;
- component contract exists in `docs/design/component-spec.md`;
- states/variants are listed in `docs/design/component-state-matrix.md`;
- screen/prototype behavior is mapped in `docs/ux/prototype-state-map.md`
  where applicable;
- backend/ViewModel source is named for domain components;
- no old Figma content is being copied as canonical.

The canonical Figma file skeleton exists, but it is not ready for dev handoff
until these readiness checks pass for the relevant components and states.
