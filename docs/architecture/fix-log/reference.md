# Core Architecture Reference Fact Calibration Log

> Source document: `docs/architecture/reference.md`
> Preserved original: `docs/architecture/reference.original.md`
> Calibration date: 2026-07-10
> Scope: current typed-event/runtime/tool/AgentLoop substrate, CLI and Main Page
> assembly, workspace/session layout, upper-domain boundaries, and protocol
> inventory claims.

## 1. Workflow Gate Report

- User request summary: fact-calibrate every architecture document one at a
  time, preserve the original, replace the active document, and add a factual
  per-document log.
- Detected workflow phase: P5 backend/core architecture fact maintenance, with
  P7/P8 implementation evidence and P9 test evidence.
- Task type: documentation-only core reference correction.
- Required upstream artifacts:
  - full existing reference document;
  - current core substrate source;
  - current Main Page and CLI composition roots;
  - current workspace/session/product-domain source;
  - neighboring calibrated architecture documents;
  - targeted tests.
- Found artifacts: all required source, architecture, and test evidence was
  present.
- Missing or weak artifacts:
  - the old document stopped at an early Phase 3 substrate view;
  - it had no reliable current protocol inventory;
  - it mixed substrate availability with Main Page product assembly;
  - it omitted major Product 1.0/1.1 domains and stores;
  - several absolute lifecycle and uniqueness claims were not enforced by code.
- Implementation allowed now: yes, for documentation-only calibration.
- Prework required: inspect exact APIs/lifecycles and compare standalone CLI
  assembly with Main Page sidecar assembly.
- Execution scope: preserve and rewrite `reference.md`, add this log, and run
  core-focused verification. No production code changes.
- Acceptance criteria:
  - original matches the pre-calibration Git blob;
  - current WorkspaceLayout, Session, AgentLoop, LoopResult, LLM, interaction,
    audit, and thought facts match source;
  - the reference does not claim an exhaustive protocol list;
  - CLI-only and Main Page behavior are distinguished;
  - upper product authorities are indexed instead of collapsed into two streams;
  - targeted tests and document checks pass.
- Risks and assumptions:
  - source module docstrings still contain historical Phase wording and cannot
    be treated as sole evidence;
  - several substrate classes remain valid but are not assembled by Main Page;
  - adjacent architecture files are being calibrated sequentially, so this
    document links to their current working-tree versions.

## 2. Original Preservation

- Original path: `docs/architecture/reference.md`
- Preserved path: `docs/architecture/reference.original.md`
- Original Git blob: `e0b793e919365dd4d3df61aaf61d934cf3ecadd7`
- The pre-calibration working-tree hash matched `HEAD`.
- The original contained 864 lines.
- It labeled itself a partial implementation map but used present-tense and
  absolute statements throughout the body.

## 3. Evidence Inspected

### 3.1 Typed Events, Runtime, Tools

- `src/taskweavn/types/base.py`
- `src/taskweavn/types/registry.py`
- `src/taskweavn/types/common.py`
- `src/taskweavn/types/code_action.py`
- `src/taskweavn/types/ask.py`
- `src/taskweavn/types/confirmation.py`
- `src/taskweavn/types/computer_use.py`
- `src/taskweavn/runtime/base.py`
- `src/taskweavn/runtime/local.py`
- `src/taskweavn/runtime/sandbox.py`
- `src/taskweavn/tools/base.py`
- `src/taskweavn/tools/workspace.py`
- filesystem, precision-file, shell, web, computer-use, ASK, and confirmation
  Tool modules.

### 3.2 AgentLoop And Context

- `src/taskweavn/core/loop.py`
  - current fields, bundle invariants, run identity, context preparation,
    cooperative interruption, LLM error handling, gating, waiting, audit, and
    stop reasons.
- `src/taskweavn/core/loop_profile.py`
  - profile-neutral contracts are separate from AgentLoop's constructor.
- `src/taskweavn/context/agent_loop_provider.py`
- `src/taskweavn/context/manager.py`
- `src/taskweavn/server/main_page_agent.py`
  - actual Main Page runner/tool/context/interruption assembly.
- `src/taskweavn/task/execution.py`
  - outer fixed-route exception/lifecycle boundary.

### 3.3 Event, Thought, Audit, Interaction

- `src/taskweavn/core/event_stream.py`
- `src/taskweavn/core/sqlite_event_stream.py`
- `src/taskweavn/memory/thought_store.py`
- `src/taskweavn/memory/sqlite_thought_store.py`
- `src/taskweavn/memory/config.py`
- `src/taskweavn/audit/agent.py`
- `src/taskweavn/interaction/message.py`
- `src/taskweavn/interaction/sqlite_message_stream.py`
- `src/taskweavn/interaction/bus.py`
- `src/taskweavn/interaction/autonomy.py`
- `src/taskweavn/interaction/gate.py`
- `src/taskweavn/interaction/wait.py`
- `src/taskweavn/interaction/ask.py`

### 3.4 LLM And Usage

- `src/taskweavn/llm/client.py`
- `src/taskweavn/llm/contracts.py`
- `src/taskweavn/llm/agent_config.py`
- `src/taskweavn/llm/agent_resolver.py`
- provider, retry, config, logging modules;
- `src/taskweavn/server/main_page_llm_helpers.py`
- `src/taskweavn/usage/recording.py`
- calibrated `docs/architecture/llm-provider-reliability.md` and its evidence
  log.

### 3.5 Workspace, Session, Composition

- `src/taskweavn/core/workspace_layout.py`
- `src/taskweavn/core/session.py`
- `src/taskweavn/core/session_manager.py`
- `src/taskweavn/core/session_status.py`
- `src/taskweavn/server/ui_contract/query_snapshot_helpers.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/cli/main.py`
- upper-domain packages under `task`, `context`, `contract_revision`,
  `execution_plane`, `runtime_config`, `workspace_inspection`, `skills`,
  `usage`, `observability`, and `server/ui_contract`.

### 3.6 Protocol Inventory Check

- Source scan on 2026-07-10 found 91 `@runtime_checkable` occurrences under
  `src/taskweavn`.
- The old “all runtime-checkable Protocols” table listed only 9 entries.
- Major omitted families included Task stores/commands/projections, Context,
  UI gateways, Execution Plane, runtime config, skills, result summaries, and
  collaborator boundaries.
- The calibrated document therefore provides a selected substrate table and
  explicitly rejects a hand-maintained exhaustive claim.

## 4. Stale Or Incorrect Claims Found

1. The global dependency “arrows always point down” rule no longer described
   current package composition.
2. “Every cross-layer dependency starts with a Protocol” was not a repository
   invariant.
3. The old protocol table was presented as exhaustive despite dozens of omitted
   protocols.
4. The WorkspaceLayout tree used legacy `.taskweavn` instead of `.plato`.
5. It described a nested per-Session project directory; current Session project
   root is the shared workspace root.
6. It omitted most workspace-level SQLite stores added after early phases.
7. SessionManager omitted current rename/delete behavior and delete archival.
8. It treated core session status derivation as the live product algorithm;
   Main Page uses a separate UI projection.
9. AgentLoop fields omitted Context Provider and interruption checker.
10. LoopResult used a three-value Literal although current stop reasons are
    broader and the field is `str`.
11. The loop pseudocode omitted context errors, provider timeout/error,
    cooperative interruption, explicit ASK/confirmation waiting, and usage/log
    metadata.
12. It called `task_id` one AgentLoop-run identity; Main Page supplies a domain
    Task id that can be reused across runs.
13. It did not distinguish internal `agent_run_id` from `task_id`.
14. It said Tool startup/shutdown are always paired; startup may raise and all
    tools receive best-effort shutdown.
15. It called AgentLoop.run total/never-raising; several store/startup/bus paths
    can still raise.
16. It treated ThoughtRecord `event_id` as a reliable EventStream reference;
    AgentLoop writes `step-N` labels.
17. It implied AuditAgent covers current Main Page CodeActions; Main Page
    assembles neither CodeActionTool nor AuditAgent.
18. It treated `agent_id` as fixed to agent/user/system; current writers use
    additional role labels.
19. It described replay-then-attach as preventing message loss/duplication,
    without an atomic snapshot/cursor attach contract.
20. It treated EventStream plus MessageStream as enough to reconstruct system
    truth, omitting Task/ASK/authoring/context/usage/UI event stores.
21. It implied `event_id` global uniqueness without a SQLite UNIQUE constraint.
22. It treated the old channel logger as the whole logging architecture.
23. It described Orchestrator as a future-filled shell without recording that it
    still has no concrete caller.

## 5. Verified Current Facts

1. Base event models are frozen Pydantic models with extra fields forbidden.
2. Observation `action_id` is optional.
3. Action/Observation subclasses auto-register by kind, and collisions fail.
4. Registry replay depends on concrete module imports.
5. LocalRuntime dispatches by exact Action class and normalizes executor errors.
6. Re-registering an Action class overwrites its executor.
7. Workspace rejects out-of-root and protected metadata paths but is not an OS
   sandbox.
8. Main Page and CLI assemble different Tool sets.
9. Main Page has precision file, shell, optional web/computer-use, and explicit
   ASK/confirmation tools.
10. CLI adds CodeActionTool and optional audit/thought/autonomy substrate.
11. AgentLoop validates Tool names and gate bundle completeness.
12. Main Page supplies domain `task_id`; AgentLoop generates a separate run id.
13. Current EventStream rows do not store `agent_run_id`.
14. AgentLoop converts context/LLM/interruption-check errors to LoopResult.
15. AgentLoop can still raise from unguarded dependencies.
16. Explicit ASK/confirmation observations return `waiting_for_user`.
17. Main Page Context Provider prepares every LLM call and records context
    metadata.
18. Main Page interruption is cooperative at explicit safe points.
19. EventStream remains a typed Action/Observation log, not TaskBus authority.
20. SQLite EventStream is per Session and carries optional Task correlation.
21. ThoughtStore defaults to null, and Main Page does not override it.
22. Current AgentLoop ThoughtRecord keys are step labels rather than BaseEvent
    ids.
23. AuditAgent is optional CLI substrate for CodeAction pairs.
24. Main Page audit evidence is broader than AuditAgent verdicts.
25. LLM chat is provider-backed; complete/count_tokens retain OpenHands
    compatibility paths.
26. Main Page role-aware resolver currently assembles four roles.
27. Injected shared LLM bypasses per-role resolver selection.
28. MessageStream has three message types and open-string agent labels.
29. InProcessMessageBus is the only live bus implementation.
30. Main Page does not assemble AutonomyGate.
31. Workspace metadata canonical root is `.plato`.
32. Session project root is the workspace root, not a nested Session directory.
33. Workspace-level product stores and Session-level execution/context stores
    have distinct paths.
34. SessionManager supports create/get/require/list/touch/rename/delete/status.
35. Core and Main Page Session status derivation are different algorithms and
    vocabularies.
36. Product facts live in multiple domain authorities; no two-stream universal
    replay exists.
37. Process-local locks do not implement distributed concurrency control.
38. Orchestrator remains a Null placeholder with no product caller.

## 6. Corrections Applied

- Reframed the document as a current contributor reference, not an exhaustive
  global API inventory.
- Replaced the obsolete strict layer diagram with a current package authority
  map and product execution path.
- Updated typed-event semantics, including optional action ids, registry
  collisions/import requirements, and non-unique SQLite event ids.
- Updated Runtime/Tool lifecycle and documented the actual exception boundary.
- Added Main Page versus CLI Tool and substrate assembly.
- Rebuilt the AgentLoop section from current source, including Context Provider,
  cooperative interruption, error paths, waiting, and all current stop reasons.
- Corrected Task/run identity semantics and added `agent_run_id` limitations.
- Updated EventStream, ThoughtStore, AuditAgent, LLM, and Interaction sections.
- Replaced the old workspace tree with current `.plato` paths and stores.
- Added SessionManager rename/delete and current status projection split.
- Indexed upper product domains and their authoritative documents.
- Replaced the false exhaustive Protocol table with a selected substrate table
  plus domain-family guidance.
- Added current identity/authority, resource/concurrency, recovery, and logging
  boundaries.
- Added an explicit non-fact table for common stale interpretations.

## 7. Targeted Test Plan

Core validation covers:

- typed events and registries;
- LocalRuntime and filesystem/shell Tools;
- Workspace path/protected metadata behavior;
- in-memory/SQLite EventStream;
- null/SQLite ThoughtStore and config;
- AuditAgent;
- AgentLoop base, interaction, context, interruption, and profile contracts;
- Message model/bus/SQLite stream/WaitCoordinator;
- WorkspaceLayout, SessionManager, and both status behaviors;
- real Main Page sidecar assembly.

## 8. Validation Record

Validation completed on 2026-07-10:

- Original preservation:
  - `git hash-object docs/architecture/reference.original.md` returned
    `e0b793e919365dd4d3df61aaf61d934cf3ecadd7`.
  - `git rev-parse HEAD:docs/architecture/reference.md` returned the same blob
    id.
- Targeted backend tests:
  - 31 files covering types, Runtime/Tools, Workspace, EventStream,
    ThoughtStore, AuditAgent, AgentLoop, interaction, LLM/providers/usage,
    WorkspaceLayout, Session, and Main Page sidecar assembly.
  - Command: `uv run pytest -q` with the files listed in the calibrated
    document plus LLM/autonomy/workspace support suites.
  - Result: `394 passed in 19.77s`.
- Document checks:
  - all linked calibrated architecture targets exist;
  - the preserved file hash matches `HEAD`;
  - stale absolute statements appear only as explicitly rejected non-facts or
    fix-log findings;
  - no source or frontend files were changed;
  - `git diff --check` passed for the reference document artifacts.

## 9. Follow-Up Boundary

- `review.md` and `session.md` remain separate calibration targets.
- README index updates remain deferred until every architecture document has
  its final active/original/fix-log set.
- A future exhaustive API inventory should be generated from source rather than
  hand-maintained in this document.
