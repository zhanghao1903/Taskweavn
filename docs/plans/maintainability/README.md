# Maintainability Plans

> Status: active planning category
> Last Updated: 2026-06-01
> Scope: refactor, module-boundary cleanup, large-file split, and architecture hygiene work.

Maintainability plans are executable work packages for reducing delivery risk
without changing product behavior.

Use this directory when a task is primarily about:

- splitting large files;
- preserving module boundaries;
- reducing merge-conflict and review risk;
- moving code behind stable compatibility wrappers;
- preparing a safer base for later feature work.

Maintenance plans should be explicit about:

1. current code facts and line counts;
2. public import compatibility;
3. behavior-preserving migration slices;
4. tests/checks required for every slice;
5. which later product work becomes safer after the split.

Do not hide feature work inside a maintenance plan. If a refactor reveals a
missing product or API decision, create or update the appropriate product,
feature, UI, or architecture document before implementing that behavior.

## Active Plans

| File | Purpose |
|---|---|
| [ui-backend-large-file-split-plan.md](ui-backend-large-file-split-plan.md) | Split current UI/backend hotspots while preserving Audit/Main Page behavior and public contracts. |
