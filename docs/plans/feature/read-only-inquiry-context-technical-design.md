# Read-Only Inquiry Context Technical Design

> Status: accepted for Product 1.1 local runtime
>
> Last Updated: 2026-06-14
>
> Owner: Product / Context / Backend UI Gateway / Frontend
>
> Related:
> [Read-Only Inquiry Context](read-only-inquiry-context.md),
> [Runtime Input And Contract Revision Program](runtime-input-and-contract-revision-program.md),
> [Runtime Input Router Contract](runtime-input-router-contract.md),
> [Runtime Input Router Technical Design](runtime-input-router-contract-technical-design.md),
> [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md),
> [Git, Diff, And File Viewer API Contract](../../engineering/git-diff-file-viewer-api-contract.md),
> [Audit Page Contract](../../engineering/audit-page-contract.md),
> [Plato Session Content Model](../../product/plato-session-content-model.md)

---

## 1. Purpose

Read-Only Inquiry answers user questions about current Plato and workspace facts
without changing product state or workspace state.

It is a downstream capability used by Runtime Input Router when the route
decision is:

```text
intent = question
sideEffect = no_effect
dispatchTarget = read_only_inquiry
```

The capability belongs to the Contract Revision Loop only as a read-only
interpretation tool. It must not record guidance, mutate Plan/TaskNode, resolve
ASK/confirmation, enqueue TaskBus work, write files, or run side-effecting
commands.

---

## 2. Design Decisions

These decisions are part of the technical boundary for the accepted foundation
implementation.

1. Runtime Input Router owns interpretation. Inquiry does not decide whether a
   user input is guidance, contract revision, execution request, ASK answer, or
   question.
2. Inquiry owns answer generation only after Router has selected
   `dispatchTarget=read_only_inquiry` and `sideEffect=no_effect`.
3. Inquiry is not Collaborator, not an execution agent, and not a general agent
   loop. It may use read-only providers behind narrow service interfaces, but
   it must not receive write tools or TaskBus access.
4. Evidence refs are pointers to existing evidence owners. Inquiry may summarize
   safe facts, but it must not persist or expose raw context packs as a new
   evidence source of truth.
5. The first public path is through Runtime Input Router. A direct Inquiry HTTP
   endpoint is deferred until a separate API contract is accepted.
6. Deterministic answers for status/progress questions come before LLM-backed
   answers. LLM-backed answers require redaction and no-mutation tests first.
7. Activity projection is a user-facing trace. It is not canonical product
   state and cannot repair or override Plan, TaskNode, Audit, result, file, ASK,
   confirmation, or TaskBus facts.
8. The first version is scoped to the selected Session/Plan/Task and explicit
   refs. Cross-workspace search, semantic memory, and broad workspace scans are
   out of scope.

### 2.1 Architectural Boundary

Read-Only Inquiry is a downstream answer service, not a second Router.

```text
User input
  -> Runtime Input Router
      -> route decision: question / no_effect
      -> Read-Only Inquiry
          -> bounded read context
          -> answer result
      -> Router result envelope
      -> Activity / Main Page presentation
```

The service has exactly one product responsibility: convert already-authorized,
bounded, read-only product/workspace facts into a user-facing answer with safe
evidence refs.

It must not:

- infer whether the user meant guidance, command, ASK answer, or execution;
- create a new Task, Plan, confirmation, or ASK;
- reinterpret rejected output as a mutating command;
- own durable Conversation state beyond accepted answer Activity persistence.

This keeps the Product 1.1 model simple:

```text
Router decides consequence.
Inquiry explains facts.
Contract Revision Skills change contracts.
TaskBus changes the workspace.
```

### 2.2 Current Implementation Status

This technical design is accepted for the Product 1.1 foundation, but the full
product experience is not closed.

Implemented foundation:

- Runtime Input Router can dispatch a `question/no_effect` decision to
  Read-Only Inquiry when session context is available.
- Inquiry has explicit request/result/evidence/warning models in backend and
  frontend contract fixtures.
- Deterministic status/progress answers are available without an LLM provider.
- The context builder can summarize selected Session/Plan/Task status, result
  summaries, file-change summaries, explicit Activity refs, explicit Audit
  record/evidence refs, Workspace Inspection file snippets and diffs, and safe
  Main Page planning diagnostic descriptors.
- The runtime input route carries opaque `workspaceId` into Inquiry when using
  workspace-scoped routes, so generated file/diff/Audit hrefs preserve
  workspace context.
- Runtime Input Router accepts explicit `inquiryRefs` alongside generic
  selection refs. These refs are the accepted bridge for file, diff, Audit,
  diagnostic, result, and Activity anchors that are already known to the UI and
  should be passed directly to Inquiry without overloading
  `selection.refs`.
- A read-only diagnostic support descriptor can explain the accepted redacted
  diagnostic bundle export action without exporting a bundle or reading raw
  diagnostic artifacts.
- Main Page can display the answer through the existing notice path and
  Activity strip/overlay.
- Answered read-only questions are persisted as safe informational
  MessageStream rows and replay as `answer/no_effect` Activity items while
  preserving safe evidence refs.
- Focused backend/frontend contract tests and real sidecar no-mutation
  acceptance cover the foundation across file, diff, Audit record, Audit
  evidence, diagnostic, result, status, and Activity replay refs.
- Configured Electron smoke covers durable read-only answer Activity replay,
  diagnostic export action handling, and Audit evidence focus in the desktop
  shell.
- `npm run electron:smoke:read-only-inquiry-llm` extends the configured
  Electron smoke with a seeded guarded LLM provider fixture and verifies the
  LLM-rendered answer remains answer-only in the desktop shell.
- `npm run electron:smoke:packaged-read-only-inquiry-llm` verifies the same
  guarded LLM-rendered answer path against the unsigned packaged app directory
  without Vite.
- `npm run electron:smoke:launcher` verifies the launcher-backed package path
  keeps read-only inquiry provider-independent while preserving the same
  no-mutation Activity, Audit evidence, diagnostic export, first-run, and
  startup-diagnostics behavior through the bundled sidecar launcher.
- Guarded LLM answer provider module, service injection seam, and default
  sidecar runtime wiring are implemented behind explicit configuration:
  `enable_read_only_inquiry_llm` in assembly, with
  `PLATO_ENABLE_READ_ONLY_INQUIRY_LLM=0` or
  `--disable-read-only-inquiry-llm` available for deterministic fallback in
  CLI/packaged sidecar entrypoints.
  The provider calls LLM without tools, accepts only JSON output citing known
  evidence refs, redacts home paths from prompt input, falls back on
  unavailable/invalid output, and rejects mutating output.

Non-blocking follow-ups outside the local runtime acceptance boundary:

- richer exported diagnostic bundle section descriptors, if needed by support;
- broader Router Conversation / Activity persistence for non-answer outcomes;
- localization polish for all answer, warning, and recovery copy;
- signed installer no-mutation acceptance if Product 1.1 requires this path
  before release hardening;
- optional result/detail deep links if Product 1.1 needs direct result focus
  beyond Activity result refs.

### 2.3 Local Design Versus Program Closure

This document owns the local Read-Only Inquiry technical design:

- how a `question/no_effect` route becomes a bounded inquiry request;
- which read providers may supply context;
- what evidence refs and warnings mean;
- which links can be produced safely;
- how no-mutation is tested for inquiry answering.

It intentionally does not own the global runtime-input closure plan. The
umbrella [Runtime Input And Contract Revision Program](runtime-input-and-contract-revision-program.md)
owns sequencing across Router, Contract Revision Skills, Session
Conversation/Activity, Audit linkage, diagnostics, and execution handoff.

When a remaining gap is not specific to answer-only inquiry, this design should
link to the umbrella program instead of duplicating the dependency matrix.

### 2.4 Capability Stages

Read-Only Inquiry should advance in explicit stages so Product 1.1 can accept
the no-mutation boundary before adding broader intelligence.

| Stage | Capability | Acceptance bar |
|---|---|---|
| Foundation | Deterministic answer-only route over selected Session/Plan/Task facts and explicit refs. | Backend/frontend contract tests plus sidecar no-mutation acceptance. |
| Evidence closure | File, diff, result, Activity, Audit record, Audit evidence, and diagnostic refs are preserved as safe citations and actions. | Real sidecar coverage for href/action generation; Electron coverage for desktop route/action behavior. |
| Provider expansion | LLM-backed answers over normalized redacted context items. | Redaction, provider-failure, cited-evidence, and no-mutation tests pass before enabling in desktop shell. |
| Conversation closure | Router outcomes beyond answer-only routes become durable typed Session Activity. | Session Activity replay shows interpreted intent, side effect, and refs for supported route classes. |

The foundation and evidence-closure stages are allowed to ship without
LLM-backed answers. LLM-backed answers must not be used to compensate for
missing read providers, missing evidence refs, or unresolved Router command
contracts.

### 2.5 Runtime Input Boundary

The same Main Page input can eventually support answer-only questions,
contract-changing guidance, Plan/TaskNode edits, ASK/confirmation answers, and
execution requests. Read-Only Inquiry owns only one branch of that input model:

```text
question -> no_effect -> read_only_inquiry
```

The Product 1.1 boundary is intentionally explicit:

| Input outcome | Owning capability | Read-Only Inquiry role |
|---|---|---|
| Answer a factual question about current state | Read-Only Inquiry | Produce answer and evidence refs |
| Add or revise guidance | Contract Revision Command Skills | None; may explain current guidance only |
| Modify Plan/TaskNode structure or fields | Contract Revision Command Skills | None; may explain current contract only |
| Resolve ASK or confirmation | ASK/confirmation command surfaces | None |
| Start or continue workspace-changing work | Execution handoff / TaskBus | None; may explain current execution status only |

This means Inquiry must not attempt to "helpfully" convert a rejected question
into a mutating request. If the user asks a question whose answer would require
changing product state or workspace files, Inquiry returns `rejected` with the
no-mutation boundary. A separate Router decision can handle a later explicit
change request.

The user-facing goal is low learning cost without hidden side effects: the
input remains conversational, but every branch has a clear owner and observable
result.

---

## 3. Scope Model

Read-Only Inquiry has two scope levels:

1. initial accepted implementation scope, which must be small enough to prove
   the no-mutation boundary;
2. product-complete context scope, which can grow only through accepted read
   providers and explicit evidence refs.

### 3.1 Initial Accepted Implementation Scope

The first implementation should answer bounded questions over data already
available through accepted backend query projections:

- selected Session, Plan, or Task status;
- selected result or file-change summary refs that are already in Main Page
  snapshots;
- explicit Activity item summaries;
- explicit Audit record/detail/evidence summaries through existing Audit
  gateway calls;
- deterministic unsupported or partial responses for refs whose read provider
  is not yet wired.

This slice proves the Router-to-Inquiry handoff, result shape, no-mutation
contract, evidence refs, and Activity projection semantics before broader
workspace context is added.

### 3.2 Product-Complete Context Scope

The product-complete Inquiry capability should support bounded answers over
these accepted read surfaces:

- selected Task, Plan, or Session status;
- selected result or file-change summary;
- workspace git status, changed files, file snippets, and diffs through
  Workspace Inspection;
- Audit snapshot, records, record detail, and evidence descriptors;
- diagnostic summary descriptors already safe for renderer/support display.

The product-complete scope still does not need semantic memory, vector retrieval,
cross-session search, web browsing, or workspace command execution.

---

## 4. No-Mutation Contract

Read-Only Inquiry guarantees:

1. no workspace file writes;
2. no shell commands except accepted read-only providers already behind
   Workspace Inspection, such as controlled git read commands;
3. no Plan, TaskNode, ASK, confirmation, TaskBus, result, or Audit mutation;
4. no hidden guidance recording;
5. no provider prompt, provider payload, raw log, raw SQLite row, raw tool
   argument, secret, or absolute workspace path in renderer-visible output;
6. no durable state writes except optional Activity / Session content records
   that classify the answer as `no_effect`.

If an answer would require mutation or execution, Inquiry returns a rejected or
unsupported result and lets Runtime Input Router choose another route only after
an explicit user input.

---

## 5. Public Contract Shape

Read-Only Inquiry may be exposed only through Runtime Input Router in the first
slice. The internal service contract should still be explicit so Router,
backend tests, and future direct API routes stay aligned.

### 5.1 Request

```ts
type ReadOnlyInquiryRequest = {
  inquiryId: string;
  sessionId: string;
  workspaceId?: string | null;
  question: string;
  scope: {
    kind: "session" | "plan" | "task";
    planId?: string | null;
    taskNodeId?: string | null;
  };
  refs: ReadOnlyInquiryRef[];
  limits?: {
    maxEvidenceItems?: number;
    maxContextBytes?: number;
    maxAnswerChars?: number;
  };
};
```

Rules:

- `question` is user-visible input text, not a prompt transcript.
- `workspaceId` is renderer-safe and opaque.
- `refs` are optional anchors from selection, Activity, Audit, result, file, or
  diagnostic surfaces.
- `limits` are advisory; backend caps remain authoritative.

### 5.2 References

```ts
type ReadOnlyInquiryRef = {
  kind:
    | "task"
    | "plan"
    | "result"
    | "file"
    | "diff"
    | "audit_record"
    | "audit_evidence"
    | "diagnostic"
    | "activity";
  id?: string;
  path?: string;
  evidenceId?: string;
  label: string;
};
```

Rules:

- `path` is workspace-relative when present.
- `label` must be renderer-safe.
- raw absolute paths are not accepted or returned.
- unknown refs are ignored with a warning, not treated as fatal unless no usable
  context remains.

### 5.3 Response

```ts
type ReadOnlyInquiryResult = {
  inquiryId: string;
  sessionId: string;
  scope: {
    kind: "session" | "plan" | "task";
    planId?: string | null;
    taskNodeId?: string | null;
  };
  status: "answered" | "needs_clarification" | "unsupported" | "rejected";
  answer: {
    title?: string | null;
    body: string;
    confidence: "high" | "medium" | "low";
  } | null;
  evidenceRefs: ReadOnlyInquiryEvidenceRef[];
  warnings: ReadOnlyInquiryWarning[];
  activity?: SessionActivityItemView | null;
  generatedAt: string;
};
```

`activity` is a projection item only until durable Router/Session content is
accepted. It must not become the authority for product state.

### 5.3.1 Result State Semantics

Inquiry result state describes answer quality, not product-state success.

| Status | Meaning | User-facing behavior | Router side effect |
|---|---|---|---|
| `answered` | The service found enough safe evidence to answer. | Show answer with evidence refs and any partiality warnings. | `no_effect` |
| `needs_clarification` | The question is valid but cannot be scoped or disambiguated safely. | Ask for a narrower scope or explicit ref. | `no_effect` |
| `unsupported` | The question needs a read provider or answer provider that is not available. | Say the capability is not available yet and preserve safe refs. | `no_effect` |
| `rejected` | The question asks for mutation, unsafe disclosure, or unsupported hidden context. | Explain the boundary and suggest submitting an explicit change request when appropriate. | `no_effect` |

Rules:

- `answered` without evidence refs is allowed only for simple selected
  Session/Plan/Task status answers whose status fact itself is represented as
  an evidence ref.
- `unsupported` is preferable to low-confidence speculation.
- `rejected` must not include a mutating recovery action. A separate Router
  route may handle a future explicit change request.
- `needs_clarification` may include suggested scope choices, but the first
  version should not create a modal ASK or confirmation.

### 5.4 Evidence Ref

```ts
type ReadOnlyInquiryEvidenceRef = {
  kind:
    | "workspace_status"
    | "file_snapshot"
    | "diff_snapshot"
    | "result_summary"
    | "file_change_summary"
    | "audit_record"
    | "audit_evidence"
    | "diagnostic_summary"
    | "activity_item"
    | "session_status"
    | "task_status"
    | "plan_status";
  refId: string;
  parentRefId?: string | null;
  label: string;
  disclosure: "public" | "partial" | "hidden";
  truncated: boolean;
};
```

Evidence refs are safe pointers and summaries. The full evidence owner remains
Workspace Inspection, Audit, diagnostics, result/file stores, or Activity.

`parentRefId` is optional and exists only for evidence that needs a parent
object to produce a stable route. The first accepted use is Audit evidence:
`kind=audit_evidence`, `refId=<evidenceId>`, and
`parentRefId=<auditRecordId>`. The frontend must not infer parent records from
an evidence id alone.

Rules:

- `refId` always identifies the cited evidence object for the evidence kind.
- `parentRefId` must be renderer-safe and opaque when present.
- Missing `parentRefId` downgrades a deep link to the parent surface fallback or
  non-clickable evidence.
- `parentRefId` is not a raw path, log id, provider id, or SQLite row id unless
  the owning route has explicitly accepted that id as renderer-safe.

### 5.4.1 Evidence Ref Versus Activity Ref Links

`ReadOnlyInquiryEvidenceRef` is the canonical answer citation. It does not have
to be clickable.

`SessionActivityRefView` is the UI navigation affordance used by Activity and
Main Page surfaces. It may add an optional `href` only after the backend has
resolved a safe route with:

- opaque `workspaceId`, `sessionId`, `planId`, and `taskNodeId` values;
- workspace-relative paths only;
- known route ownership, such as Workspace Inspection or Audit;
- no raw log, SQLite, provider, or absolute path payload.

Mapping policy:

| Evidence kind | Activity ref kind | Safe href owner | Product-complete status |
|---|---|---|---|
| `file_snapshot` | `file` | Workspace Inspection file view | implemented for safe paths |
| `diff_snapshot` | `diff` | Workspace Inspection diff view | implemented for safe paths |
| `audit_record` | `audit_record` | Audit page focused by `recordId` | implemented |
| `audit_evidence` | `audit_evidence` | Audit page focused by `recordId` and `evidenceId` | implemented for focused route; configured Electron smoke covered |
| `diagnostic_summary` | `diagnostic` | Diagnostic summary/export action or route | support descriptor and Main Page export action implemented; configured Electron smoke covered |
| `result_summary` | `result` | Result/detail surface | partial; depends on result route availability |
| `activity_item` | `activity` | Activity overlay/timeline focus | partial; depends on SAT focus route |

If a safe href cannot be produced, the ref remains visible as non-clickable
evidence. The frontend must not synthesize routes from ids it does not own.

### 5.4.2 Diagnostic Ref Action Boundary

Diagnostic refs are not always navigational links. Some diagnostic affordances
are commands over an accepted API surface, such as redacted diagnostic bundle
export.

Rules:

- a diagnostic summary page or log viewer may use `href` only when the route is
  an accepted safe `GET` route;
- diagnostic bundle export is a side-effecting support action and must be
  invoked through the accepted frontend API client, not by rendering a raw
  `href` to `POST /api/v1/sessions/{sessionId}/diagnostics/export`;
- the Inquiry context builder may describe that an export action is available,
  but it must not export the bundle, read the generated bundle, or expose raw
  diagnostic sections;
- Activity refs may carry a diagnostic ref without `href`; the frontend can
  render a user-facing action button only when the owning surface provides an
  explicit `onOpenDiagnostic` or equivalent action handler;
- if no accepted action handler exists, diagnostic refs remain visible as
  partial, non-clickable evidence.

### 5.5 Warning

```ts
type ReadOnlyInquiryWarning = {
  code:
    | "inquiry.context_empty"
    | "inquiry.context_partial"
    | "inquiry.context_truncated"
    | "inquiry.evidence_hidden"
    | "inquiry.provider_unavailable"
    | "inquiry.unsupported_question"
    | "inquiry.no_mutation_boundary";
  message: string;
  ref?: ReadOnlyInquiryRef | null;
};
```

Warnings are user-safe and may be surfaced in Activity or answer UI.

---

## 6. Backend Components

```text
RuntimeInputRouter
  -> ReadOnlyInquiryService
      -> InquiryScopeResolver
      -> InquiryContextBuilder
      -> InquiryAnswerProvider
      -> InquiryActivityProjector
```

Data flow:

```text
RuntimeInputRouteRequest
  -> RouteDecision(question, no_effect)
  -> ReadOnlyInquiryRequest
  -> bounded InquiryContext
  -> InquiryAnswerProvider
  -> ReadOnlyInquiryResult
  -> RuntimeInputRouteResult(answered / needs_clarification / unsupported / rejected)
```

### 6.1 Protocol Boundary

The service should be wired through narrow protocols so future LLM-backed
answers and richer evidence providers can be added without turning Inquiry into
an agent loop.

```py
class InquiryContextProvider(Protocol):
    def collect(self, request: ReadOnlyInquiryRequest) -> InquiryContext: ...

class InquiryAnswerProvider(Protocol):
    def answer(self, request: ReadOnlyInquiryRequest, context: InquiryContext) -> InquiryAnswer: ...

class InquiryActivityPublisher(Protocol):
    def publish_answered(self, result: ReadOnlyInquiryResult) -> SessionActivityItemView | None: ...
```

Rules:

- providers receive normalized models, not raw HTTP requests or renderer
  payloads;
- answer providers cannot call workspace write APIs, TaskBus, command gateways,
  Plan/TaskNode stores for mutation, or shell execution;
- context providers can call only accepted read gateways;
- activity publishing is best-effort and must not make the user-visible answer
  fail when Activity persistence is unavailable.

Rejected implementation shapes:

- adding a second Router inside Inquiry;
- giving Inquiry an execution AgentLoop;
- passing the raw Main Page snapshot directly into an LLM prompt;
- writing answer context packs as durable hidden product state;
- using frontend ids to infer file paths or Audit destinations without backend
  normalization.

### 6.2 `ReadOnlyInquiryService`

Coordinates the request, enforces no-mutation policy, calls the context builder
and answer provider, then returns `ReadOnlyInquiryResult`.

It must depend on protocols, not concrete HTTP route handlers or frontend
models.

### 6.3 `InquiryScopeResolver`

Normalizes the selected Session/Plan/Task scope from Router state and backend
facts.

It must reject invalid Plan/TaskNode ids and degrade to `needs_clarification`
when the question cannot be scoped safely.

### 6.4 `InquiryContextBuilder`

Builds bounded context from accepted read sources:

| Source | Allowed material |
|---|---|
| Main Page snapshot / PlanView | Session, Plan, Task status, selected title, result/file summary refs |
| Workspace Inspection | git status summaries, changed file metadata, bounded file snippets, bounded diff summaries, inspection evidence refs |
| Audit Gateway | snapshot overview, record summaries, record detail summaries, safe evidence descriptors |
| Diagnostic Bundle descriptors | redacted summary descriptors and section status only |
| Activity Timeline | prior user-visible Activity item summaries and safe refs |

The builder must attach truncation/disclosure metadata to each context item.
It must not read `.plato` through normal file inspection, raw logs, raw
EventStream rows, SQLite files, provider payloads, or hidden Audit payloads.

Internal context items should be normalized before they reach an answer
provider:

```ts
type InquiryContextItem = {
  source:
    | "snapshot"
    | "workspace_inspection"
    | "audit"
    | "diagnostic"
    | "activity"
    | "result"
    | "file_change";
  ref: ReadOnlyInquiryRef | null;
  evidenceRef: ReadOnlyInquiryEvidenceRef;
  title: string;
  summary: string;
  occurredAt?: string | null;
  workspaceRelativePath?: string | null;
  disclosure: "public" | "partial" | "hidden";
  truncated: boolean;
};
```

Rules:

- `summary` is already redacted and renderer-safe.
- `workspaceRelativePath` is optional and never absolute.
- `hidden` context items may contribute counts or warnings, but their summaries
  must not derive from hidden raw payloads.
- Provider prompts, if added later, may include only normalized context items,
  not raw gateway responses.

### 6.5 `InquiryAnswerProvider`

First accepted options:

1. deterministic answer for simple status questions;
2. LLM answer through a read-only profile over bounded context.

The provider output is answer text plus cited evidence refs. It must not return
commands, tool calls, or hidden state changes.

If the provider is unavailable or the context is insufficient, the result
should be `needs_clarification` or `unsupported`, not a fabricated answer.

LLM-backed answer generation is a later slice and must satisfy these gates
before it is enabled:

- prompt input is assembled only from normalized `InquiryContextItem` records;
- every context item carries a safe evidence ref and disclosure flag;
- prompt and provider payloads are not exposed in renderer, Audit, or
  diagnostic bundle output;
- provider output is parsed into answer text, confidence, cited refs, and
  warnings only;
- any requested action, command, file edit, Plan edit, or TaskBus operation in
  provider output is ignored and converted to a `rejected` or
  `needs_clarification` result;
- no streaming partial answer may be shown as final until cited evidence refs
  are attached.

The answer provider should prefer this failure order:

1. deterministic answer when the question matches a known status/progress
   pattern;
2. LLM answer only when enough safe context exists;
3. `needs_clarification` when scope or refs are ambiguous;
4. `unsupported` when the needed provider is not available;
5. `rejected` when answering would violate the no-mutation or disclosure
   boundary.

### 6.5.1 LLM Answer Provider Contract

The LLM-backed provider is a bounded answer renderer, not an agent. It receives
only the normalized context prepared by `InquiryContextBuilder` and returns
only the accepted Inquiry answer model.

Provider input:

```ts
type InquiryAnswerProviderInput = {
  inquiryId: string;
  question: string;
  scope: {
    kind: "session" | "plan" | "task";
    planId?: string | null;
    taskNodeId?: string | null;
  };
  contextItems: InquiryContextItem[];
  evidenceRefs: ReadOnlyInquiryEvidenceRef[];
  limits: {
    maxAnswerChars: number;
    maxCitedRefs: number;
  };
};
```

Provider output:

```ts
type InquiryAnswerProviderOutput = {
  status: "answered" | "needs_clarification" | "unsupported" | "rejected";
  body?: string | null;
  confidence?: "high" | "medium" | "low" | null;
  citedRefIds: string[];
  warnings: ReadOnlyInquiryWarning[];
};
```

Rules:

- `contextItems` are already redacted; the provider must not receive raw Main
  Page snapshots, raw Audit payloads, raw logs, raw provider messages, raw
  SQLite rows, secrets, or absolute workspace paths.
- The provider has no tools. It must not receive shell, file, TaskBus,
  Plan/TaskNode, ASK, confirmation, web, or MCP tool access.
- The provider cannot introduce new evidence. `citedRefIds` must be a subset of
  the supplied `evidenceRefs`.
- `answered` requires at least one cited evidence ref unless the deterministic
  fallback has already created a selected Session/Plan/Task status evidence ref.
- Output is parsed and validated before display. Invalid JSON, unknown statuses,
  unknown cited refs, action requests, file-edit proposals, command text, or
  hidden-context references are discarded and converted to deterministic
  fallback, `unsupported`, or `rejected`.
- Provider prompts, raw completions, token payloads, and provider errors are
  never renderer-visible and are not included in diagnostic bundles. Diagnostics
  may expose only provider kind, safe error category, warning codes, evidence
  counts, and truncation flags.

The first implementation should wire the provider behind an explicit service
dependency. Product runtime may leave it disabled until the no-mutation and
redaction acceptance suite covers LLM-backed answers in the desktop shell.

### 6.6 `InquiryActivityProjector`

Projects a safe `answer` Activity item:

- kind: `answer`;
- sideEffect: `no_effect`;
- scope: Session, Plan, or Task;
- related refs: evidence refs and original route decision ref when available;
- disclosure: `public` or `partial`.

The foundation persists answered read-only questions as safe informational
MessageStream rows so they can replay as `answer/no_effect` Activity items.
That replay preserves the safe Activity evidence refs attached to the answer.
Diagnostic bundle export refs now have a Main Page Activity action that calls
the accepted redacted export API instead of rendering the `POST` endpoint as a
link. Configured Electron smoke covers the durable read-only answer Activity
replay path, diagnostic export action, and Audit evidence focus over the
`recordId + evidenceId` route contract. Broader Router Activity / Conversation persistence for
unsupported, clarification, guidance, command, and execution-handoff outcomes
remains owned by the Runtime Input Router / Session content slices.

---

## 7. Context Assembly Policy

Context is layered and ordered. Inquiry must not merge sources in a way that
obscures which layer supplied an answer.

| Priority | Layer | Purpose |
|---:|---|---|
| 1 | Current selection | Answer the user's visible Session/Plan/Task/file/Audit focus first. |
| 2 | Explicit refs | Follow refs attached by Router, Activity, Audit, result, file, or diagnostic surfaces. |
| 3 | Snapshot summary | Use safe Main Page PlanView/Task/result/file summaries for status and progress. |
| 4 | Evidence owner reads | Resolve bounded details from Audit, Workspace Inspection, diagnostics, or result stores. |
| 5 | Recent Activity | Add user-visible prior context only when directly relevant or explicitly selected. |

If layers disagree, Inquiry must say which source it used and cite its evidence
refs. It must not silently reconcile conflicting facts or promote projected
Activity over canonical Plan/TaskNode/Audit facts.

Default Product 1.1 limits:

| Limit | Default |
|---|---:|
| Evidence items | 12 |
| Context bytes | 64 KiB |
| File snippet lines per file | 80 |
| Diff hunks per file | 8 |
| Audit records | 20 |
| Activity items | 20 |
| Answer length | 4000 chars |

Rules:

- Prefer selected refs over broad session context.
- Prefer summaries and evidence refs over raw payloads.
- Include enough provenance for the user to inspect the source surface.
- Mark partial answers when evidence is truncated, hidden, or unavailable.
- Never expand context by scanning the entire workspace in ROI-1/ROI-2.

### 7.1 Path And Redaction Policy

Inquiry inherits the Product 1.0 renderer-safety boundary:

- renderer-visible paths are workspace-relative only;
- absolute paths, home directory paths, `.plato` internals, SQLite file names,
  provider payload paths, and raw log paths are hidden or replaced with safe
  labels;
- file refs must be normalized through the same path policy used by Workspace
  Inspection and Audit evidence links;
- secrets, API keys, environment values, provider prompts, raw completions, raw
  tool arguments, and raw exception objects are never included in answer text,
  warnings, Activity, diagnostics, or JSON fixtures;
- hidden evidence can be counted and labeled as hidden, but not summarized from
  its raw payload.

---

## 8. Runtime Input Router Integration

RIR question route should dispatch to Inquiry only when:

- Router intent is `question`;
- sideEffect is `no_effect`;
- selected scope is valid;
- question is within accepted size limits;
- no active ASK/confirmation answer shape has higher priority.

Router maps `ReadOnlyInquiryResult` back to `RuntimeInputRouteResult`:

| Inquiry status | Router outcome |
|---|---|
| `answered` | `answered` |
| `needs_clarification` | `needs_clarification` |
| `unsupported` | `unsupported` |
| `rejected` | `rejected` |

Router decision remains the interpretation record. Inquiry result owns the
answer text and evidence refs.

Router request refs are split by responsibility:

- `selection.refs` remains the generic object-ref surface used by the Router to
  understand selected product objects such as messages, tasks, plans, asks, and
  confirmations.
- `inquiryRefs` carries already-normalized `ReadOnlyInquiryRef` anchors that
  should be passed directly to Inquiry when the route is
  `question/no_effect/read_only_inquiry`.
- Router may translate safe `selection.refs` into Inquiry refs, but it must
  merge them with `inquiryRefs` instead of replacing explicit anchors.
- `inquiryRefs` must be ignored for mutating routes. They cannot authorize
  guidance, Plan/TaskNode changes, TaskBus work, or workspace writes.

The workspace-scoped Runtime Input route also injects the opaque path
`workspaceId` into the validated Router request. If the body contains a
different `workspaceId`, the backend rejects the request instead of generating
links against the wrong workspace.

Router must not retry an Inquiry result through a mutating route automatically.
For example, when a user asks "can you update this task?", the first route may
be rejected as a question that requests mutation. The next mutating route must
come from a separate explicit user input or accepted UI action.

### 8.1 Boundary With Contract Revision Skills

Inquiry can explain current contract state. It cannot revise contract state.

| User need | Owner |
|---|---|
| "What is this task doing?" | Read-Only Inquiry |
| "Why did this task fail?" | Read-Only Inquiry over Audit/result refs |
| "Add this requirement to Task 2." | Contract Revision Command Skills |
| "Split this task into two tasks." | Contract Revision Command Skills |
| "Run the next task." | Execution request / TaskBus handoff |

This separation keeps answer-only UX natural while preserving explicit control
over product-state and workspace-state changes.

---

## 9. Frontend Integration

The first frontend slice is intentionally minimal:

- Main Page still has one input surface.
- `Ask` override can force `mode=ask` through Router.
- Answer appears as a transient Main Page Activity item and notice, not as a
  new primary page.
- Evidence refs link to existing surfaces when available:
  - file/diff viewer;
  - Audit record/detail/evidence;
  - result/file summary;
  - diagnostic export or summary where accepted.
- Unsupported/clarification states must be visibly non-mutating.

Answered-question Activity replay is available through the existing typed
Activity query. Broader Router Conversation / Activity replay for non-answer
outcomes remains a later Router/SAT slice. The transient item is allowed to make
the answer visible immediately, but it must not become canonical product state.

### 9.1 Frontend State Model

The Main Page should treat Inquiry as an answer overlay on top of the work
surface, not as a separate chat mode.

```text
idle
  -> routing_question
      -> answered
      -> needs_clarification
      -> unsupported
      -> rejected
      -> error
```

State rules:

- `routing_question`: input submission is pending; do not optimistically record
  guidance or append a mutating message.
- `answered`: show the answer as a notice and latest Activity item; keep the
  selected Plan/Task unchanged.
- `needs_clarification`: keep focus in the input and show a non-mutating
  clarification message.
- `unsupported`: show a recovery note without trying another route
  automatically.
- `rejected`: explain the boundary and leave the user's selection unchanged.
- `error`: use the Product Error taxonomy where possible; do not expose raw
  backend exceptions.

Selection rules:

- opening an evidence link may navigate to file/diff/Audit surfaces;
- closing the evidence surface should preserve the previous workspace, session,
  and task selection when route params provide them;
- opening Activity overlay should not change selected Task unless the user
  explicitly activates a Task/Plan ref.

Persistence rules:

- immediately returned Activity may be transient;
- durable replay comes from Session Activity query;
- if transient and durable copies exist for the same route id, frontend should
  de-duplicate by stable Activity id.

### 9.2 Evidence Link Action Policy

Evidence links are inspection affordances only. They must not mutate product
state or workspace state.

| Ref kind | Preferred UI action | Fallback |
|---|---|---|
| `plan` | select Plan overview in Main Page | show non-clickable evidence label |
| `task` | select Task detail in Main Page | show non-clickable evidence label |
| `result` | open existing result/detail surface for the selected Task | show result summary only |
| `file` | open Workspace Inspection file view with workspace-relative path | show file summary only |
| `diff` | open Workspace Inspection diff view with workspace-relative path | show diff summary only |
| `audit_record` | open Audit page focused on record id | open Audit page at scope |
| `audit_evidence` | open Audit page with `recordId` plus `evidenceId` focus when both ids are present | open parent Audit record or show non-clickable evidence |
| `diagnostic` | open accepted diagnostic summary route or invoke accepted diagnostic action | show diagnostic summary only |
| `activity` | focus Activity item in overlay/timeline | show Activity summary only |

If a ref cannot be resolved safely, the UI should show it as partial evidence
with no action rather than guessing a destination.

Do not add a chat-first transcript UI in this slice.

### 9.3 Diagnostic Action UX Boundary

Diagnostic inquiry evidence should not create a second diagnostics UI. It should
reuse the existing Settings/Main Page diagnostic affordances when those
affordances have an accepted owner.

Frontend behavior:

- if a diagnostic ref has a safe `href`, render it as a normal inspection link;
- if a diagnostic ref has no `href` but matches a supported diagnostic action,
  render a button that calls the owning action handler;
- for diagnostic bundle export, the action handler must call the existing
  diagnostic export API and display the same success/error copy used by the
  Settings diagnostics flow;
- the Activity overlay should not treat a diagnostic export action as route
  navigation, because the export endpoint is `POST`;
- if the diagnostic action fails, show Product Error taxonomy output where
  available and do not expose raw exception, log, provider, prompt, or SQLite
  payloads.

This keeps Inquiry answer evidence inspectable while preserving the Product 1.0
diagnostic bundle redaction boundary.

---

## 10. Audit And Diagnostic Semantics

Inquiry answers are user-facing explanations, not Audit verdicts.

Audit can reference Inquiry decisions later, but the first Inquiry slice should:

- expose safe evidence refs only;
- not persist raw context packs;
- not include provider prompt or answer-generation payloads in diagnostics;
- include redacted diagnostic descriptors such as inquiry id, status, scope,
  evidence ref counts, warning codes, and truncation flags.

If an answer cites Audit evidence, the cited Audit record remains the authority.

### 10.1 Diagnostic Payload Boundary

Diagnostics may include:

- inquiry id, route decision id, session id, opaque workspace id, and safe scope;
- status, warning codes, confidence, evidence ref counts, and truncation flags;
- provider unavailable/error category if an answer provider was attempted.

Diagnostics must not include:

- question-expanded prompt text beyond the original user-visible question;
- hidden context packs;
- raw Audit/EventStream/log/provider/SQLite payloads;
- absolute workspace paths;
- secret values or environment-derived credential hints.

### 10.2 Support Descriptor Contract

Product-complete diagnostics should expose a compact descriptor that helps
support understand whether an answer was complete without reconstructing the
hidden context.

The foundation implements the first read-only support descriptor for the
accepted diagnostic bundle export action. It advertises the safe export action
and redaction boundary, but it does not call the export endpoint and does not
read bundle files.

Current foundation shape:

```ts
type DiagnosticSupportDescriptor = {
  refId: string;
  label: string;
  summary: string;
  disclosure: "public" | "partial" | "hidden";
  truncated: boolean;
};
```

The descriptor summary may name the accepted support action, but it is not an
imperative instruction and is not an export result. The descriptor itself
remains evidence. When the descriptor is carried by a diagnostic Activity ref
and the owning frontend surface has an accepted action handler, the surface may
render a user action such as redacted bundle export; otherwise it stays
non-clickable evidence.

Product-complete target shape:

```ts
type ReadOnlyInquiryDiagnosticDescriptor = {
  inquiryId: string;
  routeDecisionId?: string | null;
  sessionId: string;
  workspaceId?: string | null;
  scopeKind: "session" | "plan" | "task";
  planId?: string | null;
  taskNodeId?: string | null;
  status: "answered" | "needs_clarification" | "unsupported" | "rejected";
  confidence?: "high" | "medium" | "low" | null;
  evidenceRefCount: number;
  hiddenEvidenceCount: number;
  truncatedEvidenceCount: number;
  warningCodes: string[];
  providerKind: "deterministic" | "llm" | "unavailable";
  availableActions: ReadOnlyInquiryDiagnosticAction[];
  generatedAt: string;
};

type ReadOnlyInquiryDiagnosticAction = {
  id: string;
  kind: "export_redacted_bundle" | "open_summary" | "open_logs";
  label: string;
  method: "GET" | "POST";
  routeOwner: "settings" | "diagnostics" | "audit";
  href?: string | null;
};
```

Descriptor rules:

- the original user-visible question may be referenced by existing Session
  content id, but should not be duplicated into diagnostic bundles unless the
  Session content redaction policy explicitly allows it;
- actions with `method=POST` must not be rendered as raw links;
- `href` is allowed only for accepted safe `GET` routes;
- warning codes are safe; raw exception messages are not safe by default;
- provider errors are classified by product error category, not by raw provider
  payload;
- descriptor ids are support breadcrumbs and must not become a second evidence
  store.

### 10.3 Audit Linkage

Audit linkage for Inquiry has two separate meanings:

1. cited Audit evidence, where Inquiry points to existing Audit records or
   evidence and Audit remains the authority;
2. future Router/Audit traceability, where Audit can explain that a user input
   was routed to a no-effect answer.

The first is in scope for ROI evidence refs. The second is owned by the
Runtime Input Router / Audit linkage closure and should not be implemented by
Inquiry directly.

### 10.4 Audit Evidence Deep-Link Contract

Audit evidence links require two ids:

- `recordId`: the Audit record that owns the evidence descriptor;
- `evidenceId`: the evidence descriptor id within that record.

The backend must resolve this pair through the Audit query gateway before it
adds an href to an Inquiry Activity ref. The renderer must not derive
`recordId` by scanning timeline rows or guessing from `evidenceId`.

Accepted route shape:

```text
/sessions/{sessionId}/audit
  ?entry=from_session|from_task
  &recordId={auditRecordId}
  &evidenceId={auditEvidenceId}
  &returnFocus=session|task|file_change|...
  &returnSessionId={sessionId}
  &returnTaskNodeId={taskNodeId?}
  &workspaceId={workspaceId?}
```

Frontend behavior:

- parse `evidenceId` as route state, not global app state;
- select `recordId` first, then select or load the matching evidence detail;
- if `evidenceId` is missing or not found under the selected record, keep the
  record detail visible and mark the evidence focus as unavailable;
- selecting a different timeline row should clear `evidenceId` so the UI does
  not preserve a stale evidence focus;
- clicking a timeline row must not reset the timeline scroll position before
  the selected detail renders.

Fallback behavior:

- if only `recordId` is available, open the parent Audit record;
- if only `evidenceId` is available, show non-clickable partial evidence
  instead of attempting a route;
- if the Audit gateway cannot resolve the pair, return a partial evidence ref
  without href and add an `inquiry.context_partial` warning.

---

## 11. Failure Semantics

| Case | Result status | Required behavior |
|---|---|---|
| Empty or invalid scope | `needs_clarification` or `rejected` | Explain that the question cannot be safely scoped. Do not infer a different Task. |
| Context source unavailable | `unsupported` or `needs_clarification` | Return a safe warning and no answer if evidence is insufficient. |
| Hidden or redacted evidence | `answered` with warning, or `unsupported` | Do not reveal hidden evidence. Make partiality explicit. |
| Question asks Plato to change Plan/Task/workspace | `rejected` | Keep `sideEffect=no_effect` and recommend the user submit an explicit change request. |
| Provider unavailable | `unsupported` or deterministic fallback | Never fabricate an answer. |
| Context truncated | `answered` with low/medium confidence or warning | Cite only included evidence refs and mark truncation. |

Unsupported and rejected Inquiry results remain no-mutation outcomes. Router may
show recovery guidance, but it must not automatically re-route the same input
into a mutating path.

---

## 12. Tests

ROI-1/ROI-2 contract and context tests:

- request/response JSON fixture round-trip;
- invalid scope rejection;
- unknown refs produce warnings;
- bounded context truncation metadata;
- hidden Audit evidence remains hidden;
- absolute workspace paths are redacted or rejected;
- `.plato` is not readable through Inquiry context.

ROI-3 answer provider tests:

- deterministic status answer with evidence refs;
- provider unavailable returns `unsupported` or `needs_clarification`;
- answer without evidence is low confidence or rejected;
- raw prompt/provider payload is not exposed.

No-mutation tests:

- Plan/TaskNode rows unchanged;
- TaskBus state unchanged;
- ASK/confirmation stores unchanged;
- workspace files unchanged;
- result/Audit source facts unchanged.

Integration tests:

- Router question route returns `answered` when Inquiry succeeds;
- Router question route remains `unsupported` when Inquiry is unavailable;
- Activity item uses `sideEffect=no_effect`;
- frontend displays answer and evidence refs without enabling mutation actions.

### 12.1 No-Mutation Verification Matrix

No-mutation is the central acceptance property. Each implementation slice should
prove the boundary at the narrowest layer it touches.

| Layer | Must remain unchanged | Suggested check |
|---|---|---|
| Workspace files | user files and `.plato` protected internals | snapshot file tree/hash before and after read-only route |
| Plan/TaskNode | title, body, status, lifecycle, active Plan identity | query durable Plan/TaskNode rows before and after |
| Legacy TaskBus | claim/complete/fail state, task execution queue | query TaskBus/task stores before and after |
| ASK/confirmation | active pending ids and resolution state | query projection before and after |
| Result/Audit | source records and evidence payloads | query counts/ids before and after |
| Message/Activity | allowed only for explicit answer Activity persistence | assert records are typed `answer/no_effect` and contain safe refs only |

The only permitted durable write in the foundation is the safe informational
answer record used for Activity replay. That write must be:

- scoped to the current session;
- classified as answer/no-effect;
- free of raw prompts, provider payloads, hidden evidence, absolute paths, and
  secrets;
- idempotent or de-duplicated by Router/inquiry identity where possible.

### 12.2 Sidecar/Electron Acceptance

The foundation now has a formal real sidecar acceptance pass for the
workspace-scoped Runtime Input route. It uses seeded sidecar data and explicit
`inquiryRefs` to exercise the same backend route that the renderer uses.

Implemented sidecar coverage:

- selected session and task context;
- workspace-scoped `POST /api/v1/workspaces/{workspaceId}/sessions/{sessionId}/runtime-input/route`;
- explicit file and diff refs for a workspace-relative file;
- explicit Audit record and Audit evidence refs, including `recordId` plus
  `evidenceId` focused href preservation;
- explicit result ref for the safe result summary in the Main Page snapshot;
- explicit diagnostic support ref for the accepted diagnostic bundle export
  action;
- LLM-rendered read-only answer path through
  `enable_read_only_inquiry_llm`;
- durable answered-question Activity replay;
- no user file mutation and no TaskBus/task snapshot mutation;
- no absolute workspace path disclosure in answer text or LLM prompt input.

The broader Electron acceptance pass should use a seeded workspace with:

- a selected session and task;
- at least one result summary;
- one changed workspace file;
- one diff-capable git repository;
- one Audit record and one Audit evidence descriptor;
- one diagnostic descriptor or export capability when accepted.

Required acceptance observations:

- status/progress question answers without mutation;
- file snippet question opens or cites Workspace Inspection file evidence;
- diff question opens or cites Workspace Inspection diff evidence;
- Audit question opens or cites Audit record/evidence without exposing raw
  payload, and evidence links preserve `recordId + evidenceId` focus when the
  pair is available;
- diagnostic support question cites the accepted support descriptor without
  exporting a bundle or reading raw diagnostic artifacts;
- app reload preserves durable answered-question Activity refs.

Audit evidence precise focus is covered by the real sidecar acceptance suite
for generated Activity refs and durable Activity replay, and by configured
Electron smoke for the desktop shell route/action behavior.

The guarded LLM-rendered path is covered by seeded desktop commands:

```bash
npm run electron:smoke:read-only-inquiry-llm
npm run electron:smoke:packaged-read-only-inquiry-llm
```

These commands use the same configured seeded sidecar fixture as the default
Electron smoke, enable the fixture's guarded LLM provider, and assert the
Activity replay displays the provider-rendered answer while retaining
diagnostic export and Audit evidence actions. The packaged command builds an
unsigned local app directory with smoke files and runs the same acceptance path
without Vite.

Launcher-backed no-mutation acceptance is covered by
`npm run electron:smoke:launcher`. Signed installer no-mutation acceptance
remains optional release hardening if Product 1.1 wants coverage beyond dev
shell, unsigned package-dir runtime, and launcher-backed local runtime.

---

## 13. Implementation Slices

### ROI-1. Contract And Fixtures

Status: implemented for backend/frontend transport foundation; partial and
rejected fixtures can still be added when UI display needs them.

- Add backend/frontend models for `ReadOnlyInquiryRequest`,
  `ReadOnlyInquiryResult`, evidence refs, and warnings.
- Add JSON fixtures for answered, partial, unsupported, and rejected results.
- Do not expose a direct public endpoint unless Router integration needs it.

### ROI-2. Context Builder

Status: implemented for accepted read providers.

- Implemented: scope resolution plus Main Page snapshot, Activity, Audit
  explicit-ref summaries, Workspace Inspection file snippets, Workspace
  Inspection diff summaries, safe Main Page planning diagnostic descriptors,
  and a safe diagnostic bundle support descriptor for the accepted export
  action.
- Follow-up: richer exported bundle section summaries can be added after a
  separate read-only descriptor contract is accepted by support needs.
- Add truncation/disclosure metadata.
- Add no raw path/log/provider/SQLite payload tests.

### ROI-3. Answer Provider

Status: deterministic backend foundation implemented; guarded LLM provider seam
and default sidecar runtime wiring implemented with explicit disable controls.

- Add deterministic status answer path first.
- Implemented: add guarded read-only LLM profile over safe answer/evidence
  context with citation validation, no-tool calls, provider-unavailable
  fallback, and mutation-output rejection tests.
- Implemented: default sidecar runtime wiring through
  `enable_read_only_inquiry_llm`; operators can set
  `PLATO_ENABLE_READ_ONLY_INQUIRY_LLM=0` or pass
  `--disable-read-only-inquiry-llm` to force deterministic answers.
- Return answer plus evidence refs.

### ROI-4. Router And Activity Integration

Status: implemented for Router result mapping and projected answer Activity;
answered-question durable Activity persistence with safe evidence refs is
implemented through the workspace MessageStream.

- Wire RIR question route to `ReadOnlyInquiryService`.
- Map Inquiry result to Router outcome.
- Return or persist `answer` Activity projection with `no_effect`.
- Persist answered read-only questions as safe informational MessageStream rows
  that project back to `answer/no_effect` Activity with Router identity.
- Preserve the answer Activity's safe related refs through durable replay.
- Keep broader Router session-content persistence for non-answer outcomes as a
  separate SAT/RIR slice.

### ROI-5. Frontend Acceptance

Status: minimal Main Page question route, transient Activity display, durable
answered-question Activity replay, safe evidence ref preservation, file/diff
Workspace Inspection hrefs, Audit record hrefs, Audit evidence
`recordId + evidenceId` focused route wiring, and Activity overlay actions are
implemented; workspace-scoped Runtime Input routes pass opaque `workspaceId`
into Inquiry for safe href generation; real sidecar acceptance covers explicit
file/diff/Audit record/Audit evidence/result/diagnostic refs. Main Page
diagnostic export action wiring is implemented for diagnostic Activity refs.
Configured Electron smoke covers durable Activity replay, diagnostic export
action, and Audit evidence focus. `npm run
electron:smoke:read-only-inquiry-llm` and `npm run
electron:smoke:packaged-read-only-inquiry-llm` cover the guarded LLM
answer path in the dev shell and unsigned package-dir runtime. `npm run
electron:smoke:launcher` covers the launcher-backed local runtime with
provider-independent read-only inquiry fallback.

- Main Page can ask a question about selected Task/file/Audit/result context.
- Answer is visible through the existing Main Page notice path and transient
  Activity strip/overlay projection.
- Existing Activity overlay actions can open Plan, Task, result, file, diff,
  Audit record refs, and Audit evidence refs when a safe route is available;
  diagnostic bundle export refs invoke the existing redacted export API when
  the Main Page adapter exposes it.
- Follow-up: result/detail deep links can be added if direct result focus
  becomes necessary.
- Unsupported/clarification states are non-mutating and localized.
- Sidecar acceptance proves no-mutation on seeded real workspace data.
- Signed installer acceptance can still prove the no-mutation boundary for
  distribution-style runtime if Product 1.1 requires that before release
  hardening.

### ROI-6. LLM Answer Provider

Status: backend provider foundation, default sidecar wiring with deterministic
fallback controls, and formal real sidecar no-mutation acceptance implemented.

- Implemented: add a guarded read-only LLM provider profile over safe
  answer/evidence context.
- Implemented: parse output into the accepted answer/result model only.
- Implemented: reject provider-suggested actions or hidden state changes and
  fall back to the deterministic answer.
- Implemented: provider unavailable, invalid citation, non-answer status, home
  path redaction, no-tool call, and mutation-output rejection tests.
- Implemented: formal real sidecar no-mutation acceptance path for
  LLM-rendered read-only answers.
- Implemented: Electron smoke command for the configured seeded sidecar
  LLM-rendered answer path.
- Implemented: packaged Electron smoke command for the configured
  seeded sidecar LLM-rendered answer path without Vite.
- Implemented: default sidecar enablement with
  `PLATO_ENABLE_READ_ONLY_INQUIRY_LLM=0` and
  `--disable-read-only-inquiry-llm` fallback controls.

### ROI-7. Diagnostic And Audit Deep-Link Closure

Status: implemented for Main Page diagnostic export actions and configured
Electron smoke acceptance.

- Define diagnostic summary/export route and action ownership for Inquiry refs.
- Treat diagnostic bundle export as an action over the existing diagnostics API,
  not as a GET link.
- Use the accepted Audit evidence focus contract:
  `recordId=<auditRecordId>&evidenceId=<auditEvidenceId>`.
- Implemented: backend link generation includes `evidenceId` only when it has
  resolved the parent `recordId`.
- Implemented: frontend Audit route parsing treats `evidenceId` as detail focus
  state under the selected `recordId`, not as a timeline filter.
- Implemented: real sidecar acceptance verifies generated Activity refs and
  durable Activity replay preserve `recordId + evidenceId`.
- Keep non-resolvable refs visible as partial, non-clickable evidence.
- Implemented: Main Page/Activity overlay wiring invokes the existing redacted
  diagnostic export API for supported diagnostic refs and displays safe
  success/error feedback without raw diagnostic payload disclosure.
- Add frontend acceptance that links preserve previous workspace/session/task
  return context.

---

## 14. Acceptance Criteria For Foundation Closure

The implementation foundation is considered complete when these checks remain
true:

Minimum first implementation:

1. contract models and fixtures;
2. bounded context builder over existing read surfaces;
3. deterministic status answer path or explicit provider-unavailable result;
4. Router question-route integration;
5. no-mutation tests for product stores, TaskBus, and workspace files.

Do not start LLM answer generation before the context builder and no-mutation
tests are in place.

Local runtime closure is accepted for Read-Only Inquiry. Broader Router
Activity/Conversation writes for non-answer outcomes are owned by the Runtime
Input Router / Session Activity program. Optional richer diagnostic bundle
section descriptors, localization polish, signed installer no-mutation
hardening, and direct result/detail deep links remain follow-ups because safe
diagnostic actions and result refs are already preserved in Activity.

---

## 15. Open Questions

These are deferred and should not block ROI-1/ROI-2.

1. Whether a direct Inquiry API endpoint is useful after Router integration is
   stable.
2. Whether LLM-backed answers should be a separate provider profile or reuse the
   existing LLM setup with stricter prompt/output guards.
3. How much of the answer history should be durable Session content versus
   projected Activity after the Conversation model matures.
4. Whether broad cross-session or cross-workspace search belongs to Inquiry or a
   later workspace knowledge feature.

---

## 16. Non-Goals

- No workspace writes.
- No shell execution outside accepted read-only inspection providers.
- No vector store or semantic memory.
- No full chat transcript UI.
- No hidden guidance recording.
- No Plan/TaskNode mutation.
- No ASK or confirmation resolution.
- No broad cross-workspace search.
