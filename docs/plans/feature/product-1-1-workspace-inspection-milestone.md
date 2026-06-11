# Feature Plan: Product 1.1 Workspace Inspection Milestone

> Status: accepted
> Last Updated: 2026-06-10
> Product Baseline: [Plato Product 1.1 Plan](../../product/plato-1-1-product-plan.md)
> Focus Memo: [Workspace-Aware Agent Foundation](../../product/plato-1-1-workspace-aware-agent-foundation.md)
> Engineering Contract: [Git, Diff, And File Viewer API Contract](../../engineering/git-diff-file-viewer-api-contract.md)
> Related: [Multi-Workspace API And Runtime Contract](../../engineering/multi-workspace-api-runtime-contract.md), [Outcome Review Model](../../product/plato-outcome-review-model.md), [Runtime Input Model](../../product/plato-runtime-input-model.md), [Task Semantics](../../product/plato-task-semantics.md)

---

## 1. Purpose

Product 1.1 starts by making a real workspace inspectable.

Product 1.0 can show result summaries, file summaries, Audit entries, and
diagnostic bundles. That closes the first loop, but it does not yet let the
user inspect the actual repository state or open the file/diff that explains a
Task outcome.

This milestone creates the Product 1.1 P0 foundation for:

```text
Task / Result / Audit
  -> changed files
  -> file viewer
  -> per-file diff
  -> captured inspection evidence
```

The goal is trust before broader automation.

## 2. Product Decision

Workspace inspection is the first Product 1.1 milestone.

The first implementation should deliver read-only inspection:

- repository status;
- changed file list;
- per-file structured diff;
- text file viewer with line ranges;
- safe path labels;
- file/diff evidence refs for Main Page, Audit Page, Outcome Review, and
  diagnostics.

Do not start Product 1.1 with Skills, MCP, Result Packaging cards, public Agent
protocols, or multi-agent routing. Those remain important, but they depend on
the user first being able to verify what changed.

## 3. Scope

In scope:

- workspace-scoped inspection APIs under the accepted multi-workspace route
  model;
- safe git status and diff read model;
- optional desktop Git initialization readiness as a follow-up to reduce
  `not_git` friction for new plain-folder workspaces;
- text file content reads by bounded line range;
- large file, binary file, missing file, and non-git workspace fallbacks;
- path normalization and `.plato` protection;
- evidence ref model for captured status, diff, and file snapshots;
- frontend entry points from Main Page file summaries, Audit evidence, and
  Outcome Review;
- Browser/Electron smoke against a real local repo with deterministic changes.

Out of scope:

- branch management UI;
- commit authoring automation;
- merge conflict resolution UI;
- staging/unstaging controls;
- line-range write/replace tools;
- read-only inquiry answers over files/diffs;
- semantic/vector search;
- public Skills or MCP integration;
- binary, document, spreadsheet, or image viewers.

## 4. User-Facing Behavior

The user should be able to answer:

1. What changed in this workspace?
2. Which Task or result is related to that change?
3. What changed inside this file?
4. Can I open the relevant file lines?
5. Is there Audit evidence for this file or diff?

The first visible surfaces are:

| Surface | Product behavior |
|---|---|
| Main Page | File summary items can open file or diff when inspection data is available. |
| Task Detail | Completed/failed Tasks expose related file changes, file viewer links, and Audit links. |
| Audit Page | Evidence records can link to captured file/diff evidence without exposing raw paths. |
| Outcome Review | Workspace Changes area shows changed files near result summary and warnings. |
| Diagnostics | Bundles include redacted inspection descriptors and evidence refs, not raw absolute paths. |

## 5. Backend Ownership

The backend owns a workspace-scoped inspection gateway.

```text
WorkspaceInspectionGateway
  git status provider
  diff provider
  file content provider
  path policy
  evidence snapshot writer
```

Decision: the first provider uses controlled `git` CLI calls behind a backend
provider interface.

```text
GitInspectionProvider
  ControlledGitCliInspectionProvider
```

The provider must use fixed executable calls and argument lists. It must not
shell-concatenate user input, expose raw command output, or allow arbitrary git
commands. The public API must not expose this provider choice, so a future
Python git library provider can replace it without renderer contract changes.

Rules:

- route by `workspaceId`;
- resolve all filesystem access through the selected workspace root;
- reject `.plato` and path traversal;
- forbid symlink escapes outside the workspace root;
- return renderer-safe path labels;
- never return raw absolute paths;
- capture evidence snapshots only when a Task, Result, Audit record, or
  explicit diagnostic flow needs durable proof.

## 6. Frontend Ownership

The frontend owns a small inspection experience, not a full IDE.

First-version components:

- changed file list;
- file viewer with line numbers;
- diff viewer with file header and hunks;
- empty/non-git/error states;
- links from Main Page, Task Detail, Audit, and Outcome Review.

The first UI may be desktop-first. Mobile polish can be documented as a later
gap as long as the route remains reachable and readable.

## 7. Evidence Model

Live workspace reads and durable evidence are separate.

| Concept | Meaning |
|---|---|
| Live inspection | Reads current workspace status, diff, or file content for user inspection. |
| Captured evidence | Stores a stable, bounded status/diff/file snapshot ref for Audit, result, or diagnostics. |
| Path label | Renderer-safe path, such as `workspace://<workspaceId>/src/app.ts`. |
| Content hash | Hash of the content or line range used to detect drift. |

Audit should prefer captured evidence refs. Main Page and file viewer may read
live data, but must show stale/unavailable states when the workspace has
changed since the captured evidence was produced.

Decision: captured status, diff, and file snapshots are owned by a dedicated
workspace-scoped inspection store.

```text
<workspace>/.plato/inspection.sqlite
  inspection_evidence
```

Audit, diagnostics, result summaries, and future Outcome Review surfaces should
store and render `WorkspaceInspectionEvidenceRef` references from this store.
They should not duplicate snapshot payload ownership in their own stores.

Decision: Product 1.1 P0 uses bounded inspection responses.

| Limit | Default | Hard cap | Behavior when exceeded |
|---|---:|---:|---|
| Status changed files | 200 files | 500 files | `hasMore=true` and `workspace.inspection_truncated`. |
| File viewer range | 200 lines | 1000 lines | Return the bounded range only. |
| File viewer text payload | 256 KiB | 256 KiB | `truncated=true`. |
| Readable text file size | 1 MiB | 1 MiB | Return metadata with `too_large`; no content. |
| Single line length | 8 KiB | 8 KiB | Truncate the rendered line. |
| Diff context lines | 3 lines | 8 lines | Cap to 8. |
| Per-file diff payload | 256 KiB | 512 KiB | Return partial structured hunks with `truncated=true`. |
| Evidence safe payload | 128 KiB | 128 KiB | Keep descriptor and truncate payload. |

Decision: Product 1.1 P0 exposes staged/unstaged state as inspection metadata,
not as Git controls. The API returns staged, unstaged, and untracked counts plus
per-file `staged` and `unstaged` booleans. The UI may show lightweight
`Staged`, `Unstaged`, `Mixed`, and `Untracked` labels, but must not expose
stage/unstage commands in this milestone.

Decision: Product 1.1 P0 does not support arbitrary historical git refs,
branch compare, commit range compare, or raw revspec input. Stable historical
views come from captured evidence by `evidenceId`; live inspection reads the
current workspace state only.

## 8. Implementation Slices

### WIP-0. Contract And Plan

Status: accepted.

Deliver:

- this milestone plan;
- Git/Diff/File Viewer API contract;
- gap registry and index links.

Acceptance:

- Product 1.1 P0 decisions are documented before code.

### WIP-1. Backend Inspection Gateway

Status: implemented.

Deliver:

- status, diff, and file read models;
- `InspectionEvidenceStore` for captured status, diff, and file snapshots;
- path policy and safe labels;
- non-git, binary, large file, and missing file fallbacks;
- focused backend contract tests.

Acceptance:

- two registered workspaces route independently;
- no response exposes raw absolute paths;
- `.plato` and path traversal are rejected;
- changed file and diff output is deterministic.

### WIP-2. Frontend File/Diff Viewer

Status: accepted.

Deliver:

- API client/types;
- changed file list;
- text file viewer;
- structured diff viewer;
- loading, empty, error, unsupported, and stale states.

Acceptance:

- links from a seeded sidecar file summary open the correct file/diff;
- unsupported files show a clear fallback;
- text remains readable at desktop and tablet widths.

### WIP-3. Main/Audit/Outcome Wiring

Status: accepted.

Deliver:

- Main Page file summary links;
- Task Detail outcome links;
- Audit evidence links to captured file/diff evidence;
- Outcome Review Workspace Changes area.

Acceptance:

- Main Page, Audit, and result detail expose file/diff links;
- user can move from Task/Result file changes to file or diff inspection;
- broader Outcome Review acceptance remains outside this inspection milestone.

### WIP-4. Product Acceptance Smoke

Status: accepted.

Deliver:

- repeatable sidecar/Electron smoke with a seeded git repo;
- deterministic changed files and diff;
- file viewer, diff viewer, Audit evidence, and diagnostics export path.

Acceptance:

- configured Electron smoke covers the workspace inspection path through
  Main Page -> Audit file record -> diff viewer -> changed-files status;
- smokeRunner regression coverage proves the Electron configured path includes
  workspace inspection in fast non-GUI regression tests;
- packaged smoke can run the same path once release readiness needs it.

### WIP-5. Desktop Git Initialization Preference

Status: implemented.

Related plan:
[Workspace Git Initialization On Open](workspace-git-initialization-on-open.md).

Deliver:

- Settings Git availability status;
- Settings checkbox for "Initialize Git for opened workspaces";
- Electron bridge option for workspace open/switch;
- Electron main Git preparation before sidecar startup;
- `.plato/` written to `.git/info/exclude` instead of project `.gitignore`;
- focused Electron and frontend tests.

Acceptance:

- Git-unavailable environments show a safe unavailable state and disable the
  checkbox;
- option off preserves current `not_git` behavior;
- option on initializes plain folders and makes `.plato/` locally excluded;
- existing Git repositories are not reinitialized and do not duplicate the
  exclude entry.
- repeatable dev-shell smoke is available through
  `npm run electron:smoke:workspace-git`.

## 9. Test Plan

Backend:

- git repo status with clean, modified, deleted, renamed, and untracked files;
- non-git workspace returns `not_git` without failing the sidecar;
- file content reads respect line range limits;
- binary files return unsupported metadata without content;
- large text files return bounded content with truncation metadata;
- symlink escape and `.plato` paths are rejected;
- duplicate `sessionId` values in different workspaces do not cross-read.

Frontend:

- loading, empty, dirty, non-git, unsupported, stale, and error states;
- file/diff links from Main Page and Audit;
- no raw absolute path rendering;
- keyboard/focus path for viewer close/back navigation.

Smoke:

- real sidecar workspace with deterministic git changes;
- Electron dev-shell inspection path;
- diagnostics export includes redacted inspection descriptors.

Acceptance evidence:

```bash
cd frontend
npm run test:e2e:sidecar
npm run electron:smoke
```

Both commands passed on 2026-06-10 in a local environment that permits local
HTTP sidecar bind/connect to `127.0.0.1` and Electron GUI launch.

## 10. Decisions Closed And Remaining Gaps

Fixed decisions:

1. Provider implementation: controlled `git` CLI first, behind
   `GitInspectionProvider`.
2. Evidence storage: dedicated workspace inspection store under `.plato`.
3. Audit, diagnostics, result summaries, and Outcome Review reference
   inspection evidence refs instead of owning duplicated snapshot payloads.
4. Limits: bounded status, file viewer, diff, and evidence payload caps as
   listed in the Evidence Model section.
5. Staged/unstaged: expose metadata and labels only; no stage/unstage controls.
6. Historical refs: defer arbitrary refs; use captured evidence for stable
   historical views.
7. Untracked files: file content is viewable through the same bounded file
   viewer policy; diff remains unavailable until a frontend need is documented.

Remaining follow-ups after acceptance:

1. Raw unified diff remains deferred. Structured hunks are the canonical P0
   response unless a concrete UI or diagnostic need appears.
2. Live inspection is captured only through explicit evidence capture requests.
   Opening a viewer route does not create durable evidence.
3. Desktop Git initialization preference is implemented for Electron dev shell.
   Packaged/installer smoke can reuse the same path once release readiness
   needs it.

## 11. Acceptance Criteria

This milestone is accepted when:

1. A user can inspect workspace status and changed files for the selected
   workspace.
2. A user can open a changed text file and a per-file diff from Main Page or
   Audit.
3. Captured evidence refs can be linked from Audit/diagnostics without raw
   absolute paths.
4. Non-git, missing, binary, large, and stale cases are handled explicitly.
5. `.plato` and path traversal are protected.
6. Sidecar/Electron smoke validates the product path with real repo data.

## 12. Follow-Up Milestones

After Workspace Inspection:

1. Precision file tools: completed Product 1.1 line-range read, replace,
   append, search, and changed-line evidence scope.
2. Runtime input modes: read-only question, guidance, command, ASK answer, and
   confirmation response routing.
3. Inquiry context: answer questions over file/diff/result/audit without
   mutating TaskTree, TaskBus, or workspace.
4. Skills contract: metadata, risk, context, capability, and Audit semantics.
