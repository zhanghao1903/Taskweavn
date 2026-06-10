import {
  createContext,
  useContext,
  useMemo,
  type PropsWithChildren,
} from "react";

import type { UiLocale, UiTextCatalog } from "./catalogShape";
import { DEFAULT_UI_LOCALE, getUiText } from "./locale";

type UiTextContextValue = {
  locale: UiLocale;
  text: UiTextCatalog;
};

const UiTextContext = createContext<UiTextContextValue>({
  locale: DEFAULT_UI_LOCALE,
  text: getUiText(DEFAULT_UI_LOCALE),
});

export type UiTextProviderProps = PropsWithChildren<{
  locale?: UiLocale;
}>;

export function UiTextProvider({
  children,
  locale = DEFAULT_UI_LOCALE,
}: UiTextProviderProps) {
  const value = useMemo<UiTextContextValue>(
    () => ({
      locale,
      text: getUiText(locale),
    }),
    [locale],
  );

  return (
    <UiTextContext.Provider value={value}>{children}</UiTextContext.Provider>
  );
}

export function useUiText(): UiTextCatalog {
  return useContext(UiTextContext).text;
}

export function useUiLocale(): UiLocale {
  return useContext(UiTextContext).locale;
}
