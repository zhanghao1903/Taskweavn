# ADR-0005: Result Packaging As Post-task Policy And Normal Task

> Status: accepted
> Date: 2026-05-11
> Related: [Result Packaging Plan](../plans/feature/result-packaging-agent-cards.md), [Task Publisher Plan](../plans/feature/task-publishers-schedule-api.md), [Pipeline Task Loading](../plans/feature/pipeline-task-loading.md)

---

## Context

TaskWeavn needs better presentation for information-style answers. Many useful answers are not best consumed as a long text block:

- options and comparisons;
- ranked candidates;
- steps and checklists;
- risks and trade-offs;
- cited research summaries.

The UI can render cards, and LLMs can structure results into card-friendly shapes. The open question is how to trigger result packaging:

1. let Collaborator Agent decide whether to publish a packaging Task;
2. automatically evaluate every completed result and publish a packaging Task only when useful.

---

## Decision

Use a post-task `ResultPresentationPolicy` as the default trigger.

```text
Task completed
  -> ResultPresentationPolicy evaluates result shape and hints
  -> if useful, TaskPublisher publishes ResultPackagingTask
  -> TaskBus dispatches to ResultPackagingAgent
  -> UI receives ResultCardSet
```

Result packaging itself is a normal Task with a `result_packaging` capability.

Collaborator Agent can provide presentation hints during Task authoring, and users can explicitly request or disable card output, but Collaborator Agent is not the sole runtime judge.

---

## Consequences

Positive:

- Packaging is consistent across user, collaborator, pipeline, API, and scheduled tasks.
- The decision can use actual task result shape, not only the initial task intent.
- Packaging remains auditable, retryable, and skippable because it goes through TaskBus.
- Raw text results remain available even if packaging fails.

Trade-offs:

- A policy layer is required before packaging.
- Poor policy thresholds could create noisy cards or miss useful card opportunities.
- Result artifacts and card sets need persistence/replay design.
