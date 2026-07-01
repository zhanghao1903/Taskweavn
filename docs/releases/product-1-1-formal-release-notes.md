# Plato Product 1.1 Formal Release Notes

> Status: release candidate verified for public `v1.1`
>
> Last Updated: 2026-07-01
>
> Audience: public release readers, reviewers, and release operators
>
> Prior public baseline: Product 1.0 public baseline / `0.1.0`
>
> Beta predecessor: [Product 1.1 Beta External Release Notes](product-1-1-beta-external-release-notes.md)

## Summary

Plato Product 1.1 is the first formal public release of the Product 1.1
collaboration model. It moves the public release channel beyond the Product 1.0
task-first baseline and makes the Conversation, Runtime Input Router, Activity,
Audit, diagnostics, workspace inspection, and release packaging foundations the
default stable experience.

The release remains a local macOS Apple Silicon distribution. The public DMG is
unsigned and not notarized.

## What Changed From Product 1.0

Product 1.0 proved the task-first loop:

```text
goal -> draft plan -> publish tasks -> run local work -> inspect result/audit
```

Product 1.1 changes the main product model to a router-first conversation and
evidence loop:

```text
user input
  -> Runtime Input Router
  -> read-only answer, ASK/confirmation answer, guidance, revision command,
     archived-plan inspection, or execution handoff
  -> durable Conversation / Activity
  -> Audit, diagnostics, workspace inspection, and file evidence
```

The practical difference is that the user no longer has to know whether an
input is a new goal, guidance, a question, an ASK answer, a plan revision, or a
task execution request before typing. Plato routes the input, records what
happened, and keeps evidence inspectable.

## Added In 1.1

### Runtime Input Router

- Adds a Router-first Main Page input path.
- Classifies user input into question, guidance, ASK answer, confirmation
  answer, plan/task revision, or execution handoff.
- Keeps workspace-changing requests behind command-backed behavior instead of
  allowing direct Router writes.

### Durable Conversation And Activity

- Makes user input, Router interpretation, read-only answers, ASK cards,
  confirmation flows, command outcomes, task updates, and plan archive events
  reloadable as Session conversation and Activity.
- Preserves user questions and answers as product-visible content, not only as
  backend state.

### Read-Only Inquiry

- Answers questions about the current session or workspace without mutating
  files or task state.
- Records no-effect answers and evidence references in the Activity stream.
- Supports external evidence paths when web retrieval is configured.

### ASK And Confirmation Routing

- Routes authoring ASK, execution ASK, and confirmation responses through the
  same input surface.
- Displays Router-generated question cards and persists both the prompt and the
  user's answer as conversation content.

### Contract Revision Commands

- Adds command-backed plan/task refinement behavior for guidance and revision
  input.
- Keeps task execution handoff separate from read-only answers and simple
  guidance.

### Workspace Inspection

- Adds public workspace inspection foundations for git status, changed files,
  file viewer paths, and structured diff entry points.
- Uses renderer-safe labels and audit-linked evidence so users can inspect
  changed work without relying only on a summary.

### Token Usage Analytics

- Adds token usage recording and summary foundations for local sessions and
  workspace-level review.
- Makes AI runtime cost and cache behavior more inspectable.

### Precision File Tools

- Adds foundations for line-range reads, search, guarded line-range
  replacement, append operations, and changed-line evidence.
- Improves file-work auditability and reduces broad opaque edits.

### Archived Plan Access

- Keeps completed or archived plans reachable from Conversation.
- Opens archived plans in a Plan & Progress view close to the original active
  plan page, including task rows and Audit entry points.

### Frontend Interaction Runtime

- Adds submit responsiveness, local pending-row behavior, focus return targets,
  route-return focus for Audit/file/diff links, overlay close-return focus, and
  scroll stability protections.
- Fixes a release-blocking installer smoke issue where submitting while reading
  history could force the Conversation to the bottom.

### Startup And Packaging Evidence

- Shows the Electron startup shell before sidecar readiness.
- Adds startup timing instrumentation for Electron, launcher, Python import,
  sidecar readiness, and renderer readiness.
- Uses explicit release version packaging for the formal `1.1` DMG.
- Keeps production DMGs free of smoke/test assets.

## Changed Behavior

- Main input is no longer only "create a plan" or "add task guidance"; it is a
  routed product input.
- Conversation is the primary user-visible history surface. Activity, Audit,
  diagnostics, and workspace evidence are reachable from it.
- Read-only questions do not create tasks unless the Router decides execution
  work is required.
- Plan and task changes use accepted commands, making revision behavior
  auditable.
- Workspace inspection links route through app-owned views and return focus
  after Audit/file/diff navigation.
- Release packaging now accepts explicit release versions and validates that
  smoke-only files are not present in the public DMG.

## Release Artifact

| Field | Value |
|---|---|
| Version | `1.1` |
| Package version | `1.1.0` |
| Asset | `Plato-1.1-macos-arm64.dmg` |
| Runtime | Bundled Python sidecar |
| SHA256 | `fd9588592fcc8f0f04322dac8b84038bc3ebd713bdf68cf5a5b1cd4fd76e809e` |
| Signed | No |
| Notarized | No |
| Smoke assets included | No |

## Validation

Formal `1.1` release validation:

- `npm run electron:package:installer -- --release-version 1.1`
- `hdiutil verify frontend/dist-electron-installer/Plato-1.1-macos-arm64.dmg`
- `npm run electron:smoke:installer -- --skip-package --installer ./dist-electron-installer/Plato-1.1-macos-arm64.dmg`
  - configured installer smoke with packaged default workspace;
  - first-run installer smoke;
  - startup diagnostics installer smoke.
- Targeted frontend runtime tests for the release-blocking scroll behavior:
  `npm run test -- src/pages/main-page/runtime/mainPageFocusScrollRuntime.test.ts src/pages/main-page/useMainPageFocusScrollRuntime.test.tsx src/pages/main-page/MainPageWorkbench.test.tsx`

## Known Limitations

- The macOS DMG is unsigned and not notarized.
- The release is macOS Apple Silicon only.
- The app is local-first; it is not a hosted SaaS release.
- Public skill marketplace, broad MCP integration, multimodal input, signed
  distribution, auto-update, and remote execution are outside this release.
- Web retrieval remains configuration-dependent and should be documented as a
  capability foundation, not a universal default.
- Some Product 1.1 surfaces are foundations that will continue to receive UX
  polish in later releases.

## Safe Public Claims

- Product 1.1 is the formal public release of Plato's Router-first
  Conversation, Activity, Audit, diagnostics, and workspace inspection model.
- Product 1.1 moves Product 1.0's task-first baseline into a more durable,
  inspectable, user-guided workflow.
- Product 1.1 improves input routing, ASK handling, read-only inquiry,
  plan/task revision, token visibility, file evidence, and release packaging.
- The current public artifact is unsigned, not notarized, and intended for
  local macOS Apple Silicon evaluation.

Avoid claiming that Product 1.1 is fully autonomous, signed/notarized,
marketplace-ready, or production-hardened for broad consumer distribution.
