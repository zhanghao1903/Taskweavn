# Configuration Control Plane Capability

> Status: planned
> Product Version: Plato 1.0
> Architecture Version: A1
> Owner Area: backend + frontend

## User Problem

Plato has many settings that shape user experience: provider, model, autonomy, audit strength, logging, workspace, and task/session defaults. Users and testers need safe layered configuration with clear defaults and hot updates where appropriate.

## Current System Capability

- LLM provider config exists through environment variables.
- Observability has structured config, session overrides, and same-process hot update.
- Autonomy presets exist.

## Target Capability

Centralized runtime configuration supports global, workspace, session, and possibly task-level overrides. Effective snapshots are auditable and can be used by UI, agents, logging, provider selection, and safety gates.

## Known Gaps

| Gap | Plan | Status | Notes |
|---|---|---|---|
| No general config store | unplanned feature package | planned | Core backend gap; legacy plan archived. |
| No config bus / hot update protocol | unplanned feature package | planned | Logging has feature-local control; legacy plan archived. |
| No Settings UI contract | unplanned | open | Required for first-run/settings. |
| No user-facing config hierarchy model | unplanned | open | Need simple product language. |

## Related Architecture Docs

- [Current Architecture](../../architecture/current.md)
- [Architecture A1](../../architecture/versions/a1-product-1.0/overview.md)

## Related Plans

- Needs new feature package under `docs/plans/features/configuration-control-plane/`.

## Legacy Sources

- [Centralized Runtime Configuration](../../archive/legacy-2026-05-18/plans/feature/centralized-runtime-configuration.md)
- [Configurable Logging System](../../archive/legacy-2026-05-18/architecture/configurable-logging-system.md)
- [LLM Provider Reliability](../../archive/legacy-2026-05-18/architecture/llm-provider-reliability.md)

## Related Code

- `src/taskweavn/llm/config.py`
- `src/taskweavn/interaction/autonomy.py`
- `src/taskweavn/observability/`

## Open Questions

- Which settings are safe to hot update during execution?
- Should task-level config exist in Plato 1.0 or remain architecture reserve?
