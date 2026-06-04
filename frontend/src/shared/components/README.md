# Plato Shared Components

These primitives are the first frontend implementation layer over Plato design
tokens. They should stay product-neutral and avoid embedding Task, Session, or
Message semantics.

## Components

| Component | Purpose |
|---|---|
| `Button` | Commands and icon buttons. Variants: `primary`, `secondary`, `ghost`, `danger`. |
| `Badge` | Compact status and metadata labels. Tones: `neutral`, `blue`, `success`, `warning`, `danger`. |
| `ChoiceGroup` | Domain-neutral single, multi, and segmented option picking. |
| `Panel` | Framed repeated items, sidebars, inspectors, and tool surfaces. |
| `Text` | Stable typography variants over tokenized colors and sizing. |

## Rules

- Keep product object logic outside primitives.
- Prefer token variables from `shared/styles/tokens.css`.
- Keep cards at `8px` radius or less.
- Keep icon-only actions as `Button size="icon"` with an `aria-label`.
- Do not add one-off colors in feature or page components unless a new token is
  deliberately introduced.
