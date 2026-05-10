# Architecture Review and Self-Evaluation

> A working review document that turns critique into follow-up plans

---

## 0. Review Goal

This document evaluates the multi-agent collaboration architecture from three angles:

1. novelty and highlights;
2. completeness;
3. intuitiveness.

The goal is not to "score the design" for its own sake. The goal is to expose the next useful work items.

---

## 1. Novelty: 7 / 10

### 1.1 Designs With Real Independent Thought

**CreateTaskTool as collaboration capability.** Instead of making "orchestrator" a special Agent type, the architecture turns task creation into a tool capability. This makes control-flow capability and business capability part of the same permission model.

**Strong constraints with explicit relaxation paths.** Many architecture documents explain why the current design exists. This one also explains when each constraint should be relaxed. That makes the document operational rather than decorative.

**TaskBus v2 IOScope insight.** The observation that LLM calls dominate wall-clock time changes the concurrency discussion. Parallel LLM calls may be valuable even if workspace writes remain constrained.

**LLM scheduling with rationale.** LLM-based dispatch is not new, but forcing each scheduling decision to emit a rationale into EventStream makes the scheduler inspectable.

### 1.2 Not New

- tree-shaped task decomposition;
- minimal state machines;
- stateless Agent instances;
- EventStream / event sourcing;
- OS thread-model analogy.

These are not novel individually, but they combine into a coherent design.

---

## 2. Completeness: 6 / 10

### 2.1 What Is Covered

The architecture covers the major structural pieces:

- overview;
- Task;
- Session;
- Agent;
- TaskBus v1;
- TaskBus v2;
- review-to-plan mapping.

Each component has definition, abstraction, lifecycle, relationship with other components, and future development.

### 2.2 Gaps

| Area | Gap | Severity |
|------|-----|----------|
| Error handling | retry, partial failure, scheduler failure, degraded operation | high |
| Security and permissions | tool access, workspace permissions, sandbox boundaries | high |
| Observability | trace, metrics, replay, debugging workflow | medium |
| HITL / UX | user confirmations, delayed response, concurrent approvals | medium |
| Cost and quota | token budget, cost attribution, cost overflow behavior | medium |
| Storage | ThoughtStore and EventStream backends are underspecified | low |
| Configuration | schemas and migration need concrete design | low |
| Testing | replay, deterministic regression tests, fuzzing | low |

The main issue is not architectural philosophy. It is engineering depth.

---

## 3. Intuitiveness: 7 / 10

### 3.1 Strengths

- The OS process/thread mapping makes the design easy to grasp.
- Decision-summary tables help readers remember the tradeoffs.
- The overview-to-component-to-v2 structure gives a good reading path.
- ASCII diagrams appear where they clarify real decisions.

### 3.2 Weaknesses

**No end-to-end trace.** Readers need a concrete "user request -> task -> agent -> subtask -> result -> user" walkthrough.

**Too many terms without a map.** SessionConfig, ConstraintProfile, AutonomyBehavior, AgentTemplate, AgentInstance, IOScope, ScheduleAction, TaskResult, and others need a terminology map.

**Result flow is scattered.** How child results reach the parent and how the final result returns to the user should be shown in one diagram.

**Some concepts lack implementation texture.** Workspace, ThoughtStore, and EventStream need more concrete examples.

**v1 to v2 jump is steep.** A `v1.5` step should introduce IOScope before LLM scheduling.

**Few counterexamples.** The documents would be stronger if they showed what goes wrong without TaskBus, without constraints, or with a full DAG too early.

---

## 4. Overall Score

Approximate score:

```
Novelty       7 / 10
Completeness 6 / 10
Intuitiveness 7 / 10
Overall      7.3 / 10
```

Summary:

> The architecture has stronger conceptual maturity than implementation depth. Its best ideas are the task-centric collaboration model, strong constraints with relaxation paths, and TaskBus v2's IOScope-based concurrency. The biggest improvement is to add a concrete walkthrough and engineering plans for observability, cost, configuration, UX, and user guidance.

---

## 5. Follow-Up Roadmap

| Plan | Priority | Why |
|------|----------|-----|
| `plans/walkthrough.md` | P0 | fixes the largest intuitiveness gap |
| `plans/ux-interaction.md` | P0 | turns HITL and autonomy into product behavior |
| `plans/observability.md` | P0 | makes the system debuggable |
| `plans/cost-quota.md` | P1 | prevents uncontrolled LLM spend |
| `plans/configuration.md` | P1 | makes constraints and presets real |
| `plans/user-guide.md` | P1 | turns internal architecture into usable product |

Deferred but important:

- error handling plan;
- security and permission plan;
- testing strategy;
- `bus-v1.5` transition plan;
- counterexample document.

---

## 6. Review Attitude

A good architecture document does not only describe the current design. It also names the missing pieces clearly enough that future work has a path.
