# Plato 1.1 Public Release Docs Sync

> Status: Product 1.1 P1 external-doc sync package
> Last Updated: 2026-06-24
> Target public repository: `zhanghao1903/plato-public`
> Scope: release/user docs only; no private source, logs, workspaces, or
> diagnostics payloads

This document defines the approved package for mirroring Product 1.1 beta
evidence and known limitations into the public Plato repository.

It does not directly change `zhanghao1903/plato-public`. The purpose is to make
the public sync explicit, reviewable, and safe before a separate public-repo PR.

## 1. Source Of Truth

Use these private repository sources when preparing the public update:

| Source | Public use |
|---|---|
| [`../plato-1-1-p0-release-evidence-2026-06-20.md`](../plato-1-1-p0-release-evidence-2026-06-20.md) | Product 1.1 beta release evidence summary, validation categories, known limitations, and next work. |
| [`../../releases/product-1-1-runtime-input-router-release-evidence.md`](../../releases/product-1-1-runtime-input-router-release-evidence.md) | Runtime Input Router beta behavior, route matrix summary, packaged/mounted installer evidence, and deferred signing/notarization. |
| [`../plato-1-1-open-work.md`](../plato-1-1-open-work.md) | P1/P2 boundary and active follow-up list. |
| [`../plato-runtime-input-model.md`](../plato-runtime-input-model.md) | User-facing explanation of question, guidance, command, ASK, confirmation, and execution routing. |
| [`../plato-session-active-work-lifecycle.md`](../plato-session-active-work-lifecycle.md) | Session/Plan lifecycle, manual archive, and history behavior. |
| [`../plato-settings-logs-audit-boundary.md`](../plato-settings-logs-audit-boundary.md) | Settings, diagnostics, logs, and Audit boundary language. |
| [`public-visual-asset-gaps.md`](public-visual-asset-gaps.md) | Public-safe screenshots and visual asset readiness. |

If a dedicated Product 1.1 web retrieval limitations page exists on the branch
being synced, include its user-facing boundaries. If it is not merged yet, keep
web retrieval limitations in the general known-limitations section and avoid
linking a non-existent private source.

## 2. Public Repository Targets

The public PR should update or add only public-safe docs:

| Public target | Required change |
|---|---|
| `README.md` | Update release/status summary to mention Product 1.1 beta capability scope without implying full public availability beyond published artifacts. |
| `docs/release-status.md` or equivalent | Add Product 1.1 beta evidence summary, tested surfaces, artifact status, SHA/checksum if publicly distributed, and known limitations. |
| `docs/user-guide.md` or equivalent | Add user-facing explanation of Session conversation, Plan/Direct Task behavior, ASK/confirmation, Audit, diagnostics, and workspace inspection. |
| `docs/trust-and-audit.md` or equivalent | Add Product 1.1 Audit/Activity/diagnostics evidence behavior and safety boundaries. |
| `docs/architecture-overview.md` or equivalent | Refresh high-level architecture only where public docs already discuss Plato's planes. Avoid private implementation internals. |
| `assets/screenshots/` | Add or replace screenshots only if they pass `public-visual-asset-gaps.md`. |

Do not add private implementation docs wholesale. Public docs should be
rewritten product docs, not copied internal records.

## 3. Public Claims Allowed

Public docs may claim:

- Plato is a Session-first, Task-aware AI workbench.
- Product 1.1 beta focuses on runtime input routing, durable Conversation /
  Activity, command-backed state changes, Audit/diagnostics evidence, packaged
  local desktop validation, and workspace inspection.
- The Main Page supports question-like input, guidance, Direct Task / Plan
  routing, ASK/confirmation, and task execution visibility.
- Product 1.1 has beta-level evidence for configured local sidecar/Electron
  paths and selected packaged app smoke paths.
- Signing and notarization are not yet complete unless a later public release
  artifact proves otherwise.
- P1 follow-ups remain active for public docs sync, sidecar restart replay,
  stop/cancel polish, token budget boundaries, localization polish, web
  retrieval hardening, and diagnostics depth.

## 4. Claims That Must Be Avoided

Public docs must not claim:

- Product 1.1 is broadly production-ready.
- Hosted cloud execution, remote worker fleets, or authenticated browser
  automation are available.
- Signed/notarized macOS distribution is complete without accepted evidence.
- Web retrieval is a full browsing/research system.
- Skills, MCP, multimodal file ingestion, custom Agent protocol, Result
  Packaging Agent, or `task_after` are public Product 1.1 capabilities unless a
  later accepted release proves them.
- Internal workspace paths, logs, diagnostic payloads, provider secrets,
  user-specific session data, or private screenshots are public-safe.

## 5. Known Limitations To Publish

The public known-limitations section should include:

- Local beta distribution remains unsigned/not notarized until Apple Developer
  credentials and Gatekeeper acceptance exist.
- Product 1.1 beta is validated against controlled local workspace scenarios,
  not broad customer data.
- Conversation/Activity replay and sidecar restart replay require beta-depth
  evidence beyond the P0 route matrix unless the dedicated sidecar replay PR is
  merged and accepted.
- Web retrieval is opt-in, provider-dependent, public-web-only, and bounded.
- Stop/cancel semantics, token-budget warnings, localization polish, richer
  diagnostics descriptors, broader citation/result UI, and public support docs
  remain P1 polish.
- External integrations such as MCP, custom Agents, remote execution, and
  multimodal files remain roadmap items.

## 6. Required Public PR Checklist

Before opening or updating the public PR:

- Map every public claim to one source in section 1.
- Rewrite internal evidence into user-facing language.
- Remove private paths, usernames, workspace ids, session ids, raw logs, and
  local diagnostic payloads.
- Keep screenshots public-safe and consistent with current Plato branding.
- Preserve clear labels: `available`, `beta`, `preview`, `roadmap`, or
  `deferred`.
- Include a known-limitations section.
- Include a reviewer note that the public PR is docs/assets only unless a
  separate release artifact update is explicitly included.

## 7. Acceptance Criteria

This private sync package is complete when:

- public target files are identified;
- source-of-truth private docs are listed;
- allowed claims and forbidden claims are explicit;
- Product 1.1 beta known limitations are ready to copy into public docs;
- the public PR checklist can be followed without re-reading private planning
  history.

The external sync itself is complete only after a separate PR updates
`zhanghao1903/plato-public` and passes public repository review.
