import type { UiLocale, UiTextCatalog } from "./catalogShape";
import { enUS } from "./enUS";
import { zhCN } from "./zhCN";

export const DEFAULT_UI_LOCALE: UiLocale = "en-US";

export const SUPPORTED_UI_LOCALES = ["en-US", "zh-CN"] as const satisfies readonly UiLocale[];

type UiLocaleRuntimeEnv = {
  readonly VITE_PLATO_UI_LOCALE?: string;
};

export type ResolveUiLocaleInput = {
  readonly electronRuntimeLocale?: string | null;
  readonly explicitLocale?: string | null;
  readonly navigatorLanguages?: readonly string[];
  readonly persistedLocale?: string | null;
  readonly runtimeEnv?: UiLocaleRuntimeEnv | null;
};

export function normalizeUiLocale(locale: string | null | undefined): UiLocale {
  if (!locale) {
    return DEFAULT_UI_LOCALE;
  }

  const normalized = locale.trim().toLowerCase().replace("_", "-");
  if (normalized === "zh" || normalized.startsWith("zh-cn") || normalized.startsWith("zh-hans")) {
    return "zh-CN";
  }
  if (normalized === "en" || normalized.startsWith("en-")) {
    return "en-US";
  }

  return DEFAULT_UI_LOCALE;
}

export function resolveUiLocale(input: ResolveUiLocaleInput = {}): UiLocale {
  const candidates = [
    input.explicitLocale,
    input.runtimeEnv?.VITE_PLATO_UI_LOCALE,
    input.persistedLocale,
    input.electronRuntimeLocale,
    ...navigatorLanguageCandidates(input.navigatorLanguages),
  ];

  for (const candidate of candidates) {
    if (candidate) {
      return normalizeUiLocale(candidate);
    }
  }

  return DEFAULT_UI_LOCALE;
}

export function getUiText(locale: UiLocale): UiTextCatalog {
  switch (locale) {
    case "zh-CN":
      return zhCN;
    case "en-US":
      return enUS;
  }
}

function navigatorLanguageCandidates(
  explicitLanguages: readonly string[] | undefined,
): readonly string[] {
  if (explicitLanguages) {
    return explicitLanguages;
  }

  const navigatorObject = globalThis.navigator;
  if (!navigatorObject) {
    return [];
  }

  if (Array.isArray(navigatorObject.languages) && navigatorObject.languages.length > 0) {
    return navigatorObject.languages;
  }

  return navigatorObject.language ? [navigatorObject.language] : [];
}
