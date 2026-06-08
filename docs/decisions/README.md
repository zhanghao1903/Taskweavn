# Architecture Decision Records

This directory records decisions that affect TaskWeavn's architecture, roadmap, or long-term maintenance model.

ADRs are used when a choice is costly to reverse. They should be linked from
architecture docs, plans, the [Gap Registry](../gaps/), or release records when
they constrain future work.

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
| [ADR-0009](ADR-0009-single-active-session-worktree.md) | accepted | Use one active RawTask, draft tree, and work-tree projection per Session for the MVP product model. |
| [ADR-0010](ADR-0010-line-first-authoring-experience-for-1-0.md) | accepted | Keep tree-capable architecture but adopt line-first authoring experience defaults for 1.0. |
| [ADR-0011](ADR-0011-routing-agent-assignment-and-cooperative-interruption.md) | accepted | Use Routing Agent assignment commands and cooperative interruption instead of TaskBus-owned routing strategy or hard cancellation. |
| [ADR-0012](ADR-0012-taskbus-centered-agent-assignment-convergence.md) | accepted | Use TaskBus-centered convergence loops for minimal Agent assignment and stale pending degradation. |
| [ADR-0013](ADR-0013-cache-aware-append-only-context-rendering.md) | accepted | Preserve append-only execution transcripts with context deltas and checkpoints for cache-aware Context Manager rendering. |
| [ADR-0014](ADR-0014-interaction-control-taxonomy-for-product-1-0.md) | accepted | Keep interruption, ASK, confirmation, and MessageStream as separate Product 1.0 interaction control mechanisms. |
| [ADR-0015](ADR-0015-main-page-activity-overlay-message-history.md) | accepted | Replace the Main Page persistent message column with Latest Activity, Activity Overlay, and Result Artifact/Reader surfaces. |
| [ADR-0016](ADR-0016-collaborator-workspace-aware-authoring.md) | accepted | Give Collaborator a bounded read-only authoring loop with workspace read/query/search, without workspace writes or unrestricted execution tools. |
| [ADR-0017](ADR-0017-session-and-workspace-context-management-foundation.md) | accepted foundation | Define Workspace, Session, and Task context layers as a future contract without implementation. |
