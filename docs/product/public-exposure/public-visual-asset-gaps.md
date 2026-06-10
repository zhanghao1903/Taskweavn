# Public Visual Asset Gaps

> Status: active
> Last Updated: 2026-06-10
> Related Plan: [Plato Public Exposure Plan](plato-public-exposure-plan.md)
> Scope: visual assets needed before Plato product, architecture, and UI content
> can be published in `zhanghao1903/plato-public`.

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
| PUB-VIS-001 | README hero | Plato product mark / hero image | `candidate` | `docs/product/product Mark image/product mark light.png` | Brand approval and split export decision | Prefer a clean 16:9 or 3:1 hero crop plus a square mark. |
| PUB-VIS-002 | README and product overview | Product journey diagram: intent -> TaskTree -> review -> execution -> result/audit | `missing` | `docs/product/core-product-principles.md`, `docs/product/plato-mvp-prd.md` | Diagram design | Should be product-readable, not architecture-heavy. |
| PUB-VIS-003 | Architecture overview | Authoring / Execution / Projection / Audit architecture diagram | `missing` | `docs/architecture/overview.md` | Diagram design and public wording | Should avoid raw private package paths. |
| PUB-VIS-004 | Trust and audit docs | Result / file change / audit evidence flow diagram | `missing` | `docs/product/core-product-principles.md`, `docs/plans/feature/result-exposure-surface.md` | Diagram design | Explain why audit exists without showing raw logs. |
| PUB-VIS-005 | README / product overview | Current Main Page screenshot with sanitized sample data | `needs_capture` | Current frontend runtime | Sanitized scenario and screenshot pass | Existing historical screenshots are not publish-ready. |
| PUB-VIS-006 | Trust and audit docs | Current Audit Page screenshot with sanitized evidence detail | `needs_capture` | Current frontend runtime | Sanitized scenario and screenshot pass | Must not expose raw absolute paths or diagnostic payloads. |
| PUB-VIS-007 | Product 1.1 / workspace docs | Workspace inspection screenshot: changed files, diff, file viewer | `needs_capture` | Product 1.1 workspace inspection route | Release/status wording | Publish only when docs clearly state availability status. |
| PUB-VIS-008 | Usage docs | Unsigned macOS local release install/open visual | `missing` | Public release `0.1.0` README and manifest | Decide whether screenshot is necessary | Optional; may be replaced by concise text. |
| PUB-VIS-009 | README / social preview | Open Graph / repository preview image | `missing` | Brand hero and product journey assets | Hero asset approval | Should work at small preview size. |
| PUB-VIS-010 | Architecture docs | Context governance diagram: task/workspace/events -> Context Manager -> LLM input | `missing` | `docs/architecture/context-manager.md` | Public architecture scope decision | Useful for developer docs, not README first screen. |
| PUB-VIS-011 | Product overview | Main Page vs Audit Page comparison graphic | `missing` | `docs/product/core-product-principles.md` | Diagram design | Good candidate for explaining control plane vs trust plane. |
| PUB-VIS-012 | Public docs index | Visual map of public docs / release status | `missing` | Public repository target information architecture | Not required for first pass | Defer unless README becomes too dense. |

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

1. `plato-hero.png`: brand/product mark and concise product identity.
2. `plato-product-flow.png`: user journey from intent to audit.
3. `plato-main-page.png`: sanitized current Main Page screenshot.
4. `plato-architecture-overview.png`: public-safe architecture diagram.

Second set:

1. `plato-audit-page.png`: trust/evidence screenshot.
2. `plato-trust-flow.png`: result, file changes, audit, diagnostics.
3. `plato-workspace-inspection.png`: changed files / diff / file viewer.
4. `plato-og-image.png`: repository/social preview.

## 8. Update Rule

When a visual asset moves forward:

1. update the status in this file;
2. record the source artifact or capture command;
3. record any product/release caveat in the notes;
4. add the exported target filename once known;
5. only copy the asset to `zhanghao1903/plato-public` after it is approved.
