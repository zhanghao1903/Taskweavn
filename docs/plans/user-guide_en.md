# Plan: User Guide

## 1. Background

The architecture is becoming coherent, but users need a path that does not require reading every design document. The user guide should turn the system from an internal architecture into something people can try, understand, and extend.

## 2. Goals

- Provide a 30-minute onboarding path.
- Explain core terms with one map.
- Show common workflows.
- Teach debugging basics.
- Separate beginner, advanced, and developer content.

## 3. Audience Tiers

| Tier | Audience | Need |
|------|----------|------|
| Tier 1 | first-time user | run one useful task |
| Tier 2 | power user | configure autonomy, budget, presets |
| Tier 3 | developer | create Agent templates and tools |

## 4. Chapter Structure

1. What this system is
2. 30-minute quick start
3. Core concepts map
4. Running your first Session
5. Understanding Tasks and Agents
6. Autonomy and confirmations
7. Cost and budget
8. Reading traces
9. Configuration examples
10. Extending with Agent templates
11. Troubleshooting
12. FAQ

## 5. Terminology Map

### 5.1 One Diagram

```
User
  ↓
Session
  ├── Workspace
  ├── TaskBus
  │     └── Task tree
  ├── Agent instances
  ├── EventStream
  └── ThoughtStore
```

### 5.2 Quick Reference

| Term | Plain meaning |
|------|---------------|
| Session | one working context |
| Task | one unit of work |
| Agent | one-time executor for a Task |
| TaskBus | scheduler and state authority |
| Workspace | files / artifacts being worked on |
| EventStream | audit log |
| ThoughtStore | reusable memory |
| ActionCard | user decision card |

## 6. 30-Minute Quick Start

### 6.1 Principle

The quick start should produce a useful result before explaining the full architecture.

### 6.2 Draft Flow

```bash
# install
uv sync

# run first task
uv run agent run "Audit this folder and summarize risks"
```

Expected output:

```text
Session created
Root Task created
AuditAgent is analyzing...

Report
- potential issue ...
- suggested fix ...

Done (12s, $0.04)
```

## 7. Configuration Examples

Show three levels:

1. minimal config;
2. medium customization;
3. full customization.

Avoid dumping the whole schema first. Each example should explain why a user would choose it.

## 8. FAQ Directions

Include:

- Why did the Agent ask me for approval?
- How do I stop it from interrupting me?
- Why is a Task pending?
- How do I see what happened?
- How do I limit cost?
- How do I add a new Agent?

## 9. Debugging Chapter

### 9.1 Task Is Stuck

Checklist:

- Does the required capability exist?
- Is the parent Task done?
- Is the Session active?
- Is the budget exhausted?

### 9.2 Reading a Trace

Use one trace from `walkthrough.md` and explain each event in plain language.

## 10. Extension Chapter

### 10.1 Custom Agent Template

Show one small template:

```yaml
id: markdown_reviewer
capability: review_markdown
tools:
  - read_file
  - write_file
```

### 10.2 When Not to Extend

Warn users not to create new Agents when a config preset or tool toggle is enough.

## 11. Writing Style

- Concrete examples before abstractions.
- One term at a time.
- Avoid framework jargon unless it is immediately defined.
- Prefer "what you will see" over "what the system internally does" in beginner chapters.

## 12. Open Questions

- Should the first example be code-oriented or general-purpose?
- Should screenshots be required for the Web UI guide?
- How much architecture should be exposed to first-time users?

## 13. Milestones

| Milestone | Output |
|-----------|--------|
| M1 | terminology map |
| M2 | quick start |
| M3 | config examples |
| M4 | debugging chapter |
| M5 | extension chapter |

## 14. Acceptance Criteria

- A new user can run one useful task in 30 minutes.
- A user can explain Session / Task / Agent / TaskBus after reading one page.
- A user can debug a stuck Task using the guide.
- The guide links to deeper architecture docs but does not require them.

## 15. Related Plans

- `walkthrough.md`: canonical example.
- `ux-interaction.md`: explains ActionCards.
- `configuration.md`: source for config examples.
- `observability.md`: source for debugging workflow.
