# Plan: Configuration System

## 1. Background

The architecture relies on user-configurable autonomy, constraints, presets, budgets, and Agent templates. These settings need a coherent configuration system instead of scattered constants.

## 2. Goals

- Define layered configuration for global, project, and Session scopes.
- Make constraints and presets explicit data.
- Support schema validation and migration.
- Allow selected runtime changes with EventStream audit.
- Provide a clear path for user-defined Agent templates.

## 3. Problems to Solve

| Problem | Need |
|---------|------|
| Settings live in many places | unified SessionConfig |
| Users need presets but also overrides | layered merge model |
| Config changes affect running tasks | clear mutable / immutable fields |
| Schema will evolve | versioning and migration |
| Tool access needs boundaries | permission-aware templates |

## 4. Configuration Layers

Configuration is merged from three layers:

```
Global config      ~/.agent/config.yaml
Project config     .agent/config.yaml
Session override   runtime / UI settings
```

Precedence:

```
Session override > Project config > Global config > built-in defaults
```

## 5. File Format

Example:

```yaml
version: 1

session:
  autonomy: balanced
  interrupt_allowed: true

taskbus:
  mode: v1
  max_concurrent: 1

budget:
  soft_limit_usd: 2.0
  hard_limit_usd: 5.0
  exceed_behavior: ask

constraints:
  profile: default

agents:
  enabled:
    - planner
    - executor
    - auditor
```

## 6. Pydantic Schema

### 6.1 Top Level

```python
class AppConfig(BaseModel):
    version: int
    session: SessionConfig
    taskbus: TaskBusConfig
    budget: BudgetPolicy
    constraints: ConstraintProfile
    agents: AgentRegistryConfig
```

### 6.2 ConstraintProfile

`ConstraintProfile` controls what the system is allowed to create or execute:

- allowed Agent templates;
- allowed tools;
- max task depth;
- max subtasks per task;
- allowed autonomy modes;
- allowed TaskBus mode.

### 6.3 OrchestrationPreset

Presets are named configuration bundles:

- careful;
- balanced;
- fast;
- hands-off;
- audit-focused;
- research-focused.

Presets are immutable templates. User changes create overrides.

## 7. Loading Flow

1. Load built-in defaults.
2. Load global config if present.
3. Load project config if present.
4. Apply Session overrides.
5. Validate with Pydantic.
6. Run cross-field validation.
7. Emit `ConfigLoadedEvent`.

## 8. Runtime Changes

### 8.1 Mutable vs Immutable

| Config | Runtime Mutable? |
|--------|------------------|
| autonomy mode | yes |
| interrupt policy | yes |
| soft budget | yes |
| hard budget | with confirmation |
| enabled Agent templates | no in v1 |
| TaskBus mode | no in v1 |
| Workspace path | no |

### 8.2 ConfigChangedEvent

Every runtime change emits:

```python
class ConfigChangedEvent(Event):
    path: str
    old_value: Any
    new_value: Any
    changed_by: UserId | AgentId
    reason: str | None
```

## 9. Schema Versioning and Migration

### 9.1 Required Version Field

All config files must include `version`.

### 9.2 Automatic Migration

Loaders migrate older versions to the current schema before validation.

### 9.3 Existing Sessions

Running Sessions keep their loaded config unless the user explicitly applies migration.

## 10. Agent Template Registration

### 10.1 Built-In Templates

Built-ins ship with the application and are versioned.

### 10.2 User Templates

Users can define templates:

```yaml
id: my_researcher
capability: research
tools:
  - search
  - read_file
model:
  name: ...
```

### 10.3 Project Templates

Project templates can override or extend global templates inside the project boundary.

### 10.4 Template Versioning

Template changes should be versioned because old EventStream replays need to know which template was used.

## 11. Permission Layers

Config should express:

- which tools an AgentTemplate may use;
- which paths are readable / writable;
- which external effects require confirmation;
- which settings a user may change.

## 12. Validation

### 12.1 Static Validation

Pydantic validates types and required fields.

### 12.2 Cross-Field Validation

Examples:

- `max_concurrent > 1` requires TaskBus v2.
- tools used by AgentTemplates must be registered.
- hard budget must be greater than or equal to soft budget.

### 12.3 Capacity Validation

Reject configurations that exceed provider limits or local runtime capabilities.

## 13. Open Questions

- Should config be stored as YAML, TOML, or JSON?
- Should project config be allowed to reduce global safety constraints?
- How much of Agent template editing belongs in UI?

## 14. Milestones

| Milestone | Output |
|-----------|--------|
| M1 | schema draft |
| M2 | loader and merge logic |
| M3 | validation and errors |
| M4 | runtime changes and events |
| M5 | template registry |

## 15. Acceptance Criteria

- A Session can be created entirely from config.
- Invalid config produces actionable errors.
- Runtime changes are auditable.
- Presets and overrides behave predictably.

## 16. Related Plans

- `ux-interaction.md`: exposes autonomy settings.
- `cost-quota.md`: consumes budget config.
- `observability.md`: records config changes.
- `user-guide.md`: documents examples.
