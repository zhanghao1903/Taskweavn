# ADR-0004: Docs Governance For The Planning Session

> Status: accepted
> Date: 2026-05-11
> Related: [Docs Operating Model](../../project/docs-operating-model.md), [Roadmap](../../roadmap.md), [Project Plan](../../project/roadmap.md), [Release Records](../../releases/)

---

## Context

This conversation is now the project planning and global overview session. Implementation, bug fixes, and experiments happen in other sessions. The planning session produces and maintains docs under `docs/`.

As the project grows, plans alone are not enough:

- the phase roadmap can drift;
- architecture decisions can be buried inside long plan files;
- completed work can be hard to reconstruct;
- implementation sessions need a stable way to know what changed after a plan is done.

---

## Decision

Use four document types as the planning control plane:

| Document Type | Path | Purpose |
|---|---|---|
| Roadmap | `docs/roadmap.md` | Phase-level route and priority sequencing. |
| Project plan | `docs/project/roadmap.md` | More operational plan with completed baseline and next work queue. |
| Decision records | `docs/decisions/{product,architecture,technology}/` | Important product, architecture, and technology decisions. |
| Releases | `docs/releases/` | Completed phase/milestone summaries and change records. |

When a plan is completed, update:

1. the original plan file;
2. the project plan if status or priority changed;
3. the global roadmap if sequencing changed;
4. ADRs if a decision was made or reversed;
5. release notes if a phase or milestone completed.

---

## Consequences

Positive:

- The planning session has a durable memory.
- Implementation sessions can start from current docs instead of chat history.
- Important decisions are easier to revisit.
- Completed work has a readable project history.

Trade-offs:

- More docs need maintenance.
- Some changes will require touching several docs.
- The planning session must stay disciplined about status updates.
