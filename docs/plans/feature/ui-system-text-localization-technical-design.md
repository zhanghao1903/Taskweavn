# UI System Text And Localization Technical Design

> Status: accepted / implemented foundation
>
> Last Updated: 2026-06-10
>
> Related Plan:
> [UI System Text And Localization Foundation](product-copy-localization-foundation.md)
>
> Related Contract:
> [UI System Text And Localization Contract](../../engineering/product-copy-localization-contract.md)

## 1. Purpose

This technical design defines the first implementable frontend architecture for
managed UI system text and bilingual localization.

The design covers system text that users see in the UI: menus, options, labels,
status text, placeholders, empty states, disabled reasons, recovery labels,
tooltips, banners, toasts, and short inline hints.

It explicitly does not cover:

- user-authored text;
- LLM input text, including system/developer prompts and model requests;
- LLM output text, including generated task plans, asks, answers, summaries, or
  task titles;
- backend raw exception text, provider payloads, log payloads, prompt payloads,
  SQLite payloads, secrets, or absolute workspace paths.

Implementation closure:

- `shared/ui-text` registry, provider, locale resolver, and parity tests are in
  place.
- Main Page, Settings/first-run, Diagnostics, Workspace Inspection, and stable
  Audit enum/code labels use the registry for renderer-owned UI system text.
- Product recovery labels/descriptions localize from stable recovery action
  codes while legacy helper wrappers keep English defaults.
- Settings language selector, persisted preference, Electron native menu
  localization, and translator extraction tooling remain deferred follow-ups.

## 2. Current Code Shape

The current frontend has no localization layer. UI system text is distributed
across:

- route composition in `frontend/src/app`;
- page components under `frontend/src/pages/*`;
- view-model helpers such as `mainPageViewModel.ts`;
- API-to-UI mapping helpers such as `shared/api/productErrors.ts`;
- fixtures and tests.

Important examples:

- `TaskTreePanel.tsx` owns empty/generating state strings.
- `ContextInputPanel.tsx` splits the hardcoded `"Writing to "` prefix.
- `productErrors.ts` maps recovery action codes to English labels and
  descriptions.
- Settings and first-run routes contain many button, field, and error labels.
- `mainPageCopy.ts` and `settingsCopy.ts` already act as page-local copy
  adapters, but they are not bilingual and are not shared product contracts.
- `auditPageLabels.ts` centralizes part of the Audit page chrome, but it is
  still English-only and page-specific.
- View-model helpers such as `mainPageViewModel.ts` create some display labels
  from backend facts, so they need an adapter strategy rather than ad hoc
  string replacement.

The implementation should introduce a shared layer before migrating surfaces.

## 3. Design Decisions

### 3.1 Build A Lightweight Typed Registry First

Do not introduce a third-party i18n framework in the first slice.

Reasons:

- the app currently needs two locales and deterministic local runtime behavior;
- the first migration is small and typed TypeScript catalogs are enough;
- avoiding a library keeps Electron/package risk low;
- the main Product 1.1 problem is ownership and key discipline, not complex
  ICU formatting.

Future migration to a library remains possible if pluralization, date/number
formatting, extraction tooling, or translator workflows become real needs.

### 3.2 Frontend Owns Localized System Text

Backend APIs should continue returning stable facts: status codes, recovery
action codes, readiness issue codes, ids, and safe summaries.

Frontend maps those facts to localized UI system text.

Backend-owned display text is allowed only when documented by an API contract,
and it must not contain raw internal payloads.

### 3.3 LLM Content Is Outside The Registry

LLM prompts and LLM outputs must not be placed in the UI system text registry.

Generated task plans, generated asks, task titles, summaries, and answers are
content. Their language policy requires a separate prompt/content governance
decision.

## 4. File Layout

Add a new shared frontend package:

```text
frontend/src/shared/ui-text/
  catalogShape.ts
  enUS.ts
  zhCN.ts
  locale.ts
  UiTextProvider.tsx
  testing.tsx
  index.ts
  uiText.test.tsx
```

Responsibilities:

| File | Responsibility |
|---|---|
| `catalogShape.ts` | `UiLocale`, template types, and `UiTextCatalog` shape. |
| `enUS.ts` | English catalog implementing `UiTextCatalog`. |
| `zhCN.ts` | Chinese catalog implementing `UiTextCatalog`. |
| `locale.ts` | Locale normalization and resolution helpers. |
| `UiTextProvider.tsx` | React context/provider/hook for UI components. |
| `testing.tsx` | Test helpers for rendering React components with a selected locale. |
| `index.ts` | Public exports. |
| `uiText.test.tsx` | Catalog parity, fallback, and template smoke tests. |

Keep this layer independent from `shared/api` so API clients do not import
React or locale state.

### 4.1 Dependency Rules

The dependency direction must stay simple:

```text
app/App.tsx
  -> shared/ui-text

pages/*
  -> shared/ui-text
  -> shared/api

shared/api
  -> shared/ui-text/catalogShape types only when unavoidable
```

Rules:

- `shared/ui-text` must not import `app/*`, page components, React routes, API
  adapters, Electron modules, or sidecar code.
- `locale.ts` should accept a small runtime-env-like object instead of importing
  `PlatoRuntimeEnv` from `app/platoRuntime.ts`.
- `shared/api/productErrors.ts` may expose a compatibility wrapper that uses the
  English catalog, but UI components should prefer passing the active catalog.
- Page-local copy helpers may remain temporarily as adapters, but new shared UI
  system text keys should be added to `shared/ui-text`.

## 5. Catalog Shape

Use explicit TypeScript types for the first implementation. The shape starts
small and grows by migration slice.

```ts
export type UiLocale = "en-US" | "zh-CN";

export type UiTextTemplate<TParams extends Record<string, string | number>> = (
  params: TParams,
) => string;

export type UiTextCatalog = {
  common: {
    actions: {
      cancel: string;
      close: string;
      retry: string;
    };
  };
  main: {
    sidebar: {
      workspaceLabel: string;
      noSessions: string;
      openOrAddWorkspace: string;
      newSession: string;
    };
    empty: {
      noPlanTitle: string;
      noPlanBody: string;
      createFirstSessionTitle: string;
      createFirstSessionBody: string;
    };
    input: {
      contextMessageAriaLabel: string;
      sendMessageAriaLabel: string;
      writingTo: UiTextTemplate<{ target: string }>;
    };
    plan: {
      overviewLabel: string;
      generatingTitle: string;
      generatingBody: string;
      defaultTitle: string;
      overviewPrepared: string;
      overviewSummary: UiTextTemplate<{
        count: number;
        titles: string;
        remainingCount: number;
      }>;
    };
  };
  productError: {
    recovery: Record<ProductRecoveryAction, {
      label: string;
      description: string;
    }>;
  };
};
```

The actual C1 implementation may trim this shape further if it keeps the first
slice smaller. The important rule is that both catalogs satisfy the same
`UiTextCatalog` type.

### 5.1 Key Namespace Rules

Use stable product namespaces:

| Namespace | Content |
|---|---|
| `common` | Shared actions and status words such as retry, close, loading, failed. |
| `main` | Main Page chrome, workspace/session sidebar, task plan chrome, input states. |
| `settings` | Settings modal and first-run readiness copy. |
| `audit` | Audit page navigation, detail labels, empty states, evidence chrome. |
| `diagnostics` | Diagnostic log/export page chrome and safe next actions. |
| `workspace` | Workspace entry, switcher, picker, and add/open actions. |
| `workspaceInspection` | Git/diff/file viewer chrome and status labels. |
| `productError` | User-facing labels/descriptions derived from product error codes. |

Keys must describe the product role, not the English prose:

Allowed:

```text
main.empty.noPlanTitle
settings.actions.saveAndCheck
productError.recovery.openAudit.label
```

Avoid:

```text
main.empty.noTaskPlanYet
settings.buttons.saveAndCheckButtonText
productError.openAuditEnglishLabel
```

### 5.2 Non-Text Values Stay Out Of Catalogs

Do not store these values in UI text catalogs:

- CSS class names;
- route paths;
- API endpoint paths;
- feature flags;
- test ids;
- icon names;
- provider ids;
- task/session/workspace ids;
- raw file paths;
- generated or user-authored content.

## 6. Template Rules

Use template functions when grammar or word order can vary by locale.

Allowed:

```ts
uiText.main.input.writingTo({ target: taskLabel });
```

Avoid:

```ts
"Writing to " + taskLabel;
```

For C1, template params should be limited to `string | number`. Rich React
nodes, markdown, HTML, and interpolation of untrusted content are out of scope.

If a string needs plural rules that are awkward in simple functions, keep the
template function explicit rather than introducing a formatter library.

## 7. Locale Resolution

Add `VITE_PLATO_UI_LOCALE` to `PlatoRuntimeEnv` as an optional test/dev
override:

```ts
export type PlatoRuntimeEnv = {
  VITE_PLATO_UI_LOCALE?: string;
  // existing fields...
};
```

Add optional Electron runtime field:

```ts
type PlatoElectronRuntimeConfig = {
  uiLocale?: string;
  // existing fields...
};
```

Resolution order:

1. explicit provider prop or test override;
2. `runtimeEnv.VITE_PLATO_UI_LOCALE`;
3. `window.platoRuntimeConfig?.uiLocale`;
4. persisted local preference, once Settings selector exists;
5. `navigator.languages` / `navigator.language`;
6. fallback `en-US`.

Supported normalization:

| Input | Locale |
|---|---|
| `zh`, `zh-CN`, `zh-Hans` | `zh-CN` |
| `en`, `en-US`, `en-GB` | `en-US` |
| unknown / empty | `en-US` |

C1 may implement persisted preference as a no-op placeholder. The visible
Settings selector is a later slice.

### 7.1 Locale Source Contract

Resolution should accept these optional inputs:

```ts
type ResolveUiLocaleInput = {
  explicitLocale?: string | null;
  runtimeEnv?: {
    VITE_PLATO_UI_LOCALE?: string;
  };
  electronRuntimeLocale?: string | null;
  navigatorLanguages?: readonly string[];
};
```

The resolver should not directly read React state. It may read `navigator` only
through a small default branch so tests can pass deterministic inputs.

When Settings later adds a language selector, persisted preference should be
inserted before Electron/browser language and after explicit test/runtime
overrides.

## 8. React Integration

Wrap the app content in `UiTextProvider` near the top of `App`.

Target shape:

```tsx
export function App(props: AppProps = {}) {
  const runtimeEnv = props.runtimeEnv ?? resolvePlatoRuntimeEnv();
  const uiLocale = resolveUiLocale({ runtimeEnv });

  return (
    <UiTextProvider locale={uiLocale}>
      <AppErrorBoundary>{/* existing routes */}</AppErrorBoundary>
    </UiTextProvider>
  );
}
```

Hook:

```ts
export function useUiText(): UiTextCatalog;
export function useUiLocale(): UiLocale;
```

Non-React helper:

```ts
export function getUiText(locale: UiLocale): UiTextCatalog;
```

Use the non-React helper in pure mapping utilities such as product error label
mapping only when a React hook is unavailable.

### 8.1 View-Model Integration

View-model helpers should not call React hooks. Use one of these approaches:

1. Pure view-model builders accept an optional `uiText: UiTextCatalog` argument
   and default to `en-US` for compatibility.
2. Page controllers keep existing view-model output unchanged and React
   components map specific display labels at render time.
3. Page-local adapters translate old copy helper values to catalog entries
   during migration.

Preferred C1 approach:

- localize React component chrome first;
- keep view-model generated labels stable unless the label is clearly system
  text and the builder can accept `uiText` without broad refactoring;
- if `mainPageViewModel.ts` needs production edits and is over the
  maintainability threshold, run the maintainability gate before touching it.

Do not localize backend-generated task names, task descriptions, Collaborator
asks, or user messages through view-model changes.

## 9. Product Error Label Migration

`shared/api/productErrors.ts` currently returns English labels/descriptions.

First migration option:

```ts
export function productRecoveryActionText(
  action: ProductRecoveryAction,
  uiText: UiTextCatalog,
) {
  return uiText.productError.recovery[action];
}
```

Keep existing `productRecoveryActionLabel(action)` as a compatibility wrapper
returning `en-US` until call sites migrate:

```ts
export function productRecoveryActionLabel(action: ProductRecoveryAction): string {
  return productRecoveryActionText(action, enUS).label;
}
```

This avoids a broad one-shot migration and keeps existing tests stable while new
components can use localized text.

## 10. Main Page C1 Migration Boundary

C1 should migrate only high-value, low-risk Main Page text:

- sidebar labels:
  - workspace label;
  - no sessions;
  - new session;
  - open/add workspace;
- empty states:
  - no task plan title/body;
  - create first session title/body;
- input labels:
  - context message aria label;
  - send message aria label;
  - writing-to prefix/template;
- plan overview chrome:
  - plan overview label;
  - generating plan title/body;
  - default plan title;
- product recovery action labels/descriptions.

C1 should not migrate:

- generated task titles or descriptions;
- task plan content from backend snapshots;
- user messages;
- Settings route;
- Audit route;
- Diagnostics route;
- Workspace Inspection route;
- Electron native menu labels.

### 10.1 Main Page Adapter Details

Main Page has three different text sources:

| Source | Treatment |
|---|---|
| UI chrome in React components | Move to `uiText.main.*`. |
| Stable code-to-label mappings, such as product recovery actions | Move to `uiText.productError.*`. |
| Snapshot/task/user/generated content | Do not localize in this registry. |

`mainPageCopy.ts` can become a temporary bridge that re-exports catalog values,
but the long-term owner should be `shared/ui-text`.

The first implementation should not remove backend snapshot fields such as
`workflow`, `title`, `description`, `status`, or `audit.label`; it should only
change how renderer-owned chrome is displayed.

## 11. Testing Strategy

Add focused tests:

1. catalog key parity:
   - every `en-US` leaf exists in `zh-CN`;
   - every `zh-CN` leaf exists in `en-US`;
   - functions count as leaf values;
2. locale normalization:
   - `zh`, `zh-CN`, `zh-Hans` -> `zh-CN`;
   - `en`, `en-US`, `en-GB` -> `en-US`;
   - unsupported -> `en-US`;
3. provider fallback:
   - `UiTextProvider` renders `en-US` when locale is unsupported;
4. Main Page smoke:
   - render one no-plan state in `en-US`;
   - render the same no-plan state in `zh-CN`;
5. product recovery labels:
   - all known `ProductRecoveryAction` values have both locale labels and
     descriptions.
6. component migration smoke:
   - render one Main Page empty/no-plan state using `renderWithUiText("en-US")`;
   - render the same state using `renderWithUiText("zh-CN")`;
   - assert by visible product text only where localized text is the contract.
7. compatibility wrappers:
   - `productRecoveryActionLabel(action)` continues returning English until all
     old call sites migrate;
   - new `productRecoveryActionText(action, uiText)` returns active locale text.

Existing tests should prefer roles and stable structure. Exact text assertions
should either:

- use `getUiText("en-US")` for English expectations; or
- be changed to role/structure assertions when text is not the behavior under
  test.

### 11.1 Test Helper Contract

Add a helper shaped like:

```tsx
export function renderWithUiText(
  ui: React.ReactElement,
  options?: { locale?: UiLocale },
) {
  return render(
    <UiTextProvider locale={options?.locale ?? "en-US"}>{ui}</UiTextProvider>,
  );
}
```

Tests should import this helper instead of manually creating providers in each
component test.

Do not rewrite every test in the first slice. Only update tests for components
whose text moved into the registry.

## 12. Build And Runtime Safety

The registry must be static imports only. Do not fetch catalogs at runtime in
C1.

Rules:

- no network fetch for translations;
- no dynamic `eval` or HTML interpolation;
- no raw backend message localization;
- no automatic translation;
- no locale-dependent API request shape changes;
- no secrets or workspace paths in catalog entries.

## 13. Accessibility Rules

Localized system text must cover accessible names as well as visible labels.

When migrating a control:

- update visible label and `aria-label` together when they represent the same
  action;
- keep icon-only buttons accessible;
- keep test selectors based on role/name only when the name is a stable product
  contract.

C1 should avoid changing layout or component density.

## 14. Migration Workflow

Each migration slice should follow this sequence:

1. add keys to `UiTextCatalog`;
2. add entries to `enUS` and `zhCN`;
3. add or update parity tests;
4. migrate the component;
5. update affected tests;
6. run focused tests;
7. avoid unrelated visual changes.

Do not add a broad lint ban on all string literals in C1. Many strings are data,
test names, CSS class names, ARIA roles, or generated fixtures. A later lint
slice can add a targeted check for JSX text under selected directories after
the registry proves stable.

### 14.1 Slice Boundaries

Recommended implementation order:

| Slice | Scope | Exit Criteria |
|---|---|---|
| C1 | Registry, locale resolver, provider, product-error mapper, one Main Page smoke. | Catalog parity tests pass and app still defaults to English. |
| C2 | Main Page full chrome migration. | Sidebar, top bar, empty states, plan chrome, input labels, recovery labels bilingual. |
| C3 | Settings and first-run migration. | Settings modal and first-run blocked/degraded paths bilingual. |
| C4 | Audit/Diagnostics/Workspace Inspection migration. | Technical pages keep evidence raw but chrome bilingual. |
| C5 | Backend code-to-label audit. | User-facing backend display strings are either stable codes or documented exceptions. |
| C6 | Settings language preference. | User can switch locale without restarting; preference persists locally. |
| C7 | Bilingual acceptance. | Sidecar/Electron smoke can force `en-US` and `zh-CN`. |

Each slice should be separately reviewable. Avoid a single PR that changes all
visible UI copy across the app.

## 15. C1 Implementation Checklist

Files to add:

- `frontend/src/shared/ui-text/catalogShape.ts`
- `frontend/src/shared/ui-text/enUS.ts`
- `frontend/src/shared/ui-text/zhCN.ts`
- `frontend/src/shared/ui-text/locale.ts`
- `frontend/src/shared/ui-text/UiTextProvider.tsx`
- `frontend/src/shared/ui-text/testing.tsx`
- `frontend/src/shared/ui-text/index.ts`
- `frontend/src/shared/ui-text/uiText.test.tsx`

Files likely to modify:

- `frontend/src/vite-env.d.ts`
- `frontend/src/app/platoRuntime.ts`
- `frontend/src/app/App.tsx`
- selected Main Page components and tests;
- `frontend/src/shared/api/productErrors.ts` and tests.

Recommended first checks:

```text
npm run test -- --run src/shared/ui-text src/pages/main-page src/shared/api/productErrors.test.ts
npm run build
```

### 15.1 C1 Non-Goals

C1 must not:

- add a visible language selector;
- persist a language preference;
- localize Electron native menus;
- rewrite generated content;
- add backend localized fields;
- add network-loaded translation bundles;
- change visual layout, spacing, or component density;
- change API response shapes.

### 15.2 File Review Notes

Before C1 implementation, inspect line counts for large files. If adding
production behavior to a file over the maintainability threshold, run the
maintainability gate and either proceed narrowly or split the change.

Likely sensitive files:

- `frontend/src/pages/main-page/mainPageViewModel.ts`;
- `frontend/src/pages/main-page/MainPage.tsx`;
- Settings route files if copy and state logic are mixed.

The registry itself should stay small and easy to review.

## 16. Deferred Work

- centralized backend-owned language preference, if broader settings ownership
  is accepted;
- Electron native menu localization;
- Settings/first-run migration;
- Audit/Diagnostics/Workspace Inspection migration;
- extraction tooling for translators;
- LLM prompt/content language governance;
- generated task/ask language policy.

## 17. Acceptance Criteria

The technical design was accepted for the implemented foundation when:

- the shared `ui-text` file layout was implemented;
- the locale resolution order was implemented;
- C1-C4 foundation migration boundaries were implemented;
- product error compatibility wrapper strategy was implemented;
- test strategy was implemented;
- LLM input/output exclusion remains explicit.

## 18. Review Checklist

Reviewer should confirm:

- `shared/ui-text` is the right ownership location;
- C1 should not include a visible language selector;
- `en-US` should remain the fallback locale;
- `zh-CN` should use natural Chinese rather than literal translation;
- existing English compatibility wrappers are acceptable during migration;
- backend should continue returning stable codes/facts instead of localized
  strings;
- generated/user-authored/LLM content remains out of scope.

## 19. Open Implementation Questions

Resolved for the implemented foundation:

1. Migrated components read directly from `shared/ui-text`; page-local copy
   helpers now act only as small adapters where still useful.
2. `auditPageLabels.ts` remains the Audit code-to-label adapter, now with active
   catalog support and English defaults for compatibility.
3. A small Settings language selector now writes a renderer-local persisted
   locale preference; runtime override / Electron runtime `uiLocale` remain
   supported inputs.
4. Exact English assertions were migrated only where touched by this slice;
   broader test assertion cleanup is deferred.
