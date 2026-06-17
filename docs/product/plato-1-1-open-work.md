# Plato Product 1.1 Open Work

> Status: active open-work index
>
> Last Updated: 2026-06-18
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
- several foundation slices are already accepted or implemented;
- the remaining Product 1.1 risk is the collaboration loop around runtime
  input, contract revision, durable evidence, and user trust.

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
| Session Activity surface | Accepted foundation: typed Activity query, backend projection, frontend drawer, related refs. Router-written records remain open. | [Session Conversation / Activity Timeline](../plans/feature/session-conversation-activity-timeline.md) |
| Read-only inquiry | Accepted for Product 1.1 local runtime: no-mutation answers, evidence refs, Activity display/replay, Audit focused refs, diagnostic actions, sidecar/Electron smoke. | [Read-Only Inquiry Context](../plans/feature/read-only-inquiry-context.md) |
| Token usage analytics | Completed Product 1.1 slice: usage ledger, Task/Plan/Session/Workspace aggregation, cache hit-rate visibility, Settings/Main Page entries, diagnostics-safe summaries. | [Token Usage Analytics](../plans/feature/token-usage-analytics.md) |
| UI system text foundation | Implemented typed UI system text registry, `en-US` / `zh-CN` catalogs, runtime locale override, Settings language selector, staged chrome migration. | [Product Copy Localization Foundation](../plans/feature/product-copy-localization-foundation.md) |
| Web fetch | Implemented first Product 1.1 `web_fetch` capability behind the Web Search provider/key path. | [Execution Web Fetch Capability](../plans/feature/execution-web-fetch-capability.md) |

## 4. P0 Milestone: Runtime Input And Evidence Closure

### 4.1 Milestone Statement

Product 1.1 P0 is now one milestone:

```text
Runtime Input Router
  + Contract Revision Command Skills
  + durable Activity / Audit evidence
```

The milestone is complete when a user can type into the Main Page once, Plato
can safely interpret the input as a question, guidance, command, ASK answer,
confirmation response, or execution request, and the user can later inspect
what happened through durable Activity and Audit evidence.

### 4.2 Why This Is The P0

Product 1.1 already has useful workspace and trust surfaces. The remaining
failure mode is that user input can still feel like chat attached to several
separate command paths. That is a product problem:

- guidance can be lost as informal text instead of becoming typed context;
- command-like requests can be ambiguous or unsupported without a clear
  product explanation;
- ASK and confirmation resolution can exist in explicit UI paths but still be
  inconsistent with the natural-language input surface;
- workspace-changing requests must become executable contract work, not direct
  tool execution;
- Router decisions must be durable and auditable, not transient UI metadata.

### 4.3 P0 Work Packages

| ID | Work package | Target outcome | Source |
|---|---|---|---|
| P0-RIR-1 | Main Page default Router path | Main Page submit routes through Runtime Input Router by default while explicit ASK/confirmation controls continue to work. | [Runtime Input Router Contract](../plans/feature/runtime-input-router-contract.md) |
| P0-RIR-2 | Question and guidance routes | Read-only questions use the accepted Inquiry path; guidance routes to command-backed guidance recording. Unsupported guidance never becomes hidden behavior. | [Runtime Input And Contract Revision Program](../plans/feature/runtime-input-and-contract-revision-program.md) |
| P0-CRS-1 | Command skill protocol | Internal command skills return versioned, idempotent, auditable results with Activity metadata and no direct workspace writes. | [Contract Revision Command Skills](../plans/feature/contract-revision-command-skills.md) |
| P0-CRS-2 | `record_guidance` | Session, Plan, or Task guidance persists as typed contract/context facts and appears in Activity. | [Contract Revision Command Skills](../plans/feature/contract-revision-command-skills.md) |
| P0-CRS-3 | ASK and confirmation routed resolution | The same input surface can resolve active ASK and confirmation states through accepted domain commands. | [Runtime Input Router Contract](../plans/feature/runtime-input-router-contract.md) |
| P0-CRS-4 | Execution request handoff | Workspace-changing requests create executable Plan/TaskNode contract work and enter TaskBus only through the accepted execution path. | [Contract Revision Command Skills](../plans/feature/contract-revision-command-skills.md) |
| P0-CRS-5 | Plan/TaskNode mutation commands | Contract-changing requests use command-backed patch/create/delete operations with state, version, idempotency, and confirmation guards. | [Plan / TaskNode Contract Migration](../plans/feature/plan-tasknode-contract-migration.md) |
| P0-ACT-1 | Durable Router Activity | Router decisions and outcomes are stored as durable Session content or equivalent facts, not only returned as transient route-result metadata. | [Session Conversation / Activity Timeline](../plans/feature/session-conversation-activity-timeline.md) |
| P0-TRUST-1 | Audit and diagnostics linkage | Routed input links to downstream command, Activity, Audit, and diagnostic refs without exposing prompts, provider payloads, raw logs, SQLite rows, secrets, or absolute paths. | [Runtime Input And Contract Revision Program](../plans/feature/runtime-input-and-contract-revision-program.md) |
| P0-QA-1 | Real acceptance suite | Electron/sidecar acceptance covers question, guidance, ASK, confirmation, stop/retry, execution-request handoff, unsupported routes, and no-mutation guarantees. | [Product 1.1 QA Report](plato-1-1-real-local-qa-report-2026-06-11.md) |

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

### 4.6 Suggested P0 Execution Order

1. Done: implement the CRS-A command protocol models and focused unit tests.
2. Done: implement `record_guidance` persistence, projection, and Activity
   output.
3. Done for guidance: wire RIR guidance routes into Main Page default submit.
   RIR question routes remain read-only inquiry backed.
4. Done: add ASK/confirmation routed resolution parity with explicit UI
   controls.
5. Partial: add guarded Plan/TaskNode mutation commands. `patch_task_node` is
   implemented through the existing versioned `update_task_node` handler;
   `create_task_node`, `delete_task_node`, and `create_execution_task` remain
   open.
6. Partial: persist Router decisions/outcomes as durable Session Activity for
   read-only inquiry and implemented Contract Revision commands.
7. Partial: add Router Audit/diagnostic refs and redacted diagnostic
   descriptors for implemented Contract Revision commands.
8. Open: run the real Electron/sidecar acceptance suite for all P0 routes.

## 5. P1 Open Work

| Area | Open work | Why P1 |
|---|---|---|
| Workspace inspection hardening | Decide whether viewer route openings should automatically capture durable evidence; add richer Audit evidence detail expansion; keep raw unified diff deferred unless a concrete UI/diagnostic need appears. | Useful for trust and support, but the accepted inspection milestone already covers the beta path. |
| Precision file tools product acceptance | Run broader sidecar/Electron evidence-link smoke after frontend entry points consume precision evidence links. | Tool/backend scope is complete; remaining work is acceptance depth. |
| Stop / cancel UX | Represent intentional user stop as `stopped` or `cancelled`, not as a generic `failed` state with `Retry`. | Avoids user trust damage in long-running tasks. |
| Token usage budget boundary | Add visible warning or budget boundary for long-running or extremely high-token execution. | Prevents cost surprises during beta use. |
| Diagnostics descriptors | Add richer diagnostic bundle section descriptors, including workspace inspection evidence and Router decision descriptors. | Improves supportability without changing the main work loop. |
| Localization polish | Clean remaining mixed English/Chinese execution ASK and recovery copy; continue moving UI system text behind typed keys. | Product quality issue for zh-CN beta builds. |
| Web search status reconciliation | Align the `web_search` feature plan, implementation status, Settings path, real Tavily smoke, Audit evidence, and release docs. | Needed before claiming web retrieval as a stable Product 1.1 capability. |
| Web fetch beta hardening | Verify real Tavily Extract smoke, result citations, Audit/diagnostic projection, and user-visible limitations. | `web_fetch` is implemented, but beta trust language still needs closure. |
| Electron release hardening | Keep packaged/installer smoke current for Product 1.1 paths; signed/notarized distribution remains deferred until Apple Developer credentials exist. | Protects beta release quality. |

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
