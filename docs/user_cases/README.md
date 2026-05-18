# User Test Cases

> Status: active directory, needs Plato 1.0 refresh
> Last Updated: 2026-05-18
> Related: [Plato 1.0 Acceptance](../product/versions/1.0/acceptance.md), [Capability Map](../capabilities/index.md)

This directory is reserved for current manual and product-level user tests.

Older CLI-era user cases and their terminal outputs were archived under:

```text
docs/archive/legacy-2026-05-18/user_cases/
```

New user tests should be written against the current Plato 1.0 workflow:

1. first-run/settings;
2. natural language to RawTask / DraftTaskTree;
3. Task card review and confirmation;
4. Task execution and message stream updates;
5. file change summary and audit/trust evidence;
6. diagnostic bundle and error recovery.

## Writing Convention

Each new user case should include:

- target capability;
- difficulty;
- user goal;
- setup;
- exact test steps;
- expected UI states;
- expected backend evidence, if relevant;
- failure observations;
- tester notes.

Artifacts should use:

- `docs/assets/images/` for screenshots;
- a dedicated local test workspace outside the project root for generated files;
- links to diagnostic bundles or logs only when they are safe to keep in the repository.
