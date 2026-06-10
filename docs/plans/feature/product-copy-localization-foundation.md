# UI System Text And Localization Foundation

> Status: implemented Product 1.1 foundation
>
> Last Updated: 2026-06-10
>
> Owner: Product / Frontend
>
> Related contract:
> [UI System Text And Localization Contract](../../engineering/product-copy-localization-contract.md)
>
> Technical Design:
> [UI System Text And Localization Technical Design](ui-system-text-localization-technical-design.md)

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
6. Make tests resilient: prefer role/structure assertions, and use UI text
   helpers when exact text is the contract.

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

- Implemented: typed frontend UI system text registry with `en-US` and `zh-CN`
  catalogs.
- Implemented: locale resolution and fallback helpers.
- Implemented: integrity tests that fail when a key is missing in either locale.
- Deferred: eslint/test convention that new UI system text should not be
  introduced as untracked page-level strings.
- Implemented: file layout, provider/hook boundary, product-error compatibility
  wrapper, and bilingual UI smoke coverage from the technical design.

### C2. Main Page UI System Text Migration

- Implemented: Main Page top bar, workspace/session sidebar, empty states,
  input labels, task plan chrome, session lifecycle dialog, no-session states,
  and recovery labels now read from the registry.
- Existing roles and accessibility names stay English by default and follow the
  active locale when a locale override is supplied.
- Tests use UI text helpers for bilingual smoke coverage where exact localized
  text is the product contract.

### C3. Settings And First-Run UI System Text Migration

- Implemented: Settings modal, first-run blocked/degraded states, readiness
  actions, diagnostics actions, setup form labels, and safe helper text now read
  from the registry.
- Secret redaction language remains explicit in both locales; stored secret
  values are still write-only and not rendered.

### C4. Audit, Diagnostics, And Workspace Inspection UI System Text Migration

- Implemented foundation: Audit stable enum/code labels, diagnostics handoff and
  export chrome, and Workspace Inspection status/diff/file viewer chrome now
  read from the registry.
- Raw evidence payloads, diagnostic payloads, file contents, diff hunks, warning
  messages, generated task content, and user-authored content remain
  untranslated and redacted according to their existing contracts.

### C5. Backend Code-To-UI-Text Mapping

- Implemented for current frontend mappings: product recovery actions localize
  from stable action codes in the renderer while compatibility wrappers keep
  English defaults for old call sites.
- Existing backend APIs continue returning stable facts and safe messages; no
  localized backend response shape was added.
- Follow-up: audit remaining backend-owned display values before expanding
  localization beyond current renderer chrome.

### C6. Language Preference UX

- Deferred: add a small Settings control for UI language if Product 1.1 acceptance needs
  manual switching.
- Persist only the locale preference, not translated text.

### C7. Bilingual Acceptance

- Implemented: focused UI tests for `en-US` and `zh-CN` smoke paths.
- Deferred: add one Electron smoke or sidecar E2E path that exercises the configured
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

1. Product 1.1 still needs a visible language selector decision before broader
   UX polish acceptance.
2. Audit currently uses "审计" in Chinese UI system text while raw evidence and
   generated content remain unchanged.
3. Remaining backend-owned display values should be audited before any future
   localization expansion that depends on them.

## 9. Implemented Foundation

Implemented on 2026-06-10:

- `frontend/src/shared/ui-text` owns the typed `UiTextCatalog`, `en-US` and
  `zh-CN` catalogs, locale resolution, React provider/hook, and test helper.
- `App` resolves `VITE_PLATO_UI_LOCALE` / Electron `uiLocale` and provides UI
  text to all routes.
- Product recovery labels/descriptions render from active locale text while
  legacy helper functions continue returning English defaults.
- Main Page, Settings/first-run, Diagnostics, Workspace Inspection, and the
  stable Audit label helpers now use the registry for renderer-owned UI system
  text.
- Full frontend unit test suite and production build pass.

## 10. Remaining Follow-Ups

- Visible Settings language selector and persisted locale preference.
- Electron native menu localization.
- Translator extraction/lint tooling for future broad copy work.
- Sidecar/Electron bilingual smoke once a user-facing selector or launch-time
  locale acceptance path is needed.
- LLM prompt/content language governance remains separate from this UI system
  text foundation.
