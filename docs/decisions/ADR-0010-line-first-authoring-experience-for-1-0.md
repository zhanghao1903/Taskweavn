# ADR-0010: Line-First Authoring Experience For 1.0 On Top Of Tree-Capable Runtime

> Status: accepted
> Date: 2026-05-28
> Related: [ADR-0008](ADR-0008-authoring-domain-execution-boundary.md), [Authoring Domain](../architecture/authoring-domain.md), [Workflow Session Task UX Model](../product/workflow-session-task-ux-model.md), [Core Product Principles](../product/core-product-principles.md)

---

## Context

TaskWeavn's Authoring Domain is modeled as a task tree and supports branchable planning.
In practice, recent internal usage shows most work progresses as a single linear flow,
with occasional side tracks.

For 1.0, the operational bottleneck is not AI-side parallel execution throughput.
The bottleneck is human acceptance and decision latency:

- users must review intermediate outputs to avoid drift;
- unchecked parallel work increases rework risk;
- overlapping workspace edits create conflict cost;
- product direction choices require explicit human decisions.

The runtime architecture already supports future expansion:

- tree-capable authoring model;
- publish boundary into TaskBus;
- potential future routing strategy and multi-agent orchestration.

However, exposing full orchestration complexity in 1.0 weakens clarity and slows users.

---

## Decision

For 1.0, adopt a **line-first user experience** without changing the underlying
architecture.

1. Keep the current tree-capable Authoring Domain and execution boundary.
2. Default product interaction to single-task, single-agent, fixed-route flow.
3. Prioritize acceptance checkpoints and decision checkpoints over parallel fan-out.
4. Treat multi-line/multi-agent orchestration as deferred capability, not default UX.
5. Hide orchestration complexity from ordinary users unless explicitly needed.

Practical interpretation for 1.0:

- Engine remains extensible.
- Runtime defaults remain constrained.
- Main UX emphasizes "current step", "pending acceptance", and "next decision".

---

## Consequences

Positive:

- Aligns product behavior with observed user operating mode.
- Improves clarity by reducing unnecessary branching mental load.
- Reduces rework from unaccepted parallel output.
- Preserves architectural optionality for future orchestration features.
- De-risks 1.0 by avoiding broad domain refactors.

Trade-offs:

- Tree-native orchestration value is under-exposed in 1.0.
- Some advanced parallel scenarios may require manual multi-session workflows.
- Future versions must explicitly define progressive disclosure for advanced controls.

Rejected alternatives:

| Alternative | Reason Rejected |
|---|---|
| Refactor Authoring Domain from tree model to a new line-only core before 1.0 | Large change, high risk, and not required to deliver 1.0 user value. |
| Make dynamic routing strategy a 1.0 requirement | Adds complexity before acceptance/decision workflow maturity is proven. |
| Optimize for maximum parallel Task execution in 1.0 | Mismatched with current bottleneck: human acceptance and product decisions. |

---

## Follow-up

- Add a product document that defines line-first 1.0 interaction policy.
- Ensure Main Page wording and state model emphasize acceptance and decision flow.
- Keep advanced orchestration capability behind non-default entry points.
- Revisit routing strategy and multi-agent defaults only after acceptance-latency metrics justify it.
