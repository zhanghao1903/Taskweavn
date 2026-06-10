# UI System Text And Localization Foundation

> Status: draft Product 1.1 plan
>
> Last Updated: 2026-06-10
>
> Owner: Product / Frontend
>
> Related contract:
> [UI System Text And Localization Contract](../../engineering/product-copy-localization-contract.md)

## 1. Problem

Product 1.0 focused on closing the functional loop. The UI now has enough
coverage to expose a product quality issue: user-facing system text is scattered
across components, fixtures, tests, and small mapping helpers. Some text is
rough, overly implementation-shaped, or only available in English.

Product 1.1 needs a managed UI system text layer so Plato can improve the
system text users see in the interface without unstable string edits and can
support English and Chinese consistently.

## 2. Scope Definition

This plan covers user-visible UI system text:

- application menu labels, command menu options, select options, segmented
  control labels, tab labels, button labels, links, field labels, headings,
  placeholders, empty states, loading states, error states, disabled reasons,
  status labels, badge labels, recovery labels, banners, toasts, tooltips, and
  short explanatory text;
- system-generated UI labels derived from stable backend facts, such as
  product error category and recovery action labels;
- first-run, Settings, Workspace, Main Page, Audit, Diagnostics, and Workspace
  Inspection UI system text.

This plan does not cover:

- user-authored content;
- LLM input text, including system/developer prompts and model request content;
- LLM output text, including generated task plans, task titles, answers,
  summaries, or questions;
- raw exception text, provider text, log payloads, prompt payloads, SQLite
  payloads, or diagnostic internals;
- LLM system/developer prompts that change model behavior.

LLM prompt files remain behavior contracts. They may get a separate prompt
governance plan later, but they must not be treated as normal UI localization
strings.

## 3. Goals

1. Centralize frontend UI system text behind typed keys.
2. Support `en-US` and `zh-CN` from the first implementation slice.
3. Keep UI text changes observable in review by editing registry entries
   instead of scattered JSX strings.
4. Keep backend APIs language-neutral wherever possible: return stable codes,
   states, ids, and data; localize in the renderer.
5. Prevent raw technical details from becoming localized UI system text.
6. Make tests resilient: prefer role/structure assertions, and use copy helpers
   when exact text is the contract.

## 4. UI System Text Style

Plato UI system text should sound like a calm, clear collaborator:

- short labels;
- direct state explanation;
- concrete next action;
- no marketing tone;
- no implementation terms unless the user is inspecting a technical audit view;
- no false certainty when a state is degraded or diagnostic-only.

English and Chinese entries are not required to be literal translations. They
must carry the same product meaning in natural language.

Initial glossary:

| Concept | en-US | zh-CN |
|---|---|---|
| Workspace | Workspace | 工作区 |
| Session | Session | 会话 |
| Task | Task | 任务 |
| Plan | Plan | 计划 |
| Audit | Audit | 审计 |
| Evidence | Evidence | 证据 |
| Diagnostics | Diagnostics | 诊断 |
| Settings | Settings | 设置 |

## 5. Locale Behavior

The first implementation should support:

- `en-US`;
- `zh-CN`;
- fallback to `en-US` for unsupported browser locales;
- a deterministic test override.

Locale source priority:

1. explicit runtime/test override;
2. persisted local UI locale preference, when the selector exists;
3. Electron runtime config, when supplied by desktop shell;
4. browser / OS language;
5. `en-US`.

A visible language selector is useful, but it is not required for the first
registry slice. It should be a follow-up Settings slice unless a Product 1.1
acceptance pass needs manual switching immediately.

## 6. Implementation Slices

### C1. Registry Foundation

- Add typed frontend UI system text registry with `en-US` and `zh-CN` catalogs.
- Add locale resolution and fallback helpers.
- Add integrity tests that fail when a key is missing in either locale.
- Add an eslint/test convention that new UI system text should not be
  introduced as untracked page-level strings.

### C2. Main Page Copy Migration

- Move Main Page top bar, sidebar, empty states, input placeholders, task plan
  labels, recovery labels, and no-session states into the registry.
- Keep existing roles and accessibility names stable where possible.
- Update tests to use copy helpers or role/structure assertions.

### C3. Settings And First-Run Copy Migration

- Move Settings modal, first-run blocked/degraded states, readiness actions,
  validation errors, and diagnostics actions into the registry.
- Keep secret redaction language explicit in both locales.

### C4. Audit, Diagnostics, And Workspace Inspection Copy Migration

- Move Audit labels, evidence/detail labels, diagnostics export labels, and
  Workspace Inspection status/diff/file viewer chrome into the registry.
- Keep raw evidence payloads untranslated and redacted.

### C5. Backend Code-To-Copy Mapping

- Ensure product error categories, recovery actions, readiness issue codes, and
  diagnostic descriptors are exposed as stable codes.
- Localize labels in frontend copy, not by sending localized backend strings.
- Document any unavoidable backend-owned display text before implementation.

### C6. Language Preference UX

- Add a small Settings control for UI language if Product 1.1 acceptance needs
  manual switching.
- Persist only the locale preference, not translated text.

### C7. Bilingual Acceptance

- Add focused UI tests for `en-US` and `zh-CN` smoke paths.
- Add one Electron smoke or sidecar E2E path that exercises the configured
  locale once the selector/runtime override exists.

## 7. Acceptance Criteria

- UI system text keys are typed and shared through a stable frontend API.
- `en-US` and `zh-CN` catalogs have identical key coverage.
- Main Page and Settings no longer introduce new user-facing text outside the
  registry after their migration slices.
- Product error recovery labels can render in both languages.
- Backend APIs do not expose raw exception, prompt, provider, log, or SQLite
  payloads as user-facing localized text.
- Tests cover missing key fallback and at least one bilingual UI surface.

## 8. Open Decisions

1. Whether Product 1.1 needs a visible language selector before broader UX
   polish acceptance.
2. Whether Audit should keep the English word "Audit" in Chinese UI for
   technical familiarity, or consistently use "审计".
3. Whether non-generated backend-owned display values should be converted to
   stable codes before localization, or temporarily mapped by display value.

## 9. First Recommended Slice

Start with C1 plus a narrow Main Page copy migration:

- introduce the registry and locale helpers;
- move no-session, no-plan, sidebar workspace/session labels, input labels, and
  product recovery labels;
- add `en-US` / `zh-CN` integrity tests;
- do not add a Settings language selector yet.
