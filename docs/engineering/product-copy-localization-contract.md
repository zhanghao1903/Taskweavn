# UI System Text And Localization Contract

> Status: draft Product 1.1 contract
>
> Last Updated: 2026-06-10
>
> Related plan:
> [UI System Text And Localization Foundation](../plans/feature/product-copy-localization-foundation.md)

## 1. Purpose

This contract defines how Plato manages user-visible UI system text and
bilingual localization without mixing UI text, backend facts, diagnostics, and
LLM input/output contracts.

The goal is a small, typed UI system text registry that can be adopted slice by
slice.

## 2. Locale Contract

Supported Product 1.1 locales:

```ts
type UiLocale = "en-US" | "zh-CN";
```

Locale resolution must be deterministic:

1. explicit runtime or test override;
2. persisted UI locale preference;
3. Electron runtime config;
4. browser / OS language;
5. fallback `en-US`.

Unsupported language tags must map to the closest supported locale when safe:

| Input | Resolved |
|---|---|
| `zh`, `zh-CN`, `zh-Hans` | `zh-CN` |
| `en`, `en-US`, `en-GB` | `en-US` |
| any other value | `en-US` |

## 3. UI Text Key Contract

UI system text keys must be stable and descriptive:

```text
<surface>.<state-or-section>.<element>
```

Examples:

```text
main.sidebar.workspaceLabel
main.empty.noPlanTitle
main.input.sessionPlaceholder
settings.actions.retryCheck
diagnostics.actions.exportBundle
productError.recovery.openAudit
```

Rules:

- keys are product contracts, not implementation details;
- keys should not include English prose;
- keys should not include runtime ids;
- deleted keys must be removed from all locale catalogs in the same change;
- renaming a key is a breaking UI text contract change and should be scoped.

## 4. Catalog Shape

The implementation should expose a typed lookup API equivalent to:

```ts
type CopyPrimitive = string;
type CopyTemplate<TParams extends Record<string, string | number>> = (
  params: TParams,
) => string;

type UiSystemTextCatalog = {
  main: {
    empty: {
      noPlanTitle: CopyPrimitive;
      noPlanBody: CopyPrimitive;
    };
  };
};
```

Template functions must receive explicit params. Components should not assemble
sentences through ad hoc string concatenation when grammar differs by locale.

Allowed:

```ts
copy.main.input.writingTo({ target: taskLabel });
```

Avoid:

```ts
"Writing to " + taskLabel;
```

## 5. Frontend Boundary

Frontend owns final localized UI system text for:

- application menus, command menu options, select options, segmented controls,
  tab labels, labels, buttons, links, headings, placeholders, empty states,
  loading states, disabled reasons, status text, badges, banners, toasts,
  tooltips, and recovery labels;
- labels derived from stable backend enums or codes;
- product error category and recovery action labels;
- Settings and first-run readiness explanations when based on stable issue
  codes.

Components should read copy through a shared helper or hook. Page-specific copy
objects are allowed only as temporary migration adapters and must be local to a
single slice.

## 6. Backend Boundary

Backend should return stable facts:

- ids;
- states;
- statuses;
- categories;
- recovery action codes;
- readiness issue codes;
- evidence ids;
- diagnostic descriptor ids;
- safe file paths and summaries.

Backend should not return localized UI system text unless the text is:

- user-authored;
- LLM-generated content intentionally shown as generated content and not
  treated as system text;
- a documented domain display value that cannot be expressed as a stable code.

If backend-owned display text is unavoidable, the API contract must document:

- why the backend owns the text;
- whether it is localized;
- whether it can contain generated content;
- redaction and safety constraints.

## 7. Diagnostics And Security Rules

Localized UI system text must never be a path for exposing raw internals.

Do not expose raw:

- exceptions;
- prompts;
- provider payloads;
- log payloads;
- SQLite rows;
- secrets;
- absolute local paths in renderer diagnostics.

Diagnostics UI system text should explain the state and next action. Evidence and
bundle contents stay redacted and structured.

## 8. LLM Input / Output Boundary

LLM input and output are not UI system text.

LLM system/developer prompts are behavior-affecting artifacts and require
separate review. The UI system text registry must not silently translate prompts
that control model behavior.

Generated Collaborator asks, task titles, and task descriptions are content,
not UI system text. Their language policy is a Product 1.1 follow-up decision.

## 9. Testing Contract

Required tests for the registry foundation:

- every `en-US` key exists in `zh-CN`;
- every `zh-CN` key exists in `en-US`;
- unsupported locales fall back to `en-US`;
- template copy receives required params;
- at least one component renders in both `en-US` and `zh-CN`.

UI tests should prefer stable roles and structure. Exact text assertions should
use the copy helper when the text itself is the contract.

## 10. Migration Rules

When moving existing UI system text into the registry:

1. keep behavior unchanged;
2. keep accessible names stable unless the slice explicitly changes copy;
3. migrate tests in the same change;
4. avoid broad visual changes;
5. leave user-authored and LLM-generated fixture content alone unless the slice
   is explicitly a generated-content language slice.

## 11. First Implementation Boundary

The first implementation slice should add:

- `UiLocale`;
- locale resolver;
- typed catalogs for `en-US` and `zh-CN`;
- copy lookup/helper;
- catalog parity tests;
- a narrow Main Page migration.

It should not add:

- full Settings language selector;
- backend localization;
- generated task translation;
- LLM prompt translation;
- LLM output translation;
- cloud account language preferences.
