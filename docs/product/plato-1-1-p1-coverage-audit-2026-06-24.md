# Plato Product 1.1 P1 Coverage Audit - 2026-06-24

> Status: accepted closure record
>
> Baseline: `main` after `git pull --ff-only origin main`
>
> Last verified: 2026-07-06
>
> Scope: Product 1.1 P1 open-work closure after P0 release evidence closure.
> This document records the standalone owner PRs that were merged into `main`
> or explicitly deferred as external release operations.

## 1. Purpose

Product 1.1 P0 is closed as a beta evidence package. The remaining P1
beta-depth hardening and release polish was intentionally split across small
branches. This audit now records the accepted closure map so the project can
distinguish:

- a P1 gap that was merged into `main`;
- a P1 gap that was accepted as a docs-only planning / release-evidence item;
- a P1 gap that is intentionally deferred because it requires external
  credentials or a later release decision.

This audit is a control-plane artifact. The owning PR for each row remains the
source of implementation, evidence, tests, and acceptance.

## 2. Coverage Rule

A Product 1.1 P1 row is considered closed for the current beta-readiness pass
when:

1. its owner PR or accepted source names the row's product risk;
2. the PR is narrow enough to be reviewed as one product work item, or the row
   is explicitly listed as needing branch hygiene before merge;
3. the row is linked from the Product 1.1 open-work index or release evidence;
4. remaining work is called out as follow-up instead of hidden in the PR.

Closed does not mean all future hardening is complete. It means the Product 1.1
P1 beta-readiness work is either merged into `main`, accepted as a scoped
planning/release-evidence closure, or explicitly deferred outside the current
repo release gate.

## 3. Product 1.1 P1 Coverage Matrix

| P1 area | Closure status | Owner PR / source | Notes |
|---|---|---|---|
| Workspace inspection hardening | Accepted on `main` | PR #99, PR #107 | PR #99 adds workspace inspection Audit source/detail support. PR #107 records the durable evidence capture policy and keeps raw unified diff capture deferred unless a concrete UI/diagnostic need appears. |
| Precision file tools product acceptance | Accepted on `main` | PR #100 | Adds sidecar acceptance smoke for precision file tool evidence linkage. |
| Stop / cancel UX | Accepted on `main` | PR #94 | Projects intentional stops as cancelled/stopped user intent instead of generic failed/retry language. |
| Token usage budget boundary | Accepted on `main` | PR #95 | Adds visible high-token/budget warning boundary for beta trust. |
| Diagnostics descriptors | Accepted on `main` | PR #97, PR #108 | PR #97 adds workspace inspection diagnostic support summaries. PR #108 adds per-route Electron log descriptor planning. |
| Localization polish | Accepted on `main` | PR #96 | Localizes remaining ASK / confirmation detail chrome and continues typed UI text migration. |
| Web retrieval beta hardening | Accepted on `main` | PR #98, PR #101, PR #102, PR #104, PR #106 | Covers read-only fallback hardening, live Tavily smoke, user-visible limitations, citation/result UI planning, and retrieval budget boundary planning. |
| Electron release hardening | Accepted on `main`; credential-gated items deferred | PR #108, PR #110 | PR #110 owns sidecar restart replay confidence as a narrow smoke/evidence PR. PR #108 owns route-log descriptor planning. Signed/notarized distribution remains credential-gated and deferred. |
| External release docs sync | Accepted internally; external publication deferred | PR #103, PR #111 | PR #103 defines the public Product 1.1 release docs sync plan. PR #111 prepares the public-facing Product 1.1 beta source release notes and related indexes. Copying those notes into an external public repository remains a publishing operation outside this repo closure. |

## 4. Related Accepted Or Existing Evidence

The following are not new P1 gaps:

- Optional LLM-rendered read-only inquiry smoke is represented by
  `npm run electron:smoke:read-only-inquiry-llm` and
  `npm run electron:smoke:packaged-read-only-inquiry-llm`, but it is not green
  evidence yet. The 2026-07-02 feature test report shows the deterministic LLM
  answer renders, then the script fails later in stale retry recovery. Treat it
  as beta-depth follow-up until the smoke is split or fixed.
- Public visual assets and screenshots are tracked under
  `docs/product/public-exposure/` and the public repository draft PR.
- Signed and notarized distribution is intentionally deferred until Apple
  Developer credentials exist.

## 5. Current Assessment

As of the 2026-06-25 verification, every Product 1.1 P1 open-work row has
either:

- a dedicated owner PR merged into `main`;
- a split set of owner PRs merged into `main` for independently reviewable
  sub-risks; or
- an explicit external dependency deferral.

The previously broad PR #93 was closed as superseded because it mixed sidecar
restart replay confidence with external release notes. Its scope is now split
across PR #110 and PR #111.

Product 1.1 P1 beta-readiness closure is accepted for this repository. The
remaining visible work is not hidden P1 implementation: it is optional LLM smoke
hardening, signed / notarized distribution, external-publication execution, or
later Product 1.1+ hardening.

## 6. Follow-Up Checklist

1. Keep PR #93 closed; do not merge the superseded mixed branch.
2. Keep PR #105 out of the Product 1.1 P1 closure unless the WeChat runtime
   input line is explicitly pulled into a later release scope.
3. Treat signed/notarized distribution as credential-gated release work.
4. Treat copying prepared public release notes into an external public
   repository as a publishing operation, not an internal Product 1.1 P1 blocker.
5. Treat optional LLM-rendered inquiry smoke as beta-depth follow-up until the
   script has independent green evidence for LLM answer rendering and retry
   recovery.
6. Use this closure record plus `plato-1-1-open-work.md` as the accepted P1
   control-plane state.
