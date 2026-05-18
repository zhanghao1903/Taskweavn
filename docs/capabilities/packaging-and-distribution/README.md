# Packaging And Distribution Capability

> Status: planned
> Product Version: Plato 1.0
> Architecture Version: A1
> Owner Area: release

## User Problem

Users should double-click Plato and start using it without cloning a repository, installing Python/npm dependencies, or starting frontend/backend manually.

## Current System Capability

- Packaging strategy is documented.
- Frontend is React/Vite.
- Backend is Python and can be packaged as a sidecar in principle.

## Target Capability

macOS Apple Silicon first: signed and notarized `Plato.app` / DMG with Electron frontend, Python sidecar, local auth token, app data directories, and clean startup/shutdown.

## Known Gaps

| Gap | Plan | Status | Notes |
|---|---|---|---|
| No Electron shell | [packaging strategy](../../plans/release/packaging-and-distribution-strategy.md) | planned | First release slice. |
| No Python sidecar executable | [packaging strategy](../../plans/release/packaging-and-distribution-strategy.md) | planned | PyInstaller baseline. |
| No app signing/notarization pipeline | [packaging strategy](../../plans/release/packaging-and-distribution-strategy.md) | planned | Needed beyond trusted alpha. |
| No local backend health/auth startup path | unplanned | open | Depends on sidecar API. |

## Related Plans

- [Packaging And Distribution Strategy](../../plans/release/packaging-and-distribution-strategy.md)

## Related Product Docs

- [Plato 1.0 P0 Scope](../../product/versions/1.0/p0-scope.md)

## Open Questions

- What minimum backend server framework should ship inside sidecar?
- When should notarization credentials be obtained relative to first trusted alpha?
