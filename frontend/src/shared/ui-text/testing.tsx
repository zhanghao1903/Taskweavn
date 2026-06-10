import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement } from "react";

import type { UiLocale } from "./catalogShape";
import { UiTextProvider } from "./UiTextProvider";

export function renderWithUiText(
  ui: ReactElement,
  options: RenderOptions & { locale?: UiLocale } = {},
) {
  const { locale = "en-US", ...renderOptions } = options;
  return render(
    <UiTextProvider locale={locale}>{ui}</UiTextProvider>,
    renderOptions,
  );
}
