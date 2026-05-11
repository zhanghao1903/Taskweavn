# ADR-0001: Roadmap Rebaseline After Phase 3.8

> Status: accepted
> Date: 2026-05-11
> Related: [Roadmap](../roadmap.md), [Project Plan](../project/roadmap.md), [Interaction Layer Design](../architecture/interaction-layer.md)

---

## Context

The original Phase 3 plan was driven by the Interaction Layer technical design. That design has now been implemented through Phase 3.8:

- session/workspace/event persistence;
- risk and autonomy model;
- message stream and message bus;
- wait coordination;
- AgentLoop interaction integration;
- LLM risk assessment;
- derived session status.

After that work, the architecture direction changed in a meaningful way. TaskWeavn is no longer best described as a chat-first code agent with tools. The intended product shape is now **Task-first**:

```text
natural language -> draft Task Tree List -> user confirmation/editing -> Task publish -> TaskBus execution
```

This means the old Phase 3.9-3.13 order is no longer the best execution route. PlanTool, shared collaboration, RAG, and summarization remain useful, but they are less foundational than reliability, logging, Task authoring, Task publishing, and UI projection.

---

## Decision

Rebaseline the roadmap after Phase 3.8:

1. Treat Phase 3.1-3.8 as the completed **Interaction Substrate**.
2. Move reliability and observability work before deeper Task execution work:
   - LLM Provider abstraction, retry, DeepSeek thinking, OpenRouter routing.
   - Configurable logging with global/session/object/category controls.
3. Move Task-first model work before full UI implementation:
   - Task domain model vs UI ViewModel separation.
   - Collaborator Agent and Task authoring tools.
   - Task interaction replay.
4. Move Task publishing and pipeline work before multi-agent execution:
   - TaskPublisher abstraction.
   - Pipeline task loading.
   - Scheduled/API/custom Task publishing.
5. Move the old Phase 3.10-3.13 memory/collaboration/summarization work later, after TaskBus and UI projection are stable.

---

## Consequences

Positive:

- The plan now matches the actual product direction: Task as the user interaction object.
- Upcoming implementation sessions can pick sharper work packages.
- RAG/summarization will later operate on richer Task/message/log records, not only chat history.
- UI work will not be forced to depend on unstable backend Task shapes.

Trade-offs:

- Some originally planned Phase 3 items are delayed.
- The roadmap now has more parallel streams, so docs maintenance becomes more important.
- Short-term implementation may feel less linear, but each work package has clearer architectural value.
