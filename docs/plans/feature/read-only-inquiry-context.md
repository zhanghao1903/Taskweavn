# Feature Plan: Read-Only Inquiry Context

> Status: accepted for Product 1.1 local runtime
>
> Last Updated: 2026-06-14
>
> Owner: Product / Context / Backend / Frontend
>
> Related:
> [Plato Runtime Input Model](../../product/plato-runtime-input-model.md),
> [Plato Session Content Model](../../product/plato-session-content-model.md),
> [ADR-0017 Session And Workspace Context Management Foundation](../../decisions/ADR-0017-session-and-workspace-context-management-foundation.md),
> [Runtime Input Router Contract](runtime-input-router-contract.md),
> [Read-Only Inquiry Context Technical Design](read-only-inquiry-context-technical-design.md)

---

## 1. Gap

Users need to ask questions about files, diffs, results, audit records, errors,
and current progress without creating or changing work.

Current system now has a dedicated backend Read-Only Inquiry foundation for
status/progress questions, explicit Activity/Audit refs, and Workspace
Inspection file/diff refs. Main Page can route read-only questions through
Runtime Input Router and show the no-effect answer as both a notice and
transient Activity strip/overlay item, while answered read-only questions are
also persisted through the workspace MessageStream for durable Activity replay
with safe evidence refs.
Safe planning diagnostic descriptors are available through explicit diagnostic
refs, and a read-only diagnostic support descriptor can explain the accepted
redacted bundle export action without triggering export. Main Page Activity can
now invoke the accepted redacted diagnostic export action from diagnostic refs
without rendering the `POST` endpoint as an href. A real sidecar no-mutation
acceptance path now covers workspace-scoped file, diff, Audit record, Audit
evidence, result, diagnostic, and Activity replay refs. Audit evidence
`recordId + evidenceId` deep-link wiring is implemented with focused
backend/frontend tests, real sidecar acceptance, and configured Electron smoke.
Configured Electron smoke also covers durable read-only answer Activity replay
and the Activity diagnostic export action against real sidecar data.
The guarded LLM answer provider module, service injection seam, and default
sidecar runtime wiring are now implemented with citation validation, no-tool
calls, provider-unavailable fallback, mutation-output rejection tests, explicit
disable controls, and a formal real sidecar no-mutation acceptance test.
Electron smoke commands exercise the guarded LLM-rendered answer path in the
dev shell and packaged app directory. Launcher-backed smoke keeps the runtime
provider-independent while covering the same no-mutation
Activity/Audit/diagnostic path through the release-local sidecar launcher.

Read-Only Inquiry is accepted for the Product 1.1 local runtime. Broader Router
Conversation persistence for non-answer outcomes belongs to the Runtime Input
Router / Session Activity program. Richer diagnostic descriptors, direct
result/detail deep links, localization polish, and signed installer
distribution hardening remain non-blocking follow-ups.

---

## 2. Target

Read-only inquiry answers questions with evidence refs and no side effects.

Allowed reads:

- selected file snippets;
- diff summaries;
- result summaries;
- audit records and evidence descriptors;
- diagnostic summaries;
- task/session status;
- safe workspace inspection data.

Forbidden:

- workspace writes;
- shell commands with side effects;
- Plan or TaskNode mutation;
- TaskBus claim/complete/fail;
- hidden context promotion;
- raw prompt/provider/log payload exposure.

---

## 3. Implementation Slices

### ROI-1. Inquiry Contract

Status: implemented backend/frontend transport foundation.

- Define inquiry request/response shape.
- Define answer provenance refs.
- Define no-mutation guarantee and test contract.

### ROI-2. Inquiry Context Builder

Status: implemented for accepted read providers.

- Build bounded context from selected refs.
- Reuse Main Page snapshot status/result/file-summary facts.
- Reuse Activity, Audit record, and Audit evidence refs when explicitly
  provided.
- Reuse Workspace Inspection file snippets and diff summaries when explicitly
  provided as refs.
- Reuse safe Main Page planning diagnostic descriptors when explicitly
  provided as diagnostic refs.
- Reuse safe diagnostic bundle support descriptors when explicitly provided as
  diagnostic refs, without exporting a bundle or reading raw diagnostics.
- Follow-up: richer exported bundle section summaries can be added after a
  separate read-only descriptor contract is accepted by support needs.
- Include disclosure and truncation metadata.

### ROI-3. Answer Provider

Status: deterministic backend path implemented; guarded LLM provider seam and
default sidecar runtime wiring implemented with explicit disable controls;
formal sidecar no-mutation acceptance covered.

- Add deterministic status answer path.
- Implemented: read-only LLM/profile provider seam over safe answer/evidence
  context, with citation validation and no-tool calls.
- Implemented: default sidecar runtime wiring through
  `enable_read_only_inquiry_llm`; use
  `PLATO_ENABLE_READ_ONLY_INQUIRY_LLM=0` or
  `--disable-read-only-inquiry-llm` to force deterministic answers.
- Return answer plus evidence refs.
- Record Activity item as `Answer only`.

### ROI-4. Frontend Entry

Status: implemented for Main Page question route, transient Activity display, and
durable answered-question Activity replay with safe evidence refs implemented;
file/diff/audit safe hrefs implemented when workspace route context is
available; explicit result refs implemented; diagnostic support descriptor
implemented; Audit evidence precise focus wiring is implemented with focused
tests and real sidecar acceptance; diagnostic export action wiring is
implemented for Activity refs; configured Electron smoke covers durable
Activity replay, diagnostic export action, and Audit evidence focus.

- Route `Ask` / read-only question through Runtime Input Router.
- Display answer in transient Main Page Activity / notice surfaces.
- Persist answered read-only questions into the existing workspace
  MessageStream so Session Activity query can replay them.
- Preserve answer evidence refs through durable Activity projection.
- Preserve file/diff/audit safe hrefs when route context is available through
  workspace-scoped Runtime Input routing.
- Preserve result refs and diagnostic support refs; diagnostic bundle export
  refs can invoke the existing redacted export API through Activity actions.
- Follow-up: broader Router Conversation persistence for non-answer outcomes is
  owned by RIR/SAT; optional result/detail deep links can be added if direct
  result focus becomes necessary.

### ROI-5. No-Mutation Tests

Status: focused backend contract tests plus real sidecar no-mutation
acceptance implemented; configured Electron smoke covers diagnostic action and
Audit evidence focus; Electron smoke covers the guarded LLM-rendered
answer path with `npm run electron:smoke:read-only-inquiry-llm` and
`npm run electron:smoke:packaged-read-only-inquiry-llm`; launcher smoke covers
release-local no-mutation through the bundled sidecar launcher.

- Verify inquiry does not write workspace files.
- Verify inquiry does not mutate Plan, TaskNode, ASK, confirmation, or TaskBus.
- Verify Main Page read-only question submission does not call legacy
  append/generate mutating input commands.
- Verify workspace-scoped sidecar route preserves safe file/diff/Audit hrefs,
  result refs, diagnostic support refs, and durable `answer/no_effect`
  Activity replay without mutating seeded workspace or TaskBus snapshots.
- Verify launcher-backed packaged smoke keeps the path provider-independent and
  preserves the same Activity/Audit/diagnostic behavior.

---

## 4. Non-Goals

- No semantic memory.
- No vector retrieval.
- No autonomous research workflow.
- No file edits.
- No hidden guidance recording.
