# Plato 1.0 Line-First Authoring Policy

> Status: product policy baseline
> Version: 1.0
> Date: 2026-05-28
> Related: [Core Product Principles](core-product-principles.md), [Workflow Session Task UX Model](workflow-session-task-ux-model.md), [ADR-0010](../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md)

## 1. Why This Policy Exists

Plato's 1.0 goal is reliable user progress, not maximal orchestration exposure.

Observed usage indicates:

- most tasks progress linearly;
- occasional branch work is real but limited;
- user acceptance and direction decisions are the practical throughput limit.

Therefore, 1.0 should optimize for clear sequential control.

## 2. 1.0 Default Operating Mode

Plato 1.0 defaults to:

- single active task flow;
- single active agent per flow;
- fixed routing behavior;
- explicit acceptance before critical continuation.

This is a product-policy default, not an architecture limitation.

## 3. UX Principles

### 3.1 Show Progress As A Line

Main UX should primarily render a line-like progression:

- current step;
- pending acceptance;
- next required user decision;
- result produced.

Tree and branch concepts may exist internally, but are not the main mental model.

### 3.2 Prefer Clarity Over Fan-Out

When choosing between:

- exposing additional orchestration controls, or
- preserving simple next-step comprehension,

1.0 prioritizes comprehension.

### 3.3 Acceptance Is A First-Class Action

The system should not implicitly optimize for producing more parallel outputs
than users can verify.

Acceptance checkpoints should be visible and actionable.

## 4. What 1.0 Explicitly Does Not Optimize For

1.0 does not optimize for:

- maximum concurrent task execution;
- dynamic routing strategies in everyday flows;
- multi-agent orchestration as a default user path;
- full workflow-programming style authoring UX.

These remain candidates for post-1.0 evolution.

## 5. Architecture And Product Boundary

- Architecture remains extensible for orchestration and routing growth.
- Product UX intentionally hides unnecessary complexity in 1.0.
- Advanced controls, if present, should be progressive disclosure, not default surface.

## 6. 2.x Revisit Triggers

Revisit defaults only when evidence shows line-first no longer fits:

- sustained acceptance queue pressure despite streamlined UX;
- repeatable scenarios where parallel branches reduce total completion time;
- stable workspace isolation model that limits cross-line conflicts;
- validated demand for multi-agent authoring controls.

Until these triggers are met, 1.0 policy remains line-first.
