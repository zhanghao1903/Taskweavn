# User Segments and Persona Baseline

This file defines stable user segments for product and architecture decisions.

## Segment U1 — Tech Lead / Senior Engineer

- Primary goal: turn ambiguous engineering goals into executable, controllable task flows.
- Typical pain: context switching, unclear delegation boundaries, weak auditability.
- High-value capability: task authoring quality, risk-gated execution, replay visibility.

## Segment U2 — Solo Builder / Small Team Developer

- Primary goal: increase delivery throughput with bounded risk and low process overhead.
- Typical pain: limited bandwidth, unstable automation quality, manual orchestration load.
- High-value capability: draft task tree quality, fast node-level edits, actionable summaries.

## Segment U3 — AI-native Operator

- Primary goal: run long or multi-step work through an AI collaboration cockpit.
- Typical pain: chat-first tools lose structure over long sessions.
- High-value capability: task-first interaction, scoped context, status clarity.

## Out-of-scope segments (current stage)

- Non-technical end users requiring zero-config domain tooling.
- Enterprise governance-heavy users needing full RBAC/approval/compliance workflows.

## Persona usage rules

1. Every user need (`UN-*`) must reference at least one segment above.
2. If a new segment appears repeatedly, add it here before scaling feature scope.
3. Segment additions require architecture and roadmap review due to potential scope shift.
