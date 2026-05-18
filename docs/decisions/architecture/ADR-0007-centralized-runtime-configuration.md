# ADR-0007: Centralized Runtime Configuration

> Status: accepted
> Date: 2026-05-13
> Related: [Configuration Control Plane Capability](../../capabilities/configuration-control-plane/), [Roadmap](../../roadmap.md), [Legacy Runtime Configuration Plan](../../archive/legacy-2026-05-18/plans/feature/centralized-runtime-configuration.md), [Legacy Logging Plan](../../archive/legacy-2026-05-18/plans/feature/configurable-logging-system.md)

---

## Context

TaskWeavn now has many configuration domains:

- autonomy;
- audit;
- logging;
- LLM provider and retry;
- Task and pipeline behavior;
- result presentation;
- budget and safety;
- UI preferences.

These settings shape user experience directly. If every module owns its own config loading and hot update behavior, the system will become hard to explain and hard to debug.

The logging plan already needs global/session/object-level config and hot updates. Autonomy, audit, result presentation, and LLM provider behavior need similar scope semantics.

---

## Decision

Introduce centralized hierarchical runtime configuration as a system control plane.

Configuration resolution follows:

```text
built-in defaults
  -> user global config
  -> workspace config
  -> session config
  -> task config
  -> runtime override
```

The effective configuration is an immutable snapshot. Runtime changes are represented as patches and recorded as config changes:

```text
ConfigPatch
  -> validate
  -> append ConfigChange
  -> recompute EffectiveConfig
  -> publish ConfigChanged
  -> subscribers apply at the allowed lifecycle boundary
```

Every config key must declare when it can take effect:

- live;
- next_action;
- next_llm_call;
- next_task;
- next_session;
- static.

Logging, autonomy, audit, LLM provider, and result presentation should consume this shared configuration layer instead of implementing separate override systems.

---

## Consequences

Positive:

- User-facing behavior becomes explainable: the system can answer which config layer caused a decision.
- Session and Task-level overrides become consistent.
- Hot updates become safe because every key declares its lifecycle boundary.
- Logging and other subsystems can share one config bus.
- Session replay can include config history.

Trade-offs:

- The configuration layer becomes a core dependency.
- Schema design and migration need discipline.
- Some feature work should wait for the config control plane instead of building local ad hoc settings.
