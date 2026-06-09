# Engineering Contracts

Engineering contracts bridge product/UX intent to backend and frontend
implementation work. They are implementation-facing handoff specs, not visual
designs and not release records.

| File | Purpose | Status |
|---|---|---|
| [ask-lifecycle-contract.md](ask-lifecycle-contract.md) | ASK lifecycle contract: `ask_user` tool semantics, durable request/answer objects, task pause/resume behavior, events, API candidates, and recovery rules. | Draft Product 1.0 closure contract; implementation and canonical status/ViewModel/event updates remain pending. |
| [audit-page-contract.md](audit-page-contract.md) | Audit Page backend-to-frontend contract: snapshot, record, evidence, scopes, events, endpoint candidates, mock scenarios, and implementation status. | Frontend mock baseline, backend projection/EventStream/log/config query path, AP-012 sanitized payload disclosure first pass, AP-013A runtime event/refetch design, AP-013B frontend event router/hook, AP-013C live refresh/stale/disconnected UI, AP-013D workspace-backed UI event replay source, AP-013E first AgentLoop/EventStream `audit.records_changed` emission, and AP-013F config/log/confirmation source emissions are in place; end-to-end readiness validation remains pending. |
| [collaborator-workspace-informed-authoring-contract.md](collaborator-workspace-informed-authoring-contract.md) | Collaborator workspace-informed authoring contract: shared AgentLoop profile, read/search tools, wait/finish states, terminal outcome mapping, and audit/diagnostic evidence rules. | Accepted contract; Slice A profile seam and authoring evidence store contract implementation is open. |
| [multi-workspace-api-runtime-contract.md](multi-workspace-api-runtime-contract.md) | Multi-workspace API/runtime contract: workspaceId-scoped routes, runtime registry, catalog semantics, event/cursor/idempotency boundaries, and compatibility aliases. | Accepted contract; implemented foundation with one sidecar process, safe workspace catalog, workspace-scoped route aliases, Main Page catalog sidebar, and deferred concurrent execution policy. |
| [workspace-entry-contract.md](workspace-entry-contract.md) | Electron desktop workspace picker contract: safe preload IPC, current/recent workspace state, runtime config handoff, and W2 root-semantics boundary. | Accepted for W1 Workspace Picker and W2 workspace-root-as-agent-cwd semantics. |
