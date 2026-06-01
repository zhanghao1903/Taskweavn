# Task-first UI Design Docs

This directory contains the Task-first UI planning documents.

> Status note:
> This directory is an early Task-first UI planning archive. It remains useful
> for object-level reasoning, but the current Plato UI implementation line is:
>
> ```text
> Figma UI baseline 1.0 reference
>   -> governed canonical Figma file
>   -> docs/product/plato-main-page-ux-flow.md
>   -> docs/product/plato-frontend-technical-design.md
> ```
>
> Documents in this directory should not be treated as current implementation
> specs unless a new plan explicitly references them.
> New Figma work must follow `docs/design/figma-governance.md`.

## Overview

| File | Purpose |
|---|---|
| [frontend-framework-design.md](frontend-framework-design.md) | Superseded frontend framework plan. Use [Plato Frontend Technical Design](../../product/plato-frontend-technical-design.md). |
| [page-project-implementation-template.md](page-project-implementation-template.md) | Reusable end-to-end workflow template for creating a new UI page from PRD through user testing. |
| [main-page-project-implementation-plan.md](main-page-project-implementation-plan.md) | End-to-end Main Page project plan from PRD through UX, Figma, mock UI, API contract, backend integration, and user testing. |
| [audit-page-project-implementation-plan.md](audit-page-project-implementation-plan.md) | End-to-end Audit Page project plan from PRD through UX, Figma, mock UI, API contract, backend integration, and user testing. |
| [audit-page-sanitized-payload-disclosure-technical-design.md](audit-page-sanitized-payload-disclosure-technical-design.md) | AP-012B technical design for safe Audit Page record/evidence payload disclosure; AP-012 first pass now uses it for request-time sanitized detail/evidence rendering. |
| [audit-page-runtime-event-refetch-technical-design.md](audit-page-runtime-event-refetch-technical-design.md) | AP-013A technical design for Audit Page runtime event subscription, scope-aware refetch, stale/resync handling, and backend event emission slices. |
| [visual-reference.md](visual-reference.md) | Historical visual sketches and prototype screenshots. Current canonical Figma work is governed by `docs/design/figma-governance.md`. |
| [ui-api-interfaces.md](ui-api-interfaces.md) | Shared UI API and view model interface archive. |
| [information-architecture.md](information-architecture.md) | Main layout regions and information hierarchy. |
| [task-generation-flow.md](task-generation-flow.md) | Natural language to Task Tree List flow. |
| [task-tree-view.md](task-tree-view.md) | Task tree / topology display rules. |
| [task-node-detail.md](task-node-detail.md) | Selected Task Node detail panel. |
| [task-message-view.md](task-message-view.md) | Task-scoped message view over the Session Message Stream. |
| [session-message-stream.md](session-message-stream.md) | Session-level message stream. |
| [confirmation-actions.md](confirmation-actions.md) | User confirmation action design. |
| [task-editing-rules.md](task-editing-rules.md) | State-based Task editing rules. |
| [file-change-summary.md](file-change-summary.md) | Task-based file change summaries. |
| [task-scoped-chat-flow.md](task-scoped-chat-flow.md) | Selected Task local chat workflow. |

## UI Page Delivery Workflow

Important Plato UI pages must follow this delivery workflow:

```text
Product PRD
  -> UX interaction spec
  -> Figma design / prototype
  -> design review and refinement
  -> UI component code
  -> mock data integration
  -> backend API contract
  -> real backend communication
  -> user testing
  -> iteration
```

This workflow is the gate for page-level product work. A page may have a
technical spike or throwaway prototype before Figma, but production UI code
should not begin until:

1. the page PRD exists;
2. the UX interaction spec exists;
3. Figma v0.1 covers the required page states;
4. design review has recorded P0/P1 decisions.

If a session intentionally skips one of these gates, the relevant page plan must
say why and mark the work as a spike, not as production UI implementation.

For a reusable template, start from
[page-project-implementation-template.md](page-project-implementation-template.md).

## Assets

Visual references live under [images/](images/). They are working sketches, not final UI specs.
