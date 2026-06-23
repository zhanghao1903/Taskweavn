# Product 1.1 Runtime Input Router Release Evidence

> Status: done for Product 1.1 beta P0 evidence
>
> Date: 2026-06-20
>
> Product evidence: [Product 1.1 P0 Release Evidence](../product/plato-1-1-p0-release-evidence-2026-06-20.md)
>
> Open work index: [Product 1.1 Open Work](../product/plato-1-1-open-work.md)

## Summary

Product 1.1 P0 is closed for beta release evidence. The functional work is on
`main`; this release record closes the remaining P0 evidence gates:

- Electron acceptance;
- Audit / Diagnostics closure;
- release evidence for the `1.1-beta` unsigned local DMG.

The remaining Product 1.1 work is P1 beta-depth polish, not P0 capability
delivery.

## What Shipped

Product 1.1 beta includes the collaboration-loop foundation:

- Runtime Input Router as the Main Page input path;
- durable Conversation / Activity entries for user input, Router trace, question
  cards, answers, and outcomes;
- Contract Revision Command Skills for guidance, ASK answers, confirmation
  answers, Plan/TaskNode changes, and execution handoff;
- Router read-only answers with no workspace mutation;
- backend-only Agent LLM and Router LLM configuration;
- Router-specific Audit records and diagnostic descriptors;
- packaged Electron app and unsigned local DMG installer with bundled Python.

## Stable Versus Beta

| Area | Product 1.1 beta behavior | Stability |
|---|---|---|
| Main Page input | Routes through Runtime Input Router by default. | Beta stable for covered route matrix. |
| Read-only question | Produces a no-effect answer with evidence refs and durable Activity. | Beta stable for deterministic provider path. |
| Guidance | Persists typed context through `record_guidance`. | Beta stable for session-scoped smoke; broader scope is covered by backend tests. |
| ASK / confirmation | Natural-language input can answer active ASK and confirmation states. | Beta stable for routed sidecar smoke and explicit UI tests. |
| Execution handoff | Workspace-changing input creates executable contract work, not direct tool execution. | Beta stable for handoff and no-mutation smoke. |
| Audit / Diagnostics | Router messages project into Audit and diagnostic `runtime_input` summaries. | Beta stable for redacted support export. |
| Distribution | Unsigned local DMG with bundled Python. | Beta only; signing and notarization are deferred. |

## Validation

The following checks passed on 2026-06-20:

| Check | Command | Result |
|---|---|---|
| Backend Router and Agent LLM targeted tests | `uv run pytest tests/test_runtime_input_router.py tests/test_read_only_inquiry_answer_provider.py tests/test_runtime_input_llm_router.py tests/test_agent_llm_config.py tests/test_agent_llm_resolver.py` | Pass: 37 tests |
| Frontend Main Page / Conversation targeted tests | `npm run test -- useMainPageController.test.tsx SessionMessageCard.test.tsx mainPageViewModel.test.ts` | Pass: 52 tests |
| Runtime Input diagnostics descriptors | `uv run pytest tests/test_runtime_input_router.py tests/test_read_only_inquiry_answer_provider.py tests/test_diagnostic_bundle_export.py` | Pass: 32 tests |
| Runtime Input Audit records/details | `uv run pytest tests/test_ui_query_gateway.py tests/test_audit_entry_closure.py` | Pass: 38 tests |
| Configured Electron route matrix | `npm run electron:smoke` | Pass |
| Packaged app smoke | `npm run electron:smoke:packaged` | Pass |
| `1.1-beta` installer package | `npm run electron:package:installer -- --release-version 1.1-beta --include-smoke` | Pass |
| `1.1-beta` mounted installer smoke | `npm run electron:smoke:installer -- --skip-package --installer ./dist-electron-installer/Plato-1.1-beta-macos-arm64.dmg` | Pass |

Additional P1 beta-depth checks:

| Check | Command | Result |
|---|---|---|
| Sidecar restart replay smoke | `npm run electron:smoke:sidecar-restart` | Pass on 2026-06-24: repo-mode Electron sidecar lifecycle replayed durable Conversation, Activity, Audit record, Audit evidence, and fixture file state without duplicate IDs. |

## Release Artifact

| Field | Value |
|---|---|
| DMG | `frontend/dist-electron-installer/Plato-1.1-beta-macos-arm64.dmg` |
| SHA256 | `fa67d9441d45537e6f59d674f03811fe10fcbf936da5986e12e6aef846e9406e` |
| Runtime | `bundled-python` |
| Release asset check | `ok=true`, `externalSymlinks=0` |
| Signed | `false` |
| Notarized | `false` |

## Known Limitations

- The `1.1-beta` DMG is unsigned and not notarized.
- Smoke assets are included only for deterministic beta smoke artifacts.
- Sidecar restart replay is covered by repo-mode Electron sidecar smoke, but is
  not yet folded into the packaged or installer smoke matrix.
- Optional LLM-rendered read-only inquiry smoke remains beta-depth evidence.
- Public repository release/user docs still need external sync before public
  publishing.
- Signing, notarization, Gatekeeper assessment, and signed installer acceptance
  remain deferred until Apple Developer credentials are available.

## Follow-Ups

| Priority | Follow-up |
|---|---|
| P1 | Fold sidecar restart replay evidence into packaged or installer smoke after the repo-mode signal stays stable. |
| P1 | Mirror Product 1.1 beta evidence and known limitations into public docs. |
| P1 | Add optional real/LLM-rendered read-only inquiry smoke evidence. |
| P1 | Continue stop/cancel UX, token budget warnings, localization, and web retrieval beta hardening. |
| P2 | Signed/notarized distribution and broader platform expansion. |
