import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type { UiTextCatalog } from "../../shared/ui-text";

export function formatRecoveryAction(
  action: ProductRecoveryAction,
  uiText: UiTextCatalog,
): string {
  return uiText.settings.recovery[action];
}

export function settingsProviderLabel(provider: string): string {
  switch (provider) {
    case "litellm":
      return "LiteLLM";
    case "deepseek":
      return "DeepSeek";
    case "openrouter":
      return "OpenRouter";
    default:
      return provider;
  }
}
