# Agent Architecture Design

> Core abstraction of the multi-agent collaboration architecture · v1.0 · 2026-05-08

---

## 1. Definition

**Agent is a stateless execution object created to complete exactly one Task.**

In this architecture, an Agent is not a long-lived actor. It is closer to a function call:

```
Task -> AgentInstance -> result -> destroy
```

The reusable part is `AgentTemplate`: capability declaration, prompt, model choice, and tool set. The runtime part is `AgentInstance`: a short-lived object holding one execution context.

---

## 2. Core Abstraction

### 2.1 Agent Is a Function, Not an Actor

Actor-style agents own mailboxes, private state, and long-running identity. This architecture rejects that model for v1.

An Agent instance:

- handles one Task;
- owns one temporary working memory;
- may call tools;
- may publish subtasks if it has `CreateTaskTool`;
- is destroyed after completion.

It does not keep state across Tasks.

### 2.2 Identity vs Instance

The architecture separates "what this Agent can do" from "one concrete execution":

```python
@dataclass(frozen=True)
class AgentTemplate:
    id: str
    capability: str
    system_prompt: str
    tools: list[ToolSpec]
    model_config: ModelConfig

@dataclass
class AgentInstance:
    id: AgentRunId
    template_id: str
    task_id: TaskId
    working_memory: WorkingMemory
```

`AgentTemplate` is registered once. `AgentInstance` is created per Task.

### 2.3 Capability Is a Single String

In v1, routing uses one capability string:

```
required_capability = "audit"
agent_template.capability = "audit"
```

This is intentionally weaker than a capability set. It keeps dispatching understandable and pushes nuanced routing to later versions.

### 2.4 Tools Define Fine-Grained Power

Capability decides whether an Agent can receive a Task. Tools decide what it can actually do.

Examples:

| Agent Capability | Possible Tools |
|------------------|----------------|
| `plan` | `create_task`, `read_context` |
| `audit` | `read_file`, `grep`, `write_report` |
| `execute` | `read_file`, `write_file`, `run_command` |
| `validate` | `run_command`, `read_file`, `diff` |

`CreateTaskTool` is just another tool, which makes collaboration a normal capability rather than a privileged role.

---

## 3. Core Attributes

### 3.1 AgentTemplate

| Attribute | Meaning |
|-----------|---------|
| `id` | stable template ID |
| `display_name` | user-facing name |
| `capability` | routing key |
| `system_prompt` | stable prompt prefix |
| `tools` | allowed tool set |
| `model_config` | model and generation settings |
| `constraints` | optional safety and scope restrictions |
| `version` | template version |

### 3.2 AgentInstance

| Attribute | Meaning |
|-----------|---------|
| `id` | unique run ID |
| `template_id` | source template |
| `session_id` | owning Session |
| `task_id` | assigned Task |
| `working_memory` | per-run context |
| `created_at` | creation time |
| `status` | `running`, `done`, `failed` |

AgentInstance is runtime-only. It should not be the place where long-term memory lives.

---

## 4. Design Principles

### 4.1 Stateless Beats Stateful

Stateless Agents remove:

- lifecycle ambiguity;
- cross-task memory leaks;
- scheduling affinity requirements;
- hard-to-replay actor histories.

The cost is lower cache reuse and repeated setup. That cost is acceptable for v1 because the simplicity gain is large.

### 4.2 One Agent, One Task

An Agent instance never runs multiple Tasks. If two Tasks need the same capability, the system creates two instances from the same template.

This keeps logs, traces, and failures clean: one `agent_run_id` maps to one `task_id`.

### 4.3 Agent Is a Runtime Projection of Capability

The Task says what capability it needs. The AgentTemplate says it can provide that capability. The AgentInstance is the runtime projection of that match.

### 4.4 Tool Is the Fine-Grained Capability

High-level capability is coarse. Tool access is the real permission boundary. A planning Agent and an execution Agent may both understand code, but only the latter should have write or shell tools.

---

## 5. Lifecycle

### 5.1 Registration

AgentTemplates are registered when the Session starts. Registration validates capability names, tool availability, prompt schema, and model configuration.

### 5.2 Instantiation

When the TaskBus selects a Task, it creates an AgentInstance from the matching template and injects:

- SessionConfig;
- Task intent and parent context;
- relevant Task results;
- ThoughtStore retrievals;
- tool bindings.

### 5.3 Execution

The instance runs an LLM loop, calls tools, and may publish subtasks. All events are written to EventStream with `agent_run_id`.

### 5.4 Destruction

After `done` or `failed`, temporary working memory is discarded. Durable outputs are already in Task results, EventStream, Workspace, or ThoughtStore.

---

## 6. Relationships With Other Components

| Component | Relationship |
|-----------|--------------|
| Task | one AgentInstance executes one Task |
| TaskBus | selects template and starts the instance |
| Session | owns config and resource boundaries |
| Workspace | tool-mediated read/write target |
| EventStream | stores the full run history |
| ThoughtStore | stores reusable knowledge outside the Agent |

---

## 7. Future Development

### 7.1 v1.x: Warm Agent Pool

Preload prompts and tool schemas without preserving task state. This improves latency while keeping the stateless rule intact.

### 7.2 v1.x: Capability Namespaces

Move from `"audit"` to namespaced capabilities such as `"code.audit"` or `"research.summarize"`.

### 7.3 v2.x: Experience Inheritance

Let templates retrieve historical experience from ThoughtStore. The Agent remains stateless; memory is injected explicitly.

### 7.4 v3.x: Capability Composition

Allow a Task to request multiple capabilities, or allow the dispatcher to compose several Agents.

### 7.5 v3.x: Cross-Session Templates

Share validated AgentTemplates across projects and users with permission controls.

---

## 8. Decision Summary

| Decision | Choice | Reason |
|----------|--------|--------|
| Agent model | function-like instance | easier scheduling and replay |
| State | no state across Tasks | avoids memory leakage |
| Task concurrency | one Task per instance | traceability |
| Routing | single capability | simple v1 dispatcher |
| Collaboration | through tools | no special orchestrator class required |
