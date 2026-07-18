# Fix Log: context-manager.md

> Architecture document:
> [../context-manager.md](../context-manager.md)
>
> Original:
> [../context-manager.original.md](../context-manager.original.md)
>
> Calibration date: 2026-07-10

## Workflow Gate Report

1. User request summary: calibrate architecture documents one at a time against
   current code and related docs, preserve each original, and record facts in a
   per-document fix log.
2. Detected workflow phase: P5/P8 execution architecture and backend
   integration maintenance, with P9 tests as verification evidence.
3. Task type: documentation-only architecture fact calibration.
4. Required upstream artifacts: Context Manager plans/releases, cache-aware
   ADR, context package, AgentLoop/fixed-route integration, sidecar assembly,
   Runtime Config, related sources, and tests.
5. Found artifacts: all required artifacts were present.
6. Missing or weak artifacts: the old document retained large design-contract
   sections and acceptance criteria that were broader than current source,
   budget, persistence, and recovery behavior.
7. Whether implementation is allowed now: yes. Current code provides direct
   evidence for a docs-only rewrite.
8. Prework required before implementation: preserve the original and inspect
   related docs, code paths, models, stores, and tests.
9. Proposed execution scope: replace only
   `docs/architecture/context-manager.md` and add this fix log.
10. Acceptance criteria: original preserved; runtime path, source population,
    rendering modes, budget enforcement, persistence, configuration, and known
    gaps stated accurately; targeted tests pass.
11. Risks and assumptions: accepted release wording can describe intended
    bounds; this calibration must verify each bound at its actual call site.

## Sources Inspected

Architecture, decisions, plans, and releases:

- `docs/architecture/context-manager.md`
- `docs/decisions/ADR-0013-cache-aware-append-only-context-rendering.md`
- `docs/decisions/ADR-0017-session-and-workspace-context-management-foundation.md`
- `docs/plans/feature/context-manager-1-0.md`
- `docs/plans/feature/context-manager-1-0-technical-design.zh-CN.md`
- `docs/plans/feature/context-manager-cache-aware-rendering.md`
- `docs/plans/feature/context-manager-cache-aware-rendering-technical-design.zh-CN.md`
- `docs/releases/context-manager-1-0.md`
- `docs/releases/context-manager-cache-aware-rendering.md`
- `docs/plans/feature/centralized-runtime-configuration.md`
- `docs/plans/feature/cooperative-task-interruption.md`
- `docs/plans/feature/contract-revision-command-skills.md`

Context package and integration code:

- `src/taskweavn/context/models.py`
- `src/taskweavn/context/sources.py`
- `src/taskweavn/context/policy.py`
- `src/taskweavn/context/renderer.py`
- `src/taskweavn/context/manager.py`
- `src/taskweavn/context/store.py`
- `src/taskweavn/context/sqlite_store.py`
- `src/taskweavn/context/agent_loop_provider.py`
- `src/taskweavn/core/loop.py`
- `src/taskweavn/task/execution.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/main_page_agent.py`
- `src/taskweavn/server/runtime_config_consumers.py`
- `src/taskweavn/runtime_config/defaults.py`
- `src/taskweavn/contract_revision/context_source.py`
- `src/taskweavn/skills/context_source.py`
- `src/taskweavn/diagnostics/skills.py`
- `src/taskweavn/diagnostics/bundle.py`

Tests selected for verification:

- `tests/test_context_manager.py`
- `tests/test_loop.py`
- `tests/test_fixed_route_task_executor.py`
- `tests/test_main_page_sidecar_app.py`
- `tests/test_runtime_config.py`
- `tests/test_main_page_sidecar_config.py`
- `tests/test_skill_governance.py`
- `tests/test_contract_revision_commands.py`
- `tests/test_task_commands.py`
- `tests/test_diagnostic_bundle_export.py`

## Verified Facts

### Runtime ownership and integration

1. Context Manager controls the message list passed into fixed-route Default
   Agent LLM calls.
2. AgentLoop separately passes tool schemas and metadata to `llm.chat`.
3. Generic AgentLoop supports no context provider; sidecar resident execution
   wires one when TaskBus is available.
4. `AgentLoopResidentDefaultAgent` performs a preflight `execution_start`
   context build before running AgentLoop.
5. The cache-aware provider performs a separate `execution_step` start build
   before the first LLM call.
6. Preflight failure stops before AgentLoop with a context-build failure result.
7. Per-call build failure emits a context-build AgentErrorObservation and stops
   the loop without an unmanaged fallback.
8. Each sidecar context build opens the session EventStream and context SQLite
   stores, constructs a SessionContextManager, builds, and closes the stores.
9. The manager object itself is therefore ephemeral per build; session scope is
   represented by sources and storage paths.

### Models and source population

10. ContextBuildRequest models four purposes and four render modes.
11. Production execution uses execution_start and execution_step purposes.
12. `writer` is modeled and set true but is not read by SessionContextManager.
13. Purpose is persisted but does not alter source selection or policy.
14. TaskExecutionContextV0 contains task, execution, facts, controls, guidance,
    and trace reference.
15. Task source maps TaskDomain intent to original_target and exposes active
    interrupt intent.
16. Current construction leaves interpreted_goal, success_criteria, and
    non_goals empty.
17. Event source produces event summaries, observation/tool summaries, and
    explicit read-file snippets.
18. Event summary removes direct content/stdout/stderr and records character
    counts.
19. Web search observations receive an external-evidence summary with bounded
    URL list.
20. Ask source selects only pending and answered task ASKs.
21. Ask facts have no ContextBudget count/character limit.
22. Default sidecar workspace evidence source is empty.
23. Sidecar controls are an assembly-time allowed-tool tuple; denied tools,
    approval requirements, pending approval, and file scopes are empty.
24. AgentLoop request tool_names are not propagated into ContextBuildRequest.
25. Contract guidance is merged from at most 20 scoped facts.
26. SkillContextSource is implemented/tested but not supplied by sidecar
    context assembly.
27. Changed artifacts and arbitrary workspace refs are not populated by the
    current production source set.
28. The fixed-route provider does not set ContextBuildRequest's structured
    latest_user_instruction field.
29. Workspace Inspection, read-only Inquiry, token usage, Agent LLM profile,
    MCP, multimodal, retrieval, and workspace/session context layers are not
    current sources.

### Policy and budgets

30. Deterministic policy keeps the newest bounded event, tool-result, and file
    snippet facts.
31. File snippet policy applies a shared character total to selected snippets.
32. File read source also truncates each snippet before policy selection.
33. Generic candidate selection exists but SessionContextManager does not call
    it.
34. Manager traces currently record empty candidate seen/selected/excluded
    tuples.
35. Token estimates are approximate and do not enforce a total prompt-token
    budget.
36. `max_rendered_chars` has no production read/enforcement call site.

### Rendering and transcript

37. Full render prepends system and full structured user context.
38. Start render creates a two-message stable prefix and excludes volatile ids.
39. Ordinary cache-aware reuse still builds/stores context but returns the
    existing transcript unchanged.
40. Delta and checkpoint are system messages appended after prior messages.
41. Current production interval checkpoint defaults to every five steps.
42. A newly observed interrupt request can trigger an appended delta.
43. Additional trigger evaluator support exists, but pending-decision triggering
    is demonstrated only in tests.
44. Checkpoint content omits selected file content and uses refs/summaries.
45. Checkpoint does not remove or compact prior messages.
46. AgentLoop tool messages contain complete observation JSON.
47. Structured fact budgets do not trim the reused AgentLoop transcript.
48. `_prior_messages` applies max_prior_messages only in the compatibility
    build_for_llm_call path.
49. Production AgentLoop uses prepare_llm_call, which passes loop_messages
    directly after the start call.
50. Therefore max_prior_messages does not bound the cache-aware production
    transcript.

### Run state, storage, and trace

51. Cache-aware run state is an in-memory map keyed by agent_run_id.
52. It is not persisted or rehydrated from context.sqlite.
53. No provider-specific cache control is emitted by Context Manager.
54. Runtime config hash and context ids/hashes/mode/reasons are copied into LLM
    metadata.
55. ContextSnapshot persists structured context and rendered input hash, not
    the rendered message list.
56. ContextTrace persists segment hashes and policy/renderer metadata.
57. Context sqlite rows are stored without redaction.
58. Snapshots may contain file snippets and ASK answers.
59. There is no UI/HTTP/Audit read path for full snapshots or traces.
60. Diagnostic export reads traces only for a sanitized Skill governance
    summary and does not export full snapshots.

### Runtime configuration and future layers

61. RuntimeContextSettings maps checkpoint interval, max prior messages, all
    budget fields, and config hash from effective Runtime Config.
62. Sidecar assembly creates this settings object once and passes it to future
    loop providers.
63. There is no Context Manager ConfigBus consumer that mutates an existing
    provider after a runtime patch.
64. ADR-0017 explicitly marks WorkspaceContext and SessionContext layers not
    implemented.
65. Context Manager itself does not enforce a single active writer lane.

## Stale or Corrected Claims

1. The old document called Context Manager the only component assembling the
   full LLM API input. It governs messages; AgentLoop owns tools/metadata and the
   provider owns transport settings.
2. The old lifecycle described one retained SessionContextManager. Sidecar
   builds construct it inside each `_SessionContextBuilder.build` call.
3. The old document described generic candidate collection/selection and trace
   exclusions as the normal pipeline. Manager builds bypass the candidate
   selector and record empty candidate tuples.
4. The old Task identity contract implied interpreted goal, success criteria,
   and non-goals were populated. Current construction does not populate them.
5. The old facts section implied workspace refs and changed artifacts were
   active sources. They are empty in sidecar assembly.
6. The old control section implied permission/approval facts. Default assembly
   supplies only allowed tool names.
7. The old Skill discussion implied active skill trace integration. The library
   seam exists, but sidecar does not wire SkillContextSource.
8. The old Product 1.1 alignment named inquiry, inspection, usage, and Agent
   profile sources. They are future selectors, not current execution sources.
9. The old acceptance boundary implied rendered input is finite by the declared
   budget. max_rendered_chars is not enforced.
10. The old max-prior-message claim does not hold for the cache-aware
    prepare_llm_call path used in production.
11. The old checkpoint language could be read as compaction. Current checkpoint
    appends and never removes transcript content.
12. The old recovery language implied persisted run-state recovery. Provider
    run state is memory-only and no recovery purpose call is wired.
13. The old trace language implied exact rendered input could be explained from
    context.sqlite. The message list is not stored, only context and hashes.
14. The old storage discussion did not state that snapshots are unredacted and
    can contain file snippets/answers.
15. The old source boundary implied ASK lifecycle variants generally. Current
    source query selects only pending and answered.
16. The old writer-lane contract was presented as Context Manager policy.
    `writer` is currently unconsumed by the manager.
17. The old Runtime Config wording did not distinguish catalog mutability from
    actual assembly-time consumer behavior.
18. The old document contained Product 1.0 acceptance criteria as if they all
    remained current facts; the new document replaces them with verified
    implementation and explicit limits.

## New Document Decisions

1. Define ownership as LLM message governance rather than the entire provider
   request.
2. Describe the preflight and per-call builds separately.
3. List production source population field by field.
4. Separate structured fact budgets from the unbounded append-only transcript.
5. State that checkpointing and compaction are different operations.
6. Treat context.sqlite as sensitive derived local metadata.
7. Separate implemented library seams from sidecar wiring.
8. Preserve ADR-0017 as an explicit not-implemented future layer contract.

## Validation Log

Validation commands run after this rewrite:

```bash
git diff --check
uv run pytest tests/test_context_manager.py tests/test_loop.py tests/test_fixed_route_task_executor.py tests/test_main_page_sidecar_app.py tests/test_runtime_config.py tests/test_main_page_sidecar_config.py tests/test_skill_governance.py tests/test_contract_revision_commands.py tests/test_task_commands.py tests/test_diagnostic_bundle_export.py
```

Results:

- `git diff --check`: passed.
- Backend pytest: 178 passed.
