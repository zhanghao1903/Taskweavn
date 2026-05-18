# Task Authoring Capability

> Status: current / active
> Product Version: Plato 1.0
> Architecture Version: A1
> Owner Area: backend + frontend

## User Problem

Users express goals in natural language. Plato must turn those goals into understandable, editable, and publishable Task Tree Lists.

## Current System Capability

- RawTask, feasibility report, clarification ask/answer, DraftTaskTree, and Authoring Command Protocol exist.
- Collaborator Agent server-core flow exists.
- Draft task trees can be generated and refined through structured commands.
- User/collaborator interactions are designed to be replayable.

## Target Capability

Users can create a RawTask from natural language, answer clarification questions, review a Draft TaskTree, edit selected TaskNodes, and publish when ready.

## Known Gaps

| Gap | Plan | Status | Notes |
|---|---|---|---|
| Authoring UI not connected to backend | unplanned | open | Main Page real backend plan should cover this. |
| Persistent authoring stores need product path | partial | open | Current server-core uses in-memory first boundaries in places. |
| First-run capability disclosure not visible | unplanned | open | Collaborator needs user-readable capability boundaries. |
| Contract needs stable transport form | unplanned | open | Existing adapter contracts need UI/backend contract consolidation. |

## Related Architecture Docs

- [Current Architecture](../../architecture/current.md)
- [Architecture A1](../../architecture/versions/a1-product-1.0/overview.md)
- [UI Backend Contracts](../../contracts/ui-backend/)

## Related Plans

- New UI/backend integration work should be created under `docs/plans/features/`.

## Legacy Sources

- [Authoring Domain](../../archive/legacy-2026-05-18/architecture/authoring-domain.md)
- [Authoring Command Protocol](../../archive/legacy-2026-05-18/architecture/authoring-command-protocol.md)
- [Collaborator Agent Task Authoring](../../archive/legacy-2026-05-18/architecture/collaborator-agent-task-authoring.md)
- [Tool Capability Layer](../../archive/legacy-2026-05-18/architecture/tool-capability-layer.md)
- [Legacy Collaborator Plan](../../archive/legacy-2026-05-18/plans/feature/collaborator-agent-task-authoring.md)
- [Legacy Task Domain/UI Plan](../../archive/legacy-2026-05-18/plans/feature/task-domain-ui-model-separation.md)

## Related Code

- `src/taskweavn/task/authoring.py`
- `src/taskweavn/task/authoring_service.py`
- `src/taskweavn/task/collaborator.py`
- `src/taskweavn/task/collaborator_api.py`
- `src/taskweavn/task/stores.py`

## Open Questions

- How much feasibility detail should UI expose before overwhelming first-time users?
- Should structured TaskTree import be exposed in 1.0 or kept as internal/API-only?
