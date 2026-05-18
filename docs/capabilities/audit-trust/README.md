# Audit Trust Capability

> Status: planned
> Product Version: Plato 1.0
> Architecture Version: A1
> Owner Area: full-stack

## User Problem

Users need trust evidence: what Plato did, why it asked for confirmation, what changed, what failed, and where to inspect details.

## Current System Capability

- AuditAgent exists for CodeAction review.
- EventStream records actions/observations.
- MessageStream records user-facing messages.
- Structured observability and session archives exist.
- Main Page has audit link concepts.

## Target Capability

Plato has a user-facing Audit / Trust page that aggregates task evidence, action/observation history, risk/confirmation records, file changes, and relevant logs into readable timelines.

## Known Gaps

| Gap | Plan | Status | Notes |
|---|---|---|---|
| No Audit Page UI | unplanned | open | P0 trust surface. |
| No audit evidence projection API | unplanned | open | Needs aggregation across EventStream, MessageStream, logs, tasks. |
| AuditAgent scope is code-action centric | unplanned | open | 1.0 trust page needs broader task/session evidence. |
| No user-readable severity model | unplanned | open | Need labels that are useful without leaking internals. |

## Related Product Docs

- [Plato 1.0 Overview](../../product/versions/1.0/overview.md)
- [Plato 1.0 P0 Scope](../../product/versions/1.0/p0-scope.md)

## Related Architecture Docs

- [Current Architecture](../../architecture/current.md)
- [Architecture A1](../../architecture/versions/a1-product-1.0/overview.md)

## Legacy Sources

- [Interaction Layer](../../archive/legacy-2026-05-18/architecture/interaction-layer.md)
- [Configurable Logging System](../../archive/legacy-2026-05-18/architecture/configurable-logging-system.md)

## Related Code

- `src/taskweavn/audit/`
- `src/taskweavn/core/sqlite_event_stream.py`
- `src/taskweavn/observability/`

## Open Questions

- Should 1.0 Audit Page be session-first, task-first, or timeline-first?
- What evidence is useful to normal users vs testers?
