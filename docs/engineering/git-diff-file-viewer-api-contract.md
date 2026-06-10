# Git, Diff, And File Viewer API Contract

> Status: accepted Product 1.1 P0 contract and implementation
> Last Updated: 2026-06-10
> Related Plan: [Product 1.1 Workspace Inspection Milestone](../plans/feature/product-1-1-workspace-inspection-milestone.md)
> Related Contract: [Multi-Workspace API And Runtime Contract](multi-workspace-api-runtime-contract.md)
> Product Baseline: [Workspace-Aware Agent Foundation](../product/plato-1-1-workspace-aware-agent-foundation.md)

---

## 1. Purpose

This contract defines the Product 1.1 P0 API shape for read-only workspace
inspection:

- repository status;
- changed file list;
- per-file diff;
- text file viewer;
- captured file/diff evidence refs.

The contract is backend-implementation neutral at the API boundary. Product
1.1 P0 implements the first provider with controlled `git` CLI calls behind
`GitInspectionProvider`; renderer-facing payloads must remain the shapes
defined here if a Python git library provider replaces it later.

## 2. Route Principles

All new routes are workspace-scoped.

```http
GET /api/v1/workspaces/{workspaceId}/inspection/status
GET /api/v1/workspaces/{workspaceId}/inspection/diff
GET /api/v1/workspaces/{workspaceId}/files/content
POST /api/v1/workspaces/{workspaceId}/inspection/evidence
```

Compatibility session routes may link to these endpoints, but new frontend
work should carry `workspaceId`.

Route rules:

- `workspaceId` is opaque and renderer-safe.
- File paths are workspace-relative query parameters, not raw absolute paths.
- Responses must include safe `pathLabel` values.
- Responses must not include raw absolute paths.
- `.plato` is protected from normal inspection reads.

## 3. Shared Types

### 3.1 Safe Path

```ts
type WorkspacePathRef = {
  relativePath: string;
  pathLabel: string;
};
```

Rules:

- `relativePath` uses POSIX separators.
- `relativePath` must not start with `/`.
- `relativePath` must not contain `..` segments after normalization.
- `pathLabel` uses `workspace://<workspaceId>/<relativePath>`.
- Renderer diagnostics may use `pathLabel`, never raw root paths.

### 3.2 Content Hash

```ts
type WorkspaceContentHash = {
  algorithm: "sha256";
  value: string;
};
```

The hash is over the exact bytes or normalized text segment represented by the
response. It is used for drift detection and future line-scoped writes.

### 3.3 Limits

Product 1.1 P0 uses fixed backend caps.

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

### 3.4 Inspection Evidence Ref

```ts
type WorkspaceInspectionEvidenceRef = {
  evidenceId: string;
  kind: "git_status_snapshot" | "diff_snapshot" | "file_snapshot";
  workspaceId: string;
  pathLabel?: string;
  createdAt: string;
};
```

Evidence refs are stable, bounded records that Audit and diagnostics can
project safely. Live file viewer reads are not durable evidence until captured.
Evidence refs are owned by the dedicated inspection evidence store, not by
Audit, diagnostics, or result-summary stores.

### 3.5 Warning

```ts
type WorkspaceInspectionWarning = {
  code:
    | "workspace.not_git"
    | "workspace.inspection_truncated"
    | "workspace.file_too_large"
    | "workspace.binary_unsupported"
    | "workspace.evidence_stale"
    | "workspace.provider_partial";
  message: string;
  pathLabel?: string;
};
```

Warnings are user-safe and renderer-facing. They must not contain raw absolute
paths, raw provider exceptions, or command output.

## 4. Repository Status

```http
GET /api/v1/workspaces/{workspaceId}/inspection/status
```

Query parameters:

| Name | Required | Meaning |
|---|---|---|
| `includeIgnored` | no | Include ignored files when supported. Default `false`. |
| `maxFiles` | no | Maximum changed files. Default implementation may cap. |

Response:

```ts
type WorkspaceGitStatusResponse = {
  schemaVersion: "plato.workspace_inspection.git_status.v1";
  workspaceId: string;
  generatedAt: string;
  repository: {
    status:
      | "clean"
      | "dirty"
      | "untracked_only"
      | "not_git"
      | "unavailable";
    branch?: string;
    headSha?: string;
    isDetachedHead: boolean;
    rootLabel: string;
  };
  summary: {
    changedFileCount: number;
    stagedFileCount: number;
    unstagedFileCount: number;
    untrackedFileCount: number;
    hasMore: boolean;
  };
  files: WorkspaceChangedFile[];
  warnings: WorkspaceInspectionWarning[];
};
```

```ts
type WorkspaceChangedFile = WorkspacePathRef & {
  changeKind:
    | "added"
    | "modified"
    | "deleted"
    | "renamed"
    | "copied"
    | "type_changed"
    | "untracked"
    | "unknown";
  staged: boolean;
  unstaged: boolean;
  oldPathLabel?: string;
  oldRelativePath?: string;
  binary: boolean | null;
  relatedTaskRefs: {
    sessionId: string;
    taskNodeId?: string;
    taskId?: string;
  }[];
};
```

Notes:

- Staged versus unstaged is displayed as information only in Product 1.1 P0.
- The first UI must not expose stage/unstage commands.
- The API preserves `staged`, `unstaged`, and summary counts so later Git
  controls can be added without changing the read model.
- `not_git` is a valid workspace state, not a sidecar failure.

## 5. Per-File Diff

```http
GET /api/v1/workspaces/{workspaceId}/inspection/diff?path=<relativePath>
```

Query parameters:

| Name | Required | Meaning |
|---|---|---|
| `path` | yes | Workspace-relative path. |
| `base` | no | `head` or `index`. Default `head`. |
| `contextLines` | no | Hunk context lines. Default `3`. |
| `maxBytes` | no | Maximum diff bytes before truncation. |

Historical git refs, branch compare, commit range compare, and raw revspec
input are intentionally out of scope for Product 1.1 P0. Stable historical
views must be rendered from captured evidence by `evidenceId`.

Response:

```ts
type WorkspaceDiffResponse = {
  schemaVersion: "plato.workspace_inspection.diff.v1";
  workspaceId: string;
  generatedAt: string;
  file: WorkspacePathRef & {
    changeKind: WorkspaceChangedFile["changeKind"];
    oldRelativePath?: string;
    oldPathLabel?: string;
    binary: boolean;
  };
  base: "head" | "index";
  isAvailable: boolean;
  unavailableReason?:
    | "not_git"
    | "file_not_changed"
    | "file_missing"
    | "binary"
    | "too_large"
    | "provider_error";
  hunks: WorkspaceDiffHunk[];
  stats: {
    additions: number;
    deletions: number;
    hunkCount: number;
    truncated: boolean;
  };
  contentHash?: WorkspaceContentHash;
  evidenceRef?: WorkspaceInspectionEvidenceRef;
  warnings: WorkspaceInspectionWarning[];
};
```

```ts
type WorkspaceDiffHunk = {
  hunkId: string;
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  header: string;
  lines: WorkspaceDiffLine[];
};

type WorkspaceDiffLine = {
  kind: "context" | "add" | "delete";
  oldLine: number | null;
  newLine: number | null;
  text: string;
};
```

Rules:

- Structured hunks are the canonical first-version API.
- Raw unified diff is intentionally omitted from P0. It can be added later if a
  UI or diagnostic need is documented.
- Binary, too-large, and unavailable diffs return safe metadata rather than
  failing the whole route.
- `base` is limited to `head` and `index`; arbitrary refs are rejected.

## 6. Text File Viewer

```http
GET /api/v1/workspaces/{workspaceId}/files/content?path=<relativePath>
```

Query parameters:

| Name | Required | Meaning |
|---|---|---|
| `path` | yes | Workspace-relative path. |
| `startLine` | no | 1-based first line. Default `1`. |
| `lineCount` | no | Maximum lines to return. |
| `evidenceId` | no | Optional captured file evidence to render instead of live file. |

Live file reads use the current workspace state. Historical file views are
served only from captured evidence by `evidenceId`.

Response:

```ts
type WorkspaceFileContentResponse = {
  schemaVersion: "plato.workspace_inspection.file_content.v1";
  workspaceId: string;
  generatedAt: string;
  file: WorkspacePathRef & {
    exists: boolean;
    fileKind: "text" | "binary" | "directory" | "missing" | "unsupported";
    sizeBytes?: number;
    encoding?: string;
  };
  range: {
    startLine: number;
    endLine: number;
    totalLines: number | null;
    truncated: boolean;
  };
  content: {
    lines: {
      lineNumber: number;
      text: string;
    }[];
  };
  contentHash?: WorkspaceContentHash;
  source: "live" | "captured_evidence";
  evidenceRef?: WorkspaceInspectionEvidenceRef;
  unavailableReason?:
    | "file_missing"
    | "binary"
    | "directory"
    | "too_large"
    | "unsupported_encoding"
    | "path_forbidden"
    | "provider_error";
  warnings: WorkspaceInspectionWarning[];
};
```

Rules:

- `lineCount` must have a backend cap.
- Binary and unsupported files return metadata and no content.
- Large files return bounded lines and `truncated=true`.
- Reading captured evidence must not silently fall back to live file content if
  the evidence is missing.

## 7. Evidence Capture

```http
POST /api/v1/workspaces/{workspaceId}/inspection/evidence
```

Evidence capture writes to a dedicated workspace-scoped inspection store.

```text
<workspace>/.plato/inspection.sqlite
  inspection_evidence
```

Conceptual storage record:

```ts
type WorkspaceInspectionEvidenceRecord = {
  evidenceId: string;
  workspaceId: string;
  kind: WorkspaceInspectionEvidenceRef["kind"];
  capturedAt: string;
  source: "git_status" | "git_diff" | "file_content";
  path?: WorkspacePathRef;
  contentHash?: WorkspaceContentHash;
  payload: Record<string, unknown>;
  descriptor: Record<string, unknown>;
};
```

Request:

```ts
type WorkspaceInspectionEvidenceCaptureRequest = {
  kind: "git_status_snapshot" | "diff_snapshot" | "file_snapshot";
  sessionId?: string;
  taskId?: string;
  taskNodeId?: string;
  path?: string;
  reason:
    | "task_result"
    | "audit_record"
    | "diagnostic_export"
    | "manual_capture";
  lineRange?: {
    startLine: number;
    lineCount: number;
  };
};
```

Response:

```ts
type WorkspaceInspectionEvidenceCaptureResponse = {
  schemaVersion: "plato.workspace_inspection.evidence_capture.v1";
  workspaceId: string;
  capturedAt: string;
  evidenceRef: WorkspaceInspectionEvidenceRef;
  descriptor: {
    kind: WorkspaceInspectionEvidenceRef["kind"];
    pathLabel?: string;
    contentHash?: WorkspaceContentHash;
    truncated: boolean;
  };
};
```

Rules:

- Evidence payloads are bounded and redacted.
- Evidence ownership stays in `InspectionEvidenceStore`.
- Audit records, diagnostic bundle sections, result summaries, and Outcome
  Review projections reference `WorkspaceInspectionEvidenceRef` instead of
  duplicating snapshot payload ownership.
- Diagnostic export may include descriptors and selected safe snippets, but
  never raw absolute paths.
- Evidence capture is explicit. Opening a file viewer route does not capture
  durable evidence by itself.

## 8. Errors

Use the existing sidecar envelope and `ApiError` top-level shape.

Required safe error categories:

| Condition | Product category | Recovery actions |
|---|---|---|
| Unknown workspace | `workspace_unavailable` | `open_workspace` |
| Path traversal or `.plato` access | `input_validation` | `edit_input`, `open_audit` |
| Non-git workspace status | no error | Return `repository.status = "not_git"`. |
| Git provider failure | `workspace_inspection_unavailable` | `retry_check`, `export_diagnostics` |
| File missing | `input_validation` | `edit_input` |
| Binary unsupported | no error | Return safe unsupported metadata. |
| Evidence missing | `evidence_unavailable` | `open_audit`, `export_diagnostics` |

Error details must not expose:

- raw absolute paths;
- raw provider exceptions;
- command output with local paths;
- prompts, provider payloads, secrets, logs, or SQLite payloads.

## 9. Path Policy

The backend must normalize every requested path.

Reject:

- absolute paths;
- `..` traversal;
- `.plato` and descendants;
- paths outside the workspace after symlink resolution;
- control characters;
- empty paths when a path is required.

Allow:

- normal workspace-relative files;
- untracked files;
- symlinks whose resolved target remains inside the workspace root.

## 10. Frontend State Contract

Every inspection surface must handle:

- loading;
- clean workspace;
- dirty workspace;
- non-git workspace;
- missing file;
- binary unsupported;
- too large/truncated;
- stale evidence;
- route or provider error.

Diff and file viewer links should preserve:

- `workspaceId`;
- `sessionId` when launched from a session surface;
- `taskNodeId` or Audit record id when available;
- return focus target.

## 11. Audit And Diagnostics

Audit may show:

- status snapshot descriptors;
- diff snapshot descriptors and hunks when safe;
- file snapshot descriptors and bounded line snippets when safe;
- hidden/omitted evidence reasons.

Audit resolves workspace inspection evidence through
`WorkspaceInspectionEvidenceRef` records in `InspectionEvidenceStore`. Audit
entries may store references and projection metadata, but they do not own the
captured diff/file/status snapshot payload.

Diagnostics may include:

- inspection route health;
- redacted evidence descriptors;
- path labels;
- content hashes;
- truncation/omission reasons.

Diagnostic bundles may resolve selected descriptors or safe snippets from
`InspectionEvidenceStore` by evidence ref. Bundles should record unresolved or
omitted evidence as diagnostic metadata rather than falling back to raw live
workspace reads.

Diagnostics must not include raw absolute paths or unbounded file content.

## 12. Test Requirements

Backend contract tests:

- clean, dirty, untracked, and non-git status;
- modified, added, deleted, renamed, and binary changed files;
- structured diff hunk parsing;
- text file range read;
- large file truncation;
- binary unsupported response;
- `.plato`, traversal, and symlink escape rejection;
- no raw absolute path in success or error payloads;
- workspace routing isolation.

Frontend contract tests:

- API client parses all three response contracts;
- file viewer renders line numbers and truncation;
- diff viewer renders added/deleted/context lines;
- non-git and binary states are explicit;
- no raw path rendering.

Acceptance smoke:

- real sidecar with seeded git repo changes;
- Main Page -> file summary -> diff/file viewer;
- Audit evidence -> captured diff/file evidence;
- `npm run electron:smoke` covers Audit file record -> diff viewer ->
  changed-files status in the Electron dev shell;
- `frontend/electron/smokeRunner.test.ts` protects that Electron smoke route
  sequence without requiring a GUI launch;
- diagnostic bundle contains redacted inspection descriptors.

Acceptance evidence:

```bash
cd frontend
npm run test:e2e:sidecar
npm run electron:smoke
```

Both commands passed on 2026-06-10 in a local environment that permits local
HTTP sidecar bind/connect to `127.0.0.1` and Electron GUI launch.

## 13. Implementation Decisions And Remaining Gaps

Fixed decisions:

1. Provider implementation: controlled `git` CLI first, behind
   `GitInspectionProvider`.
2. Evidence snapshots are stored in dedicated
   `InspectionEvidenceStore`/`inspection.sqlite`, scoped to the selected
   workspace.
3. Audit, diagnostics, result summaries, and Outcome Review reference
   `WorkspaceInspectionEvidenceRef` records instead of owning duplicated
   snapshot payloads.
4. Limits: use the Product 1.1 P0 fixed backend caps defined in Shared Types.
5. Staged/unstaged: expose counts and per-file metadata, with lightweight UI
   labels only; no stage/unstage commands.
6. Historical refs: defer arbitrary refs and branch/commit compare; use
   captured evidence for stable historical views.
7. Untracked files: file content is viewable through bounded file viewer reads;
   per-file diff may return unavailable until a frontend need is documented.

WIP-1 implementation status:

1. Backend gateway, route adapter, path policy, controlled git provider, and
   dedicated SQLite inspection store are implemented.
2. Focused backend contract tests cover multi-workspace routing, path
   protection, safe labels, non-git fallback, diff/file reads, and captured
   file evidence lookup.
3. The current implementation captures evidence only through explicit
   `POST /inspection/evidence` requests. Opening a live viewer route still does
   not create durable evidence.

Remaining follow-ups after acceptance:

1. Raw unified diff remains deferred. Structured hunks are the canonical P0
   response unless a concrete diagnostics or UI need appears.
