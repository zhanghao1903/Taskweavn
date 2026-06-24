# Plato Product 1.1 Open Work

> Status: active open-work index
>
> Last Updated: 2026-06-20
>
> Scope: Product 1.1 unfinished product work after the accepted workspace,
> precision-tool, read-only inquiry, token-usage, and local Electron beta
> foundations.

## 1. Purpose

This document is the Product 1.1 open-work index. It does not replace the
feature plans. It keeps the product-level unfinished work in one place so 1.1
does not drift into disconnected Router, command, Activity, Audit, web
retrieval, diagnostics, and release-hardening tasks.

The current Product 1.1 state is:

- the workspace-aware foundation is real enough for beta use;
- the main collaboration-loop feature set is now on `main`: Runtime Input
  Router, Router-first Main Page input, Contract Revision Command Skills,
  durable Conversation / Activity, and backend-only Agent LLM / Router LLM
  configuration;
- Product 1.1 P0 is no longer first-capability work. The remaining P0 closure
  scope was Electron acceptance, Audit / Diagnostics closure, and release
  evidence;
- that P0 closure scope now has beta release evidence: configured Electron,
  packaged app, and mounted `1.1-beta` installer smoke pass the Runtime Input
  route matrix, Audit / Diagnostics closure, startup diagnostics, and first-run
  paths;
- the remaining Product 1.1 risk has moved to P1 beta-depth work: sidecar
  restart replay, optional LLM-rendered inquiry smoke, public repository
  release-note sync, signed/notarized distribution, and broader release polish.

## 2. Priority Model

| Priority | Meaning | Product 1.1 rule |
|---|---|---|
| P0 | Required to make Product 1.1 feel like one coherent collaboration loop. | Must be planned and closed before calling Product 1.1 product-complete. |
| P1 | Release hardening, trust polish, or beta-readiness work. | Should be pulled in when it protects user trust or reduces support risk. |
| P2 | Platform expansion after the Product 1.1 loop is coherent. | Keep planned, but do not let it block P0 closure. |

## 3. Accepted Or Implemented 1.1 Baselines

These items are not open P0 blockers unless a later regression is found:

| Area | Current baseline | Source |
|---|---|---|
| Workspace inspection | Accepted Product 1.1 P0 milestone: git status, diff, file viewer, Main/Audit/Outcome links, diagnostic descriptors, sidecar/Electron smoke. | [Workspace Inspection Milestone](../plans/feature/product-1-1-workspace-inspection-milestone.md) |
| Precision file tools | Completed Product 1.1 line-range read, workspace search, guarded replace, append, changed-line evidence, Agent/CLI registration, file-summary projection. | [Precision File Tools](../plans/feature/precision-file-tools.md) |
| Plan / TaskNode foundation | Accepted Plan/TaskNode migration foundation: durable Plan/TaskNode storage, active Plan identity, publish handoff, lifecycle sync, result/file/detail reads, Audit identity normalization. | [Plan / TaskNode Contract Migration](../plans/feature/plan-tasknode-contract-migration.md) |
| Session Activity surface | Accepted foundation plus Router-written durable Conversation / Activity: user input, Router trace, question cards, read-only answers, command outcomes, and reloadable Activity projection are on `main`. | [Session Conversation / Activity Timeline](../plans/feature/session-conversation-activity-timeline.md) |
| Read-only inquiry | Accepted for Product 1.1 local runtime: no-mutation answers, evidence refs, Activity display/replay, Audit focused refs, diagnostic actions, sidecar/Electron smoke. | [Read-Only Inquiry Context](../plans/feature/read-only-inquiry-context.md) |
| Token usage analytics | Completed Product 1.1 slice: usage ledger, Task/Plan/Session/Workspace aggregation, cache hit-rate visibility, Settings/Main Page entries, diagnostics-safe summaries. | [Token Usage Analytics](../plans/feature/token-usage-analytics.md) |
| UI system text foundation | Implemented typed UI system text registry, `en-US` / `zh-CN` catalogs, runtime locale override, Settings language selector, staged chrome migration. | [Product Copy Localization Foundation](../plans/feature/product-copy-localization-foundation.md) |
| Execution web retrieval | Implemented first Product 1.1 external-evidence baseline: Tavily-backed `web_search`, selected-URL `web_fetch`, global Settings/key path, URL safety policy, gated execution tool registration, Context/Audit/diagnostic descriptors, and mock-provider tests. | [Execution Web Search Capability](../plans/feature/execution-web-search-capability.md), [Execution Web Fetch Capability](../plans/feature/execution-web-fetch-capability.md) |
| Runtime Input Router and Router LLM | Implemented Router-first Main Page path, durable Router Conversation protocol, question cards/options, read-only answers, guidance, ASK/confirmation routes, execution handoff, and backend-only Agent LLM / Router LLM configuration. | [Runtime Input Router Contract](../plans/feature/runtime-input-router-contract.md), [Router-first Main Page Input](../plans/feature/router-first-main-input-durable-activity-technical-design.zh-CN.md), [Agent LLM Config And Router LLM](../plans/feature/agent-llm-config-and-router-llm.md) |
| Contract revision command substrate | Implemented CRS-A through CRS-G: command protocol, `record_guidance`, routed ASK/confirmation resolution, Plan/TaskNode patch/create/delete, `create_execution_task` handoff, Audit / Diagnostics linkage, and configured Electron acceptance evidence. | [Contract Revision Command Skills](../plans/feature/contract-revision-command-skills.md), [P0 Release Evidence](plato-1-1-p0-release-evidence-2026-06-20.md) |

## 4. P0 Closure: Runtime Input And Evidence Readiness

### 4.1 Milestone Statement

Product 1.1 P0 is now one milestone:

```text
Runtime Input Router
  + Contract Revision Command Skills
  + durable Activity / Audit evidence
```

The functional milestone implementation is now on `main`. Product 1.1 P0 is no
longer missing first capability work. The remaining P0 closure scope was:

```text
Electron acceptance
  + Audit / Diagnostics closure
  + release evidence
```

That scope is now recorded for the configured Electron app, packaged app, and
mounted `1.1-beta` installer. Public repository release-note sync and richer
visual evidence remain useful release polish, but they are no longer P0
capability blockers.

The milestone is product-complete when a user can type into the Main Page once,
Plato can safely interpret the input as a question, guidance, command, ASK
answer, confirmation response, or execution request, and the user can later
inspect what happened through durable Conversation, Activity, Audit, and
diagnostic evidence.

### 4.2 Why This Is The P0

Product 1.1 already has useful workspace and trust surfaces. The previous
failure mode was that user input could feel like chat attached to several
separate command paths. The main code path now routes through the Runtime Input
Router, and the configured Electron sidecar now passes the P0 route matrix.
Product 1.1 needed release evidence that proves the loop behaves correctly
under beta distribution conditions:

- Router decisions must remain durable and replayable after reload;
- command-like requests must keep using command-backed product-state mutation;
- workspace-changing requests must create executable contract work, not direct
  tool execution;
- ASK and confirmation resolution must work from both explicit controls and the
  natural-language input surface;
- diagnostics and release evidence must prove that prompts, provider payloads,
  raw logs, SQLite rows, secrets, and absolute paths are not exposed.

### 4.3 P0 Work Packages

| ID | Work package | Current state | Target outcome | Source |
|---|---|---|---|---|
| P0-RIR-1 | Main Page default Router path | Implemented on `main`; component coverage exists for the default submit path and configured Electron smoke covers the P0 route matrix through Runtime Input routes. | Main Page submit routes through Runtime Input Router by default while explicit ASK/confirmation controls continue to work. | [Runtime Input Router Contract](../plans/feature/runtime-input-router-contract.md), [P0 Release Evidence](plato-1-1-p0-release-evidence-2026-06-20.md) |
| P0-RIR-2 | Question and guidance routes | Implemented on `main`; configured Electron smoke verifies read-only question Activity replay and command-backed guidance in the sidecar runtime. | Read-only questions use the accepted Inquiry path; guidance routes to command-backed guidance recording. Unsupported guidance never becomes hidden behavior. | [Runtime Input And Contract Revision Program](../plans/feature/runtime-input-and-contract-revision-program.md), [P0 Release Evidence](plato-1-1-p0-release-evidence-2026-06-20.md) |
| P0-CRS-1 | Command skill protocol | Implemented. | Internal command skills return versioned, idempotent, auditable results with Activity metadata and no direct workspace writes. | [Contract Revision Command Skills](../plans/feature/contract-revision-command-skills.md) |
| P0-CRS-2 | `record_guidance` | Implemented. | Session, Plan, or Task guidance persists as typed contract/context facts and appears in Activity. | [Contract Revision Command Skills](../plans/feature/contract-revision-command-skills.md) |
| P0-CRS-3 | ASK and confirmation routed resolution | Implemented. Follow-up fixes have covered PlanTaskNode/published-task ASK matching in Main Page detail. | The same input surface can resolve active ASK and confirmation states through accepted domain commands. | [Runtime Input Router Contract](../plans/feature/runtime-input-router-contract.md), [Contract Revision Command Skills](../plans/feature/contract-revision-command-skills.md) |
| P0-CRS-4 | Execution request handoff | Implemented on `main`; configured Electron smoke verifies `mode: change` routes to execution handoff and does not mutate workspace files directly. | Workspace-changing requests create executable Plan/TaskNode contract work and enter TaskBus only through the accepted execution path. | [Contract Revision Command Skills](../plans/feature/contract-revision-command-skills.md), [P0 Release Evidence](plato-1-1-p0-release-evidence-2026-06-20.md) |
| P0-CRS-5 | Plan/TaskNode mutation commands | Implemented for patch/create/delete with version, editable-Plan, idempotency, and tombstone semantics. | Contract-changing requests use command-backed patch/create/delete operations with state, version, idempotency, and confirmation guards. | [Plan / TaskNode Contract Migration](../plans/feature/plan-tasknode-contract-migration.md), [Contract Revision Command Skills](../plans/feature/contract-revision-command-skills.md) |
| P0-ACT-1 | Durable Router Conversation / Activity | Implemented on `main`; configured Electron smoke verifies durable Activity replay after renderer reload for read-only, guidance, ASK, confirmation, execution handoff, and unsupported routes. | Router decisions and outcomes are stored as durable Session content or equivalent facts, not only returned as transient route-result metadata. | [Session Conversation / Activity Timeline](../plans/feature/session-conversation-activity-timeline.md), [P0 Release Evidence](plato-1-1-p0-release-evidence-2026-06-20.md) |
| P0-TRUST-1 | Audit and diagnostics linkage | Passed for the configured P0 route matrix. Router-specific diagnostic bundle descriptors and Router-specific Audit records/details exist; Electron smoke verifies Audit navigation, diagnostic export, `runtime_input` descriptors, and no absolute path leakage. | Routed input links to downstream command, Activity, Audit, and diagnostic refs without exposing prompts, provider payloads, raw logs, SQLite rows, secrets, or absolute paths. | [Runtime Input And Contract Revision Program](../plans/feature/runtime-input-and-contract-revision-program.md), [P0 Release Evidence](plato-1-1-p0-release-evidence-2026-06-20.md) |
| P0-QA-1 | Real acceptance suite | Passed for configured Electron, packaged app, and mounted `1.1-beta` installer smoke. Sidecar restart replay remains beta-depth release confidence work. | Electron/sidecar acceptance covers question, guidance, ASK, confirmation, stop/retry, execution-request handoff, unsupported routes, and no-mutation guarantees. | [Product 1.1 QA Report](plato-1-1-real-local-qa-report-2026-06-11.md), [P0 Release Evidence](plato-1-1-p0-release-evidence-2026-06-20.md) |
| P0-REL-1 | Release evidence package | Closed for Product 1.1 P0 beta evidence. The release evidence package links the route matrix, Audit / Diagnostics closure, packaged app, mounted `1.1-beta` installer smoke, SHA256, known limitations, and release record. Public repository release-note sync remains P1 external-doc polish. | Stable/beta release docs clearly show what Product 1.1 includes, what was verified, and what remains deferred. | [P0 Release Evidence](plato-1-1-p0-release-evidence-2026-06-20.md), [Product 1.1 Runtime Input Router Release Evidence](../releases/product-1-1-runtime-input-router-release-evidence.md), [Runtime Input And Contract Revision Program](../plans/feature/runtime-input-and-contract-revision-program.md) |

### 4.4 P0 Non-Goals

This milestone should not expand into:

- public skill marketplace or custom skill authoring;
- MCP integration;
- browser automation or deep research workflows;
- full public Agent protocol;
- unrestricted natural-language command language;
- prompt-only state mutation;
- direct workspace mutation from the Router;
- broad result packaging cards;
- semantic memory or cross-session memory.

### 4.5 P0 Acceptance Criteria

The P0 milestone is accepted when:

1. Main Page input routes through Runtime Input Router by default.
2. Read-only questions return answers with evidence refs and `no_effect`.
3. Guidance is persisted as typed context through command-backed facts.
4. ASK and confirmation answers work from both explicit UI and routed input.
5. Contract-changing requests use versioned, idempotent command skills.
6. Workspace-changing requests create executable contract work and enter TaskBus
   only through the accepted path.
7. Every accepted route creates durable user-visible Activity evidence.
8. Router decisions link to downstream command, Audit, and diagnostic refs.
9. Low-confidence and unsupported input never mutates product state or
   workspace files.
10. Real sidecar/Electron acceptance covers happy paths, rejected commands,
    unsupported routes, and no-mutation guarantees.
11. Release evidence links the accepted Product 1.1 features to docs, tests,
    screenshots or smoke logs, and known limitations.

### 4.6 Suggested P0 Execution Order

1. Done: implement the CRS-A command protocol models and focused unit tests.
2. Done: implement `record_guidance` persistence, projection, and Activity
   output.
3. Done: wire RIR question and guidance routes to accepted downstream
   capabilities. Read-only inquiry, command-backed guidance, Router-first
   submit, and durable route replay are on `main`.
4. Done: add ASK/confirmation routed resolution parity with explicit UI
   controls.
5. Done: add guarded Plan/TaskNode mutation commands and
   `create_execution_task` handoff.
6. Done: persist Router decisions/outcomes as durable Conversation / Activity
   for read-only inquiry and implemented Contract Revision commands.
7. Done for P0: add Router Audit/diagnostic refs and redacted diagnostic
   descriptors for implemented Contract Revision commands. Diagnostic bundle
   `runtime_input` descriptors and Router-specific Audit records/details now
   exist and are covered by configured Electron smoke.
8. Done: migrate the Main Page input submit path to Runtime Input Router by
   default for the full input surface.
9. Done for configured P0 route matrix: run the real Electron/sidecar
   acceptance suite for read-only, guidance, ASK, confirmation, execution
   handoff, unsupported routes, stale retry rejection, Audit navigation,
   diagnostics export, and no-mutation guarantees.
10. Done for P0: finish Product 1.1 release evidence by tying accepted routes
    to release docs, packaged-release evidence, mounted `1.1-beta` installer
    smoke, SHA256, and known limitations.

## 5. P1 Open Work

| Area | Open work | Why P1 |
|---|---|---|
| Workspace inspection hardening | Decide whether viewer route openings should automatically capture durable evidence; add richer Audit evidence detail expansion; keep raw unified diff deferred unless a concrete UI/diagnostic need appears. | Useful for trust and support, but the accepted inspection milestone already covers the beta path. |
| Precision file tools product acceptance | Run broader sidecar/Electron evidence-link smoke after frontend entry points consume precision evidence links. | Tool/backend scope is complete; remaining work is acceptance depth. |
| Stop / cancel UX | Done in `codex/product-1-1-stop-cancel-ux`: projection treats intentional terminal stop reasons (`cancelled:` / `skipped:`) as `cancelled` execution and suppresses generic failed-task Retry. | Avoids user trust damage in long-running tasks. |
| Token usage budget boundary | Add visible warning or budget boundary for long-running or extremely high-token execution. | Prevents cost surprises during beta use. |
| Diagnostics descriptors | Add richer beta-depth diagnostic bundle descriptors for workspace inspection evidence, per-route Electron logs, and support-oriented summaries. | Improves supportability beyond the P0 route-matrix closure. |
| Localization polish | Clean remaining mixed English/Chinese execution ASK and recovery copy; continue moving UI system text behind typed keys. | Product quality issue for zh-CN beta builds. |
| Web retrieval beta hardening | Verify real Tavily Search/Extract smoke, broader citation/result UI, Audit projection depth, user-visible limitations, and future retrieval budget boundaries. | Search/fetch are implemented; the remaining work is beta trust and release evidence, not first capability delivery. |
| Electron release hardening | Keep packaged/installer smoke current for Product 1.1 paths; add sidecar restart replay; signed/notarized distribution remains deferred until Apple Developer credentials exist. | Protects beta release quality. |
| External release docs sync | Mirror Product 1.1 beta evidence and known limitations into the public repository release/user docs when publishing externally. | Public-facing clarity matters, but the internal P0 release evidence is now closed. |

## 5.1 Recommended Next Product Branches

The next branches should be selected in this order:

1. **Sidecar restart replay confidence**: prove durable Conversation /
   Activity replay after killing and relaunching the packaged sidecar, then
   fold that into installer smoke if it remains stable.
2. **External Product 1.1 release docs sync**: mirror the internal Product 1.1
   beta release record into the public repository docs with user-facing known
   limitations.
3. **P1 beta polish**: token budget warnings, localization cleanup, and web
   retrieval release evidence.

## 6. P2 Open Work

| Area | Open work | Why P2 |
|---|---|---|
| Skills productization | User-facing skill selection, skill config UI, public marketplace, custom skill authoring, MCP skill bundles, and broader routing productization. | Backend governance foundation exists, but public productization is larger than the P0 loop. |
| MCP integration | First safe MCP servers, CapabilityCatalog mapping, confirmation/risk policies, and Audit summaries. | Important platform expansion after the core collaboration loop is stable. |
| Agent protocol and routing | Baseline public Agent protocol, special Agent protocols, Routing Agent, Execution Agent, Collaborator Agent, Audit Agent, Result Packaging Agent, assignment visibility, and custom Agent validation. | Requires stronger routing and governance than Product 1.1 P0 needs. |
| File and multimodal support | Documents, spreadsheets, images, PDFs, code bundles, and mixed attachments as first-class Task context, evidence, and deliverables. | Major product surface expansion. |
| Result packaging and `task_after` | Result Packaging Agent, result cards, completion-time summaries, validation, archive, and follow-up work. | Valuable output polish, but not required for P0 runtime input closure. |
| Broader context governance | First-class Plan Context, stronger Session memory policy, semantic retrieval, and cross-session memory. | Keep behind explicit product decisions after command-backed guidance is stable. |
| Deep web research | Browser automation, authenticated browsing, crawling, PDF/OCR/table extraction, and multi-source research workflows. | Higher-risk retrieval surface beyond first search/fetch tools. |

## 7. Update Rules

When any Product 1.1 open item changes:

1. Update the owning feature plan first.
2. Update this document only when priority, milestone membership, readiness, or
   product acceptance changes.
3. Keep P0 scoped to Runtime Input Router, Contract Revision Command Skills,
   and durable Activity/Audit evidence until the milestone is accepted.
4. Do not promote P2 platform expansion into P0 unless it is required to close
   the runtime input and evidence loop.
