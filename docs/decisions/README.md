# Architecture Decision Records

This directory records decisions that affect TaskWeavn's architecture, roadmap, or long-term maintenance model.

## Format

Use:

```text
ADR-<num>-<slug>.md
```

Each ADR should include:

- status;
- date;
- context;
- decision;
- consequences;
- related docs.

## Index

| ADR | Status | Decision |
|---|---:|---|
| [ADR-0001](ADR-0001-roadmap-rebaseline-after-phase-3-8.md) | accepted | Rebaseline the roadmap after Phase 3.8 around Task-first architecture. |
| [ADR-0002](ADR-0002-task-domain-viewmodel-and-replay.md) | accepted | Separate backend Task domain model from UI ViewModel and preserve replayable interaction facts. |
| [ADR-0003](ADR-0003-task-publishers-use-taskbus.md) | accepted | All Task publishers publish normal Tasks through TaskBus. |
| [ADR-0004](ADR-0004-docs-governance-for-planning-session.md) | accepted | Use roadmap, ADRs, releases, and plan files as the planning session's control plane. |
| [ADR-0005](ADR-0005-result-packaging-task-policy.md) | accepted | Result packaging is triggered by post-task policy and executed as a normal Task. |
| [ADR-0006](ADR-0006-llm-provider-transport-boundary.md) | accepted | Treat LLM provider transport as a boundary below LLMClient. |
| [ADR-0007](ADR-0007-centralized-runtime-configuration.md) | accepted | Use centralized hierarchical runtime configuration with immutable snapshots and hot-update events. |
| [ADR-0008](ADR-0008-authoring-domain-execution-boundary.md) | accepted | Separate Authoring Domain objects from Execution TaskBus; only published Tasks enter TaskBus. |
