# Diagnostic Bundle Capability

> Status: planned
> Product Version: Plato 1.0
> Architecture Version: A1
> Owner Area: backend + release

## User Problem

Early testers need a safe way to send enough diagnostic information for debugging without exposing API keys, private files, or confusing raw logs.

## Current System Capability

- Structured logging supports categories, sinks, redaction, session archives, manifests, and hot updates.
- EventStream and MessageStream persist replayable facts.
- Packaging strategy names diagnostic bundle as a user-facing artifact.

## Target Capability

Plato can export a session diagnostic bundle containing manifests, selected logs, event/message metadata, configuration fingerprints, app version, and redacted failure context.

## Known Gaps

| Gap | Plan | Status | Notes |
|---|---|---|---|
| No bundle export command/service | unplanned | open | Need deterministic archive builder. |
| Redaction policy not productized | unplanned | open | Existing redaction exists, but bundle rules need hardening. |
| No UI entry | unplanned | open | Settings/About or error panel should expose export. |
| No clean failure template for testers | unplanned | open | Need user-readable bundle instructions. |

## Related Architecture Docs

- [Current Architecture](../../architecture/current.md)
- [Architecture A1](../../architecture/versions/a1-product-1.0/overview.md)

## Legacy Sources

- [Configurable Logging System](../../archive/legacy-2026-05-18/architecture/configurable-logging-system.md)

## Related Code

- `src/taskweavn/observability/`
- `src/taskweavn/core/sqlite_event_stream.py`
- `src/taskweavn/interaction/sqlite_message_stream.py`

## Open Questions

- Should bundles include workspace file diffs by default or only metadata?
- How strict should redaction be in trusted alpha vs broader beta?
