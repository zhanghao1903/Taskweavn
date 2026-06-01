# UI / Backend Large File Split Plan

> Status: planned
> Last Updated: 2026-06-01
> Gap: [Audit / Trust page implementation](../../gaps/README.md#4-product-10-gap-table), [Result and evidence exposure surface](../../gaps/README.md#4-product-10-gap-table), delivery maintainability risk
> Architecture: [UI Backend Communication](../../architecture/ui-backend-communication.md), [Task Domain / UI Model Separation](../../architecture/task-domain-ui-model-separation.md), [Configurable Logging System](../../architecture/configurable-logging-system.md)
> Product: no direct user-facing behavior change
> Release Record: TBD when implementation slices complete

---

## 1. Problem / Gap

Recent Audit Page and Main Page integration work added real value, but several
boundary files now carry too many responsibilities.

Current code facts checked on 2026-06-01:

| File | Lines | Risk | Current responsibilities |
|---|---:|---|---|
| `src/taskweavn/server/ui_contract/gateways.py` | 3453 | blocked | Protocols, concrete providers, query gateway, command gateway, audit projection, payload disclosure, sanitization, command response shaping. |
| `frontend/src/pages/audit-page/AuditPage.tsx` | 1041 | high | Route-level page rendering, chrome, overview, filter rail, timeline, detail panel, sanitized disclosure rendering, labels, selection helpers. |
| `src/taskweavn/server/ui_http.py` | 1020 | high | HTTP transport object, route matching, request parsing, command dispatch, SSE handling, response/error helpers. |
| `src/taskweavn/server/main_page.py` | 944 | high | Sidecar config/dependencies, app assembly, authoring stores, resident AgentLoop, session lifecycle, logging archive setup, audit event emission. |

This is not only cosmetic file size. These files now make ordinary feature work
riskier because new behavior tends to cross protocol, transport, projection,
runtime, and UI boundaries in one edit.

The next step should be a behavior-preserving split before adding more broad
Audit/Main Page behavior.

---

## 2. Gate Reports

### 2.1 Workflow Gate Report

- User request: commit current maintainability gate, then design a split plan.
- Detected phase: P0 repository/task intake plus P9 delivery readiness hygiene.
- Task type: docs/design for maintainability; no production behavior change.
- Required upstream artifacts: code facts, plan conventions, maintainability gate, existing Audit/Main Page plans.
- Found artifacts: `docs/plans/README.md`, Audit Page plans, UI contract docs, current hotspot files, `.agents/skills/maintainability-gate/SKILL.md`.
- Missing/weak artifacts: no dedicated maintainability plan category existed before this plan.
- Implementation allowed now: only documentation and planning are allowed now.
- Prework required: create this plan before refactoring.
- Execution scope: define split boundaries, slices, compatibility rules, and validation.
- Acceptance criteria: future refactor sessions can execute slices without reopening boundary decisions.
- Risks/assumptions: exact module names can still be adjusted during implementation if imports reveal better seams.

### 2.2 Maintainability Gate Report

- Requested change: design split strategy for current large UI/backend files.
- Files/modules inspected: `gateways.py`, `ui_http.py`, `main_page.py`, `AuditPage.tsx`, related tests.
- Trigger: files over 800/1200/2000 lines and mixed responsibility groups.
- Current risk level: `gateways.py` is blocked-risk; the other three are high-risk.
- Responsibility count: each hotspot mixes at least three responsibility groups.
- Size/complexity signals: 6458 lines across four files; `gateways.py` alone has over 100 class/function definitions.
- Coupling signals: Audit work crosses backend projection, HTTP transport, frontend rendering, runtime events, logs/config, and sanitized disclosure.
- Tests covering the area: backend `test_ui_query_gateway.py`, `test_ui_command_gateway.py`, `test_ui_http_transport.py`, `test_main_page_sidecar_app.py`, audit contract/model tests; frontend `AuditPageRoute.test.tsx`, mock scenario tests, API tests.
- Refactor required first: yes, before adding more broad behavior to these files.
- Allowed change type: `zero_behavior_refactor` and `adapter_extraction`.
- Proposed slice: split by responsibility while keeping public imports and route behavior stable.
- Acceptance criteria: tests pass before/after each slice; no product behavior or contract shape change.
- Validation commands: see section 8.
- Risks and assumptions: import compatibility wrappers must stay until downstream imports move.

---

## 3. Scope

This plan covers a first maintainability pass for:

1. backend UI contract gateways;
2. backend HTTP transport;
3. Audit Page React composition;
4. Main Page sidecar assembly.

The goal is to reduce file size and responsibility mixing while preserving:

- backend contract JSON;
- HTTP routes and query parameters;
- SSE event behavior;
- Audit Page A1-A14 mock scenario parity;
- Main Page runtime behavior;
- existing public imports from `taskweavn.server.ui_contract`.

---

## 4. Non-goals

This plan does not:

- redesign Audit Page product behavior;
- change API response shapes;
- add new audit sources;
- change sanitized payload policy;
- change routing, auth, or sidecar ports;
- rewrite React state management;
- remove compatibility imports in the first pass;
- add a new framework or dependency.

---

## 5. Proposed Design

### 5.1 Principles

1. Preserve behavior first; reduce file size second.
2. Split by responsibility, not by arbitrary line count.
3. Keep the old public module as a compatibility facade during migration.
4. Move pure helpers before moving stateful orchestration.
5. Do not mix feature behavior with refactor slices.
6. Validate each slice independently.

### 5.2 Backend UI Contract Split

Target area: `src/taskweavn/server/ui_contract/`.

Recommended module shape:

| Module | Responsibility |
|---|---|
| `gateways.py` | Temporary compatibility facade and stable public import surface. |
| `gateway_protocols.py` | `SessionReader`, providers, `UiQueryGateway`, `UiCommandGateway`, disclosure protocols. |
| `gateway_providers.py` | Static/workspace providers for project, workflow, audit events, config, logs. |
| `query_gateway.py` | `DefaultUiQueryGateway` orchestration only. |
| `command_gateway.py` | `DefaultUiCommandGateway` orchestration only. |
| `audit_projection.py` | Audit records, overview, filters, detail, evidence projection from task/message/event/log/config sources. |
| `audit_disclosure.py` | `DefaultAuditPayloadDisclosureService`, payload visibility decisions, redaction, sanitization. |
| `command_mapping.py` | Task tree mapping, command response helpers, object refs, task node patch helpers. |

Compatibility rule:

```python
# taskweavn.server.ui_contract.gateways
from .gateway_protocols import UiQueryGateway, UiCommandGateway
from .query_gateway import DefaultUiQueryGateway
from .command_gateway import DefaultUiCommandGateway
...
```

Downstream modules can keep importing from `ui_contract` and `gateways` until a
later cleanup slice moves imports deliberately.

### 5.3 Backend HTTP Transport Split

Target area: `src/taskweavn/server/`.

Recommended module shape:

| Module | Responsibility |
|---|---|
| `ui_http.py` | `PlatoUiHttpTransport`, `SidecarAuth`, public transport facade. |
| `ui_http_routes.py` | Route dataclass, route matching, path extraction. |
| `ui_http_query_params.py` | Query parsing, bool/int/date/string coercion. |
| `ui_http_commands.py` | Command request parsing, dispatch result shaping, debug refs. |
| `ui_http_responses.py` | JSON/contract/error response helpers. |
| `ui_http_sse.py` | SSE frame and event-stream helpers if route code keeps growing. |

`ui_http.py` should become an orchestration layer that delegates to helpers.
Routes and command dispatch can be tested without instantiating the full
transport.

### 5.4 Audit Page Frontend Split

Target area: `frontend/src/pages/audit-page/`.

Recommended module shape:

| Module | Responsibility |
|---|---|
| `AuditPage.tsx` | Page composition only. |
| `AuditPageChrome.tsx` | Top chrome/header shell. |
| `AuditHeader.tsx` | Audit title, scope, state, action header. |
| `AuditOverview.tsx` | Overview metrics and verdict notice. |
| `AuditFilterRail.tsx` | Filters, counts, selected filter behavior. |
| `AuditTimeline.tsx` | Timeline/record card rendering. |
| `AuditDetailPanel.tsx` | Selected record detail rendering. |
| `AuditDisclosure.tsx` | Sanitized/hidden/partial/redacted payload disclosure rendering. |
| `auditPageLabels.ts` | Verdict/completeness/boundary/status labels and classes. |
| `auditPageSelection.ts` | Selected record resolution and scope/subject helpers. |

`AuditPageRoute.tsx` should remain the route/controller owner for data queries,
runtime event subscription, filter state, and URL behavior.

The first split should not change CSS tokens or layout behavior. Visual polish
belongs to later UI work.

### 5.5 Main Page Sidecar Split

Target area: `src/taskweavn/server/`.

Recommended module shape:

| Module | Responsibility |
|---|---|
| `main_page.py` | Public `MainPageSidecarConfig`, `MainPageSidecarDependencies`, `MainPageSidecarApp`, `build_main_page_sidecar_app`. |
| `main_page_logging.py` | Sidecar logging config and log manifest writing. |
| `main_page_agents.py` | Resident Default Agent / AgentLoop construction and runner. |
| `main_page_sessions.py` | Session lifecycle gateway and task ref resolver. |
| `main_page_audit_events.py` | Audit event command wrapper and source-change emitters. |
| `main_page_assembly.py` | Optional internal assembly helpers if `build_main_page_sidecar_app` remains too large. |

The public module should remain import-compatible. Tests should continue to use
`build_main_page_sidecar_app` from `taskweavn.server.main_page`.

---

## 6. Implementation Slices

### M-000: Plan And Guardrail

Status: this document.

Deliverables:

- Maintainability skill exists.
- Maintainability plan category exists.
- This split plan exists.

Validation:

- `git diff --check`

### M-001: Extract UI Contract Protocols And Providers

Goal: reduce `gateways.py` by moving protocol definitions and static/workspace
providers.

Allowed changes:

- create `gateway_protocols.py`;
- create `gateway_providers.py`;
- re-export from `gateways.py`;
- update direct imports only if easy and low risk.

Acceptance:

- public imports from `taskweavn.server.ui_contract` still work;
- no contract JSON changes;
- provider tests still pass.

Suggested validation:

```bash
uv run pytest tests/test_ui_query_gateway.py tests/test_ui_command_gateway.py tests/test_ui_contract_models.py
uv run ruff check src/taskweavn/server/ui_contract tests/test_ui_query_gateway.py tests/test_ui_command_gateway.py
uv run mypy src/taskweavn/server/ui_contract
```

### M-002: Extract Audit Projection And Disclosure

Goal: isolate Audit Page projection and sanitized disclosure policy from query
gateway orchestration.

Allowed changes:

- create `audit_projection.py`;
- create `audit_disclosure.py`;
- keep `DefaultUiQueryGateway` delegating into projection helpers;
- keep sanitized payload request-time only; do not persist sanitized payload.

Acceptance:

- Audit Page snapshot/detail/evidence tests remain unchanged;
- hidden/partial/redacted/requested payload behavior remains unchanged;
- A1-A14 mock parity is not weakened.

Suggested validation:

```bash
uv run pytest tests/test_audit_page_contract_models.py tests/test_ui_query_gateway.py tests/test_ui_http_transport.py
uv run pytest tests/test_main_page_sidecar_app.py -k audit
uv run ruff check src/taskweavn/server/ui_contract tests/test_audit_page_contract_models.py tests/test_ui_query_gateway.py
uv run mypy src/taskweavn/server/ui_contract
```

### M-003: Extract Command Gateway Mapping

Goal: separate command orchestration from task-tree mapping and response helper
functions.

Allowed changes:

- create `command_gateway.py`;
- create `command_mapping.py`;
- leave command response types unchanged.

Acceptance:

- command gateway tests pass;
- idempotency/debug refs unchanged;
- Main Page command HTTP tests pass.

Suggested validation:

```bash
uv run pytest tests/test_ui_command_gateway.py tests/test_ui_http_transport.py
uv run ruff check src/taskweavn/server/ui_contract src/taskweavn/server/ui_http.py
uv run mypy src/taskweavn/server/ui_contract src/taskweavn/server/ui_http.py
```

### M-004: Extract HTTP Route, Parsing, And Response Helpers

Goal: make `ui_http.py` focus on transport orchestration.

Allowed changes:

- create `ui_http_routes.py`;
- create `ui_http_query_params.py`;
- create `ui_http_responses.py`;
- move pure helper tests or add narrow tests for route parsing if current tests
  are too indirect.

Acceptance:

- route matching behavior unchanged;
- error response shape unchanged;
- SSE route URL unchanged.

Suggested validation:

```bash
uv run pytest tests/test_ui_http_transport.py tests/test_ui_sse_transport.py tests/test_local_sidecar_server.py
uv run ruff check src/taskweavn/server/ui_http.py src/taskweavn/server/ui_http_*.py tests/test_ui_http_transport.py
uv run mypy src/taskweavn/server/ui_http.py src/taskweavn/server/ui_http_*.py
```

### M-005: Extract HTTP Command Dispatch And SSE Helpers

Goal: reduce coupling between command handling and streaming/event code.

Allowed changes:

- create `ui_http_commands.py`;
- create `ui_http_sse.py` only if enough code moves to justify it;
- preserve `PlatoUiHttpTransport.handle()` behavior.

Acceptance:

- command idempotency hash unchanged;
- dispatch debug refs unchanged;
- existing EventSource clients still receive compatible frames.

Suggested validation:

```bash
uv run pytest tests/test_ui_http_transport.py tests/test_ui_sse_transport.py
uv run pytest tests/test_main_page_sidecar_app.py -k "audit_event or confirmation or log"
uv run ruff check src/taskweavn/server/ui_http*.py tests/test_ui_http_transport.py
uv run mypy src/taskweavn/server/ui_http.py src/taskweavn/server/ui_http_*.py
```

### M-006: Split Audit Page Presentational Components

Goal: make `AuditPage.tsx` a small composition file while preserving UI output.

Allowed changes:

- extract chrome/header/overview/filter/timeline/detail/disclosure components;
- keep existing CSS module unless class ownership becomes confusing;
- no visual redesign.

Acceptance:

- `AuditPageRoute.test.tsx` passes without fixture changes;
- A1-A14 scenarios still render expected states;
- keyboard/focus behavior unchanged.

Suggested validation:

```bash
cd frontend && npm run test -- AuditPageRoute.test.tsx mockAuditScenarios.test.ts
cd frontend && npm run lint
cd frontend && npm run build
```

### M-007: Extract Audit Page Labels And Selection Helpers

Goal: remove non-render helper logic from the page file and make it directly
unit-testable.

Allowed changes:

- create `auditPageLabels.ts`;
- create `auditPageSelection.ts`;
- add focused unit tests if existing route tests do not cover moved helpers.

Acceptance:

- label text/class mapping unchanged;
- selected record fallback behavior unchanged.

Suggested validation:

```bash
cd frontend && npm run test -- AuditPageRoute.test.tsx
cd frontend && npm run lint
```

### M-008: Slim Main Page Sidecar Assembly

Goal: keep `main_page.py` as public assembly API and move supporting concerns
out of the root file.

Allowed changes:

- extract logging helpers;
- extract audit event emitters;
- extract resident agent builder/runner;
- extract session lifecycle gateway/resolver if the public surface stays stable.

Acceptance:

- `build_main_page_sidecar_app` import stays unchanged;
- default port/config behavior unchanged;
- session lifecycle, execution tick, audit event, and logging tests pass.

Suggested validation:

```bash
uv run pytest tests/test_main_page_sidecar_app.py tests/test_local_sidecar_server.py
uv run ruff check src/taskweavn/server/main_page.py src/taskweavn/server/main_page_*.py tests/test_main_page_sidecar_app.py
uv run mypy src/taskweavn/server/main_page.py src/taskweavn/server/main_page_*.py
```

---

## 7. Dependency And Ordering Rules

Recommended order:

```text
M-001 protocols/providers
  -> M-002 audit projection/disclosure
  -> M-003 command gateway/mapping
  -> M-004 HTTP route/parsing/response helpers
  -> M-005 HTTP command/SSE helpers
  -> M-006 Audit Page components
  -> M-007 Audit Page helper extraction
  -> M-008 Main Page sidecar slimming
```

Rationale:

- `gateways.py` is the largest and most blocked-risk file; split it before
  adding more audit sources.
- HTTP transport depends on gateway interfaces; stabilize gateway modules first.
- Audit Page frontend can be split after backend contract behavior is stable.
- `main_page.py` should be slimmed after HTTP/gateway seams are clearer because
  it wires many of those objects together.

Do not run M-006/M-007 together with visual redesign. That should be a separate
UI polish slice.

---

## 8. Tests And Validation

Minimum validation for every slice:

```bash
git diff --check
```

Backend slices should run targeted `pytest`, `ruff`, and `mypy` for the touched
modules. Frontend slices should run targeted Vitest, `npm run lint`, and
`npm run build` when feasible.

For the final split closure, run:

```bash
uv run pytest tests/test_ui_query_gateway.py tests/test_ui_command_gateway.py tests/test_ui_http_transport.py tests/test_main_page_sidecar_app.py
uv run ruff check src/taskweavn/server/ui_contract src/taskweavn/server/ui_http.py src/taskweavn/server/main_page.py
uv run mypy src/taskweavn/server/ui_contract src/taskweavn/server/ui_http.py src/taskweavn/server/main_page.py
cd frontend && npm run test -- AuditPageRoute.test.tsx mockAuditScenarios.test.ts
cd frontend && npm run lint
cd frontend && npm run build
```

If full-suite validation is too slow in an implementation session, document the
reason and run the targeted commands for the changed boundary.

---

## 9. Acceptance Criteria

The split work is acceptable when:

1. all four hotspot files are reduced to clear orchestration or compatibility
   modules;
2. public imports remain stable during the migration;
3. no backend contract JSON changes are introduced accidentally;
4. Audit Page A1-A14 scenarios keep their existing behavior;
5. Main Page sidecar behavior and route behavior remain stable;
6. every moved responsibility has direct or indirect tests;
7. future audit sources can be added without editing `gateways.py`,
   `ui_http.py`, `AuditPage.tsx`, and `main_page.py` in the same slice.

Suggested post-split targets:

| File | Target after split |
|---|---:|
| `src/taskweavn/server/ui_contract/gateways.py` | under 400 lines, mostly re-exports or facade |
| `src/taskweavn/server/ui_http.py` | under 550 lines |
| `frontend/src/pages/audit-page/AuditPage.tsx` | under 350 lines |
| `src/taskweavn/server/main_page.py` | under 550 lines |

These are guidance numbers, not hard gates. Responsibility clarity matters more
than hitting an exact line count.

---

## 10. Completion Updates

When this plan is implemented:

1. update this plan status to `done`;
2. update related Audit Page / Result exposure plans if implementation order or
   readiness changed;
3. update `docs/gaps/README.md` only if maintainability risk remains a tracked
   Product 1.0 blocker;
4. add a release note if the split materially changes how future work should be
   executed;
5. append any reusable lesson to `.agents/skills/maintainability-gate/SKILL.md`.
