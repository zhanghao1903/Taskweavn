# Workspace Communication Protocol Fact Calibration Fix Log

> Target document: `docs/architecture/workspace-communication-protocol.md`
> Original preserved as: `docs/architecture/archive/original/workspace-communication-protocol.original.md`
> Calibration date: 2026-07-10

## Workflow Gate

- User request: continue architecture fact calibration one document at a time.
- Detected phase: P5 architecture maintenance, verified against P8/P9 code and
  tests.
- Task type: docs-only architecture fact correction.
- Required upstream artifacts: workspace inspection implementation, precision
  file tools, workspace path policy, UI inspection routes, read-only inquiry
  refs, Collaborator read/search workspace context, related tests and adjacent
  architecture docs.
- Found artifacts: workspace inspection gateway/provider/store, precision file
  service and operation store, HTTP route adapter, workspace path resolver,
  read-only inquiry service, collaborator workspace context source, and tests.
- Missing or weak artifacts: previous document treated unified protocol objects
  as the main body even though `WorkspaceRequest`/`WorkspaceGateway` and related
  models are not implemented.
- Implementation allowed now: yes, docs-only.
- Prework required: verify which workspace surfaces are implemented and which
  protocol objects are absent.
- Scope: preserve original, revise `workspace-communication-protocol.md`, add
  this fix-log.
- Acceptance criteria: current workspace inspection/precision-tool facts are
  explicit; future protocol vocabulary is clearly non-current.
- Risks and assumptions: future plans may intentionally use `WorkspaceRequest`
  vocabulary; current runtime code and tests remain authoritative for status.

## Maintainability Gate

- Requested change: architecture hygiene for
  `workspace-communication-protocol.md`.
- Trigger: architecture fact calibration.
- Size signal: original document was 488 lines, below the 800-line threshold.
- Risk level: low for docs-only slice.
- Refactor required first: no.
- Allowed change type: docs-only boundary correction.
- Validation commands: `git diff --check` plus targeted workspace inspection,
  precision file, collaborator workspace context, read-only inquiry, workspace
  path, and web-fetch URL policy tests.

## Evidence Inspected

### Code

- `src/taskweavn/workspace_inspection/gateway.py`
- `src/taskweavn/workspace_inspection/path_policy.py`
- `src/taskweavn/workspace_inspection/git_provider.py`
- `src/taskweavn/workspace_inspection/limits.py`
- `src/taskweavn/workspace_inspection/store.py`
- `src/taskweavn/workspace_inspection/precision_files.py`
- `src/taskweavn/workspace_inspection/precision_store.py`
- `src/taskweavn/server/ui_http.py`
- `src/taskweavn/server/ui_http_routes.py`
- `src/taskweavn/server/ui_http_inspection.py`
- `src/taskweavn/server/read_only_inquiry.py`
- `src/taskweavn/task/collaborator_workspace_context.py`
- `src/taskweavn/task/event_file_changes.py`
- `src/taskweavn/task/result_summary.py`
- `src/taskweavn/tools/workspace.py`
- `src/taskweavn/tools/precision_fs.py`
- `src/taskweavn/tools/fs.py`
- `src/taskweavn/web_retrieval/url_policy.py`

### Tests

- `tests/test_workspace_inspection_api.py`
- `tests/test_precision_file_tools.py`
- `tests/test_precision_file_tools_sidecar_acceptance.py`
- `tests/test_workspace.py`
- `tests/test_collaborator_workspace_context.py`
- `tests/test_read_only_inquiry.py`
- `tests/test_read_only_inquiry_sidecar_acceptance.py`
- `tests/test_read_only_inquiry_answer_provider.py`
- `tests/test_web_fetch.py`

### Related Docs

- `docs/architecture/tool-capability-layer.md`
- `docs/architecture/fix-log/tool-capability-layer.md`
- `docs/architecture/contract-revision-and-execution-loops.md`
- `docs/architecture/task.md`
- `docs/architecture/bus.md`
- `docs/plans/feature/read-only-inquiry-context.md`
- `docs/plans/feature/collaborator-workspace-informed-authoring.md`

## Verified Facts

1. Current production code has no `WorkspaceManifest`,
   `WorkspaceCapabilityDescriptor`, `WorkspaceRequest`, `WorkspaceResult`,
   `WorkspaceDelta`, `WorkspaceEndpoint`, or unified `WorkspaceGateway`
   implementation.

2. `DefaultWorkspaceInspectionGateway` is implemented and read-only. It exposes
   status, diff, file content, and evidence capture methods.

3. Workspace inspection uses `ControlledGitCliInspectionProvider`,
   `WorkspaceInspectionPathPolicy`, `WorkspaceInspectionLimits`, and
   `SqliteInspectionEvidenceStore`.

4. Current sidecar routes expose active-workspace and workspace-scoped
   inspection status/diff/evidence and file-content endpoints.

5. `WorkspaceInspectionPathPolicy` rejects empty paths, control characters,
   backslashes, absolute paths, traversal, and protected metadata roots.

6. Inspection responses use safe `workspace://{workspaceId}/...` labels and
   tests verify absolute local workspace paths are not leaked.

7. Git inspection handles non-git workspaces safely, summarizes status,
   supports diffs against `head`/`index`, handles untracked text files, and
   returns unavailable states for missing/binary/too-large/unsupported cases.

8. `PrecisionFileService` implements `read_range`, `search`, `replace_range`,
   and `append`.

9. Precision mutations require expected content hashes and operation ids.
   Stale hash raises `workspace.file_drift`; replay of the same operation id
   returns the previous response; reuse with a different request is rejected.

10. Precision mutation observations include changed ranges, before/after
    hashes, bytes written, evidence refs, and replay state.

11. General filesystem tools still use `Workspace` path resolution directly and
    are not routed through a protocol-level request gateway.

12. `EventStreamFileChangeStore` projects file summaries from observed
    `FileWriteObservation`, `PrecisionFileMutationObservation`, and
    `CodeExecutionObservation` facts. No `WorkspaceDelta` object exists.

13. Read-only inquiry can consume file/diff refs. Service and deterministic
    Router tests verify the no-mutation path; current sidecar acceptance tests
    have a separate Router planner behavior mismatch noted under validation.

14. `LocalCollaboratorWorkspaceContextSource` implements read-only authoring
    workspace reads/searches with bounded snippets, evidence refs, safe labels,
    denied/omitted evidence, absolute path redaction, and guidance-scoped search.

15. Web fetch URL policy rejects non-public targets such as local file URLs and
    localhost/private-style URLs; it is related safety evidence but not part of
    the workspace protocol.

## Corrections Applied

1. Reframed the document around current implemented workspace surfaces first.

2. Marked `WorkspaceManifest`, `WorkspaceCapabilityDescriptor`,
   `WorkspaceRequest`, `WorkspaceResult`, `WorkspaceDelta`,
   `WorkspaceEndpoint`, and `WorkspaceGateway` as future-only.

3. Added current facts for workspace inspection routes, path policy, git
   provider behavior, inspection evidence capture, and bounded payload limits.

4. Added current facts for precision file read/search and hash-checked,
   idempotent replace/append mutations.

5. Corrected file-change language: current summaries are event projections, not
   protocol-level `WorkspaceDelta` records.

6. Added current facts for read-only inquiry file/diff refs and Collaborator
   read-only workspace context.

7. Preserved the future unified protocol direction as a migration target rather
   than implementation status.

## Follow-up Candidates

- `docs/architecture/collaborator-agent-task-authoring.md`: likely needs
  calibration around current read-only authoring workspace context and static
  capability catalogs.
- `docs/architecture/contract-revision-and-execution-loops.md`: should be
  checked for current Runtime Input Router, Read-Only Inquiry, and future
  contract command handoff status.
- `docs/architecture/README.md`: may need final alignment after the individual
  architecture docs are calibrated.

## Validation

- `git diff --check` passed.
- `uv run pytest tests/test_workspace.py tests/test_workspace_inspection_api.py tests/test_precision_file_tools.py tests/test_precision_file_tools_sidecar_acceptance.py tests/test_collaborator_workspace_context.py tests/test_read_only_inquiry.py tests/test_read_only_inquiry_answer_provider.py tests/test_runtime_input_router.py tests/test_web_fetch.py tests/test_diagnostic_bundle_export.py` passed: 89 tests.
- Additional attempted validation:
  `uv run pytest tests/test_workspace.py tests/test_workspace_inspection_api.py tests/test_precision_file_tools.py tests/test_precision_file_tools_sidecar_acceptance.py tests/test_collaborator_workspace_context.py tests/test_read_only_inquiry.py tests/test_read_only_inquiry_answer_provider.py tests/test_read_only_inquiry_sidecar_acceptance.py tests/test_web_fetch.py tests/test_diagnostic_bundle_export.py` ran 70 tests with 68 passed and 2 failed. Both failures were in `tests/test_read_only_inquiry_sidecar_acceptance.py`, where the current sidecar response returned `outcome.status="dispatched"` while the test expected `"answered"`. This appears to be a Runtime Input Router / sidecar planner acceptance mismatch, not a workspace protocol implementation failure.
