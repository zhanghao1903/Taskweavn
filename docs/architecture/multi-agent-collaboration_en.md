# Multi-Agent Collaboration Architecture

> [中文版](multi-agent-collaboration.md) · v1.1 · 2026-06-24
>
> Status: historical architecture concept reference
>
> Product 1.1 alignment: this document preserves the early multi-agent collaboration concept. Current Product 1.1 implements Runtime Input Router, task-scoped Default Agent execution, Agent LLM resolver, read-only inquiry, and command-backed contract revision. Full Agent Manager, dynamic assignment, and custom Agent protocol remain later extensions. Use [overview.md](overview.md), [agent.md](agent.md), [task.md](task.md), and [bus.md](bus.md) for current facts.

---

## Table of Contents

1. [Core Design Principles](#1-core-design-principles)
2. [Message Stream Model](#2-message-stream-model)
3. [Autonomy System](#3-autonomy-system)
4. [Conversation-driven Orchestration](#4-conversation-driven-orchestration)
5. [Constraint-driven UI Orchestration](#5-constraint-driven-ui-orchestration)
6. [Core Data Structures](#6-core-data-structures)
7. [System Architecture Overview](#7-system-architecture-overview)
8. [Progressive Constraint Evolution](#8-progressive-constraint-evolution)
9. [Key Design Trade-offs](#9-key-design-trade-offs)

---

## 1. Core Design Principles

### 1.1 Two Core Principles

The entire architecture is built around two orthogonal principles that together govern how agents and users collaborate.

**Principle 1: Stream over Interrupt**

Traditional human-in-the-loop systems rely on a "pause → wait → resume" blocking model where the system drives the pace and the user is forced to respond. This architecture replaces that with a **message stream model**: agents post requests to a stream; users can respond or not; what happens without a response is determined by the autonomy configuration. The user is always the active party.

**Principle 2: Constraint-driven User Orchestration**

Users are not forced to understand graph structures. Instead the LLM acts as the orchestration designer, generating a valid agent collaboration graph within constraint boundaries. Users describe intent in natural language and make local adjustments through the UI. The constraints themselves evolve as the system matures.

### 1.2 The Core Shift

```
Old model                           New model
──────────────────────────────────────────────────────────────
interrupt → pause → resume          message stream + response policy
user fills in orchestration config  describe intent → LLM generates draft
constraints are post-hoc validators constraints are generation-time context
flexibility is the default          constraints are the default; loosening needs data
```

---

## 2. Message Stream Model

### 2.1 Overview

All user-facing communication produced during agent execution flows into a single **Message Stream**. Users can observe in real time and intervene at any point, but are never forced to block.

```
┌─ Agent Execution ────────────────────────────────────────────┐
│  Planner → Executor → Auditor → ...                          │
│      ↓          ↓         ↓                                  │
└──────────────────────────────────────────────────────────────┘
              ↓  ↓  ↓
┌─ Message Stream ─────────────────────────────────────────────┐
│  [INFO]  Planner: execution plan generated, 5 steps          │
│  [ASK]   Executor: about to delete config.py — confirm?      │
│  [INFO]  Executor: auth.py modified (line 42)                │
│  [WARN]  Auditor: potential security vulnerability found      │
└──────────────────────────────────────────────────────────────┘
              ↑
         user may respond at any time, or not at all
```

### 2.2 Two Message Types

| Type | Meaning | Agent behaviour |
|------|---------|----------------|
| **Informational** | Tells the user what the agent did | Sends and continues immediately |
| **Actionable** | Requests user input or confirmation | Waits according to autonomy config |

### 2.3 Message Structure

```python
@dataclass
class AgentMessage:
    id: str
    agent_id: str
    message_type: Literal["informational", "actionable"]
    content: str
    context: dict               # related code snippets, file paths, etc.
    action_options: list[str]   # actionable only — options presented to user
    requires_response: bool
    created_at: datetime
    timeout_seconds: float | None
```

### 2.4 "Never Interrupted" State

When the user sets autonomy to maximum, every Actionable message has a timeout with automatic proceed, and the stream degrades to a **read-only execution log**. The user can inspect it at any time, but nothing blocks agent execution.

```
autonomy = 1.0  →  stream = execution log   →  user never interrupted
autonomy = 0.0  →  stream = collaboration   →  user participates in every key decision
```

This is the user's active choice. The system's only responsibility is to present the quality–autonomy trade-off clearly.

---

## 3. Autonomy System

### 3.1 What Autonomy Really Means

Autonomy is not a magic number — it is a precise description of "how the agent acts under uncertainty." There are two orthogonal dimensions:

- **Trigger dimension**: when the agent considers user involvement necessary
- **Wait dimension**: after sending a request, how long to wait and what to do on timeout

### 3.2 AutonomyBehavior Configuration

```python
@dataclass
class AutonomyBehavior:
    # Trigger dimension: when to send an Actionable message
    trigger: Literal[
        "never",             # never; all messages are Informational
        "on_risk",           # high-risk operations only (delete, exec, etc.)
        "on_uncertainty",    # when LLM confidence falls below threshold
        "always",            # every key action requests confirmation
    ]
    confidence_threshold: float  # 0.0–1.0; relevant only for on_uncertainty

    # Wait dimension: what happens after an Actionable message is sent
    wait_timeout: float | None   # seconds; None = wait indefinitely
    timeout_action: Literal[
        "wait",              # keep waiting (low-autonomy default)
        "proceed_default",   # continue with the most conservative choice
        "proceed_confident", # continue with the highest-confidence LLM choice
        "skip",              # skip the action entirely
    ]
    notify_on_proceed: bool      # notify user when agent self-decides on timeout
```

### 3.3 Preset Autonomy Levels

| Level | trigger | wait_timeout | timeout_action | Best for |
|-------|---------|--------------|----------------|---------|
| **Full auto** | never | — | — | Batch jobs, reversible tasks |
| **Risk confirm** | on_risk | 300s | proceed_default | Everyday default |
| **Collaborative** | on_uncertainty | None | wait | Complex, high-impact tasks |
| **Full confirm** | always | None | wait | Learning, audit scenarios |

### 3.4 AutonomyGate: Decision Entry Point

Every agent passes through the AutonomyGate before executing an action:

```python
class AutonomyGate:
    def check(
        self,
        action: CodeAction,
        confidence: float,
        behavior: AutonomyBehavior,
    ) -> GateDecision:
        if behavior.trigger == "never":
            return GateDecision.PROCEED
        if action.is_high_risk and behavior.trigger in ("on_risk", "always"):
            return GateDecision.SEND_ACTIONABLE
        if confidence < behavior.confidence_threshold:
            return GateDecision.SEND_ACTIONABLE
        return GateDecision.PROCEED
```

### 3.5 Quality vs Autonomy Trade-off

The UI should surface this trade-off explicitly rather than hiding it:

```
High autonomy  ████████░░
  ✓ Execution uninterrupted, fast
  ✓ Low cognitive load for user
  ✗ Agent guesses on ambiguous situations
  ✗ Errors may accumulate without user awareness

Low autonomy   ██░░░░░░░░
  ✓ User participates in every key decision
  ✓ Low error rate, high controllability
  ✗ Requires continuous attention from user
  ✗ Task speed depends on user response time
```

The choice belongs entirely to the user; the system makes no judgement.

---

## 4. Conversation-driven Orchestration

### 4.1 LLM as Orchestration Designer

Users do not need to understand graph structures. The **Orchestration Designer** (a meta-agent) translates user intent into a valid agent collaboration graph within constraint boundaries. Users only select and fine-tune.

```
User natural language intent
        ↓
OrchestrationDesigner (meta-agent)
  Input:  user intent + ConstraintProfile + ToolRegistry
  Output: OrchestrationDraft (valid graph + node configs + rationale)
        ↓
UI renders graph  ←→  user fine-tunes (multiple choice, not free text)
```

**Key principle: constraints are generation-time context, not post-hoc validators.** The LLM generates within constraint bounds; the output is valid by construction, eliminating "UI allows but backend rejects" inconsistencies.

### 4.2 Three Generation Phases

**Phase 1: Intent Parsing**

```
User: "I want a system that audits code for security vulnerabilities and auto-fixes them"

Parsed output:
  Core capabilities: [code reading, vuln analysis, fix execution, validation loop]
  Risk identified:   fix execution = high-risk, requires user confirmation
  Constraint map:    auditor node required; interrupt before fix
```

**Phase 2: Constraint-aware Graph Generation**

The LLM receives the ConstraintProfile as prompt context and generates a graph topology within allowed bounds — no backend validator needed.

**Phase 3: Capability Assignment**

Each agent node **selects** tools from the ToolRegistry; it cannot generate or reference tools outside the Registry. The tool set is the system's security floor.

### 4.3 Conversation as Diff, Not Full Regeneration

User feedback on a draft triggers a local patch, not a full regeneration:

```
User: "make the executor more autonomous"

DraftPatch:
  target_node: "executor"
  changes:
    autonomy_behavior.trigger: "on_uncertainty" → "on_risk"
    autonomy_behavior.confidence_threshold: 0.7 → 0.4
  reason: "Reduce interruption frequency; executor tries first rather than asking"
```

The UI highlights the changed node. The user sees a diff, not an entirely new graph to re-understand.

### 4.4 OrchestrationDraft Structure

```python
@dataclass
class OrchestrationDraft:
    nodes: list[AgentNodeDraft]
    edges: list[EdgeDraft]
    rationale: str                      # LLM explains the design; shown to user

@dataclass
class AgentNodeDraft:
    id: str
    agent_type: AgentType
    display_name: str
    description: str                    # this node's role within the orchestration
    tool_set: list[ToolRef]             # subset selected from ToolRegistry
    autonomy_behavior: AutonomyBehavior
    suggested_alternatives: list[AgentType]  # types the user may swap this node to
```

`suggested_alternatives` turns node replacement into a **multiple-choice question** — users don't need to know what agent types exist.

### 4.5 ToolRegistry: A Closed Tool Set

```python
class ToolRegistry:
    tools: dict[ToolId, ToolSpec]
    compatible_tools: dict[AgentType, list[ToolId]]  # predefined compatibility

    def suggest_for(
        self,
        agent_type: AgentType,
        intent_keywords: list[str],
    ) -> list[ToolSpec]:
        # returns compatible_tools sorted by relevance
        # LLM selects from this list; cannot introduce tools outside it
```

---

## 5. Constraint-driven UI Orchestration

### 5.1 Layered Configuration Model

```
Layer 3: Custom DAG (advanced users)
  Freely connect agent nodes within constraint bounds, adjust any parameter

Layer 2: Preset + parameter tuning (intermediate users)
  Pick a best-practice template, adjust key parameters via sliders

Layer 1: Preset selection (regular users)
  Auto-pilot / Co-pilot / Manual / Audit-Focus

All three layers normalise to the same OrchestrationConfig internally.
```

### 5.2 ConstraintProfile: Constraints as First-class Citizens

```python
@dataclass
class ConstraintProfile:
    version: str

    # Node dimension: which agent types the user may place
    allowed_agent_types: set[AgentType]

    # Edge dimension: which connections are allowed
    allowed_edges: list[EdgeRule]          # (src_type, dst_type, condition)
    forbidden_patterns: list[Pattern]      # e.g. no executor→executor direct link

    # Composition dimension: system-wide constraints
    required_nodes: set[AgentType]         # e.g. auditor must always be present
    max_parallel_branches: int

    # Meta: why each constraint exists
    rationale: dict[str, str]              # constraint_key → failure mode description
```

`rationale` is not a comment — it is **the input to loosening decisions**: it tells you what failure mode you're betting against when you remove a constraint.

### 5.3 Constraints in the UI

Constraints are **natural boundaries**, not error walls:

- The node palette only shows `allowed_agent_types`; forbidden nodes simply do not exist (not greyed out)
- Edge validation fires during drag; illegal connections snap back before the user releases the mouse
- The parameter panel only renders exposed config items; everything else is silently filled with system defaults

### 5.4 Built-in Presets

| Preset | Topology | Default autonomy | Best for |
|--------|----------|-----------------|---------|
| **Auto-pilot** | sequential | high (on_risk) | Batch jobs, hands-off execution |
| **Co-pilot** | hierarchical | medium (on_uncertainty) | Everyday development assistance |
| **Manual** | sequential | low (always) | Learning, sensitive operations |
| **Audit-Focus** | DAG + feedback loop | medium | Code audit + auto-fix |

Presets are read-only templates. Selecting a preset forks a snapshot; modifications happen on the fork. The user can diff or reset to preset at any time.

---

## 6. Core Data Structures

### 6.1 Full Configuration Hierarchy

```
OrchestrationConfig
├── preset: OrchestrationPreset | None
├── constraint_profile: ConstraintProfile
├── nodes: list[AgentNodeConfig]
│   ├── id, agent_type, display_name
│   ├── tool_set: list[ToolRef]
│   └── autonomy_behavior: AutonomyBehavior
│       ├── trigger
│       ├── confidence_threshold
│       ├── wait_timeout
│       ├── timeout_action
│       └── notify_on_proceed
└── edges: list[EdgeConfig]
    ├── src, dst
    └── condition: EdgeCondition | None
```

### 6.2 Message Stream Structure

```
MessageStream
└── messages: list[AgentMessage]
    ├── id, agent_id, created_at
    ├── message_type: "informational" | "actionable"
    ├── content, context
    ├── action_options: list[str]
    ├── requires_response: bool
    └── response: UserResponse | AutoResponse | None
        ├── source: "user" | "timeout_default" | "timeout_confident"
        ├── value: str
        └── responded_at: datetime
```

---

## 7. System Architecture Overview

```
┌─ User Layer ──────────────────────────────────────────────────────┐
│                                                                   │
│  ┌─ Orchestration Design (one-time) ─┐  ┌─ Execution (live) ──┐  │
│  │ Describe intent in chat           │  │ Message Stream panel │  │
│  │ Review / adjust OrchestrationDraft│  │ [INFO] action log    │  │
│  │ Configure autonomy sliders        │  │ [ASK]  confirmations │  │
│  └───────────────────────────────────┘  │ [WARN] alerts        │  │
│                                         └──────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
         ↑ Draft                              ↑↓ Messages
┌─ Orchestration Layer ─────────────────────────────────────────────┐
│                                                                   │
│  OrchestrationDesigner          MessageStream                     │
│  (meta-agent)                   + AutonomyGate                   │
│    ├── intent parsing                                             │
│    ├── constraint-aware graph gen                                 │
│    └── tool set matching        ConstraintValidator               │
│                                 (static analysis at load time)    │
└───────────────────────────────────────────────────────────────────┘
         ↑ ConstraintProfile              ↑ OrchestrationConfig
┌─ Execution Layer ─────────────────────────────────────────────────┐
│                                                                   │
│  Agent Graph Runtime                                              │
│    ├── Planner Agent                                              │
│    ├── Executor Agent ──→ AutonomyGate ──→ MessageStream          │
│    ├── Auditor Agent                                              │
│    └── [user-defined nodes]                                       │
│                                                                   │
│  ToolRegistry (closed tool set)                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## 8. Progressive Constraint Evolution

Constraints are not permanent restrictions — they are staged guardrails backed by data.

### Loosening Decision Framework

```
A constraint may be loosened when all of the following hold:

1. Success rate data   N executions under this constraint, success rate > threshold
2. Failure attribution Current failures are NOT caused by this constraint
3. User benefit        Number / importance of use cases unlocked by loosening
4. Rollback path       How to quickly reinstate the constraint if failure rate rises

Metric: constraint value density = Δfailure rate / Δexpressible use cases
        Prioritise loosening low-density constraints (restrict much, unlock little)
```

### Three-phase Evolution

**v1: High guardrails (current)**
- Allowed nodes: Planner / Executor / Auditor (three fixed types)
- Allowed edges: two fixed edges + optional feedback loop
- Parallel branches: forbidden
- Exposed params: autonomy_behavior + tool toggles only
- Goal: success rate > 90%, zero user learning curve

**v2: Loosen topology**
- Open parallel branches (max = 2)
- Allow custom node display names
- LLM can generate DAGs, not just sequential flows
- Basis: v1 success rate data + failure attribution does not point to topology

**v3: Loosen tools**
- Allow custom tool integration (user provides Tool spec)
- Open ToolRegistry to dynamic extension
- Basis: most-requested "wish we had" tool types from user feedback

---

## 9. Key Design Trade-offs

### 9.1 Flexibility vs Success Rate

Strict early constraints sacrifice flexibility for high success rates. This is an intentional choice, not a technical limitation. Loosening happens with data backing, not feature accumulation.

### 9.2 User Control vs System Complexity

Giving users control over interruption means the system must handle all "no response" timeout scenarios. The four `timeout_action` strategies cover the main cases at manageable complexity.

### 9.3 LLM Generation vs Manual Configuration

The main risk of conversation-driven generation is LLM misreading intent. Mitigations:
- Displaying `rationale` so users can verify their intent was understood correctly
- Using Patch rather than full regeneration — each change is small and reviewable
- The final orchestration is fully visible and adjustable in the UI at all times

### 9.4 Message Stream vs Traditional Interrupt

The cost of the stream model: users must actively monitor the stream rather than being passively interrupted. Mitigations:
- Push notifications for Actionable messages
- Stream filtering (show only Actionable, hide Informational)
- Quick-action buttons inline in stream messages

---

## Appendix: Core Type Reference

| Type | Responsibility |
|------|---------------|
| `AutonomyBehavior` | Defines agent autonomy: trigger condition + wait strategy |
| `AutonomyGate` | Decision entry point before every agent action |
| `AgentMessage` | A single message in the stream — Informational or Actionable |
| `MessageStream` | Global stream; the sole collaboration channel between agents and user |
| `ConstraintProfile` | The current version's orchestration constraint set, with rationale |
| `OrchestrationDesigner` | Meta-agent that converts user intent to a valid OrchestrationDraft |
| `OrchestrationDraft` | LLM-generated orchestration proposal: graph + node configs + rationale |
| `DraftPatch` | Local modification triggered by user feedback; the minimal iteration unit |
| `ToolRegistry` | Closed tool set; LLM selects, never creates |
| `OrchestrationPreset` | Built-in best-practice template; user forks before modifying |
