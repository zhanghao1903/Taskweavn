# User Modeling Metrics

This file defines how user-need decisions are measured over time.

## 1) Outcome metrics

- Need resolution rate (`done` needs / active needs)
- Time to first user-visible value
- Scenario success rate (per `SC-*`)

## 2) Quality and risk metrics

- Regression rate on solved needs
- Confirmation friction for high-risk flows
- Failure replay completeness (can we explain what happened?)

## 3) Traceability health metrics

- % implementation items with backward link to `UN-*`
- % active needs with architecture + plan mapping
- % `not-now` needs with valid review date/owner

## 4) Review cadence

- Weekly: active need status and blockers
- Bi-weekly: priority and evidence refresh
- Monthly: architecture alignment and scope control
