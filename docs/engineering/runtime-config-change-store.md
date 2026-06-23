# Runtime Config Change Store Contract

> Status: C5 design accepted for implementation planning; runtime mutation not
> implemented.
> Related Plan:
> [Centralized Runtime Configuration](../plans/feature/centralized-runtime-configuration.md)
> Related Product Boundary:
> [Settings, Logs, And Audit Boundary](../product/plato-settings-logs-audit-boundary.md)
> Last Updated: 2026-06-24

## 1. Purpose

C1-C4 made runtime configuration queryable, explainable, and consumable by the
current Main Page runtime assembly. C5 defines the durable write-side boundary
needed before runtime config can become editable.

The Config Change Store must answer:

- who requested a config change;
- which scope the change targets;
- which keys were accepted, rejected, or deferred;
- which effective config snapshot was produced before and after the change;
- when the change becomes effective according to each key's mutability;
- which execution/context/audit traces can reference the effective config hash.

This store is a control-plane ledger. It is not the hot-update mechanism. C6
will decide which accepted changes publish ConfigBus events and which consumers
can apply them live.

## 2. Scope

In scope for C5:

- durable `RuntimeConfigChange` records;
- durable `EffectiveRuntimeConfig` snapshot records;
- patch validation rules;
- accepted / rejected / no-op / pending semantics;
- scope validation;
- mutation boundary metadata;
- secret/redaction rules;
- query model for Settings, Diagnostics, and Audit evidence.

Out of scope for C5:

- Settings UI;
- HTTP write routes;
- live ConfigBus publication;
- applying patches to running components;
- app-specific playbooks such as WeChat send behavior;
- secret storage or API key editing.

## 3. Current Implementation Baseline

Current runtime config models live in `src/taskweavn/runtime_config/`.

Important existing facts:

- `RuntimeConfigKey` declares key metadata, supported scope levels,
  mutability, value type, and secret/restart metadata.
- `RuntimeConfigLayer` represents one source layer.
- `RuntimeConfigResolver` merges built-in defaults plus supplied layers.
- `RuntimeConfigSourceKind` already includes `runtime_patch`.
- `_effective_status(...)` already maps `runtime_patch` + mutability to
  pending statuses such as `pending_next_agent_run` or `pending_restart`.
- C4.4 records `runtime_config_hash` in context/execution trace metadata.

C5 should reuse those concepts. It should not introduce a second scope,
mutability, or effective-status vocabulary.

## 4. Source-Of-Truth Hierarchy

C5 introduces durable user/system patches as another source layer:

```text
built_in_default
  -> settings_store / workspace_file / session_override / task_override
  -> runtime_patch ledger entries accepted for the requested scope
  -> environment / cli / process_input
```

Process startup sources keep higher priority for now. That preserves local
developer/operator expectations:

- CLI/env can force a process behavior for the current sidecar launch;
- durable settings can explain intended workspace/session behavior;
- startup-only process facts such as host, port, and selected computer-use
  backend are not silently changed by a stored workspace patch.

C5 must record this priority explicitly in `RuntimeConfigChange`; a change may
be accepted into the store but not win effective resolution if a higher-priority
process source overrides it.

## 5. Data Model

### 5.1 RuntimeConfigPatch

```python
class RuntimeConfigPatch(RuntimeConfigModel):
    patch_id: str
    idempotency_key: str | None
    scope: RuntimeConfigScope
    actor: RuntimeConfigActor
    reason: str | None
    values: dict[str, Any]
    expected_base_config_hash: str | None
    dry_run: bool = False
    requested_at: datetime
```

Rules:

- `values` is a sparse key/value patch, not a full config snapshot.
- `expected_base_config_hash` is optional for first implementation but required
  by UI clients that want optimistic concurrency later.
- `dry_run=True` validates and resolves without storing a change.

### 5.2 RuntimeConfigActor

```python
class RuntimeConfigActor(RuntimeConfigModel):
    actor_type: Literal["user", "system", "test", "migration"]
    actor_id: str | None
    display_name: str | None
```

The actor object is audit metadata. It does not authorize the change by itself.
Authorization belongs to the future write API / Settings boundary.

### 5.3 RuntimeConfigChange

```python
class RuntimeConfigChange(RuntimeConfigModel):
    change_id: str
    patch_id: str
    idempotency_key: str | None
    scope: RuntimeConfigScope
    actor: RuntimeConfigActor
    reason: str | None
    status: Literal["accepted", "rejected", "no_op"]
    requested_values: dict[str, Any]
    accepted_values: dict[str, Any]
    rejected_values: dict[str, RuntimeConfigRejection]
    base_config_hash: str
    resulting_config_hash: str | None
    effective_status_by_key: dict[str, RuntimeConfigEffectiveStatus]
    created_at: datetime
```

Rules:

- `requested_values` stores redacted values for secret keys only.
- `accepted_values` stores normalized accepted values for non-secret keys.
- `rejected_values` is keyed by config key.
- `resulting_config_hash` is `None` when the change is rejected.
- `no_op` means all requested values normalize to the same effective values at
  the requested scope.

### 5.4 RuntimeConfigRejection

```python
class RuntimeConfigRejection(RuntimeConfigModel):
    code: Literal[
        "unknown_key",
        "unsupported_scope",
        "invalid_value",
        "secret_not_patchable",
        "startup_only_not_patchable",
        "stale_base_config",
        "higher_priority_source_active",
        "policy_denied",
    ]
    message: str
    details: dict[str, Any] = {}
```

Notes:

- `startup_only_not_patchable` should be used only for write paths that choose
  not to store startup-only patches. The preferred C5 behavior is to accept
  startup-only values as stored intent and mark them `pending_restart`, unless
  the key is process-only and not safe to persist.
- `higher_priority_source_active` should be a warning-like rejection only when
  the patch cannot ever become effective under the current source priority.

### 5.5 RuntimeConfigSnapshotRecord

```python
class RuntimeConfigSnapshotRecord(RuntimeConfigModel):
    snapshot_id: str
    config_hash: str
    scope: RuntimeConfigScope
    effective_config: EffectiveRuntimeConfig
    created_by_change_id: str | None
    created_at: datetime
```

Rules:

- Store the full `EffectiveRuntimeConfig` JSON for reproducibility.
- Do not store unredacted secret values.
- A snapshot can be created by resolution without a change, for example at
  sidecar startup or agent-run start.

## 6. Storage Model

Recommended SQLite tables:

### `runtime_config_changes`

| Column | Type | Notes |
|---|---|---|
| `change_id` | TEXT PRIMARY KEY | Stable generated ID. |
| `patch_id` | TEXT NOT NULL | Request-level patch ID. |
| `idempotency_key` | TEXT NULL | Unique with scope when supplied. |
| `scope_level` | TEXT NOT NULL | From `RuntimeConfigScope`. |
| `workspace_id` | TEXT NULL | Scope discriminator. |
| `session_id` | TEXT NULL | Scope discriminator. |
| `task_id` | TEXT NULL | Scope discriminator. |
| `agent_run_id` | TEXT NULL | Scope discriminator. |
| `actor_json` | TEXT NOT NULL | Actor metadata JSON. |
| `reason` | TEXT NULL | Human/system reason. |
| `status` | TEXT NOT NULL | accepted/rejected/no_op. |
| `requested_values_json` | TEXT NOT NULL | Redacted normalized payload. |
| `accepted_values_json` | TEXT NOT NULL | Accepted normalized payload. |
| `rejected_values_json` | TEXT NOT NULL | Rejections by key. |
| `base_config_hash` | TEXT NOT NULL | Effective hash before patch. |
| `resulting_config_hash` | TEXT NULL | Effective hash after accepted patch. |
| `effective_status_json` | TEXT NOT NULL | Per-key effective statuses. |
| `created_at` | TEXT NOT NULL | UTC ISO timestamp. |

Indexes:

- `(scope_level, workspace_id, session_id, task_id, agent_run_id, created_at)`
- `(idempotency_key, scope_level, workspace_id, session_id, task_id)` unique
  where `idempotency_key IS NOT NULL`
- `(resulting_config_hash)`

### `runtime_config_snapshots`

| Column | Type | Notes |
|---|---|---|
| `snapshot_id` | TEXT PRIMARY KEY | Stable generated ID. |
| `config_hash` | TEXT NOT NULL | Effective config hash. |
| `scope_level` | TEXT NOT NULL | Scope discriminator. |
| `workspace_id` | TEXT NULL | Scope discriminator. |
| `session_id` | TEXT NULL | Scope discriminator. |
| `task_id` | TEXT NULL | Scope discriminator. |
| `agent_run_id` | TEXT NULL | Scope discriminator. |
| `effective_config_json` | TEXT NOT NULL | Redacted full snapshot JSON. |
| `created_by_change_id` | TEXT NULL | Link to change ledger. |
| `created_at` | TEXT NOT NULL | UTC ISO timestamp. |

Indexes:

- `(config_hash)`
- `(scope_level, workspace_id, session_id, task_id, agent_run_id, created_at)`
- `(created_by_change_id)`

## 7. Patch Validation Flow

```text
RuntimeConfigPatch
  -> validate keys exist in RuntimeConfigRegistry
  -> validate target scope is allowed by each RuntimeConfigKey.scope_levels
  -> normalize values using existing resolver normalization rules
  -> reject secret keys unless a dedicated secret boundary owns them
  -> resolve base EffectiveRuntimeConfig
  -> apply accepted values as a runtime_patch layer
  -> resolve candidate EffectiveRuntimeConfig
  -> classify per-key effective status from mutability
  -> persist RuntimeConfigChange
  -> persist RuntimeConfigSnapshotRecord when accepted/no-op requires evidence
```

Validation must be all-or-recorded, not all-or-nothing:

- one invalid key should not hide validation results for other keys;
- `RuntimeConfigChange` should record accepted and rejected subsets;
- write API can choose whether partial acceptance is allowed, but C5 store
  should be capable of representing it.

## 8. Scope Rules

Patch scope must be explicit.

Required identifiers:

| Scope level | Required IDs |
|---|---|
| `global` | none |
| `workspace` | `workspace_id` |
| `session` | `workspace_id`, `session_id` |
| `task` | `workspace_id`, `session_id`, `task_id` |
| `agent_run` | `workspace_id`, `session_id`, `task_id`, `agent_run_id` |
| `process` | none; process patches are initially not durable user patches |

Initial C5 recommendation:

- durable user/system patches support `global`, `workspace`, `session`, and
  `task`;
- `agent_run` snapshots can be stored, but direct user patches to `agent_run`
  are deferred;
- `process` stays source-layer-only from env/CLI/process input unless a later
  operator/admin story requires durable process profiles.

## 9. Mutability Handling

C5 stores intent and resulting effective status. It does not apply live changes.

| Mutability | C5 store behavior |
|---|---|
| `live` | Accepted and marked `active`; C6 may publish ConfigBus. |
| `next_context_build` | Accepted and marked `pending_next_context_build`. |
| `next_llm_call` | Accepted and marked `pending_next_llm_call`. |
| `next_action` | Accepted and marked `pending_next_action`. |
| `next_agent_run` | Accepted and marked `pending_next_agent_run`. |
| `next_task` | Accepted and marked `pending_next_task`. |
| `next_session` | Accepted and marked `pending_next_session`. |
| `startup_only` | Accepted only if key scope is durable; marked `pending_restart`. |
| `migration_only` | Rejected outside migration actor. |

The UI must not imply that a stored patch has affected an already-running
Agent unless the effective status is `active`.

## 10. Secret And Redaction Rules

Runtime config can expose secret readiness, but it should not own raw secrets
in C5.

Rules:

- `RuntimeConfigKey.secret=True` keys are not patchable through ordinary C5
  patches.
- Secret configuration must use a dedicated Settings/secret store boundary.
- Change and snapshot JSON must preserve `redacted=True` and omit raw values.
- Audit evidence can show key names, source kind, effective status, actor,
  reason, and config hash, but not secret payloads.

## 11. Gateway Shape

C5 should introduce a backend service boundary before HTTP routes:

```python
class RuntimeConfigChangeStore(Protocol):
    def append_change(self, change: RuntimeConfigChange) -> None: ...
    def save_snapshot(self, snapshot: RuntimeConfigSnapshotRecord) -> None: ...
    def get_change(self, change_id: str) -> RuntimeConfigChange | None: ...
    def get_snapshot(self, config_hash: str) -> RuntimeConfigSnapshotRecord | None: ...
    def list_changes(self, scope: RuntimeConfigScope) -> tuple[RuntimeConfigChange, ...]: ...


class RuntimeConfigMutationService(Protocol):
    def validate_patch(self, patch: RuntimeConfigPatch) -> RuntimeConfigChange: ...
    def apply_patch(self, patch: RuntimeConfigPatch) -> RuntimeConfigChange: ...
```

HTTP write routes remain C6/C7 work. The service boundary lets tests and future
Settings UI use one mutation path.

## 12. Event / Audit / Diagnostics Integration

C5 should produce records that later surfaces can consume:

- Diagnostics: list changes, snapshots, source priority, and rejected keys.
- Audit Page: show relevant effective config hash and change records that
  influenced a task/action/confirmation.
- EventStream: C6 can emit `runtime.config_changed` or reuse a typed
  `ConfigChangedEvent` once ConfigBus semantics are accepted.

C5 itself should not publish runtime events. It only makes durable facts
available.

## 13. Implementation Plan

### C5.1 Contract Models

- Add additive runtime config patch/change/snapshot models.
- Keep them optional and independent of existing read-only resolver behavior.
- Add model validation tests for scope, rejection, and redaction.

### C5.2 SQLite Store

- Add `SqliteRuntimeConfigChangeStore`.
- Round-trip accepted, rejected, no-op, and snapshot records.
- Verify idempotency-key replay returns the original change.

### C5.3 Mutation Service

- Validate patches against `RuntimeConfigRegistry`.
- Normalize accepted values through existing value rules.
- Resolve base and candidate `EffectiveRuntimeConfig`.
- Persist change and snapshot records.
- Do not expose HTTP write routes yet.

### C5.4 Read Gateway Extension

- Extend read-only gateway with change/snapshot query methods.
- Keep existing schema/effective/explain routes unchanged.
- Add tests proving existing read-only endpoints are behavior-compatible.

### C5.5 HTTP Write API Design Gate

- Only after C5.1-C5.4 pass, design write routes:
  - `PATCH /api/v1/runtime/config`
  - `GET /api/v1/runtime/config/changes`
- Define authorization, partial-acceptance policy, and UI copy before
  implementation.

## 14. Acceptance Criteria

- A config patch can be validated without mutating runtime behavior.
- Accepted, rejected, and no-op changes are durably recorded.
- Effective config snapshots are durably stored by hash.
- Secret keys are rejected or redacted through a documented policy.
- Scope and mutability are preserved per key.
- Startup-only values do not pretend to be live.
- Existing read-only config endpoints keep current behavior.
- No app-specific automation behavior becomes runtime config.

## 15. Risks

| Risk | Mitigation |
|---|---|
| Config writes silently change running agents | C5 stores intent only; C6 owns live application. |
| Source priority becomes unintuitive | Store source-priority explanation with each change result. |
| Secret values leak through snapshots | Reject ordinary patches to secret keys and preserve redacted snapshots only. |
| Settings UI gets too broad | Keep C5 backend-only; require a separate Settings UX plan. |
| Durable patches conflict with process inputs | Keep process inputs higher priority and expose `higher_priority_source_active`. |

## 16. Open Questions

1. Should partial acceptance be allowed by default, or should the future HTTP
   write route require all keys to validate before committing?
2. Should C5 persist every sidecar startup effective snapshot, or only snapshots
   created by config changes and agent-run boundaries?
3. Should workspace-level durable patches live in the workspace `.plato`
   database, user-global settings database, or both?
4. Should `startup_only` workspace patches be accepted as intent or rejected
   until restart/profile support is implemented?
5. Should Audit Page query snapshots by `config_hash` directly, or only through
   task/action evidence refs?
