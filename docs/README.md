# TaskWeavn Docs

> Status: active documentation entry
> Last Updated: 2026-05-19

This directory is organized by document responsibility, not by implementation
module.

The current V2 documentation model is intentionally narrow:

- no product version directory;
- no architecture version directory;
- active architecture remains the source of system facts;
- roadmap and gap registry coordinate planning;
- plans are executable work packages, not global product structure.

---

## 1. Start Here

| Need | Start With |
|---|---|
| What is the current system direction? | [Global Roadmap](roadmap.md) |
| What is the current execution queue? | [Project Plan](project/roadmap.md) |
| What gaps exist and how are they routed? | [Gap Registry](gaps/) |
| What architecture facts must a technical design obey? | [Architecture](architecture/) |
| What user/product experience is intended? | [Product Docs](product/) |
| What implementation plans exist? | [Plans](plans/) |
| What decisions are expensive to reverse? | [ADRs](decisions/) |
| What actually shipped? | [Release Records](releases/) |

---

## 2. Directory Map

| Directory / File | Responsibility |
|---|---|
| [architecture/](architecture/) | Active system facts, object boundaries, lifecycles, protocols, and technical constraints. Required reading before technical design. |
| [product/](product/) | Product intent, user mental models, PRDs, UX flows, and UI direction. |
| [roadmap.md](roadmap.md) | Phase-level direction and current sequencing. |
| [project/](project/) | Operational project plan and project-specific supporting docs. |
| [gaps/](gaps/) | Known capability gaps, priorities, status, architecture references, and plan routing. |
| [plans/](plans/) | Executable plans for selected gaps and implementation sessions. |
| [decisions/](decisions/) | Architecture/product/technology decisions that are costly to reverse. |
| [releases/](releases/) | Completed phase and feature-slice records. |
| [issues/](issues/) | Bug reports and defect-oriented repair plans. |
| [discussion/](discussion/) | Exploratory thinking before a plan or ADR exists. |
| [user_model/](user_model/) | User needs, scenarios, metrics, and traceability. |
| [user_cases/](user_cases/) | Formal user test cases and artifacts. |
| [assets/](assets/) | Shared images and media assets. |
| [archive/](archive/) | Generated exports and historical artifacts that are not canonical. |

---

## 3. Working Model

Use this chain when starting new work:

```text
Product intent + Architecture facts
  -> Roadmap priority
  -> Gap registry
  -> Plan package
  -> Implementation
  -> Release record
```

The chain is not meant to create bureaucracy. It prevents work from starting
from stale chat context or from a single isolated plan file.

---

## 4. Authority Rules

| Document Type | Authority |
|---|---|
| Product docs / PRD | Defines user intent and UX expectations. |
| Architecture docs | Defines active system facts and technical boundaries. |
| Roadmap | Defines sequencing and priority. |
| Gap registry | Defines known gaps and whether a plan exists. |
| Plans | Define how selected gaps are implemented. |
| Releases | Define what is actually done. |
| ADRs | Define durable decisions and consequences. |

If a plan conflicts with active architecture, update architecture or write an
ADR before implementation. If a release closes a gap, update the gap registry.

---

## 5. Compatibility Files

Some root-level files are kept as small "moved" stubs so older README links and
external bookmarks continue to work. New docs should link to the canonical
paths above.
