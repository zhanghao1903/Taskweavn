# Engineering Contracts

Engineering contracts bridge product/UX intent to backend and frontend
implementation work. They are implementation-facing handoff specs, not visual
designs and not release records.

| File | Purpose | Status |
|---|---|---|
| [audit-page-contract.md](audit-page-contract.md) | Audit Page backend-to-frontend contract: snapshot, record, evidence, scopes, events, endpoint candidates, mock scenarios, and implementation status. | Frontend mock baseline, backend projection/EventStream/log/config query path, AP-012 sanitized payload disclosure first pass, AP-013A runtime event/refetch design, AP-013B frontend event router/hook, and AP-013C live refresh/stale/disconnected UI are in place; backend runtime event source/emission remains pending. |
