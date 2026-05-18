# Settings And First Run Capability

> Status: planned
> Product Version: Plato 1.0
> Architecture Version: A1
> Owner Area: full-stack

## User Problem

Non-developer users need to launch Plato, configure an LLM provider, choose a workspace location, test connectivity, and start without editing env vars or running CLI commands.

## Current System Capability

- LLM provider config can be loaded from environment variables.
- Provider abstraction, retry, DeepSeek thinking, and OpenRouter routing exist.
- Workspace/session layout exists.
- Logging config has same-process hot update infrastructure.

## Target Capability

Plato presents a first-run setup and Settings page for provider, API key, default model, workspace root, logging/debug profile, and basic safety/autonomy defaults.

## Known Gaps

| Gap | Plan | Status | Notes |
|---|---|---|---|
| No user-facing settings UI | unplanned | open | Needs first-run and later Settings surface. |
| No persistent product config store | unplanned feature package | planned | Needs global/workspace/session effective snapshots; legacy config plan archived. |
| No secure API key storage | unplanned | open | macOS Keychain preferred for packaged app. |
| No provider connectivity test API | unplanned | open | Required before non-technical alpha. |

## Related Product Docs

- [Plato 1.0 P0 Scope](../../product/versions/1.0/p0-scope.md)
- [Packaging Strategy](../../plans/release/packaging-and-distribution-strategy.md)

## Related Architecture Docs

- [Current Architecture](../../architecture/current.md)
- [Architecture A1](../../architecture/versions/a1-product-1.0/overview.md)

## Legacy Sources

- [Centralized Runtime Configuration](../../archive/legacy-2026-05-18/plans/feature/centralized-runtime-configuration.md)
- [LLM Provider Reliability](../../archive/legacy-2026-05-18/architecture/llm-provider-reliability.md)
- [Configurable Logging System](../../archive/legacy-2026-05-18/architecture/configurable-logging-system.md)

## Related Code

- `src/taskweavn/llm/config.py`
- `src/taskweavn/llm/providers/`
- `src/taskweavn/observability/`
- `src/taskweavn/core/workspace_layout.py`

## Open Questions

- Should API keys be stored only in Keychain, or allow local encrypted fallback?
- Which settings are first-run required vs advanced defaults?
