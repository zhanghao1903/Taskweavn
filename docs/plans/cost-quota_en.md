# Plan: Cost and Quota System

## 1. Background

LLM-based systems can spend money unpredictably. A multi-agent system compounds this risk because Agents may create subtasks and run multiple LLM calls.

Cost must become explicit data, not a backend afterthought.

## 2. Goals

- Track token and monetary cost by Session, Task, Agent run, and tool call.
- Enforce user-configured budgets.
- Estimate cost before expensive actions.
- Handle budget overflow through AutonomyGate / ActionCards.
- Make scheduler cost visible.

## 3. Problems to Solve

| Problem | Need |
|---------|------|
| Users cannot predict cost | estimates and budget previews |
| Agents can create many subtasks | per-Session and per-Task caps |
| LLM scheduler also costs money | scheduler cost attribution |
| Cache discounts complicate accounting | final cost reconciliation |
| Cost overflow can happen mid-run | clear policies |

## 4. Core Abstractions

### 4.1 Cost Is Explicit Data

```python
@dataclass(frozen=True)
class CostRecord:
    session_id: SessionId
    task_id: TaskId | None
    agent_run_id: AgentRunId | None
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    estimated_usd: Decimal
    actual_usd: Decimal | None
```

### 4.2 Budget Is an Explicit Constraint

```python
@dataclass(frozen=True)
class BudgetPolicy:
    soft_limit_usd: Decimal
    hard_limit_usd: Decimal
    exceed_behavior: Literal["ask", "stop", "degrade", "continue"]
```

## 5. Cost Attribution

Cost rolls up hierarchically:

```
LLM call -> Agent run -> Task -> parent Task -> Session -> User
```

This allows both detailed debugging and high-level billing views.

## 6. Real-Time Aggregation

### 6.1 Data Flow

1. LLMClient emits token usage.
2. CostAggregator converts usage to estimated cost.
3. EventStream records `CostRecorded`.
4. UI updates live totals.

### 6.2 CostAggregator Interface

```python
class CostAggregator:
    def record_llm_usage(self, usage: LLMUsage) -> CostRecord: ...
    def current_session_cost(self, session_id: SessionId) -> CostSummary: ...
    def check_budget(self, session_id: SessionId) -> BudgetDecision: ...
```

## 7. Budget Check Timing

### 7.1 Pre-Flight

Before a large task or subtask batch, estimate cost and compare with budget.

### 7.2 Mid-Flight

Check after each LLM call or after every N tokens for streaming calls.

### 7.3 Post-Flight

Reconcile actual provider usage and cache discounts.

## 8. Overflow Strategy

### 8.1 ExceedBehavior

| Behavior | Meaning |
|----------|---------|
| `ask` | create ActionCard |
| `stop` | fail or pause new work |
| `degrade` | use cheaper model or shorter context |
| `continue` | log and proceed |

### 8.2 Soft and Hard Limits

Soft limit triggers warning or confirmation. Hard limit blocks further spending unless user explicitly raises it.

## 9. Estimator Design

### 9.1 History-Driven

Estimate based on similar completed Tasks.

### 9.2 Static Upper Bound

Use max token settings and known model prices.

### 9.3 Error Monitoring

Track estimation error to improve future estimates.

## 10. Cache Discount Handling

Prompt cache discounts should be represented explicitly:

```
input_tokens
cached_input_tokens
cache_discount_usd
```

This keeps cost reports honest even when final provider billing differs from estimates.

## 11. Quota System

Quota can be based on:

- dollars;
- tokens;
- number of LLM calls;
- number of concurrent tasks;
- tool calls with external side effects.

## 12. Scheduler Cost

LLM scheduler calls in TaskBus v2 must be attributed to the Session and, when possible, to the decision that triggered them.

## 13. Open Questions

- Should budget be per user, per Session, or both?
- Should model downgrade happen automatically?
- How should shared or team budgets work?

## 14. Milestones

| Milestone | Output |
|-----------|--------|
| M1 | token usage event model |
| M2 | CostAggregator |
| M3 | budget checks |
| M4 | UI display |
| M5 | provider reconciliation |

## 15. Acceptance Criteria

- Every LLM call has a cost record.
- Session total can be queried live.
- Hard budget prevents further spending.
- Cost overflow can produce an ActionCard.

## 16. Related Plans

- `ux-interaction.md`: displays budget confirmations.
- `observability.md`: indexes cost events.
- `configuration.md`: stores BudgetPolicy.
- `bus-v2.md`: scheduler cost is part of dispatch decisions.
