import type { ProductRecoveryAction } from "../../shared/api/platoApi";

export function formatRecoveryAction(action: ProductRecoveryAction): string {
  switch (action) {
    case "open_settings":
      return "Configure local provider settings.";
    case "export_diagnostics":
      return "Export a redacted diagnostic bundle.";
    case "retry_command":
    case "refresh_snapshot":
      return "Retry after configuration changes.";
    case "wait_for_events":
      return "Wait for sidecar events before retrying.";
    case "edit_input":
      return "Edit the current input.";
    case "answer_ask":
      return "Answer the pending question.";
    case "retry_task":
      return "Retry the affected Task.";
    case "open_audit":
      return "Inspect Audit evidence.";
    case "none":
      return "No recovery action is available.";
  }
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
