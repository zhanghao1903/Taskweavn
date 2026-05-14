# User Modeling and Attribution

This directory defines how TaskWeavn models user needs and maps them into architecture, plans/features, and implementation.

## Why this exists

We want a complete attribution chain:

`User Need -> Architecture Decision -> Plan/Feature -> Implementation`

In many cases architecture will change. In some cases architecture boundaries remain valid, and the need is delivered only through plan/feature and implementation updates.

Without this chain, decisions drift into assumption-led work. With this chain, every capability can answer:

1. Should we build it?
2. How should we build it?
3. How do we support it now?
4. How will we support it later?

For TaskWeavn, user-facing value should progressively cover three lines:

1. **Plan line**: what to do.
2. **Execution line**: how it is done.
3. **Eval line**: whether it is suitable/effective/trustworthy.

## Directory conventions

Recommended structure:

- `README.md`: governance, schema, and traceability rules (this file).
- `users.md`: user segments and stable personas.
- `needs/`: one file per user need/problem statement.
- `scenarios/`: one file per scenario/job-to-be-done.
- `decisions/`: per-need decision records (do/not-do/conditional).
- `traceability.md`: index that links needs -> architecture -> plan/feature -> implementation.
- `metrics.md`: success metrics, guardrail metrics, and review cadence.

Teams can start with fewer files and expand as coverage grows.

## Minimum schema for each user need record

Each need file should include:

1. **Need ID** (e.g., `UN-001`)
2. **User segment/persona**
3. **Problem statement**
4. **Scenario and trigger**
5. **Decision**: do / not now / not do
6. **Current approach**
7. **Future approach**
8. **Architecture mapping**
9. **Plan/feature mapping**
10. **Implementation mapping**
11. **Evidence and validation status**
12. **Priority and scheduling rationale** (why now, why not later)
13. **Definition of done** (acceptance criteria and measurable targets)

## Decision policy

For every user need, the system/product response must explicitly state:

- **Do we do it?** (yes/no/not now)
- **How do we do it?** (interaction + system boundary)
- **How do we handle it currently?** (implemented baseline)
- **How do we handle it in future?** (planned evolution)

No ambiguous “maybe” without an owner and next review point.

## Prioritization model (lightweight)

Every user need should include:

- `impact`: expected user/business impact
- `urgency`: time sensitivity
- `confidence`: evidence confidence
- `cost`: implementation + maintenance cost
- `risk`: delivery/quality risk

Teams can use a lightweight score (e.g., ICE/RICE-style) as long as the logic is explicit and auditable.

## Evidence model

User-grounded decisions must include evidence metadata:

- `evidence_type`: interview / usability test / behavior analytics / support ticket / assumption
- `evidence_strength`: high / medium / low
- `last_validated_at`: last verification date
- `source_ref`: optional links to notes, reports, or artifacts

## Required traceability rules

1. **Architecture documents must cite user need IDs** when the need changes or introduces architecture boundaries.
2. **Plan/feature docs must cite architecture sections** they implement.
3. **Implementation PRs/commits should cite plan or feature IDs** they deliver.
4. **Release notes should summarize delivered user needs** and remaining gaps.

If a work item cannot be traced backward to a user need, it should be challenged before implementation.

## Forward + backward traceability

We require both directions:

1. **Forward traceability** supports two paths:
   - user need -> architecture -> plan/feature -> implementation
   - user need -> plan/feature -> implementation (if architecture unchanged)
2. **Backward traceability**: implementation -> plan/feature -> architecture -> user need.

Backward traceability ensures shipped code can prove which user problem it solved and whether outcomes improved.

If architecture is unchanged, backward traceability may use:

`implementation -> plan/feature -> user need`  

and should mark `architecture impact = none` in the need record.

## Not-doing governance

For needs marked `not now` or `not do`, record:

- rationale
- re-evaluation trigger
- next review date
- owner

This prevents repeated debates and keeps decision history explicit.

## Suggested starter files

Create these when you begin modeling:

- `users.md`
- `needs/UN-001-template.md`
- `scenarios/SC-001-template.md`
- `traceability.md`

The goal is not paperwork. The goal is decision quality with explicit user-grounded reasoning.
