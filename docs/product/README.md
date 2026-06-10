# Product Docs

Product docs describe Plato, the user-facing product layer of TaskWeavn, from
the user's point of view.

They are intentionally separate from architecture docs:

- Architecture docs explain how the system is built.
- Product docs explain what users believe they are using, what objects they can
  act on, and which interaction principles must stay stable across UI changes.
- Roadmap and [Gap Registry](../gaps/) decide sequencing and plan routing.
- Plans under [../plans/](../plans/) describe how selected work is executed.

Product docs are active product intent sources. They are not archives, but they
also do not replace architecture facts or project scheduling.

| File | Purpose |
|---|---|
| [public-exposure/](public-exposure/) | Public-facing Plato exposure planning: product/architecture disclosure strategy, public repository information architecture, and visual asset gap tracking. |
| [core-product-principles.md](core-product-principles.md) | Product-level principles: Task-first, Workflow-first entry, Draft before execution, Main Page vs Audit Page. |
| [plato-task-semantics.md](plato-task-semantics.md) | Core Task semantics: Task as user-visible work contract, and the Intent / Plan / Execution / Evidence layers that UI must make perceptible. |
| [plato-session-content-model.md](plato-session-content-model.md) | Session content model: typed collaboration record, Session / Plan / Task scopes, Activity boundaries, and raw chat exclusion. |
| [plato-runtime-input-model.md](plato-runtime-input-model.md) | Runtime input model: one natural language input surface with internal question / guidance / command / ASK / confirmation routing. |
| [plato-plan-cycle-semantics.md](plato-plan-cycle-semantics.md) | Plan Cycle semantics: one round of authoring, execution, outcome review, acceptance, and follow-up planning inside a Session. |
| [plato-outcome-review-model.md](plato-outcome-review-model.md) | Outcome Review model: acceptance workspace information structure after Plan execution, including result, task outcome map, workspace changes, risks, and next actions. |
| [canonical-status-model.md](canonical-status-model.md) | Canonical product status dimensions for planning, readiness, execution, confirmation, permissions/actions, and audit verdicts. |
| [workflow-session-task-ux-model.md](workflow-session-task-ux-model.md) | User-facing object model and UX lifecycles for Workflow, Session, TaskTree, TaskNode, Agent routing, Result, and Audit. |
| [plato-audit-page-prd.md](plato-audit-page-prd.md) | Product requirements for Plato Audit Page as the Trust Plane for Session and Task traceability. |
| [plato-audit-page-ux-flow.md](plato-audit-page-ux-flow.md) | UX interaction specification for Audit Page entry, scope, overview, filters, records, details, and edge states. |
| [plato-settings-logs-audit-boundary.md](plato-settings-logs-audit-boundary.md) | Product boundary for Settings, configuration change history, Diagnostics / Logs, and Audit Page reserved links. |
| [plato-brand-and-ux-direction.md](plato-brand-and-ux-direction.md) | User-facing product name, naming boundary, tone, and first UX direction for Plato. |
| [plato-design-philosophy-style-guide.md](plato-design-philosophy-style-guide.md) | Design philosophy, visual principles, interaction tone, color direction, typography, and UI style guardrails for Plato. |
| [plato-mvp-implementation-plan.md](plato-mvp-implementation-plan.md) | MVP implementation workflow from PRD to UX flow, Figma UI baseline, frontend technical design, API contract, backend integration, and user testing. |
| [plato-mvp-prd.md](plato-mvp-prd.md) | MVP product requirements: user, scope, main flows, requirements, non-goals, success criteria, and PRD-to-UX handoff. |
| [plato-1-0-line-first-authoring-policy.md](plato-1-0-line-first-authoring-policy.md) | Plato 1.0 policy baseline: line-first authoring UX, single-task/single-agent defaults, and complexity-hiding rules. |
| [plato-1-0-frontend-qa-runbook.md](plato-1-0-frontend-qa-runbook.md) | Accepted Product 1.0 local unsigned RC QA runbook for Main Page, Settings first-run, Audit Page, Diagnostics, product-error recovery, packaged Electron, and mounted unsigned DMG evidence. |
| [plato-1-0-frontend-qa-notes-2026-06-03.md](plato-1-0-frontend-qa-notes-2026-06-03.md) | Product 1.0 local sidecar HTTP frontend QA notes: Main Page, Audit Page, P0/P1 issue list, and first user-test readiness decision. |
| [plato-1-0-frontend-qa-notes-2026-06-06.md](plato-1-0-frontend-qa-notes-2026-06-06.md) | Product 1.0 frontend acceptance notes: real sidecar Audit, Diagnostics, Settings, command failure recovery labels, browser smoke, Electron gap, and action-label decision. |
| [plato-1-1-product-plan.md](plato-1-1-product-plan.md) | Product 1.1 planning baseline: items moved out of 1.0, plus skills, MCP, file, and multimodal research themes. |
| [plato-1-1-workspace-aware-agent-foundation.md](plato-1-1-workspace-aware-agent-foundation.md) | Product 1.1 focus memo: narrows the next increment around git/diff, file viewing, precision tools, runtime input modes, inquiry mode, skills contract, and context boundaries. |
| [plato-main-page-ux-flow.md](plato-main-page-ux-flow.md) | Main Page UX flow spec: key screen states, task interactions, confirmation flow, result/file/audit visibility, and Figma input. |
| [plato-figma-ui-baseline.md](plato-figma-ui-baseline.md) | Historical/reference Figma UI baseline 1.0 record: target file, screen list, visual direction, sample data, and implementation handoff notes. |
| [plato-frontend-technical-design.md](plato-frontend-technical-design.md) | Frontend technical design: governed Figma reference, technology selection, architecture, state/API boundaries, implementation slices, and risks. |
| [plato-ui-api-contract.md](plato-ui-api-contract.md) | Plato Main Page 1.0 UI API contract: snapshot, ViewModel, command, event, frontend adapter, and F6 backend integration boundaries. |
