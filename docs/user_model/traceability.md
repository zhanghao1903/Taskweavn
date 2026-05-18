# User Traceability Index

This file maintains traceability across user needs, current product capabilities, plans, and implementation.

## A. Forward Traceability

| Need ID | User Segment | Current Capability / Architecture Reference | Plan / Feature Reference | Implementation Reference | Status |
|---|---|---|---|---|---|
| UN-001 (template) | U1 | TBD | TBD | TBD | template |
| UN-101 | U2 | [Task Authoring](../capabilities/task-authoring/), [File Change Summary](../capabilities/file-change-summary/), [Audit Trust](../capabilities/audit-trust/) | P0 feature packages TBD | TBD | proposed |
| UN-102 | U2, U3 | [Task Authoring](../capabilities/task-authoring/), [Task Execution](../capabilities/task-execution/), [Main Page Real Backend](../capabilities/main-page-real-backend/) | P0 feature packages TBD; result packaging later | TBD | proposed |
| UN-103 | U3 | [Task Authoring](../capabilities/task-authoring/), [Message and Confirmation](../capabilities/message-and-confirmation/), [Audit Trust](../capabilities/audit-trust/) | P0 feature packages TBD; retrieval/governance later | TBD | proposed / not-now validation |
| UN-104 | U1, U2, U3 | [Settings and First Run](../capabilities/settings-and-first-run/), [Configuration Control Plane](../capabilities/configuration-control-plane/) | P0/P1 feature packages TBD | TBD | proposed / not-now scheduling |
| UN-105 | U1, U2, U3 | [Task Authoring](../capabilities/task-authoring/), [Audit Trust](../capabilities/audit-trust/), [Diagnostic Bundle](../capabilities/diagnostic-bundle/) | P0 feature packages TBD | TBD | proposed |

## B. Backward Traceability

| Implementation Item | Capability / Plan Reference | Need ID | Outcome Evidence | Status |
|---|---|---|---|---|
| TBD | TBD | TBD | TBD | planned |

## C. Legacy Source Material

Older discussions, feature plans, and architecture notes used to seed these needs are archived under:

```text
docs/archive/legacy-2026-05-18/
```

Use archived material as evidence when promoting a user need into a current feature package, but keep active routing through capability packets and product version docs.

## D. Governance Checks

Before merge/release:

1. every significant implementation item should map back to at least one `UN-*`;
2. every active `UN-*` should map to a capability packet and at least one plan, or be explicitly discovery-only;
3. `not_now` and `wont_do` needs should include a review date and owner.
