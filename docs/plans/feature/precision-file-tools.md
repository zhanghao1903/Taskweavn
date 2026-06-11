# Precision File Tools

> Status: completed for Product 1.1 precision file tools scope
>
> Last Updated: 2026-06-11
>
> Owner: Backend / Tools / Trust / Frontend
>
> Product Baseline:
> [Workspace-Aware Agent Foundation](../../product/plato-1-1-workspace-aware-agent-foundation.md)
>
> Predecessor:
> [Product 1.1 Workspace Inspection Milestone](product-1-1-workspace-inspection-milestone.md)
>
> Technical Design:
> [Precision File Tools Technical Design](precision-file-tools-technical-design.zh-CN.md)
>
> Related Contract:
> [Git, Diff, And File Viewer API Contract](../../engineering/git-diff-file-viewer-api-contract.md)

---

## 1. Purpose

Workspace Inspection made the repository inspectable: status, changed files,
structured diffs, text file viewer, and captured evidence refs are available.

Precision File Tools are the next Product 1.1 step. They make workspace file
operations safer and more auditable than full-file overwrite tools by giving
execution Agents bounded operations:

- read a file by line range;
- search the workspace within policy limits;
- replace a specific line range after drift validation;
- append to an existing text file safely;
- produce deterministic changed-line evidence.

The product goal is not to build an IDE. The goal is to reduce accidental file
damage and make every Agent file operation explainable in Main Page, Audit,
Outcome Review, and diagnostics.

## 2. Product Decision

Precision File Tools are a Product 1.1 P0/P1 bridge capability after Workspace
Inspection and before broader runtime input modes, skills, MCP, or multi-agent
productization.

Decision:

```text
Workspace Inspection is the read-only trust layer.
Precision File Tools are the bounded write/read/search execution layer.
```

Full-file `write_file` remains available as a legacy/general tool, but new
coding-oriented execution should prefer line-scoped tools when the Agent has
enough local context.

## 3. Goals

1. Reuse the accepted workspace path policy and `.plato` protection.
2. Provide bounded line-range read with stable line numbers and content hashes.
3. Provide bounded workspace search for filenames and text matches.
4. Provide line-range replace with expected-hash drift protection.
5. Provide append with idempotency protection so retries do not duplicate text.
6. Store durable operation/evidence records for mutating file tools.
7. Project changed-line evidence into result summaries, file summaries, Audit,
   Outcome Review, and diagnostics.
8. Keep renderer payloads path-safe and bounded.

## 4. Non-Goals

- No direct user-facing code editor in this milestone.
- No branch management, commit authoring, staging, unstaging, merge conflict,
  or git history UI.
- No raw shell-like file mutation API.
- No arbitrary patch application.
- No binary, document, spreadsheet, image, or multimodal editing.
- No semantic/vector search.
- No public Skills or MCP integration.
- No broad replacement of existing Workspace Inspection routes.

## 5. User-Facing Behavior

The user should see more reliable file changes, not necessarily more controls.

| Surface | Expected behavior |
|---|---|
| Main Page | File summaries can include changed line ranges when available. |
| Task Detail | Result/error detail can reference line-scoped operations and evidence. |
| Audit Page | File operations expose before/after hashes, path labels, and changed ranges. |
| Workspace Inspection | Existing file/diff viewer remains the read-only inspection surface. |
| Diagnostics | Bundles include redacted operation descriptors, not raw absolute paths. |

The first implementation can run behind Agent execution only. Direct UI edit
controls should wait until the tool/evidence contract is proven.

## 6. Tool Surface

Initial tool candidates:

| Tool | Effect | Risk | Product use |
|---|---|---:|---|
| `read_file_range` | read-only | low | Load just enough file context for the current Task. |
| `search_workspace` | read-only | low/medium | Find relevant files or text before editing. |
| `replace_file_range` | user workspace mutation | medium/high | Replace known line ranges after drift check. |
| `append_file` | user workspace mutation | medium | Append to an existing text file with idempotency. |

The mutating tools must require an operation id and drift guard. They must not
silently overwrite a file that changed since the Agent inspected it.

## 7. Safety And Evidence Rules

1. All paths are workspace-relative and resolved through the accepted
   `WorkspaceInspectionPathPolicy`.
2. `.plato`, path traversal, absolute paths, symlink escapes, binary files, and
   oversized files are rejected or returned as unsupported metadata.
3. Mutating tools require a stable `operationId`.
4. Mutating tools require an expected content hash or an explicit policy reason
   for why a hash is unavailable.
5. If the expected hash does not match current file content, the operation is
   rejected with a drift error and no write happens.
6. Append operations must be idempotent by `operationId`.
7. Every mutating operation records before/after content hashes, changed line
   ranges, and a bounded descriptor.
8. Agent prose is not authoritative. The operation/evidence record is the
   source of truth for what changed.

## 8. Implementation Slices

### PFT-0. Plan And Technical Design

Status: completed by this document and the accepted technical design.

Deliver:

- feature plan;
- technical design;
- gap registry update;
- plan index update.

Acceptance:

- downstream code tasks have explicit scope, non-goals, data model, tests, and
  evidence rules.

### PFT-1. Backend Contract And Models

Status: completed.

Deliver:

- line range, search match, edit request, edit result, and evidence models;
- limits and warning codes;
- operation idempotency result shape;
- drift error shape.

Acceptance:

- model validation covers path, range, limits, unsupported file, drift, and
  idempotency errors.

### PFT-2. Read-Only Precision Providers

Status: completed.

Deliver:

- line-range read provider;
- bounded workspace search provider;
- captured read/search evidence where needed.

Acceptance:

- large, binary, missing, `.plato`, symlink escape, CJK, and no-match cases are
  handled explicitly.

### PFT-3. Mutating Providers

Status: completed.

Deliver:

- line-range replace provider;
- append provider;
- idempotent operation store;
- before/after hash and changed-line evidence capture.

Acceptance:

- duplicate append retries do not duplicate content;
- drift mismatch rejects safely;
- changed-line ranges are deterministic.

### PFT-4. Agent Tool Adapters

Status: completed.

Deliver:

- LLM-visible tool adapters for the precision file tools;
- tool descriptors and risk metadata;
- integration with existing AgentLoop observation recording.

Acceptance:

- execution Agents can use precision tools without raw absolute paths or
  unrestricted shell access.

### PFT-5. Projection And Audit Wiring

Status: completed for Product 1.1 precision file tools closure.

Deliver:

- file summary projection from precision operation evidence;
- Audit evidence refs;
- diagnostics descriptors;
- Outcome Review line-range references when available.

Acceptance:

- Main Page and Audit can explain what changed without trusting Agent prose.

Closure scope:

- File summary projection from precision mutation observations is implemented.
- Precision operations capture durable inspection evidence refs.
- Full Audit Page evidence-detail expansion remains a future Audit hardening
  enhancement, not a blocker for this completed slice.

### PFT-6. Product Smoke

Status: completed for targeted backend/tool acceptance.

Deliver:

- real workspace smoke with deterministic read/search/replace/append;
- sidecar/Electron path when UI evidence links are affected.

Closure note: deterministic backend/tool coverage is complete for this slice.
Broader sidecar/Electron evidence-link smoke can be added as a future
acceptance-hardening task when Audit evidence detail expansion resumes.

Acceptance:

- a user can inspect the resulting changed lines through existing Workspace
  Inspection and Audit surfaces.

Current scope:

- Targeted tests cover line-range read, workspace search, drift rejection,
  idempotent replace/append replay, operation conflict, protected metadata
  paths, and file-summary projection.
- Full sidecar/Electron smoke should be run after frontend entry points consume
  precision evidence links.

## 9. Test Plan

Backend:

- safe path policy reuse;
- line range bounds and truncation;
- large file and binary fallback;
- missing file behavior;
- workspace search limits and ignored/protected paths;
- replace success;
- replace drift rejection;
- append success;
- append idempotent replay;
- operation id conflict;
- evidence descriptors contain no raw absolute paths.

Agent/tool:

- precision tools are visible only in approved tool pools;
- mutating tools emit file operation observations;
- failed drift checks do not mark Tasks as successful file edits.

Frontend/projection:

- file summaries include changed line ranges when precision mutation evidence
  exists;
- Audit records link to evidence and existing file/diff viewer routes in a
  later UI/API wiring slice;
- diagnostics export redacts path and content.

Smoke:

- seeded workspace with one replace and one append;
- restart or retry does not duplicate append;
- Audit and Workspace Inspection can render the changed file/diff.

## 10. Acceptance Criteria

Precision File Tools are accepted when:

1. execution Agents can read file ranges and search within a workspace safely;
2. execution Agents can replace a line range only when expected hash matches;
3. execution Agents can append without duplicate writes on retry;
4. every mutating operation records durable changed-line evidence;
5. Main Page file summary can reference that evidence safely;
6. existing Workspace Inspection routes remain valid and are not replaced;
7. focused backend, tool, projection, and smoke tests pass.

Deferred acceptance:

- Audit detail and diagnostics descriptor surfacing for precision evidence are
  reserved for the next trust-surface integration slice.

## 11. Open Questions

1. Should line-range replace support zero-length insertion in the first slice,
   or should insertion remain a later tool?
2. Should workspace search support bounded regex now, or start with literal
   search only?
3. Should direct user-initiated file edits be exposed in UI, or remain Agent
   execution only until the evidence model is proven?
4. Should high-risk file patterns trigger confirmation by default in Product
   1.1, or only through autonomy profile settings?
