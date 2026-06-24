# Plato Product 1.1 P1 Coverage Audit - 2026-06-24

> Status: active coverage audit
>
> Baseline: `main` after `git pull --ff-only origin main`
>
> Last verified: 2026-06-25
>
> Scope: Product 1.1 P1 open-work coverage after P0 release evidence closure.
> This document verifies whether each Product 1.1 P1 row has a standalone
> owner branch / PR. It does not mark those PRs accepted or merged.

## 1. Purpose

Product 1.1 P0 is closed as a beta evidence package. The remaining work is P1
beta-depth hardening and release polish. Because the P1 work is intentionally
split across small branches, this audit records the current coverage map so the
project can distinguish:

- a P1 gap that has no owner;
- a P1 gap that has a draft or ready PR;
- a P1 gap that is intentionally deferred because it requires external
  credentials or a later release decision.

This audit is a control-plane artifact. The owning PR for each row remains the
source of implementation, evidence, tests, and acceptance.

## 2. Coverage Rule

A Product 1.1 P1 row is considered covered for planning purposes when:

1. it has an open PR or accepted source that names the row's product risk;
2. the PR is narrow enough to be reviewed as one product work item, or the row
   is explicitly listed as needing branch hygiene before merge;
3. the row is linked from the Product 1.1 open-work index or release evidence;
4. remaining work is called out as follow-up instead of hidden in the PR.

Covered does not mean complete. Completion still requires the relevant PR to be
merged or otherwise accepted.

## 3. Product 1.1 P1 Coverage Matrix

| P1 area | Coverage status | Owner PR / source | Notes |
|---|---|---|---|
| Workspace inspection hardening | Covered by split PRs | PR #99, PR #107 | PR #99 adds workspace inspection Audit source/detail support. PR #107 records the durable evidence capture policy and keeps raw unified diff capture deferred unless a concrete UI/diagnostic need appears. |
| Precision file tools product acceptance | Covered | PR #100 | Adds sidecar acceptance smoke for precision file tool evidence linkage. |
| Stop / cancel UX | Covered | PR #94 | Projects intentional stops as cancelled/stopped user intent instead of generic failed/retry language. |
| Token usage budget boundary | Covered | PR #95 | Adds visible high-token/budget warning boundary for beta trust. |
| Diagnostics descriptors | Covered by split PRs | PR #97, PR #108 | PR #97 adds workspace inspection diagnostic support summaries. PR #108 adds per-route Electron log descriptor planning. |
| Localization polish | Covered | PR #96 | Localizes remaining ASK / confirmation detail chrome and continues typed UI text migration. |
| Web retrieval beta hardening | Covered by split PRs | PR #98, PR #101, PR #102, PR #104, PR #106 | Covers read-only fallback hardening, live Tavily smoke, user-visible limitations, citation/result UI planning, and retrieval budget boundary planning. |
| Electron release hardening | Covered by split PRs | PR #108, PR #110 | PR #110 owns sidecar restart replay confidence as a narrow smoke/evidence PR. PR #108 owns route-log descriptor planning. Signed/notarized distribution remains credential-gated and deferred. |
| External release docs sync | Covered by split PRs | PR #103, PR #111 | PR #103 defines the public Product 1.1 release docs sync plan. PR #111 prepares the public-facing Product 1.1 beta source release notes and related indexes. Copying those notes into the external public repository remains the final publishing operation. |

## 4. Related Accepted Or Existing Evidence

The following are not new P1 gaps:

- Optional LLM-rendered read-only inquiry smoke is already represented by
  `npm run electron:smoke:read-only-inquiry-llm` and
  `npm run electron:smoke:packaged-read-only-inquiry-llm`, and is tracked in
  the accepted read-only inquiry docs.
- Public visual assets and screenshots are tracked under
  `docs/product/public-exposure/` and the public repository draft PR.
- Signed and notarized distribution is intentionally deferred until Apple
  Developer credentials exist.

## 5. Current Assessment

As of the 2026-06-25 verification, every Product 1.1 P1 open-work row has
either:

- a dedicated open PR;
- a split set of open PRs for independently reviewable sub-risks; or
- an explicit external dependency deferral.

The previously broad PR #93 was closed as superseded because it mixed sidecar
restart replay confidence with external release notes. Its scope is now split
across PR #110 and PR #111.

Product 1.1 P1 should not be marked complete yet because the owner PRs remain
open and several are draft. The next release-readiness step is to move through
the PR list, merge or close each owner branch, and update
`plato-1-1-open-work.md` from "covered by PR" to "accepted" only after evidence
is merged.

## 6. Follow-Up Checklist

1. Keep PR #93 closed; do not merge the superseded mixed branch.
2. Review and merge / close PRs #94 through #111 one by one.
3. Merge PR #110 before PR #111 if Product 1.1 release docs should claim
   sidecar restart replay commands are available on `main`.
4. After each merge, update the owning plan, Product 1.1 open-work index, and
   gap registry only when readiness or acceptance changes.
5. After all owner PRs are accepted, create a final Product 1.1 P1 closure
   record that references merged commits instead of open PR numbers.
