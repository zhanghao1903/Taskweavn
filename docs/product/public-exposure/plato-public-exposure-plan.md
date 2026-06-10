# Plato Public Exposure Plan

> Status: done
> Last Updated: 2026-06-10
> Gap: [Public visual asset gaps](public-visual-asset-gaps.md)
> Product: [Core product principles](../core-product-principles.md), [MVP PRD](../plato-mvp-prd.md), [Brand and UX direction](../plato-brand-and-ux-direction.md), [Product 1.1 workspace-aware foundation](../plato-1-1-workspace-aware-agent-foundation.md)
> Architecture: [Architecture overview](../../architecture/overview.md), [UI/backend communication](../../architecture/ui-backend-communication.md), [Context Manager](../../architecture/context-manager.md), [Git/Diff/File Viewer API contract](../../engineering/git-diff-file-viewer-api-contract.md)
> Public Repository Reviewed: `https://github.com/zhanghao1903/plato-public`
> Public Implementation PR: `https://github.com/zhanghao1903/plato-public/pull/1`

---

## 1. Purpose

This plan defines how Plato should expose selected product, architecture,
release, and visual material through the public repository without copying
private implementation context by default.

At plan intake, the public repository was a release-hosting shell:

```text
README.md
releases/0.1.0/manifest.json
releases/0.1.0/SHA256SUMS
```

It already published the unsigned macOS Apple Silicon `0.1.0` local release
candidate download and release metadata, but did not yet explain Plato as a
product, show the task-first user journey, show architecture, or provide
public-ready UI/visual assets.

The initial planning work did not move private docs, source code, screenshots,
or assets into the public repository. The follow-up public implementation uses
rewritten public docs and sanitized/exported visual assets only.

## 2. Exposure Goal

The public repository should first become a credible public product surface,
not a mirror of the private engineering repository.

The first public message should be:

```text
Plato is a task-first intelligent workbench.
It helps users start from an unclear goal,
discover how AI can help,
shape that goal into reviewable work,
control execution,
and inspect evidence afterward.
```

The public story should preserve the product boundary:

| Product plane or object | Public role |
|---|---|
| Plato | User-facing product and release identity. |
| Inspiration Plane | AI-use discovery, prompt/workflow guidance, intent clarification, assumptions, and draft readiness. |
| Control Plane | TaskTree review, task status, confirmations, progress, results, and next actions. |
| Trust Plane | Results, file changes, audit facts, diagnostics, and traceability. |
| Workflow, Session, TaskTree, TaskNode, Result, Audit | Stable product objects that users and developers can understand. |
| Runtime/engine identity | Developer-facing architecture only; do not lead product copy with it. |
| Agent, TaskBus, Context Manager, EventStream | Architecture objects explained only after the product path is clear. |

## 3. Reviewed Inputs

Private project inputs reviewed:

- `README.md`: current product/runtime status and local start instructions.
- `docs/product/README.md`: product docs inventory and source-of-truth split.
- `docs/product/plato-mvp-prd.md`: task-first MVP problem, target user, core flows, scope.
- `docs/product/core-product-principles.md`: Task as primary object, Main Page as control plane, Audit Page as trust plane.
- `docs/product/plato-brand-and-ux-direction.md`: Plato / TaskWeavn naming boundary and product tone.
- `docs/product/plato-1-1-workspace-aware-agent-foundation.md`: Product 1.1 workspace inspection direction.
- `docs/architecture/README.md` and `docs/architecture/overview.md`: active system boundary map.
- `docs/frontend/frontend-architecture-plan.md`: Main Page / Audit Page frontend source-of-truth hierarchy.
- `docs/design/README.md` and `docs/design/design-system.md`: design governance, tokens, and Figma readiness.
- `docs/gaps/README.md`: Product 1.0 closure and Product 1.1 gap status.
- `docs/plans/feature/product-1-1-workspace-inspection-milestone.md`: accepted workspace inspection milestone.
- `docs/engineering/git-diff-file-viewer-api-contract.md`: implemented Product 1.1 inspection API contract.

Public repository inputs reviewed:

- `README.md`: release-hosting README for `0.1.0`.
- `releases/0.1.0/manifest.json`: unsigned, non-notarized macOS arm64 release metadata.
- `releases/0.1.0/SHA256SUMS`: release checksum.

Visual inputs reviewed:

- `docs/product/product Mark image/product mark light.png`: candidate brand/product mark board.
- `docs/plans/ui/images/*.png`: historical TaskWeavn/Taskwean UI concept screenshots.
- `docs/assets/images/img_1.png`: internal architecture/reference comparison image.

## 4. Public Content Boundary

### 4.1 Safe To Expose After Rewriting

These topics can become public-facing material after concise rewriting and
review:

- Plato one-line product positioning.
- Three product planes: Inspiration, Control, and Trust.
- Inspiration Plane as the future product emphasis for helping users understand
  what AI can do, how to use AI effectively, and what context is needed before
  task planning.
- Task-first product journey: intent, TaskTree, review, publish, execute,
  result, audit.
- Main Page as user control plane.
- Audit Page as trust plane.
- Local-first release model and current `0.1.0` unsigned release caveat.
- High-level architecture map: Authoring Domain, Execution Domain, UI
  projection, Audit evidence.
- Workspace inspection as the next trust-building direction, clearly labeled
  by release/status.

### 4.2 Needs Sanitization Or Redesign Before Exposure

These topics are useful but should not be copied directly:

- Private architecture docs with internal class/package details.
- Detailed API contracts that include implementation choices not intended for
  public readers.
- Roadmap tables that mention private branch names, internal PR flow, or
  unfinished planning history.
- Historical Figma or UI screenshots that still say `TaskWeavn` or `Taskwean`
  in user-facing areas.
- Screenshots using local paths, private repository names, real workspaces, or
  user-generated content.
- Internal user-test artifacts, diagnostics, logs, and archived workspaces.

### 4.3 Do Not Expose In The First Public Pass

The first public pass should not publish:

- source code from the private repository;
- private prompts or agent instructions;
- raw logs, diagnostic bundles, SQLite files, or `.plato` runtime state;
- `garbage_collect/`, `workspace/`, `plato-workspace/`, or archived user-test
  material;
- secrets, API keys, local absolute paths, machine usernames, or private
  provider configuration;
- unreviewed implementation plans that imply a release promise;
- old Figma bulk exports or visual explorations as if they are current product
  truth.

## 5. Proposed Public Repository Information Architecture

Target shape for the public repository:

```text
README.md
docs/
  product/
    overview.md
    task-first-workflow.md
    release-status.md
  architecture/
    overview.md
    trust-and-audit.md
  usage/
    macos-local-release.md
assets/
  images/
    plato-hero.svg
    plato-three-planes.svg
    plato-product-flow.svg
    plato-architecture-overview.svg
    plato-main-page.png
    plato-audit-page.png
    plato-workspace-inspection.png
releases/
  0.1.0/
    manifest.json
    SHA256SUMS
```

Initial content responsibilities:

| Public file | Purpose |
|---|---|
| `README.md` | Product-first landing page: what Plato is, three-plane model, latest release, screenshots, quick start, status caveats. |
| `docs/product/overview.md` | User-facing product explanation through Inspiration, Control, and Trust planes, without internal engineering history. |
| `docs/product/task-first-workflow.md` | Clear path from intent and clarification to TaskTree, execution, and audit. |
| `docs/product/release-status.md` | What `0.1.0` includes, what is unsigned/non-notarized, and what is not promised yet. |
| `docs/architecture/overview.md` | Public architecture diagram and short explanation. |
| `docs/architecture/trust-and-audit.md` | Why Task, Result, File Change, Audit, and workspace inspection exist. |
| `docs/usage/macos-local-release.md` | Install/open guidance for unsigned macOS local RC. |
| `assets/images/` | Approved exported visual assets only. |

## 6. Public Narrative Structure

The first public README should be ordered for a new visitor:

1. Product identity: Plato, task-first intelligent workbench.
2. Visual first impression: brand/hero image or clean product screenshot.
3. Three product planes: Inspiration, Control, and Trust, with Inspiration defined as both AI-use guidance and intent clarification.
4. User journey: discover AI use, express goal, clarify, review TaskTree, confirm, execute, inspect result.
5. Latest release: `0.1.0` macOS Apple Silicon download and checksum.
6. Current status: unsigned/non-notarized local RC, bundled Python sidecar.
7. Architecture preview: local authoring, execution, projection, and trust boundaries in one simple diagram.
8. Trust model: result, file changes, Audit, diagnostics, workspace inspection.
9. What is next: a stronger Inspiration Plane for AI-use guidance, workspace-aware inspection, and richer public docs.

Avoid leading with:

- raw architecture object names;
- release checksum details before product explanation;
- internal phase history;
- unqualified multi-agent or autonomous claims.

## 7. Architecture Exposure Strategy

Architecture should be public in two layers.

Layer 1: Product-readable architecture.

```text
User intent
  -> Authoring: draft and revise the TaskTree
  -> Publish: turn reviewed tasks into executable work
  -> Execute: run tasks in a local workspace
  -> Project: show progress, results, file changes, and audit evidence
```

Layer 2: Developer-readable architecture.

```text
Authoring Domain
  RawTask -> Feasibility / Ask -> DraftTaskTree -> TaskPublisher

Execution Domain
  PublishedTask -> TaskBus -> FixedRouteTaskExecutor -> Default Agent

Trust / UI Projection
  EventStream + MessageStream + Result/File facts -> Main Page / Audit Page

Context Governance
  TaskBus + workspace + events + permissions -> Context Manager -> LLM input
```

Public architecture docs should:

- keep diagrams small and legible;
- explain why Authoring and Execution are separate;
- explain Main Page versus Audit Page;
- explain local workspace and bundled sidecar at a user-safe level;
- label Product 1.1 workspace inspection separately from the `0.1.0` release
  unless the public release artifact has been updated.

Public architecture docs should not:

- copy private package paths wholesale;
- expose every internal table, model, or route;
- imply arbitrary multi-agent orchestration is already a public feature;
- include raw branch, CI, or private planning history unless needed for release
  provenance.

## 8. Visual Exposure Strategy

Public presentation needs visuals before broad content exposure. The current
public repository has no images. The private repository has candidate and
historical images, but most are not publication-ready.

Required first visual set:

| Asset | Purpose | Current status |
|---|---|---|
| Brand / hero image | README first impression and social preview source. | Exported in public PR #1. |
| Three product planes text diagram | Explain Inspiration, Control, Trust, and their relationships in one readable image. | Canonical SVG exported in public PR #1. |
| Product flow diagram | Explain intent -> clarification -> TaskTree -> execution -> result/audit. | Exported in public PR #1. |
| Architecture overview diagram | Explain Authoring / Execution / Projection / Audit. | Exported in public PR #1. |
| Main Page screenshot | Show the primary control plane with sanitized sample data. | Exported in public PR #1. |
| Audit Page screenshot | Show the trust plane and evidence details. | Exported in public PR #1. |
| Workspace inspection screenshot | Show file/diff inspection when public release/status supports it. | Exported in public PR #1. |
| Trust/evidence flow diagram | Explain result, file changes, audit, diagnostics. | Exported in public PR #1. |
| Open Graph image | GitHub/social preview. | Exported in public PR #1. |

All image work is tracked in
[Public Visual Asset Gaps](public-visual-asset-gaps.md).

## 9. Execution Slices

### Slice A: Public Repo Skeleton Plan

Goal: prepare the public information architecture without publishing content.

Deliverables:

- this plan;
- public visual gap registry;
- later branch/task for public README and docs skeleton.

Acceptance:

- no private content copied;
- all planned public surfaces have a purpose and owner;
- missing visuals are explicitly tracked.

### Slice B: Product Landing Draft

Goal: rewrite product narrative for public readers.

Deliverables in the public repository:

- README rewrite;
- `docs/product/overview.md`;
- `docs/product/task-first-workflow.md`;
- latest release block preserved from current README.

Acceptance:

- describes Plato before release mechanics;
- separates Plato product identity from TaskWeavn engine identity;
- no internal planning history or private paths;
- release status matches `releases/0.1.0/manifest.json`.

### Slice C: Architecture Public Draft

Goal: add public-safe architecture explanation and diagram.

Deliverables in the public repository:

- `docs/architecture/overview.md`;
- `docs/architecture/trust-and-audit.md`;
- architecture overview image.

Acceptance:

- explains Authoring, Execution, UI projection, Audit, and Context Manager;
- avoids source-code-level internals unless explicitly intended;
- clearly marks implemented, release-candidate, and planned capabilities.

### Slice D: Visual Asset Production

Goal: produce approved images for README and docs.

Deliverables:

- exported hero/product mark;
- product flow diagram;
- architecture overview diagram;
- sanitized Main Page, Audit Page, and workspace inspection screenshots;
- alt text and captions for every image.

Acceptance:

- images pass the checklist in the visual gap registry;
- no screenshot includes private paths, local usernames, secrets, real customer
  content, or outdated TaskWeavn/Taskwean branding;
- images are stored as exported assets, not raw Figma dumps.

### Slice E: Public Repository PR

Goal: apply approved public docs and assets to `zhanghao1903/plato-public`.

Acceptance:

- public repo remains coherent as a release-hosting and product-doc surface;
- download links and checksums remain correct;
- every public claim maps to an accepted release, plan, or explicitly labeled
  roadmap item;
- public visuals are approved and referenced with alt text.

## 10. Acceptance Criteria For This Plan

This planning task is complete when:

- public repo current state is documented;
- private product and architecture inputs are summarized into exposure rules;
- public information architecture is proposed;
- public visual assets and missing screenshots are tracked separately;
- no public repository content is changed;
- no private implementation content is exposed.

Current completion status: implemented in public draft PR on 2026-06-10.

Evidence:

- Public repository branch:
  `zhanghao1903/plato-public@codex/plato-public-exposure`.
- Public draft PR:
  `https://github.com/zhanghao1903/plato-public/pull/1`.
- Public commits:
  - `8411de0 Add Plato public product docs`.
  - `bd6a80e Complete public visual assets`.
  - `a04a4e6 Refine Plato product planes`.
  - `c6152cf Add generated product plane visuals`.
  - `dca508b Replace product plane visuals with text diagram`.
- Public docs added: README, product overview, task-first workflow, release
  status, architecture overview, trust/audit, and macOS local release usage.
- Public assets added: hero, text three product planes diagram, product flow, architecture
  overview, trust flow, Context Manager, Main Page vs Audit Page, macOS local
  release, public docs map, Open Graph/social preview, sanitized Main Page
  screenshot, sanitized Audit Page screenshot, and sanitized Workspace
  Inspection screenshot.

The public PR remains draft until review/merge. The private planning artifact
and public branch now satisfy the plan's first public exposure scope.

## 11. Risks And Assumptions

Assumptions:

- The public repository remains the target for product/release exposure.
- The first pass exposes docs and release assets, not source code.
- Plato is the public product name; TaskWeavn remains engine/runtime language in
  developer-facing architecture only.
- The public release status remains `0.1.0` until a later release task updates
  assets and metadata.

Risks:

- Public docs may overpromise if Product 1.1 implemented work is described as
  generally available before a matching public release exists.
- Existing screenshots can mislead because several use old TaskWeavn/Taskwean
  branding and historical UI concepts.
- Public architecture diagrams can become stale if copied too close to private
  implementation detail.
- Release metadata currently references an old source branch/commit; future
  public release work should decide whether to preserve that provenance or
  publish refreshed metadata.
- Visual assets may require brand approval and regenerated screenshots before
  they are safe for public use.
