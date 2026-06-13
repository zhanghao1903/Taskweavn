# Feature Plan: Read-Only Inquiry Context

> Status: planned
>
> Last Updated: 2026-06-13
>
> Owner: Product / Context / Backend / Frontend
>
> Related:
> [Plato Runtime Input Model](../../product/plato-runtime-input-model.md),
> [Plato Session Content Model](../../product/plato-session-content-model.md),
> [ADR-0017 Session And Workspace Context Management Foundation](../../decisions/ADR-0017-session-and-workspace-context-management-foundation.md),
> [Runtime Input Router Contract](runtime-input-router-contract.md)

---

## 1. Gap

Users need to ask questions about files, diffs, results, audit records, errors,
and current progress without creating or changing work.

Current system has workspace inspection, Audit, diagnostics, result/file
summaries, and task context, but no dedicated Inquiry Context or answer route
that guarantees no Plan, TaskBus, or workspace mutation.

---

## 2. Target

Read-only inquiry answers questions with evidence refs and no side effects.

Allowed reads:

- selected file snippets;
- diff summaries;
- result summaries;
- audit records and evidence descriptors;
- diagnostic summaries;
- task/session status;
- safe workspace inspection data.

Forbidden:

- workspace writes;
- shell commands with side effects;
- Plan or TaskNode mutation;
- TaskBus claim/complete/fail;
- hidden context promotion;
- raw prompt/provider/log payload exposure.

---

## 3. Implementation Slices

### ROI-1. Inquiry Contract

- Define inquiry request/response shape.
- Define answer provenance refs.
- Define no-mutation guarantee and test contract.

### ROI-2. Inquiry Context Builder

- Build bounded context from selected refs.
- Reuse workspace inspection and audit evidence stores.
- Include disclosure and truncation metadata.

### ROI-3. Answer Provider

- Add read-only LLM/profile path or deterministic answer path.
- Return answer plus evidence refs.
- Record Activity item as `Answer only`.

### ROI-4. Frontend Entry

- Route `Ask` / read-only question through Runtime Input Router.
- Display answer in Conversation / Activity and relevant detail surfaces.

### ROI-5. No-Mutation Tests

- Verify inquiry does not write workspace files.
- Verify inquiry does not mutate Plan, TaskNode, ASK, confirmation, or TaskBus.

---

## 4. Non-Goals

- No semantic memory.
- No vector retrieval.
- No autonomous research workflow.
- No file edits.
- No hidden guidance recording.
