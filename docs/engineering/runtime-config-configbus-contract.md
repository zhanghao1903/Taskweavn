# Runtime Config ConfigBus Contract

> Status: C6.1-C6.2 implemented.
> Related Plan:
> [Centralized Runtime Configuration](../plans/feature/centralized-runtime-configuration.md)
> Related Store Contract:
> [Runtime Config Change Store](runtime-config-change-store.md)
> Last Updated: 2026-06-24

## 1. Purpose

C5 made runtime configuration changes durable and queryable. C6 defines how
accepted changes are announced to runtime consumers without pretending every
configuration key can update a running system immediately.

ConfigBus answers:

- which accepted runtime config change was published;
- which accepted keys are active now versus pending a future boundary;
- which consumers observed or applied the event;
- whether a consumer failed while handling the event;
- why non-live keys must not mutate already-running agents.

ConfigBus is an internal control-plane bus. It is not an HTTP API, Settings UI,
or app-specific automation playbook.

## 2. Non-Goals

- Do not add Settings UI.
- Do not expose remote runtime config writes.
- Do not hot-update already-running AgentLoop or Context Manager state.
- Do not make WeChat or other app procedures runtime config.
- Do not roll back durable config changes when a subscriber fails.
- Do not bypass `RuntimeConfigMutationService` validation.

## 3. Event Source

Only `DefaultRuntimeConfigMutationService.apply_patch(...)` may publish C6
events in the first implementation slice.

Publication rules:

- `accepted` non-dry-run changes publish `runtime_config.changed`.
- `rejected` changes do not publish.
- `no_op` changes do not publish.
- `dry_run=True` changes do not publish.
- idempotency replay does not publish a duplicate event.

Durable storage is authoritative. ConfigBus is best-effort propagation.

## 4. Event Model

```python
class RuntimeConfigBusEvent(RuntimeConfigModel):
    event_id: str
    event_type: Literal["runtime_config.changed"]
    change_id: str
    patch_id: str
    scope: RuntimeConfigScope
    actor: RuntimeConfigActor
    reason: str | None
    accepted_values: dict[str, Any]
    active_values: dict[str, Any]
    pending_values: dict[str, Any]
    effective_status_by_key: dict[str, RuntimeConfigEffectiveStatus]
    base_config_hash: str
    resulting_config_hash: str
    change_created_at: datetime
    published_at: datetime
```

Rules:

- `accepted_values` contains normalized non-secret accepted values.
- `active_values` is the subset whose effective status is `active`.
- `pending_values` is every accepted key whose effective status is not
  `active`.
- `resulting_config_hash` is required because only accepted changes publish.
- Event consumers must treat the hash as the identity of the effective config
  snapshot produced by the mutation service.

## 5. Mutability Handling

ConfigBus publishes all accepted keys so diagnostics can explain the change,
but live consumers may apply only `active_values`.

| Effective Status | C6 Consumer Rule |
|---|---|
| `active` | A live consumer may apply the value immediately. |
| `pending_next_context_build` | Do not mutate current context; apply when context is rebuilt. |
| `pending_next_llm_call` | Do not mutate current LLM call; apply on next call boundary. |
| `pending_next_action` | Do not mutate current action; apply before next action boundary. |
| `pending_next_agent_run` | Do not mutate running AgentLoop; apply to next agent run. |
| `pending_next_task` | Do not mutate current task; apply to next task. |
| `pending_next_session` | Do not mutate current session; apply to next session. |
| `pending_restart` | Do not apply until restart. |

Initial live-safe application is limited to `logging.level` when it is marked
`active` by the existing resolver. `logging.profile` remains deferred because
profile application needs clearer session/global scope semantics.

## 6. Consumer Boundary

Consumers subscribe with a stable `consumer_id` and a handler:

```python
RuntimeConfigBusHandler = Callable[
    [RuntimeConfigBusEvent],
    RuntimeConfigBusConsumerResult | None,
]
```

Consumer result:

```python
class RuntimeConfigBusConsumerResult(RuntimeConfigModel):
    consumer_id: str
    status: Literal["applied", "skipped", "failed"]
    applied_keys: tuple[str, ...]
    skipped_keys: tuple[str, ...]
    message: str | None
    error_type: str | None
```

Rules:

- Consumers must ignore unknown keys.
- Consumers must not apply `pending_values`.
- Consumers should return `skipped` when the event has no relevant active keys.
- Consumer failure is recorded in publication results and does not roll back the
  durable change.

## 7. Failure Behavior

ConfigBus is deliberately non-transactional:

1. Mutation service validates and persists the change.
2. Mutation service saves the resulting snapshot.
3. Mutation service publishes the accepted change.
4. Subscriber failures are captured as failed consumer results.
5. The original `RuntimeConfigChange` remains the return value.

This avoids a misleading state where durable config changed, but the caller
thinks the write failed because one optional live consumer failed.

## 8. Diagnostics And Audit

ConfigBus events are runtime facts, not the source of truth. Diagnostics and
Audit should primarily reference:

- `RuntimeConfigChange.change_id`;
- `RuntimeConfigChange.resulting_config_hash`;
- `RuntimeConfigSnapshotRecord.config_hash`;
- consumer results when an event publication is available.

Future diagnostics can expose the latest publication result, but Product 1.0
does not require a user-facing event stream for ConfigBus.

## 9. Implementation Slices

### C6.1 Internal Bus And Publication Boundary

Status: implemented.

- Added `RuntimeConfigBusEvent`.
- Added `RuntimeConfigBusConsumerResult`.
- Added `RuntimeConfigBusPublication`.
- Added `InMemoryRuntimeConfigBus`.
- Added optional mutation service publication for accepted non-dry-run changes.
- Added tests for active versus pending keys, subscriber failures, mutation
  publication, dry-run suppression, and idempotency replay suppression.

### C6.2 First Production Consumer

Status: implemented.

- Added `RuntimeConfigLoggingConsumer` in
  `src/taskweavn/observability/runtime_config_consumer.py`.
- Added `subscribe_runtime_config_logging_consumer(...)` for runtime assembly.
- Applies only active `logging.level` values through the existing
  `LoggingManager.set_level(...)` boundary.
- Records skipped keys explicitly for pending values and unsupported active
  keys such as `logging.profile`.
- Does not mutate AgentLoop, Context Manager, computer-use, or task API state.

### C6.3 Diagnostics Projection

Status: deferred.

- expose publication/consumer results in diagnostics only after a production
  consumer exists;
- keep Audit references tied to durable change/snapshot IDs.

## 10. Acceptance Criteria

- Accepted runtime config changes can publish a typed internal event.
- Rejected, no-op, dry-run, and idempotency replay paths do not duplicate
  runtime propagation.
- Consumers can distinguish active keys from pending keys.
- Consumer failure is observable without rolling back persisted config changes.
- Active `logging.level` changes have a live-safe consumer path.
- Running agents are not hot-mutated by C6.1-C6.2.
