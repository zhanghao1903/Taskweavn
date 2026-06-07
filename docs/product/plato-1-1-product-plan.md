# Plato Product 1.1 Plan

> Status: planning baseline
>
> Last Updated: 2026-06-07
>
> Scope: Product 1.1 capability direction after the Plato 1.0 closed loop.
> This document records what is intentionally moved out of Product 1.0 and
> what should be researched for the next product increment.

## 1. Product 1.0 Boundary

Plato 1.0 should prove the complete Task-first product loop:

```text
Natural language goal
  -> Draft TaskTree
  -> user review / edit / confirmation
  -> publish and execute Tasks
  -> show status, result, file changes, and audit entry
```

The 1.0 bar is a coherent user journey, not the richest possible automation
system. A feature should remain in 1.0 only if removing it would break this
closed loop.

## 1.1 Focus Memo And Semantic Prerequisites

The current Product 1.1 focus is workspace-aware coding collaboration:

- git and diff support;
- text file viewing;
- line-scoped tool operations;
- runtime user input modes;
- read-only inquiry;
- skills contract after workspace and input foundations are stable.

See
[Plato Product 1.1 Focus Memo: Workspace-Aware Agent Foundation](plato-1-1-workspace-aware-agent-foundation.md).

Before executable Product 1.1 implementation plans, these semantic baselines
should remain aligned:

- [Plato Task Semantics](plato-task-semantics.md);
- [Plato Session Content Model](plato-session-content-model.md);
- [Plato Runtime Input Model](plato-runtime-input-model.md);
- [Plato Plan Cycle Semantics](plato-plan-cycle-semantics.md);
- [Plato Outcome Review Model](plato-outcome-review-model.md).

These documents define what users believe Tasks, Session content, runtime
input, post-execution continuation, and outcome review mean. Implementation
plans should not invent conflicting meanings in API, frontend, or backend code.

## 2. Moved Out Of 1.0

The following capabilities are moved to Product 1.1 because they improve depth,
polish, or automation breadth, but they are not required for the first complete
1.0 loop.

| Capability | Product 1.1 Role | Why Not 1.0 |
|---|---|---|
| Completion-time `task_after` pipeline | Post-completion automation for summaries, validation, archival, or follow-up work. | A user can still complete the 1.0 loop if primary Tasks execute and show result / file changes / audit entry. Automatic after-tasks are useful but not structurally required. |
| Result packaging cards | Richer presentation for information-style answers and structured deliverables. | 1.0 only needs a clear result view. Card packaging improves comprehension for some result shapes, but plain result summaries can close the loop. |

Product 1.0 may keep architecture hooks for these capabilities, but should not
treat their completion as a release blocker.

## 3. Product 1.1 Themes

Product 1.1 should expand what Tasks can understand, consume, and orchestrate
after the 1.0 control loop is stable.

### 3.1 Skills Integration

Goal: make reusable task capabilities visible and assignable without exposing
ordinary users to low-level tool wiring.

Research questions:

- What is the user-facing distinction between a Workflow, Skill, Agent, and
  Capability?
- Should skills be selected by the user, inferred by Collaborator, or both?
- How should skill availability and limitations appear on a TaskNode?
- Which skill metadata is required for feasibility assessment and assignment?

### 3.2 MCP Integration

Goal: connect TaskWeavn / Plato to external tools and data sources through MCP
while preserving Task-first control, confirmation, and audit boundaries.

Research questions:

- Which MCP servers are safe and valuable as first integrations?
- How should MCP tools appear in CapabilityCatalog and Agent assignment?
- What confirmation and risk policies are required for external side effects?
- How should MCP calls be summarized for Main Page and Audit Page?

### 3.3 File And Multimodal Support

Goal: allow users to provide files and multimodal inputs as first-class Task
context, not as hidden attachments inside chat turns.

Research questions:

- What file types should be supported first: documents, spreadsheets, images,
  PDFs, code folders, or mixed bundles?
- How should a file attachment become Task context, evidence, or a deliverable?
- What is the product model for image and document understanding in Task
  authoring and execution?
- How should multimodal inputs be represented in audit records and file change
  summaries?

### 3.4 Agent Protocol And Governance

Goal: define what an Agent must satisfy before it can be plugged into the
system, while deferring the full Agent protocol and special Agent role protocols
until the Agent model is better understood.

TODO:

- define the baseline Agent contract: stable identity, protocol version, role,
  capability declaration, tool/capability requirements, input/output schema,
  lifecycle hooks, health/failure behavior, observability events, and control
  capability declaration;
- define which state changes an Agent may request through commands, and which
  system state it must never mutate directly;
- define special Agent protocols later, including Routing Agent, Execution
  Agent, Collaborator Agent, Audit Agent, and Result Packaging Agent;
- define the routing/assignment foundation when multiple execution Agents,
  custom routing policy, or assignment visibility become product needs;
- decide how advanced users can plug in custom Agents, including router-style
  policy Agents, without making Agent extensibility part of Product 1.0;
- decide what templates, workflow scaffolding, or validation checks are needed
  to help users create compatible Agents.

This is a Product 1.1 planning item. Product 1.0 may keep conservative internal
Agent shapes, but it should not block on public Agent protocol finalization.

## 4. 1.1 Planning Principles

1. Keep Product 1.0 focused on the complete loop.
2. Treat 1.1 features as capability expansion, not prerequisites for 1.0.
3. Preserve TaskNode as the interaction anchor for skills, MCP calls, files,
   multimodal inputs, Agent assignment, result packaging, and after-task
   automation.
4. Do research before committing implementation plans for skills, MCP,
   multimodal support, and public Agent extensibility.
5. Update Gap Registry before turning any 1.1 research topic into an executable
   plan.

## 5. Downstream Planning

When Product 1.0 is stable enough for the next planning pass, create or update
feature plans for:

- completion-time `task_after` pipeline;
- Result Packaging Agent and cards;
- routing/assignment foundation;
- skills integration;
- MCP integration;
- file and multimodal support;
- runtime input model implementation;
- authoring context and Plan Cycle continuation;
- Agent protocol, special Agent protocols, and custom Agent creation /
  validation workflow.

Each plan should state whether it extends Authoring Domain, TaskBus execution,
CapabilityCatalog, UI API contract, Audit Page, or all of them.
