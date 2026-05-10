# Plan: End-to-End Walkthrough

## 1. Background

The architecture documents explain concepts well, but they still require readers to mentally stitch together the execution path. The review identified this as the largest intuitiveness gap.

This plan defines a concrete walkthrough document that shows one complete run from user request to final result.

## 2. Goals

- Show the full lifecycle of one user request.
- Demonstrate how Session, Task, Agent, TaskBus, Workspace, EventStream, and ThoughtStore interact.
- Make Task result flow explicit.
- Include one happy path and at least one failure branch.
- Serve as the shared example used by future UX, observability, and user-guide work.

## 3. Non-Goals

- Do not define new architecture.
- Do not make the example depend on v2 concurrency.
- Do not turn the walkthrough into a tutorial for all features.

## 4. Main Example: Code Audit + Fix

### 4.1 Scenario

User asks:

```
Audit src/auth.py for security issues and propose a safe fix.
```

The system creates a root Task:

```yaml
intent: Audit src/auth.py for security issues and propose a safe fix.
required_capability: plan
parent_id: null
```

### 4.2 Full Flow

1. User message enters the Session.
2. Session creates a Root Task.
3. TaskBus publishes the Task and emits `TaskCreated`.
4. TaskBus chooses a planning Agent.
5. Planner reads context and creates subtasks:
   - inspect file;
   - identify security issues;
   - propose patch;
   - validate patch.
6. Each subtask is executed through TaskBus.
7. Results flow back to the parent task.
8. Planner synthesizes the final response.
9. User sees a message stream plus ActionCards if approval is needed.

### 4.3 What to Show at Each Moment

| Moment | User-visible | Internal trace |
|--------|--------------|----------------|
| request | user message | `SessionStarted`, `TaskCreated` |
| dispatch | task status changes | `TaskDispatched`, `AgentRunStarted` |
| tool call | progress message | `ToolCallStarted`, `ToolCallFinished` |
| subtask | child task appears | parent-child relationship |
| risky action | ActionCard | `UserDecisionRequested` |
| completion | final answer | `TaskCompleted` |

### 4.4 Failure Branch

Example: validation fails after the patch.

The walkthrough should show:

- `ValidateTask` becomes `failed`;
- parent task receives failure result;
- planner creates a new patch task or reports failure;
- EventStream keeps both attempts.

## 5. Short Example 1: Single-Turn Task

Use a simple research request that does not create subtasks. This demonstrates that the architecture does not force every request into a complicated graph.

## 6. Short Example 2: User Interrupts Mid-Run

Show a user sending a clarification while an Agent is running. The message is appended to the message stream and handled according to AutonomyBehavior.

## 7. Proposed Document Structure

1. Scenario
2. Runtime objects created
3. Timeline
4. Task tree
5. EventStream excerpt
6. User-facing UI view
7. Failure branch
8. What this example proves

## 8. Key Diagrams

### 8.1 Timeline

```
User -> Session -> TaskBus -> Agent -> Tool -> TaskBus -> User
```

### 8.2 Result Flow

```
Child Task result -> Parent Task context -> Final response
```

### 8.3 State Slice

Show one Task moving through:

```
pending -> running -> done
```

## 9. Writing Rules

- Use one concrete example throughout.
- Do not introduce new terms without linking them.
- Keep internal data structures small enough to read.
- Include both UI and backend perspectives.

## 10. Open Questions

- Should the main example remain code audit if the project becomes a general agent platform?
- Should the walkthrough show v1 only, or include v2 notes?
- How much EventStream detail is useful before it becomes noise?

## 11. Milestones

| Milestone | Output |
|-----------|--------|
| M1 | happy-path timeline |
| M2 | task tree and state transitions |
| M3 | EventStream excerpt |
| M4 | user-facing message stream |
| M5 | failure branch |

## 12. Acceptance Criteria

- A reader can explain how a user request becomes Tasks.
- A reader can trace where child task results go.
- A reader can identify which component owns each state transition.
- The example can be reused in the user guide.

## 13. Related Plans

- `ux-interaction.md`: user-visible message stream and ActionCards.
- `observability.md`: EventStream and trace excerpts.
- `user-guide.md`: simplified version for onboarding.

## 14. Beyond Documentation

The walkthrough should eventually become a regression fixture: one recorded run that can be replayed in tests and shown in the UI demo.
