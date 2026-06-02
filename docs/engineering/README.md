# Engineering Contracts

Engineering contracts bridge product/UX intent to backend and frontend
implementation work. They are implementation-facing handoff specs, not visual
designs and not release records.

| File | Purpose | Status |
|---|---|---|
| [ask-lifecycle-contract.md](ask-lifecycle-contract.md) | ASK lifecycle contract: `ask_user` tool semantics, durable request/answer objects, task pause/resume behavior, events, API candidates, and recovery rules. | Draft Product 1.0 closure contract; implementation and canonical status/ViewModel/event updates remain pending. |
| [audit-page-contract.md](audit-page-contract.md) | Audit Page backend-to-frontend contract: snapshot, record, evidence, scopes, events, endpoint candidates, mock scenarios, and implementation status. | Frontend mock baseline, backend projection/EventStream/log/config query path, AP-012 sanitized payload disclosure first pass, AP-013A runtime event/refetch design, AP-013B frontend event router/hook, AP-013C live refresh/stale/disconnected UI, AP-013D workspace-backed UI event replay source, AP-013E first AgentLoop/EventStream `audit.records_changed` emission, and AP-013F config/log/confirmation source emissions are in place; end-to-end readiness validation remains pending. |
