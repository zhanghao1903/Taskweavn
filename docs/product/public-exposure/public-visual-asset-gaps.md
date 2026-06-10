# Public Visual Asset Gaps

> Status: active
> Last Updated: 2026-06-10
> Related Plan: [Plato Public Exposure Plan](plato-public-exposure-plan.md)
> Scope: visual assets needed before Plato product, architecture, and UI content
> can be published in `zhanghao1903/plato-public`.
> Public Implementation PR: `https://github.com/zhanghao1903/plato-public/pull/1`

---

## 1. Purpose

This file tracks image and screenshot gaps for public-facing Plato material.

It is not a design brief and not a public asset directory. It is a private
planning registry used to decide what visuals are missing, which existing
images can be reused, which must be redesigned, and what must be checked before
an image is copied to the public repository.

The immediate public repository has no image assets. The first public pass
needs a small, accurate, sanitized visual set so the project is understandable
before users read architecture details.

## 2. Status Values

| Status | Meaning |
|---|---|
| `missing` | No usable asset exists yet. |
| `candidate` | Existing asset may be usable after review/export. |
| `needs_redesign` | Existing asset is useful as reference but not publishable. |
| `needs_capture` | Product screen exists or should exist, but a sanitized screenshot is required. |
| `approved` | Asset is approved for export but not yet copied to public repo. |
| `exported` | Asset has been exported into a publishable image file. |
| `published` | Asset is referenced from the public repository. |
| `blocked` | Asset cannot proceed until a product, design, legal, release, or data decision is made. |

## 3. Publication Checklist

Every public image must satisfy this checklist before it moves to `approved`:

- Uses the public product name `Plato` unless the context is explicitly engine
  architecture.
- Does not show outdated `Taskwean` spelling or old user-facing `TaskWeavn`
  branding.
- Does not include secrets, API keys, private workspace paths, local usernames,
  private repository names, customer data, or raw diagnostic logs.
- Uses sanitized sample tasks, files, and timestamps.
- Matches the current product status or is clearly labeled as roadmap/prototype.
- Has alt text and a short caption.
- Has a source reference: screenshot command, Figma frame, generated diagram
  source, or manually approved export.
- Is exported as a stable file, preferably PNG for screenshots/diagrams and
  optional WebP for web delivery.
- Is visually readable at README width and normal documentation width.

## 4. Current Asset Assessment

| Existing asset | Assessment | Decision |
|---|---|---|
| `docs/product/product Mark image/product mark light.png` | Strong brand/product mark board with Plato name, product mark, concept path, palette, and values. | `candidate`; needs brand approval and possibly split exports for hero, logo, and concept path. |
| `docs/product/product Mark image/image.png` | Brand-related image, not yet assessed for exact public purpose. | `candidate`; review before use. |
| `docs/plans/ui/images/Taskwean main page 00_04_17.png` | Historical UI concept; user-facing brand/text does not match current public Plato direction. | `needs_redesign`; do not publish directly. |
| `docs/plans/ui/images/Taskwean main page 00_04_34.png` | Historical UI concept; useful for layout reference but not public current-state evidence. | `needs_redesign`; do not publish directly. |
| `docs/plans/ui/images/Taskwean Task map 00_05_55.png` | Historical UI concept; likely useful as internal reference only. | `needs_redesign`; do not publish directly. |
| `docs/plans/ui/images/Taskwean Taskcard.png` | Historical UI concept; likely useful as internal reference only. | `needs_redesign`; do not publish directly. |
| `docs/plans/ui/images/hand draw.jpeg` | Exploratory hand sketch. | `needs_redesign`; do not publish directly unless explicitly used as process material. |
| `docs/assets/images/img_1.png` | Internal architecture/reference comparison image involving third-party systems. | `blocked`; do not publish as Plato architecture. Recreate a Plato-owned diagram instead. |

## 5. Visual Gap Table

| ID | Public surface | Needed asset | Status | Source / reference | Publish blocker | Notes |
|---|---|---|---|---|---|---|
| PUB-VIS-001 | README hero | Plato product mark / hero image | `exported` | `plato-public` draft PR #1: `assets/images/plato-hero.svg` | Public PR review | Public-safe SVG hero exported from product mark concept rather than raw Figma export. |
| PUB-VIS-002 | README and product overview | Product journey diagram: intent -> TaskTree -> review -> execution -> result/audit | `exported` | `plato-public` draft PR #1: `assets/images/plato-product-flow.svg` | Public PR review | Product-readable SVG diagram. |
| PUB-VIS-002A | README and product overview | Three product planes diagram: Inspiration -> Control -> Trust | `exported` | `plato-public` draft PR #1: `assets/images/plato-three-planes.svg` | Public PR review | Added to support the public product narrative around understanding, control, and evidence. |
| PUB-VIS-003 | Architecture overview | Authoring / Execution / Projection / Audit architecture diagram | `exported` | `plato-public` draft PR #1: `assets/images/plato-architecture-overview.svg` | Public PR review | Avoids raw private package paths. |
| PUB-VIS-004 | Trust and audit docs | Result / file change / audit evidence flow diagram | `exported` | `plato-public` draft PR #1: `assets/images/plato-trust-flow.svg` | Public PR review | Explains evidence flow without raw logs. |
| PUB-VIS-005 | README / product overview | Current Main Page screenshot with sanitized sample data | `exported` | `plato-public` draft PR #1: `assets/images/plato-main-page.png` | Public PR review | Captured from local mock runtime at 1440x900. |
| PUB-VIS-006 | Trust and audit docs | Current Audit Page screenshot with sanitized evidence detail | `exported` | `plato-public` draft PR #1: `assets/images/plato-audit-page.png` | Public PR review | Captured from local mock runtime at 1440x900. |
| PUB-VIS-007 | Product 1.1 / workspace docs | Workspace inspection screenshot: changed files, diff, file viewer | `exported` | `plato-public` draft PR #1: `assets/images/plato-workspace-inspection.png` | Public PR review and release-status wording | Captured from temporary local git workspace at 1440x900; public docs explicitly avoid claiming `0.1.0` availability. |
| PUB-VIS-008 | Usage docs | Unsigned macOS local release install/open visual | `exported` | `plato-public` draft PR #1: `assets/images/plato-macos-local-release.svg` | Public PR review | Explains unsigned/non-notarized local RC flow. |
| PUB-VIS-009 | README / social preview | Open Graph / repository preview image | `exported` | `plato-public` draft PR #1: `assets/images/plato-og-image.svg` | Public PR review | Public-safe SVG preview asset. |
| PUB-VIS-010 | Architecture docs | Context governance diagram: task/workspace/events -> Context Manager -> LLM input | `exported` | `plato-public` draft PR #1: `assets/images/plato-context-governance.svg` | Public PR review | Used by public architecture overview. |
| PUB-VIS-011 | Product overview | Main Page vs Audit Page comparison graphic | `exported` | `plato-public` draft PR #1: `assets/images/plato-control-trust-plane.svg` | Public PR review | Used by public trust-and-audit doc. |
| PUB-VIS-012 | Public docs index | Visual map of public docs / release status | `exported` | `plato-public` draft PR #1: `assets/images/plato-public-docs-map.svg` | Public PR review | Public repository map asset is available in the image set. |

## 6. Screenshot Capture Requirements

Public screenshots should be captured from a deterministic sanitized scenario:

- product name shown as `Plato`;
- sample project/workflow/session names that are generic and non-private;
- sample tasks that demonstrate the product loop without implying unsupported
  enterprise features;
- no real home directory, username, repository path, branch name, API key, or
  provider secret;
- no private GitHub URLs or private PR references;
- stable viewport sizes:
  - desktop README screenshot: 1440px or 1600px wide;
  - docs detail screenshot: 1200px wide;
  - optional tablet screenshot only if the screen is actually readable;
- if a screenshot shows Product 1.1 workspace inspection, the surrounding copy
  must say whether it is available in the public release or a roadmap/current
  development preview.

## 7. Recommended First Visual Set

Minimum first public set:

1. `plato-hero.svg`: brand/product mark and concise product identity.
2. `plato-product-flow.svg`: user journey from intent to audit.
3. `plato-main-page.png`: sanitized current Main Page screenshot.
4. `plato-architecture-overview.svg`: public-safe architecture diagram.

Second set:

1. `plato-audit-page.png`: trust/evidence screenshot.
2. `plato-trust-flow.png`: result, file changes, audit, diagnostics.
3. `plato-workspace-inspection.png`: changed files / diff / file viewer.
4. `plato-og-image.svg`: repository/social preview.

## 8. Update Rule

When a visual asset moves forward:

1. update the status in this file;
2. record the source artifact or capture command;
3. record any product/release caveat in the notes;
4. add the exported target filename once known;
5. only copy the asset to `zhanghao1903/plato-public` after it is approved.
