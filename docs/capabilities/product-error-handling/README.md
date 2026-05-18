# Product Error Handling Capability

> Status: planned
> Product Version: Plato 1.0
> Architecture Version: A1
> Owner Area: full-stack

## User Problem

When Plato fails, users need to know what happened, whether they can retry, what action to take, and whether diagnostic information is available.

## Current System Capability

- LLM provider errors and retry exhaustion are classified.
- Frontend shared API types include `ApiError` and query/command envelopes.
- Task and authoring command services return structured command errors in several places.
- Observability can record structured failure logs.

## Target Capability

Plato has a product-level error taxonomy and recovery UX covering provider setup, sidecar startup, command rejection, version conflict, task failure, audit inconclusive states, and diagnostic export.

## Known Gaps

| Gap | Plan | Status | Notes |
|---|---|---|---|
| No canonical product error model | unplanned | open | Needs contract and UI copy. |
| No sidecar startup failure UX | unplanned | open | Required for packaged app. |
| No consistent retry/resync guidance | unplanned | open | Current backend errors are not enough for users. |
| No link from errors to diagnostic bundle | unplanned | open | Important for alpha/beta support. |

## Related Contracts

- [UI Backend Contracts](../../contracts/ui-backend/)

## Related Code

- `frontend/src/shared/api/types.ts`
- `frontend/src/shared/api/client.ts`
- `src/taskweavn/llm/errors.py`
- `src/taskweavn/task/authoring_service.py`
- `src/taskweavn/task/publisher_service.py`

## Open Questions

- Which errors should be recoverable by the user vs only logged for diagnostics?
- Should failed Tasks display error cards, message stream entries, or both?
