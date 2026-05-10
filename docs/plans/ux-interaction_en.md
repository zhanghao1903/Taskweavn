# Plan: UX Interaction Design

## 1. Background

The architecture replaces blocking interrupts with a message-stream model. Users should be able to keep talking while Agents work, and they should control how often the system asks for confirmation.

This plan turns that idea into concrete UX primitives.

## 2. Goals

- Define the message stream as the primary interaction surface.
- Define ActionCards for decisions and confirmations.
- Make AutonomyBehavior understandable to users.
- Support "never interrupt me" without hiding risk.
- Prepare for future concurrent task approvals.

## 3. Problems to Solve

| Problem | Need |
|---------|------|
| Users do not want constant interruptions | autonomy settings and timeout behavior |
| Some actions require confirmation | ActionCard model |
| Agents may ask questions while tasks run | message stream with non-blocking updates |
| Multiple pending confirmations may appear in v2 | batching and queueing |
| User changes settings mid-run | clear transition behavior |

## 4. Core Interaction Model

The UI has two primary surfaces:

1. **Message Stream**: chronological conversation and Agent progress.
2. **ActionCards**: structured decisions that may require user response.

```
Message
Message
ActionCard: Approve file write?
Message
Task status update
```

ActionCards are not modal dialogs by default. They live in the stream and can also appear in a pending-decision tray.

## 5. AutonomyBehavior Dimensions

Autonomy has two dimensions:

```python
@dataclass
class AutonomyBehavior:
    ask_threshold: float
    wait_timeout: float | None
    timeout_action: Literal["wait", "proceed_default", "proceed_confident", "skip"]
    notify_on_proceed: bool
```

User-facing presets:

| Preset | Behavior |
|--------|----------|
| Careful | asks often, waits for user |
| Balanced | asks on risk or uncertainty, may proceed after timeout |
| Fast | rarely asks, proceeds with safe defaults |
| Hands-off | no blocking prompts, logs decisions |

## 6. AutonomyGate Pattern

Before a risky or uncertain action:

1. Agent proposes an action.
2. AutonomyGate evaluates risk, confidence, policy, and budget.
3. It either proceeds, creates an ActionCard, or skips.
4. Decision and rationale are written to EventStream.

## 7. Interrupt Semantics

The system should avoid the word "interrupt" internally. The user sees:

- informational messages;
- pending decisions;
- completed decisions;
- timeout resolutions.

If the user chooses "never interrupt me," ActionCards should auto-resolve according to policy and remain visible in history.

## 8. Concurrent Approval UX

In v2, multiple tasks may request approval.

### 8.1 Merge Strategy

Similar decisions can be grouped:

```
Approve 5 read-only file inspections?
Approve 3 safe formatting changes?
```

### 8.2 Bulk Decisions

Allow "approve all similar actions in this Session" with a clear scope.

### 8.3 Queue Limit

Set a max pending ActionCard count. When exceeded, the system should pause new risky actions or auto-resolve according to SessionConfig.

## 9. Timeout and Default Actions

Every timeout decision must be visible:

```
No response after 30s. Proceeded with safe default: skip shell command.
```

Timeouts should not silently mutate Workspace.

## 10. Agent-Initiated Proposals

Agents can propose:

- creating subtasks;
- changing plan;
- using a tool;
- spending additional budget;
- changing autonomy mode.

Each proposal is an ActionCard with structured fields, not free-form chat only.

## 11. Navigable History

Users should filter the stream by:

- decisions;
- task events;
- tool calls;
- cost events;
- errors.

This turns the message stream into a lightweight audit UI.

## 12. Runtime Config Changes

When users change autonomy settings mid-run:

- new decisions use the new policy;
- existing pending ActionCards keep their original policy unless explicitly refreshed;
- a `ConfigChangedEvent` is emitted.

## 13. Open Questions

- Should ActionCards be inline only, or also have a sidebar tray?
- Should "approve all similar" be allowed in v1?
- How should mobile UI represent long-running task streams?

## 14. Milestones

| Milestone | Output |
|-----------|--------|
| M1 | message stream wireframe |
| M2 | ActionCard schema |
| M3 | AutonomyGate integration |
| M4 | timeout behavior |
| M5 | history filters |

## 15. Acceptance Criteria

- Users can run a task without modal interruptions.
- Users can see what decisions were made automatically.
- Risky actions can still request confirmation.
- Autonomy presets are understandable without reading docs.

## 16. Related Plans

- `configuration.md`: stores autonomy settings.
- `observability.md`: records decisions.
- `cost-quota.md`: uses ActionCards for budget overflow.
- `walkthrough.md`: provides the demo scenario.
