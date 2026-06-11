# Plato Product 1.1 Real Local QA Report - 2026-06-11

> Status: in progress
> Branch: `codex/product-1.1-qa-hardening`
> Baseline commit: `616bc1b`
> Scope: Product 1.0 core loop and Product 1.1 feature hardening
> Environment policy: use real local runtime and configured LLM provider; do not use mock mode as acceptance evidence.

## Objective

Validate and harden Plato Product 1.0 and Product 1.1 in a real local
environment.

Required outcomes:

- QA巡检 1.0 基本功能；
- QA巡检 1.1 新特性；
- confirmed product defects get GitHub issues and PR fixes;
- UX issues or improvement suggestions are recorded in an improvement list;
- final QA report records evidence, gaps, and release risk.

## Source Documents

- [Product 1.0 Frontend QA Runbook](plato-1-0-frontend-qa-runbook.md)
- [Product 1.1 Plan](plato-1-1-product-plan.md)
- [Workspace-Aware Agent Foundation](plato-1-1-workspace-aware-agent-foundation.md)
- [Product 1.1 Workspace Inspection Milestone](../plans/feature/product-1-1-workspace-inspection-milestone.md)
- [Git, Diff, And File Viewer API Contract](../engineering/git-diff-file-viewer-api-contract.md)
- [Token Usage Analytics](../plans/feature/token-usage-analytics.md)
- [Precision File Tools](../plans/feature/precision-file-tools.md)

## QA Scope Matrix

| Area | Requirement | Evidence target | Status |
|---|---|---|---|
| 1.0 startup | Open Plato from a real local app/runtime path. | URL/window, sidecar base URL, startup logs. | Pending |
| 1.0 first-run/settings | Missing config shows setup path; configured path reaches Main Page. | Screenshots/logs/API response. | Pending |
| 1.0 session loop | Create/select session, enter goal, generate/review TaskTree. | Session id, TaskTree state, UI evidence. | Pending |
| 1.0 task control | Select TaskNode, add task-scoped guidance, publish/execute. | Task status transitions and command responses. | Pending |
| 1.0 confirmation/ASK | Authoring ASK and Execution ASK are understandable and scoped. | UI evidence and API state. | Pending |
| 1.0 result/files | Result summary and file changes are visible after work. | Result/file summary evidence. | Pending |
| 1.0 Audit Page | Main Page -> Audit Page -> record detail works and stays read-only. | Audit route, record detail, return path. | Pending |
| 1.0 recovery | Recoverable errors show safe labels and no raw internal payloads. | Error state evidence. | Pending |
| 1.1 workspace inspection | Git status, changed files, file viewer, and structured diff work on a real repo. | API responses and UI evidence. | Pending |
| 1.1 path safety | Renderer/API do not expose raw absolute paths; `.plato` is protected. | Response scan and UI inspection. | Pending |
| 1.1 token usage | Real LLM activity records and displays usage summaries. | Usage API/UI evidence after provider call. | Pending |
| 1.1 precision file tools | Line-range read/search/replace/append work with drift/idempotency guards. | Tool result, file diff, evidence record. | Pending |
| 1.1 diagnostics | Diagnostics include redacted usage/inspection descriptors. | Export bundle contents. | Pending |

## Real Environment Plan

Primary runtime path:

```bash
uv run taskweavn plato-dev --workspace /private/tmp/plato-product-qa-workspace
```

Fallback/debug paths:

```bash
uv run taskweavn plato-sidecar --workspace /private/tmp/plato-product-qa-workspace
cd frontend && npm run electron:dev -- --workspace /private/tmp/plato-product-qa-workspace
```

The QA workspace must be a real Git repository with deterministic content and
safe test files. The run may use real LLM calls because the LLM environment is
configured.

## Findings

No findings recorded yet.

## GitHub Issues And Fix PRs

No issues or fix PRs recorded yet.

## UX Improvement List

No UX improvements recorded yet.

## Evidence Log

| Time | Check | Evidence | Result |
|---|---|---|---|
| 2026-06-11 | Branch baseline | `codex/product-1.1-qa-hardening` from `616bc1b` | Started |
