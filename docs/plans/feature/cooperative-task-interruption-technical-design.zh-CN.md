# Cooperative Task Interruption 详细技术方案

> 状态: planned
> 类型: Product 1.0 minimal cooperative task interruption technical design
> Last Updated: 2026-06-03
> Decisions: [ADR-0011 Routing Agent Assignment And Cooperative Interruption](../../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0014 Interaction Control Taxonomy For Product 1.0](../../decisions/ADR-0014-interaction-control-taxonomy-for-product-1-0.md)
> Feature Plan: [Cooperative Task Interruption](cooperative-task-interruption.md)
> Related: [Task](../../architecture/task.md), [TaskBus](../../architecture/bus.md), [Context Manager](../../architecture/context-manager.md), [Context Manager Cache-Aware Rendering](context-manager-cache-aware-rendering.md)

---

## 1. 背景

Product 1.0 的执行闭环已经收敛到 fixed-route Default Agent：

```text
PublishedTask
  -> TaskBus
  -> FixedRouteTaskExecutor
  -> Default Agent / AgentLoop
  -> TaskBus complete / fail
```

用户需要能表达“停止当前任务”的控制意图。但 TaskBus 不能也不应该直接强杀
LLM 请求、shell 命令、文件写入或外部 API 调用。真正知道哪里能安全停止的，
只有正在执行的 Agent/runtime。

因此 Product 1.0 采用 cooperative interruption：

```text
User/system requests stop
  -> TaskBus records interrupt intent
  -> UI projects running Task as Stopping
  -> Context Manager exposes interruption fact
  -> Agent/runtime observes the intent at safe points
  -> Agent reports failed terminal outcome
```

---

## 2. 设计约束

### 2.1 不新增 PublishedTask 状态

Product 1.0 继续使用最小状态：

```text
pending
running
done
failed
```

不新增：

- `paused`
- `cancelled`
- `stopping`

`stopping` 是 UI projection，不是 TaskDomain 状态。`cancelled` 是 failure
reason 语义，不是 PublishedTask 状态。

### 2.2 不做 hard cancel

本方案不承诺：

- 中断正在进行的 LLM request；
- kill shell process；
- 回滚已完成文件写入；
- 撤销外部 API side effect；
- 停止 runtime 不可中断动作。

Product 1.0 只保证系统能记录意图，并在下一个安全点停止继续推进。

### 2.3 TaskBus 仍是生命周期权威

TaskBus 负责：

- 接收停止请求；
- 验证 Task 当前状态；
- 记录 interrupt intent；
- 对 pending Task 做立即 terminal fail；
- 接受 Agent 在安全点提交的 `fail(...)`；
- 为 projection/audit 提供事实。

TaskBus 不负责：

- 判断工具是否可安全停止；
- 直接调用 runtime cancel；
- 重写 running Task 为 terminal；
- 决定 partial result 是否可恢复。

### 2.4 与 ASK / confirmation 的边界

[ADR-0014](../../decisions/ADR-0014-interaction-control-taxonomy-for-product-1-0.md)
将 Product 1.0 的交互控制拆成三类语义：

- interruption 是用户或系统的停止控制意图；
- ASK 是 Agent 缺少用户拥有的信息，必须等待用户回答；
- confirmation 是 Agent 已知要做的 action，但需要用户授权。

本方案只实现 interruption 最小闭环，不实现 ASK/confirmation UI，不引入
`waiting_for_user`，也不把停止请求编码成 ASK answer 或 confirmation action。

---

## 3. Domain Model

### 3.1 Interrupt Intent

建议增加最小模型：

```python
TaskInterruptRequestedBy = Literal["user", "system"]

class TaskInterruptIntent(ContextModel):
    request_id: str
    session_id: str
    task_id: str
    requested_by: TaskInterruptRequestedBy
    reason: str
    requested_at: datetime
```

这个模型是控制事实，不是执行状态。

### 3.2 TaskDomain 最小扩展

有两种实现方式。

推荐 Product 1.0 使用 Task row 上的 latest intent 字段：

```python
interrupt_requested: bool = False
interrupt_request_id: str | None = None
interrupt_reason: str | None = None
interrupt_requested_by: Literal["user", "system"] | None = None
interrupt_requested_at: datetime | None = None
```

原因：

- 查询 projection 简单；
- Context Manager source 可以直接拉 TaskBus 当前事实；
- 不需要复杂 intent 表和 join；
- 历史记录由 EventStream/Audit 保存。

后续如果需要多次 stop request 历史，再引入独立表。

### 3.3 Terminal Outcome

终态仍然走 `failed`：

```text
failed
error_ref = "cancelled: user requested stop before next tool call"
```

约定：

- 用户主动停止：`cancelled: ...`
- 系统策略跳过：`skipped: ...`
- 普通执行错误：不使用上述前缀。

这让 projection、Audit 和 retry rule 能区分失败原因，而不用扩展 TaskDomain
状态枚举。

---

## 4. TaskBus API

### 4.1 Public Command

建议 TaskBus 增加：

```python
def request_interrupt(
    self,
    task_id: str,
    *,
    session_id: str,
    reason: str,
    requested_by: Literal["user", "system"] = "user",
    request_id: str | None = None,
) -> TaskDomain:
    ...
```

返回更新后的 TaskDomain，便于 Command Gateway 立即构建 response。

### 4.2 状态规则

```text
pending + request_interrupt
  -> failed
  -> error_ref = "cancelled: ..."

running + request_interrupt
  -> running
  -> interrupt_requested = true

done / failed + request_interrupt
  -> command error
```

不建议 Product 1.0 对 terminal Task 做 silent no-op。用户需要知道停止请求没有
改变任何事实。只有 command idempotency 层能证明同一 request 已处理时，才可
返回已有结果。

### 4.3 Complete/Fail 交互

如果 `interrupt_requested=true`，TaskBus 仍可接受：

```python
complete(task_id, result_ref=...)
fail(task_id, error_ref=...)
```

原因：停止请求和执行终态存在 race。某些不可中断动作完成后，Agent 可能已经
产生有效结果。TaskBus 不应该因为收到过 stop request 就拒绝 complete。

Audit 必须保留：

```text
interrupt requested at T1
agent completed at T2
```

如果 Agent 在安全点确认停止，应该调用：

```python
fail(task_id, error_ref="cancelled: stopped at safe point ...")
```

---

## 5. SQLite 持久化

Product 1.0 推荐在 Task 表增加 latest intent 字段：

```sql
interrupt_requested INTEGER NOT NULL DEFAULT 0,
interrupt_request_id TEXT,
interrupt_reason TEXT,
interrupt_requested_by TEXT,
interrupt_requested_at TEXT
```

约束：

- `interrupt_requested=0` 时其他 interrupt 字段可以为空；
- terminal Task 可以保留 interrupt 字段，用于 projection/audit；
- retry 时建议清空 active interrupt intent，因为 retry 表示新的执行尝试。

Retry 清理规则：

```text
failed(cancelled) + retry
  -> pending
  -> interrupt_requested = false
  -> interrupt_* = null
```

历史取消事实仍在 EventStream/Audit 中。

---

## 6. Event And Audit

### 6.1 EventStream

建议新增或复用控制事件：

```python
TaskInterruptRequestedEvent(
    event_id,
    session_id,
    task_id,
    requested_by,
    reason,
    requested_at,
)
```

如果当前 EventStream 不适合新增 domain event，第一版也可以通过 TaskBus audit
record / command event 记录，但必须满足 Audit Page 能展示 stop request。

### 6.2 Audit Page

Audit 至少能展示：

- stop request；
- requested_by；
- reason；
- Task 当时状态；
- Agent safe-point acknowledgement；
- terminal outcome；
- 如果 completion 和 stop request 发生 race，展示 completion won race。

---

## 7. AgentLoop Safe Points

### 7.1 Interrupt Checker

AgentLoop 不应该直接依赖具体 SQLite TaskBus。建议注入小接口：

```python
class TaskInterruptChecker(Protocol):
    def interrupt_for_task(self, task_id: str) -> TaskInterruptIntent | None:
        ...
```

FixedRouteTaskExecutor 或 Default Agent assembly 负责把 TaskBus-backed checker
接入 AgentLoop。

### 7.2 Safe-Point Helper

AgentLoop 增加内部 helper：

```python
def _check_interrupt(self, phase: str) -> ErrorObservation | None:
    intent = self.interrupt_checker.interrupt_for_task(self._current_task_id)
    if intent is None:
        return None
    return AgentErrorObservation(
        error_type="interrupted",
        message=(
            "cancelled: user requested stop; "
            f"acknowledged at safe point {phase}"
        ),
    )
```

具体 observation 类型可按现有类型系统调整。关键是：

- message/error_ref 使用 `cancelled:` 前缀；
- EventStream 记录 safe point；
- LoopResult 能表达 interrupted stop reason。

### 7.3 Product 1.0 Safe Points

第一版检查点：

1. 每次 `llm.chat(...)` 前；
2. LLM response 返回后、tool dispatch 前；
3. 每个 tool call 前；
4. 每个 tool observation 后；
5. 等待用户确认或 drain deferred action 前后；
6. FixedRouteTaskExecutor claim 下一个任务前。

不在第一版检查：

- LLM request 执行过程中；
- runtime.execute 内部不可中断阶段；
- shell command 运行过程中；
- 文件写入已经开始之后。

### 7.4 LoopResult 映射

建议扩展 LoopResult stop reason：

```python
stop_reason: Literal[
    "agent_finish",
    "no_tool_calls",
    "max_steps",
    "llm_error",
    "context_error",
    "interrupted",
]
```

Default Agent / executor 映射：

```text
LoopResult.stop_reason == "interrupted"
  -> TaskBus.fail(task_id, error_ref=loop_result.final_answer or "cancelled: ...")
```

---

## 8. Context Manager 集成

### 8.1 Source

Task context source 从 TaskBus 当前事实读取 interrupt intent：

```python
if task.interrupt_requested:
    execution.interruption = InterruptionContext(
        requested=True,
        reason=task.interrupt_reason,
        requested_at=task.interrupt_requested_at,
    )
```

如果没有 intent：

```python
execution.interruption = None
```

### 8.2 Renderer

当前 renderer 已有 `## Interruption` section。Product 1.0 要求：

- full context / checkpoint 中包含 active interruption；
- cache-aware delta 中把 interruption 作为高优先级增量；
- stable start context 不包含 inactive/volatile interruption facts。

Delta 示例：

```text
# Context Delta

Reason: interrupt_requested

- The user requested this Task to stop.
- Stop at the next safe point.
- Do not start new file writes, shell commands, or external calls unless needed
  to leave the workspace consistent.
```

### 8.3 Cache-Aware Rendering 关系

Cooperative interruption 不要求重新生成 prompt 前缀。

正确形状：

```text
stable start context
assistant/tool transcript
system: Context Delta - interrupt requested
```

错误形状：

```text
system
full regenerated context with interrupt field
prior transcript
```

后者会破坏 prefix cache。

---

## 9. UI / Backend Projection

### 9.1 Command

UI 可以继续使用现有 `cancelTask` 概念，但 Gateway 需要按对象状态分流：

```text
draft node
  -> AuthoringCommandService cancel

published pending Task
  -> TaskBus.request_interrupt
  -> immediate failed(cancelled)

published running Task
  -> TaskBus.request_interrupt
  -> running + interrupt_requested
```

如果产品/API 后续希望语义更清楚，可以增加内部命令名
`requestTaskInterrupt`，但 Product 1.0 不要求新增外部 endpoint。

### 9.2 Projection

Projection 规则：

```text
status=running, interrupt_requested=false
  -> TaskNodeCardView.status = "running"
  -> label = "Running"
  -> canCancel = true

status=running, interrupt_requested=true
  -> TaskNodeCardView.status = "running"
  -> label = "Stopping..."
  -> canCancel = false

status=failed, error_ref startswith "cancelled:"
  -> TaskNodeCardView.status = "failed"
  -> label = "Cancelled"
  -> canRetry = existing retry rules
```

不建议新增 `TaskNodeStatus = "stopping"`，除非 Main Page 现有 view model 已经有
独立 display label 字段无法表达。状态枚举要保持稳定，停止中是 active Task 的
显示态。

### 9.3 SSE / Event

最小事件流：

```text
task.node.changed
  reason = interrupt_requested

task.node.changed
  reason = failed
  error_ref = "cancelled: ..."
```

Audit Page 可以消费更细粒度的 backend audit event；Main Page 只需要 resync 或
局部 patch。

---

## 10. Retry 交互

Manual retry 已采用原地 retry：

```text
failed -> pending
```

Interrupted/cancelled failed Task 使用同一规则：

```text
failed(error_ref startswith "cancelled:") + retry
  -> pending
  -> clear active interrupt intent
  -> preserve previous failure/audit facts
```

这保证：

- 控制面上还是原 Task；
- 历史中断事实可审计；
- 新执行尝试不会继承上一次 stop intent。

---

## 11. Test Plan

### 11.1 TaskBus

- `test_request_interrupt_pending_fails_with_cancelled_reason`
- `test_request_interrupt_running_records_intent_without_status_change`
- `test_request_interrupt_terminal_task_rejected`
- `test_retry_clears_active_interrupt_intent`

### 11.2 AgentLoop / FixedRoute

- `test_agent_loop_stops_before_llm_call_when_interrupt_requested`
- `test_agent_loop_stops_before_tool_dispatch_when_interrupt_requested`
- `test_agent_loop_does_not_hard_cancel_inflight_tool`
- `test_fixed_route_executor_maps_interrupted_loop_to_taskbus_fail`

### 11.3 Context Manager

- `test_context_source_populates_interruption_context`
- `test_cache_aware_provider_appends_interrupt_delta`
- `test_stable_start_context_excludes_inactive_interruption`

### 11.4 UI Projection / Command

- `test_running_interrupt_projects_stopping_label`
- `test_running_interrupt_disables_duplicate_cancel`
- `test_cancelled_failed_task_uses_cancelled_copy`
- `test_cancel_command_routes_running_task_to_interrupt_request`

### 11.5 Audit

- `test_audit_records_interrupt_request`
- `test_audit_records_safe_point_acknowledgement`
- `test_audit_records_completion_after_interrupt_race`

---

## 12. Implementation Order

建议分两到三个 PR：

1. TaskBus intent + projection contract tests；
2. AgentLoop safe-point checks + Context Manager source/delta；
3. Main Page command/projection + Audit evidence/docs closure。

如果与 cache-aware Context Manager 实现并行，顺序建议是：

1. 先落本 interruption design；
2. cache-aware rendering 实现时预留 interruption delta trigger；
3. interruption runtime 实现补上真实 source/checker。

这样 cache-aware provider 的接口不会因为 interruption 后补而返工。

---

## 13. Acceptance Criteria

Product 1.0 minimal cooperative interruption 完成时：

1. Pending published Task 可以被停止，并立即变成 `failed(cancelled: ...)`。
2. Running published Task 可以记录 interrupt intent，TaskDomain 仍是
   `running`。
3. Main Page 把 running + interrupt intent 投影为 `Stopping...`。
4. AgentLoop 在定义的安全点观察 intent 并停止继续推进。
5. Agent/runtime acknowledgement 通过 TaskBus `fail(...)` 写入终态。
6. Context Manager 能把 active interruption fact 放进 LLM input。
7. Cache-aware rendering 以 append-only delta 表达 interrupt，不重写稳定前缀。
8. Audit Page 能解释 stop request、safe-point acknowledgement 和 terminal
   outcome。
9. 未引入 hard cancel、`paused`、PublishedTask `cancelled` 状态或复杂恢复策略。

---

## 14. 延期项

以下进入 Product 1.1+ 或后续 DFX 工作：

- hard cancel；
- process tree signal handling；
- tool-specific cancellation contract；
- partial result recovery；
- pause/resume；
- timeout sweep；
- stuck stopping diagnostic；
- user-configurable interruption policy；
- multi-Agent interruption propagation。
