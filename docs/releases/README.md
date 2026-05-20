# Release Records

This directory records completed phases, milestones, and important feature slices.

Release records should answer:

- what shipped;
- which docs and code areas changed;
- what was validated;
- which follow-ups remain.

When a release closes or changes a known gap, update [Gap Registry](../gaps/)
alongside the release record.

## Index

| Release | Status | Summary |
|---|---:|---|
| [API Publish Server Transport](api-publish-server-transport.md) | done | Framework-neutral HTTP/RPC adapter for `DefaultApiTaskPublisher` routes and response envelopes. |
| [Configurable Logging System](configurable-logging-system.md) | done | Structured JSONL logging, session archives, profiles, same-process control API, and core object integrations. |
| [Publish Persistence Foundation](publish-persistence-foundation.md) | done | SQLite publish idempotency, audit, scheduler stores, service assembly, and deterministic idempotency hardening. |
| [Task Publishers, Schedule, API, And Pipeline Expansion](task-publishers-schedule-api.md) | done | TaskBus-backed publishing, custom tree parsing, idempotent publish service, scheduler/API publisher adapters, and publish-time pipeline expansion. |
| [Collaborator Agent And Task Authoring](collaborator-agent-task-authoring.md) | done | RawTask feasibility, Authoring Commands, DraftTaskTree stores, Collaborator service, publish boundary, and UI/API adapter. |
| [LLM Provider Reliability](llm-provider-reliability.md) | done | Provider abstraction, retry, DeepSeek thinking, and OpenRouter routing. |
| [Phase 3 Interaction Layer through 3.8](phase-3-interaction-layer-through-3-8.md) | done | Session, risk/autonomy, messages, bus, wait, loop integration, LLM risk, derived session status. |
| [Task Domain and UI ViewModel Separation](task-domain-ui-model-separation.md) | done | Task domain/draft models, UI ViewModels, projection, command mapping, replay timeline, and UI API alignment. |
| [UI/backend Contract Baseline](ui-backend-contract-baseline.md) | done | Framework-neutral Plato UI contract package, mapping/query/command/event gateways, frontend type alignment, and shared JSON fixture parity. |
