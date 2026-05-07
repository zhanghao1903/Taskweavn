# Agent Project Plan

> [中文版](agent_project_plan.md)

## Priority Legend

- 🔴 P0: Must-do
- 🟠 P1: Important
- 🟢 P2: Enhancement
- ⚪ P3: Future

---

# Tier 1 — Design Philosophy

## Architecture Track (System Design Principles)

### Action / Observation Symmetry
All operations are strongly-typed Actions; all feedback is symmetrical Observations. CodeAction is a subclass of Action and does not break the type system.

### Runtime Decoupling
The agent core has no knowledge of the execution environment (local / Docker / remote sandbox). The interface is uniform; execution is transparent.

### Single Agent First, Multi-Agent Reserved
Complete the single-agent foundation first; multi-agent is an upper-layer abstraction added on top.

### Thought Side-Channel Storage
Thoughts are not first-class members of the EventStream; they are linked via `event_id` as a side channel.

## Execution Track (Engineering Principles)

### Configurable over Hardcoded
All non-core capabilities are configuration-driven.

### Interface before Implementation
Define the Protocol first.

### Observability Built-in
Logging / replay / querying are supported from day one.

### Audit Does Not Rely on LLM Self-discipline
Tracking is declared explicitly and instrumented automatically.

---

# Tier 2 — Overall Roadmap

## Architecture Track (A)

- A1 🔴 Core Abstraction Layer (Week 1–2)
- A2 🟠 CodeAction + Audit (Week 3–4)
- A3 🟢 Multi-Agent Architecture (Week 7–8)
- A4 🟢 Experience & Evaluation System (Week 9–10)

## Execution Track (E)

- E1 🔴 Minimal Single Agent (Week 1–3)
- E2 🟠 CodeAction + Audit (Week 4–6)
- E3 🟠 Memory + RAG (Week 6–8)
- E4 🟢 Multi-Agent Orchestration (Week 9–12)

---

# Tier 3 — Detailed Plan

## Phase 1 (Week 1–3) ✅ Complete

- Action / Observation types
- EventStream
- LLMClient
- Tools (ReadFile, WriteFile, ListDir, RunCommand)
- ReAct loop

## Phase 2 (Week 4–6) ✅ Complete

- CodeAction schema with TrackingConfig
- Sandboxed executor
- AuditAgent
- SqliteThoughtStore

## Phase 3 (Week 6–8)

- ConversationHistory
- RAG (retrieval-augmented generation)
- Persistence layer
- Benchmark suite

## Phase 4 (Week 9–12)

- Multi-agent orchestration
- Observability enhancements
- Inference optimisation
