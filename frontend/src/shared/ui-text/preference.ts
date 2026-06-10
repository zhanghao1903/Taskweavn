import type { UiLocale } from "./catalogShape";
import { normalizeUiLocale } from "./locale";

export const UI_LOCALE_PREFERENCE_STORAGE_KEY = "plato.uiLocale";
export const UI_LOCALE_PREFERENCE_CHANGED_EVENT =
  "plato.uiLocalePreferenceChanged";

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export function readUiLocalePreference(
  storage: StorageLike | null | undefined = safeLocalStorage(),
): UiLocale | null {
  if (storage === null || storage === undefined) {
    return null;
  }

  try {
    const stored = storage.getItem(UI_LOCALE_PREFERENCE_STORAGE_KEY);
    if (!stored || !isRecognizedUiLocaleTag(stored)) {
      return null;
    }
    return normalizeUiLocale(stored);
  } catch {
    return null;
  }
}

export function writeUiLocalePreference(
  locale: UiLocale,
  storage: StorageLike | null | undefined = safeLocalStorage(),
  eventTarget: Pick<typeof globalThis, "dispatchEvent"> | null | undefined =
    globalThis,
): void {
  if (storage !== null && storage !== undefined) {
    try {
      storage.setItem(UI_LOCALE_PREFERENCE_STORAGE_KEY, locale);
    } catch {
      // Ignore storage failures; the current runtime locale can still update.
    }
  }

  try {
    eventTarget?.dispatchEvent(
      new CustomEvent(UI_LOCALE_PREFERENCE_CHANGED_EVENT, {
        detail: { locale },
      }),
    );
  } catch {
    // Older test environments may not support CustomEvent construction.
  }
}

function safeLocalStorage(): StorageLike | null {
  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}

function isRecognizedUiLocaleTag(locale: string): boolean {
  const normalized = locale.trim().toLowerCase().replace("_", "-");
  return (
    normalized === "zh" ||
    normalized.startsWith("zh-cn") ||
    normalized.startsWith("zh-hans") ||
    normalized === "en" ||
    normalized.startsWith("en-")
  );
}
