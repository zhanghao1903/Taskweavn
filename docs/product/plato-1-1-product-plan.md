# Plato Product 1.1 Plan

> Status: planning baseline
>
> Last Updated: 2026-05-21
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

## 4. 1.1 Planning Principles

1. Keep Product 1.0 focused on the complete loop.
2. Treat 1.1 features as capability expansion, not prerequisites for 1.0.
3. Preserve TaskNode as the interaction anchor for skills, MCP calls, files,
   multimodal inputs, result packaging, and after-task automation.
4. Do research before committing implementation plans for skills, MCP, and
   multimodal support.
5. Update Gap Registry before turning any 1.1 research topic into an executable
   plan.

## 5. Downstream Planning

When Product 1.0 is stable enough for the next planning pass, create or update
feature plans for:

- completion-time `task_after` pipeline;
- Result Packaging Agent and cards;
- skills integration;
- MCP integration;
- file and multimodal support.

Each plan should state whether it extends Authoring Domain, TaskBus execution,
CapabilityCatalog, UI API contract, Audit Page, or all of them.
