# User Traceability Index

This file maintains bi-directional traceability across user needs, architecture, plans/features, and implementation.

## A. Forward traceability

Path A (architecture changed): need -> architecture -> plan -> implementation  
Path B (architecture unchanged): need -> plan -> implementation

| Need ID | User Segment | Architecture Reference (optional if unchanged) | Plan/Feature Reference | Implementation Reference | Status |
|---|---|---|---|---|---|
| UN-001 (example) | U1 | docs/architecture/authoring-domain.md | docs/plans/feature/collaborator-agent-task-authoring.md | TBD | proposed |
| UN-101 | U2 | docs/architecture/authoring-domain.md; docs/architecture/authoring-command-protocol.md; docs/architecture/task-domain-ui-model-separation.md; docs/architecture/tool-capability-layer.md | docs/plans/feature/collaborator-agent-task-authoring.md | TBD | proposed |
| UN-102 | U2,U3 | docs/architecture/authoring-domain.md; docs/architecture/authoring-command-protocol.md; docs/architecture/task-domain-ui-model-separation.md; docs/architecture/tool-capability-layer.md | docs/plans/feature/collaborator-agent-task-authoring.md; docs/plans/feature/result-packaging-agent-cards.md | TBD | proposed |
| UN-103 | U3 | docs/architecture/authoring-domain.md; docs/architecture/authoring-command-protocol.md; docs/architecture/interaction-layer.md; docs/architecture/tool-capability-layer.md | docs/plans/feature/collaborator-agent-task-authoring.md; future retrieval/governance plan TBD | TBD | proposed / not-now validation |
| UN-104 | U1,U2,U3 | docs/architecture/task-domain-ui-model-separation.md; docs/architecture/configurable-logging-system.md | docs/plans/ui/visual-reference.md; docs/plans/feature/centralized-runtime-configuration.md | TBD | proposed / not-now scheduling |
| UN-105 | U1,U2,U3 | docs/architecture/authoring-domain.md; docs/architecture/authoring-command-protocol.md; docs/architecture/collaborator-agent-task-authoring.md; docs/architecture/interaction-layer.md; docs/architecture/tool-capability-layer.md | docs/plans/feature/collaborator-agent-task-authoring.md; docs/plans/observability.md; docs/plans/cost-quota.md | TBD | proposed |

## B. Backward traceability (implementation -> plan -> architecture -> need)

| Implementation Item | Plan/Feature Reference | Architecture Reference (optional if unchanged) | Need ID | Outcome Evidence | Status |
|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | planned |

## C. Governance checks

Before merge/release:

1. Every significant implementation item should map back to at least one `UN-*`.
2. Every active `UN-*` should map to architecture and at least one plan/feature (or explicitly marked discovery-only).
3. `not-now` and `not-do` needs should include review date and owner.
