export type { UiLocale, UiTextCatalog, UiTextTemplate } from "./catalogShape";
export { enUS } from "./enUS";
export { zhCN } from "./zhCN";
export {
  DEFAULT_UI_LOCALE,
  getUiText,
  normalizeUiLocale,
  resolveUiLocale,
  SUPPORTED_UI_LOCALES,
  type ResolveUiLocaleInput,
} from "./locale";
export { UiTextProvider, useUiLocale, useUiText } from "./UiTextProvider";
