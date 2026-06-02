# Context Manager Cache-Aware Rendering 详细技术方案

> 状态: planned
> 类型: Product 1.0 Context Manager cache-aware rendering technical design
> Last Updated: 2026-06-02
> ADR: [ADR-0013 Cache-Aware Append-Only Context Rendering](../../decisions/ADR-0013-cache-aware-append-only-context-rendering.md)
> Feature Plan: [Context Manager Cache-Aware Rendering](context-manager-cache-aware-rendering.md)
> Related: [Context Manager 1.0 详细技术方案](context-manager-1-0-technical-design.zh-CN.md)

---

## 1. 背景和目标

Context Manager 1.0 已经把“LLM input 由谁组装”这个架构责任收敛到了
Context Manager。但当前实现每次 `llm.chat(...)` 前都会重新生成完整上下文，
导致高频变化的信息出现在请求前部，破坏 provider 的最大前缀缓存匹配。

本方案的目标是保留 Context Manager 的责任边界，同时恢复 AgentLoop 原本
append-only transcript 的缓存友好性：

```text
stable start context
assistant/tool transcript
context delta messages
context checkpoint messages
```

Product 1.0 不做复杂上下文治理策略。这里只做最小但正确的执行期缓存优化：

- 启动时生成稳定前缀；
- 普通步骤尽量不重写前缀；
- 有新增关键信息时追加 delta；
- 每隔低频步数追加 checkpoint；
- snapshot/trace 继续保存完整诊断信息。

---

## 2. 当前实现分析

### 2.1 AgentLoop 调用路径

当前 `AgentLoop._run_inner(...)` 初始化本地消息：

```python
messages = [
    {"role": "system", "content": self.system_prompt},
    {"role": "user", "content": task},
]
```

每一步调用：

```python
messages_for_call, metadata = self._prepare_llm_call(messages, step)
response = self.llm.chat(messages=messages_for_call, tools=self._tool_schemas)
messages.append(response.raw_assistant_message)
messages.append(self._tool_message(tool_call.id, observation))
```

也就是说，`messages` 是 AgentLoop 的本地执行 transcript，assistant/tool
消息会持续追加。

### 2.2 当前 Context Provider 行为

当前 `SessionAgentLoopContextProvider.build_for_llm_call(...)`：

1. 从 `request.loop_messages` 中取 `loop_messages[2:]` 作为 prior messages；
2. 调 `SessionContextManager.build(...)` 重新生成完整 `TaskExecutionContextV0`；
3. renderer 返回：

```text
system
full rendered context user message
prior assistant/tool/system messages
```

这个形状的问题是：每次调用都把完整上下文放在 transcript 前面。一旦完整
上下文里的任务状态、event id、observation id、trace id、文件摘要等字段变化，
缓存前缀就会很早失效。

### 2.3 关键实现约束

Delta/checkpoint 不能只存在于 `messages_for_call`。

如果 provider 在某一次调用中临时插入 delta/checkpoint，但没有把它写回
AgentLoop 本地 `messages`，下一次调用的本地 transcript 仍然不知道这个
context message。下一次 provider 只能再次重新注入，prefix 仍然无法继承上一次
请求。

因此 provider 必须返回两份结果：

- `llm_messages`: 当前实际传给 `llm.chat(...)` 的消息；
- `persisted_messages`: 调用前需要写回 AgentLoop 本地状态的消息。

---

## 3. 目标架构

目标消息结构：

```text
AgentLoop local messages
  [0] system: base system prompt + Context Manager contract
  [1] user: stable start context
  [2...] append-only assistant/tool/system transcript
        context delta messages
        context checkpoint messages
```

Context Manager 仍然是唯一决定 LLM input 内容的管理者。区别在于，它不再
每一步替换消息前部，而是在同一个 Task run 内维护 append-only 消息形状。

```mermaid
sequenceDiagram
    participant Loop as AgentLoop
    participant Provider as AgentLoopContextProvider
    participant Manager as SessionContextManager
    participant Renderer as ContextRenderer
    participant LLM as LLMClient

    Loop->>Provider: prepare_llm_call(loop_messages, step)
    Provider->>Manager: build context snapshot/trace
    Provider->>Renderer: render start/delta/checkpoint if needed
    Provider-->>Loop: llm_messages + persisted_messages + metadata
    Loop->>Loop: replace local messages with persisted_messages
    Loop->>LLM: chat(llm_messages, tools, metadata)
    LLM-->>Loop: assistant/tool_calls
    Loop->>Loop: append assistant/tool observations
```

---

## 4. 模型和协议变更

### 4.1 Render Mode

在 `src/taskweavn/context/models.py` 增加最小枚举：

```python
ContextRenderMode = Literal[
    "start_context",
    "delta_context",
    "checkpoint_context",
]

ContextSegmentKind = Literal[
    "stable_prefix",
    "execution_transcript",
    "delta",
    "checkpoint",
]
```

### 4.2 Segment Metadata

建议增加独立 segment 模型，避免把缓存治理信息塞进 prompt 文本：

```python
class ContextMessageSegment(ContextModel):
    kind: ContextSegmentKind
    message_start_index: int = Field(ge=0)
    message_end_index: int = Field(ge=0)
    content_hash: str = Field(min_length=1)
    stable: bool = False
```

用途：

- 判断 stable prefix 的边界；
- 保存 delta/checkpoint 的 hash；
- 后续 provider metadata 可以记录 cache 观测；
- snapshot/trace 可以解释某次 call 的渲染结构。

### 4.3 Provider Call Result

当前 provider protocol：

```python
class AgentLoopContextProvider(Protocol):
    def build_for_llm_call(self, request: AgentLoopContextRequest) -> RenderedLlmInput: ...
```

建议演进为：

```python
class AgentLoopContextCallResult(ContextModel):
    llm_messages: tuple[dict[str, Any], ...]
    persisted_messages: tuple[dict[str, Any], ...]
    rendered: RenderedLlmInput
    appended_context_messages: tuple[dict[str, Any], ...] = ()
    render_mode: ContextRenderMode
    stable_prefix_hash: str | None = None
    checkpoint_reason: str | None = None
```

兼容策略：

- 第一阶段可以新增 `prepare_llm_call(...)` 方法；
- 保留 `build_for_llm_call(...)` 一段时间给旧测试或旧调用点使用；
- `AgentLoop` 优先调用 `prepare_llm_call(...)`，没有时 fallback 到旧协议。

### 4.4 RenderedLlmInput 扩展

`RenderedLlmInput` 可以增加：

```python
render_mode: ContextRenderMode = "start_context"
segments: tuple[ContextMessageSegment, ...] = ()
stable_prefix_hash: str | None = None
```

如果希望减少一次性破坏面，也可以先只把这些字段放到
`AgentLoopContextCallResult` 和 metadata 中，后续再扩展 snapshot schema。

Product 1.0 推荐做法：先扩展 `RenderedLlmInput`，因为它已经是 renderer 输出
和 snapshot 输入之间的主合同。

---

## 5. Renderer 设计

当前 `DeterministicContextRenderer.render(...)` 只支持完整上下文。建议拆成：

```python
class DeterministicContextRenderer(ContextRenderer):
    def render_start_context(...) -> RenderedLlmInput: ...
    def render_delta_context(...) -> RenderedLlmInput: ...
    def render_checkpoint_context(...) -> RenderedLlmInput: ...
```

### 5.1 Start Context

Start context 包含稳定执行事实：

- base system prompt；
- Context Manager contract；
- project/session rules；
- task original target；
- durable constraints；
- output requirements；
- allowed/denied tool classes，如果对行为稳定有影响；
- file/tool 证据的使用规则。

Start context 不应该包含：

- `snapshot_id`；
- `trace_id`；
- `event_id`；
- `observation_id`；
- `raw_ref` 列表；
- 高频变化的 task status；
- 当前 step index；
- 时间戳；
- 大块文件内容。

### 5.2 Delta Context

Delta 是低成本追加信息，只在必要时出现：

```text
# Context Delta

Reason: user_confirmation_resolved

- Previously deferred WriteFileAction resolved successfully.
- Continue from the existing transcript.
- Do not repeat completed file writes unless verification requires it.
```

Delta 适合承载：

- 最新用户指令；
- 用户确认/拒绝；
- interruption；
- 重要工具错误；
- 新增文件变更摘要；
- 新读入的短文件证据。

### 5.3 Checkpoint Context

Checkpoint 是低频当前状态整理：

```text
# Context Checkpoint

Reason: interval step 5

Objective:
- Build the requested page from the existing task brief.

Completed:
- Created src/index.html.
- Added article markdown files.

Important observations:
- npm start is unavailable in this workspace.

Pending:
- Verify responsive layout.

Next:
- Inspect generated files and run available static checks.
```

Checkpoint 不保存完整历史，不替代 audit，不内联大型文件内容。

---

## 6. Provider 状态设计

### 6.1 State Key

Provider 以 `agent_run_id` 为 key 保存 run-local 状态：

```python
class CacheAwareRunState(ContextModel):
    agent_run_id: str
    stable_prefix_hash: str
    start_context_initialized: bool = False
    last_checkpoint_step: int = 0
    appended_context_message_count: int = 0
    last_delta_hash: str | None = None
```

Product 1.0 可以先用 provider 内存状态，因为当前执行是单进程、单实例、
单 writer lane。snapshot/trace 仍然持久化，后续恢复能力可以基于 persisted
messages 或 snapshot metadata 补强。

### 6.2 第一次调用

第一次调用时：

1. `SessionContextManager.build(...)` 生成 snapshot/trace；
2. renderer 生成 `start_context`；
3. provider 返回：

```python
persisted_messages = rendered.messages
llm_messages = rendered.messages
render_mode = "start_context"
```

AgentLoop 用 `persisted_messages` 替换本地初始 `[system, task]`。

### 6.3 普通步骤

普通步骤时：

1. provider 读取当前 `loop_messages`；
2. build context snapshot/trace 用于诊断和判断；
3. 如果不需要 delta/checkpoint：

```python
persisted_messages = request.loop_messages
llm_messages = request.loop_messages
render_mode = "delta_context"
appended_context_messages = ()
```

这里 `render_mode` 可以命名为 `reuse_transcript`，但 Product 1.0 为了减少模型
类型数量，也可以用 `delta_context` 且 `appended_context_messages=()` 表示无新增。

### 6.4 追加 Delta

当策略判断需要 delta：

```python
context_message = {
    "role": "system",
    "content": renderer.render_delta_context(...).user_content,
}
persisted_messages = (*request.loop_messages, context_message)
llm_messages = persisted_messages
```

这里使用 `system` role 还是 `user` role 需要保持与现有 LLM provider 兼容。
Product 1.0 推荐使用 `system` role，因为这是运行时事实，不是用户新增目标；
如果 provider 对多 system message 支持不一致，再降级为 `user` role 并用明确
标题标记为 runtime context。

### 6.5 追加 Checkpoint

Checkpoint 与 delta 一样追加，但内容更完整、频率更低：

```python
if should_checkpoint(step, state, context):
    checkpoint_message = render_checkpoint_message(...)
    persisted_messages = (*request.loop_messages, checkpoint_message)
```

Checkpoint 的默认 interval：

```python
checkpoint_interval_steps = 5
```

---

## 7. AgentLoop 改动

当前 `_prepare_llm_call(...)` 不会更新本地 `messages`。需要改成 provider 能够
回写 persisted messages。

建议最小改动：

```python
def _prepare_llm_call(
    self,
    messages: list[dict[str, Any]],
    step: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if self.context_provider is None:
        return messages, {}

    call = self.context_provider.prepare_llm_call(request)
    messages[:] = [dict(message) for message in call.persisted_messages]
    metadata = {
        "context_snapshot_id": call.rendered.snapshot_id,
        "context_trace_id": call.rendered.trace_id,
        "context_renderer_version": call.rendered.renderer_version,
        "context_render_mode": call.render_mode,
        "context_stable_prefix_hash": call.stable_prefix_hash,
    }
    return [dict(message) for message in call.llm_messages], metadata
```

兼容 fallback：

```python
if hasattr(self.context_provider, "prepare_llm_call"):
    ...
else:
    rendered = self.context_provider.build_for_llm_call(request)
    return [dict(message) for message in rendered.messages], metadata
```

注意：fallback 不具备 cache-aware 能力，只用于旧测试和过渡。

---

## 8. Snapshot 和 Trace

LLM prompt 不是审计记录。Cache-aware rendering 会刻意从 stable prefix 中移除
volatile provenance，但 snapshot/trace 必须继续完整。

建议扩展记录：

- `render_mode`；
- `stable_prefix_hash`；
- `context_segment_hashes`；
- `appended_context_message_count`；
- `checkpoint_reason`；
- `delta_reason`；
- `cache_policy_version`。

这些字段可以先进入 `ContextTrace`，因为它解释“为什么这次 call 看到这样的
input”。如果 schema 迁移成本较高，可以先通过 metadata 字段落在 trace payload
扩展位；但当前模型 `extra="forbid"`，所以更推荐显式加字段。

---

## 9. Checkpoint Policy

Product 1.0 不需要独立复杂策略引擎。可以先在
`SessionAgentLoopContextProvider` 内部放一个小方法：

```python
def _should_checkpoint(
    self,
    request: AgentLoopContextRequest,
    state: CacheAwareRunState,
    context: TaskExecutionContextV0,
) -> tuple[bool, str | None]:
    if request.turn_index - state.last_checkpoint_step >= self.checkpoint_interval_steps:
        return True, f"interval:{self.checkpoint_interval_steps}"
    return False, None
```

后续再扩展：

- retry begin；
- interruption；
- confirmation resolved；
- repeated tool errors；
- file changes threshold；
- context budget pressure。

### Product 1.0 初始策略

建议第一版只实现：

1. start context；
2. interval checkpoint；
3. optional delta for pending decision count change。

这样能把缓存命中主问题解决，同时不会把 1.0 变成复杂上下文平台。

---

## 10. Provider Metadata 和缓存观测

结构性测试只能证明“前缀稳定”。真实缓存命中还要看 provider 返回 metadata。

LLM provider 后续可记录：

- `input_tokens`；
- `cached_input_tokens`；
- `cache_hit_ratio = cached_input_tokens / input_tokens`；
- prefill latency；
- total latency；
- model/provider name。

Context Manager 本阶段先提供：

- `context_render_mode`；
- `context_stable_prefix_hash`；
- `context_rendered_input_hash`；
- `context_appended_message_count`。

这些 metadata 能让后续日志系统把缓存表现和 context rendering 策略关联起来。

---

## 11. 测试计划

### 11.1 Renderer Tests

- `test_start_context_stable_prefix_hash_is_stable`
- `test_start_context_excludes_volatile_ids`
- `test_delta_context_is_compact_and_marked`
- `test_checkpoint_context_omits_full_event_history`

### 11.2 Provider Tests

- `test_provider_initializes_start_context_once`
- `test_provider_reuses_loop_messages_without_replacing_prefix`
- `test_provider_appends_checkpoint_to_persisted_messages`
- `test_provider_tracks_stable_prefix_hash_by_agent_run_id`

### 11.3 AgentLoop Tests

- `test_agent_loop_persists_context_provider_messages_before_llm_chat`
- `test_agent_loop_preserves_tool_call_protocol_with_context_provider`
- `test_agent_loop_no_provider_behavior_is_unchanged`
- `test_context_provider_metadata_is_passed_to_llm_chat`

### 11.4 Regression Tests

至少运行：

```bash
uv run pytest tests/test_context_manager.py tests/test_loop.py
```

如果 fixed-route executor tests 命名稳定，再追加对应执行桥测试。

---

## 12. 实施顺序

1. C1: 落 ADR、feature plan、technical design。
2. C2: 扩展 context models 和 renderer segment/hash。
3. C3: 增加 provider call result 和 `prepare_llm_call(...)`。
4. C4: 修改 AgentLoop，让 provider 可以回写 persisted messages。
5. C5: 实现 interval checkpoint policy。
6. C6: 补 renderer/provider/loop 测试。
7. C7: 补 provider metadata，并更新 release/docs closure。

推荐每个 PR 控制在一个可验证边界内。如果实现 PR 过大，可以拆成：

- PR 1: models + renderer + tests；
- PR 2: provider + AgentLoop seam + tests；
- PR 3: checkpoint policy + metrics/docs closure。

---

## 13. 验收标准

本方案实现后，需要满足：

1. Product 1.0 Default Agent 每次 `llm.chat(...)` 仍通过 Context Manager。
2. 第一次调用建立 stable start context。
3. 后续普通调用不重新生成完整 context 前缀。
4. Delta/checkpoint 以 append-only message 进入本地 AgentLoop transcript。
5. 工具调用协议顺序不被破坏。
6. Snapshot/trace 仍能解释每次 call 的上下文来源和裁剪原因。
7. 测试能证明稳定前缀、volatile 字段排除、checkpoint 追加和 metadata 输出。
8. 后续可以通过 provider metadata 计算真实 cached-token ratio。

---

## 14. 非目标和延期项

以下不进入 Product 1.0 cache-aware hardening：

- 语义检索；
- 长期记忆；
- 文件级智能选择；
- MCP 上下文接入；
- skill runtime context；
- multimodal packing；
- 用户自定义 context policy；
- 多 Agent 并行上下文合并；
- provider-specific cache directive。

这些能力应该在 append-only rendering 合同稳定后再进入 Product 1.1+。

