# Docs Operating Model

> Status: active
> Last Updated: 2026-05-18
> Maintained By: planning session
> Scope: docs organization, planning workflow, version governance, capability routing, and frontend/backend implementation boundaries
> Related: [Docs README](../README.md), [Project Roadmap](roadmap.md), [Global Roadmap](../roadmap.md), [Decisions](../decisions/), [Docs Migration Inventory](docs-migration-inventory.md)

---

## 1. Purpose

This document defines how TaskWeavn / Plato documentation should be organized and maintained as the project grows.

The goal is not to make `docs/` look tidy for its own sake. The goal is to make product work controllable:

- quickly understand what the system can do now;
- distinguish planned, active, deferred, and rejected capabilities;
- route product gaps to concrete plans or clearly mark them as unplanned;
- keep product versions aligned with architecture versions;
- let frontend, backend, contract, integration, and release work proceed in separate implementation sessions without losing one product story;
- preserve important decisions whose later reversal would be expensive.

This operating model is the control plane for planning sessions. Implementation sessions should be able to start from these docs without rereading long chat history.

---

## 2. Core Principles

### 2.1 Product Value First

Top-level planning is organized around user-facing capabilities, not implementation layers.

Good top-level plan names:

- `settings-and-first-run`
- `audit-trust-page`
- `main-page-real-backend`
- `diagnostic-bundle`
- `packaging-and-distribution`

Avoid top-level plans like:

- `frontend-settings`
- `backend-settings-api`
- `sqlite-audit-query`

Those are implementation work packages inside a product capability plan.

### 2.2 Contract First For Cross-Boundary Work

Whenever a feature crosses frontend/backend, the contract must be written before parallel implementation starts.

Frontend can then build against mocks that follow the contract. Backend can implement services and transport that satisfy the same contract. Integration should not become a late negotiation about object shape.

### 2.3 Capability Packets Over Document Searching

Important capabilities need a stable entry point under `docs/capabilities/`.

A capability packet does not duplicate every detail. It indexes the relevant product docs, architecture docs, contracts, plans, decisions, code modules, current status, and known gaps.

When starting work on a capability, the first document to read should be:

```text
docs/capabilities/<capability>/README.md
```

### 2.4 Versioned Product And Architecture

Product versions and architecture versions are related but not identical.

Example:

```text
Product 1.0 -> Architecture A1
Product 1.1 -> Architecture A1.1
Product 2.0 -> Architecture A2
```

Architecture versions should change when core object boundaries, communication protocols, execution lifecycles, capability boundaries, or storage model assumptions change.

### 2.5 Do Not Rewrite History Casually

Old docs are often valuable reasoning artifacts. Do not delete or rewrite them aggressively.

Prefer:

- mark as superseded;
- add compatibility stubs;
- move to archive when the canonical replacement is clear;
- create indexes that explain which doc is authoritative now.

---

## 3. Target Directory Model

The existing tree can migrate incrementally toward this model.

```text
docs/
  README.md

  product/
    README.md
    principles.md
    versions/
      1.0/
        overview.md
        p0-scope.md
        gap-analysis.md
        acceptance.md

  architecture/
    README.md
    current.md
    versions/
      a1-product-1.0/
        overview.md
        object-boundaries.md
        ui-backend-communication.md
        task-agent-model.md
        trust-audit.md

  capabilities/
    index.md
    <capability>/
      README.md
      status.md
      gaps.md
      references.md

  contracts/
    README.md
    ui-backend/
      main-page-snapshot.md
      task-authoring.md
      settings.md
      audit-trust.md
      events-sse.md
      error-model.md

  plans/
    README.md
    features/
      <feature>/
        overview.md
        contract.md
        frontend.md
        backend.md
        integration.md
        acceptance.md
    fixes/
    projects/
    release/

  decisions/
    README.md
    product/
    architecture/
    technology/

  releases/
  issues/
  discussion/
  user_cases/
  user_model/
  archive/
```

Legacy paths such as `docs/plans/feature/`, root-level broad plans, and old architecture files have been archived under `docs/archive/legacy-2026-05-18/`. New work should follow this model.

---

## 4. Document Roles

| Area | Primary Question | Canonical Responsibility |
|---|---|---|
| `docs/README.md` | Where do I start? | Global navigation, current version, active priorities. |
| `docs/product/` | What should users experience? | Product principles, user flows, version scopes, acceptance. |
| `docs/architecture/` | Why is the system shaped this way? | Core concepts, protocols, lifecycles, architecture versions. |
| `docs/capabilities/` | What can the system do? | Capability status, gaps, links to plans/contracts/code. |
| `docs/contracts/` | How do system boundaries talk? | UI/backend API, event, error, command, and viewmodel contracts. |
| `docs/plans/` | How will we implement one work package? | Scope, slices, frontend/backend work, tests, acceptance. |
| `docs/decisions/` | What expensive choices did we make? | Product, architecture, and technology decision records. |
| `docs/releases/` | What actually shipped? | Completed milestone summaries and deviations from plan. |
| `docs/issues/` | What is broken? | Bugs, reproduction, impact, repair plan, regression checks. |
| `docs/discussion/` | What is unresolved? | Exploratory thinking before plan or decision. |
| `docs/archive/` | What is historical? | Superseded or generated material kept for traceability. |

---

## 5. Capability Packets

### 5.1 Purpose

Capability packets solve the "related docs are scattered" problem.

Each important capability has one entry point:

```text
docs/capabilities/<capability>/README.md
```

Examples:

```text
docs/capabilities/task-authoring/README.md
docs/capabilities/ui-backend-communication/README.md
docs/capabilities/audit-trust/README.md
docs/capabilities/configuration/README.md
docs/capabilities/packaging/README.md
```

### 5.2 Required README Sections

Each capability README should include:

```md
# <Capability Name>

> Status: current | planned | active | deferred | not_now | wont_do
> Product Version: 1.0
> Architecture Version: A1
> Owner Area: frontend | backend | full-stack | release | product

## User Problem

## Current System Capability

## Target Capability

## Known Gaps

| Gap | Plan | Status | Notes |
|---|---|---|---|

## Related Product Docs

## Related Architecture Docs

## Related Contracts

## Related Plans

## Related Decisions

## Related Code

## Open Questions
```

### 5.3 Capability Status Values

| Status | Meaning |
|---|---|
| `current` | Implemented and considered part of the current system capability. |
| `active` | Currently being planned or implemented for the active product version. |
| `planned` | Planned for a future version or later slice. |
| `deferred` | Worth doing, but intentionally postponed. |
| `not_now` | Known user need, intentionally outside current product scope. |
| `wont_do` | Explicitly rejected unless assumptions change. |

### 5.4 Capability Index

`docs/capabilities/index.md` should be the system capability map.

Suggested columns:

| Capability | Current Status | Target Version | P0/P1/P2 | Gap Summary | Plan | Contract | Architecture |
|---|---|---|---|---|---|---|---|

This index should answer:

- what the system can do now;
- what is planned;
- what is intentionally not planned;
- whether every P0 gap has a routed plan.

---

## 6. Product Versions

### 6.1 Version States

| State | Meaning |
|---|---|
| `active` | Current product version being built. |
| `planned` | Future version with known goals but not active. |
| `maintenance` | Released version receiving fixes or small compatibility updates. |
| `retired` | Historical version no longer maintained. |

### 6.2 Product Version Package

Each active or planned product version should have a package:

```text
docs/product/versions/<version>/
  overview.md
  p0-scope.md
  gap-analysis.md
  acceptance.md
```

Recommended sections:

- user promise;
- target users;
- P0 / P1 / non-goals;
- capability map links;
- architecture version link;
- release criteria;
- known risks.

### 6.3 Gap Analysis

`gap-analysis.md` should map product requirements to current system reality:

| Requirement | Current Capability | Gap | Plan | Status | Acceptance |
|---|---|---|---|---|---|

Every P0 gap must either:

- link to a concrete plan;
- be marked `unplanned` with a reason;
- be removed from P0.

No silent P0 gaps.

---

## 7. Architecture Versions

### 7.1 Version Rule

Architecture should be versioned when one of these changes:

- core user interaction object;
- Task / Agent / Message / Tool boundary;
- UI/backend communication protocol;
- storage or replay model;
- capability boundary;
- trust/audit model;
- execution lifecycle;
- release/runtime architecture.

### 7.2 Architecture Version Package

```text
docs/architecture/versions/<architecture-version>/
  overview.md
  object-boundaries.md
  protocol-boundaries.md
  lifecycle.md
  storage-and-replay.md
  trust-and-audit.md
  product-version-link.md
```

The current architecture version should be linked from:

- product version overview;
- capability packets;
- relevant plans;
- decision records.

### 7.3 Current Pointer

`docs/architecture/current.md` should point to the active architecture version and explain whether older architecture docs are:

- still canonical;
- partially superseded;
- historical reference only.

---

## 8. Decision Records

### 8.1 Decision Types

Important decisions should be recorded when reversal would be expensive.

Use three decision families:

| Type | Meaning | Example |
|---|---|---|
| PDR | Product Decision Record | Task-first UI, local-first positioning, no multi-user in 1.0. |
| ADR | Architecture Decision Record | Two-stream event/message design, TaskBus boundary, authoring command protocol. |
| TDR | Technology Decision Record | Electron + Python sidecar, DeepSeek provider SDK, SQLite storage. |

The existing `ADR-*.md` files remain valid. New decision organization can be introduced incrementally.

Target structure:

```text
docs/decisions/
  index.md
  product/PDR-0001-task-first-ui.md
  architecture/ADR-0001-two-stream-architecture.md
  technology/TDR-0001-electron-python-sidecar.md
```

### 8.2 Decision Header

Each decision should include:

```md
> Status: proposed | accepted | superseded | rejected
> Date: YYYY-MM-DD
> Product Version: 1.0
> Architecture Version: A1
> Capability: audit-trust
> Affects: frontend, backend, release
> Supersedes: optional
```

### 8.3 When To Write A Decision

Write a decision record when the project chooses:

- a product principle or non-goal;
- a core system boundary;
- a long-lived protocol;
- a storage model;
- a release/runtime architecture;
- a technology choice with switching cost;
- a simplification that intentionally rejects a tempting capability.

Do not write decision records for routine implementation details.

---

## 9. Plans

### 9.1 Product Capability Plans

Top-level feature plans should be organized around user capability:

```text
docs/plans/features/<feature>/
  overview.md
  contract.md
  frontend.md
  backend.md
  integration.md
  acceptance.md
```

If a feature is backend-only or frontend-only, it may omit irrelevant files.

### 9.2 Plan File Roles

| File | Purpose |
|---|---|
| `overview.md` | User problem, scope, non-goals, priority, related capability, related version. |
| `contract.md` | API, command, event, error, schema, idempotency, and state contract. |
| `frontend.md` | UI states, components, local state, mocks, accessibility, visual acceptance. |
| `backend.md` | Domain services, storage, migrations, runtime behavior, tests. |
| `integration.md` | End-to-end flow, SSE/WebSocket, sidecar startup, failure recovery, telemetry. |
| `acceptance.md` | User-facing and technical acceptance checklist. |

### 9.3 Work Session Context Rule

Implementation sessions should read the smallest sufficient set:

Frontend session:

```text
overview.md
contract.md
frontend.md
acceptance.md
```

Backend session:

```text
overview.md
contract.md
backend.md
acceptance.md
```

Integration session:

```text
overview.md
contract.md
integration.md
acceptance.md
```

This keeps AI and human context smaller while preserving one product-level plan.

### 9.4 Plan Status

| Status | Meaning |
|---|---|
| `draft` | Being shaped; not ready for implementation. |
| `planned` | Ready to execute in another session. |
| `in_progress` | Implementation session is active. |
| `blocked` | Waiting for decision, dependency, or missing information. |
| `done` | Implemented, verified, and docs updated. |
| `cancelled` | Abandoned without replacement. |
| `superseded` | Replaced by another plan. |

---

## 10. Contracts

### 10.1 Contract Authority

`docs/contracts/` is the long-lived authority for stable boundary contracts.

Feature plan `contract.md` files are proposals or deltas. Once a feature is completed, stable contract changes should be merged back into `docs/contracts/`.

### 10.2 UI/Backend Contract Minimum

Each UI/backend contract should cover:

- query APIs;
- command APIs;
- event stream / SSE / subscription semantics;
- viewmodel shape;
- loading, empty, partial, and failed states;
- idempotency;
- optimistic update rules, if any;
- version conflict behavior;
- error model;
- example request and response;
- compatibility and migration notes.

### 10.3 Contract Change Rule

If a backend implementation changes UI-visible shape, it must update the relevant contract before or with the implementation plan completion.

If frontend needs a new field, state, or command, it should update the contract before backend implementation starts.

---

## 11. Issues

Bug and defect work belongs under `docs/issues/`.

Issue docs should include:

- impact;
- reproduction steps;
- expected behavior;
- actual behavior;
- suspected area;
- repair plan;
- regression tests;
- status;
- linked capability, if applicable.

If a bug reveals a missing capability or architecture problem, link the issue from the relevant capability packet.

---

## 12. Releases

Release records describe what actually happened.

Use releases for:

- completed phase slices;
- completed feature packages;
- product alpha/beta milestones;
- packaging milestones.

Release records should include:

- scope completed;
- commits / branches / PRs, if known;
- tests and verification;
- deviations from plan;
- follow-up gaps;
- affected capabilities;
- affected product/architecture versions.

---

## 13. Planning Workflow

### 13.1 Default Flow

```text
Discussion
  -> Decision, if an expensive choice is made
  -> Plan, if executable work is needed
  -> Contract, if boundaries are affected
  -> Implementation in another session
  -> Review
  -> Release / Capability / Roadmap updates
```

### 13.2 Entry Routing

When a new topic appears:

| Topic Shape | Route |
|---|---|
| Unclear idea or product concern | `docs/discussion/` |
| Product scope / user experience choice | `docs/decisions/product/` or product version docs |
| Architecture boundary choice | `docs/decisions/architecture/` and architecture docs |
| Technology choice | `docs/decisions/technology/` |
| User-facing feature | `docs/plans/features/<feature>/` |
| Bug or defect | `docs/issues/` |
| Release or packaging operation | `docs/plans/release/` |
| Capability status / gap | `docs/capabilities/<capability>/` |

### 13.3 Completion Checklist

When a plan is done, update:

1. original plan status and actual result;
2. capability packet status and gaps;
3. product version gap analysis, if P0/P1 changed;
4. contract docs, if boundary changed;
5. decision records, if a choice was made or reversed;
6. release record, if a milestone or meaningful feature completed;
7. roadmap, if sequence or priorities changed.

Do not mark a plan `done` if its related capability and product gap docs still say it is missing.

---

## 14. Migration Strategy

Do not attempt a single large docs migration unless explicitly planned.

Recommended migration order:

1. Establish this operating model.
2. Create `docs/capabilities/index.md`.
3. Create first capability packets for 1.0 P0 capabilities.
4. Create `docs/product/versions/1.0/`.
5. Create `docs/contracts/README.md` and initial UI/backend contract files.
6. Add `docs/architecture/current.md`.
7. Migrate high-value plans into feature plan packages.
8. Mark old plan docs as canonical, superseded, or historical.

During migration, preserve old links with small stubs when moving canonical files.

---

## 15. 1.0 Initial Capability Packet Candidates

The first capability packets should likely be:

| Capability | Reason |
|---|---|
| `main-page-real-backend` | Establishes the canonical Main Page source and connects it to a real product backend. |
| `settings-and-first-run` | Required for non-developer users to configure LLM and workspace. |
| `task-authoring` | Core Plato workflow: natural language to Task Tree. |
| `task-execution` | Published Tasks must actually run and update UI state. |
| `message-and-confirmation` | Human-in-the-loop interaction is central to product trust. |
| `audit-trust` | User trust and inspection surface. |
| `file-change-summary` | Task-centered file visibility and parent-child aggregation. |
| `diagnostic-bundle` | Early tester support and failure investigation. |
| `product-error-handling` | Recoverable user-facing failure states, retry/resync guidance, and diagnostic handoff. |
| `packaging-and-distribution` | macOS app delivery and signing. |
| `configuration-control-plane` | Centralized, layered, hot-updatable runtime config. |

These packets should link back to existing product, architecture, plan, and release docs instead of duplicating them.

---

## 16. Operating Rules Summary

1. Product plans are organized by user capability.
2. Implementation details are split inside feature plans.
3. Cross-boundary work starts from contracts.
4. Capabilities have stable entry points.
5. Product versions bind to architecture versions.
6. Expensive choices become decision records.
7. Completed plans update capability, gap, contract, roadmap, and release docs as needed.
8. Old docs are migrated incrementally, not erased in bulk.
9. Planning sessions produce docs; implementation sessions consume them.
10. The purpose of docs is to protect product quality, not to maximize documentation volume.
