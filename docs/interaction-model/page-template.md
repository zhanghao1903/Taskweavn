# <Page Name> Interaction Model

> Status: draft
>
> Last Updated: YYYY-MM-DD
>
> Page: `<PageRouteOrName>`
>
> Scope: <one sentence>

## 1. Source of Truth

| Source | Role |
|---|---|
| `<link>` | UX / product source. |
| `<link>` | API contract source. |
| `<link>` | implementation plan source, if any. |

## 2. Component Inventory

| Component | Responsibility | Local UI State | Backend Facts |
|---|---|---|---|
| `<Component>` | <what it does> | <selected id, draft text, mode, etc.> | <snapshot field, query, event, etc.> |

## 3. Interactions

### 3.1 `<Component>`

| ID | Status | User action / trigger | Availability | UI change | Backend / external call | Event / refresh | Notes |
|---|---|---|---|---|---|---|---|
| `PAGE-COMP-001` | `target` | <action> | <conditions> | <state change> | <call id or none> | <event behavior> | <notes> |

## 4. Disabled / Not Allowed Interactions

| ID | Interaction | Reason | Required UI Behavior |
|---|---|---|---|
| `PAGE-NO-001` | <not allowed> | <why> | <disabled/no-op/error> |

## 5. Maintenance Checklist

- [ ] Every visible command has an interaction row.
- [ ] Every API call is registered in [external-calls.md](external-calls.md).
- [ ] Every event-driven UI update is listed.
- [ ] Disabled or planned controls are explicitly marked.
- [ ] The document was updated together with the page implementation.

