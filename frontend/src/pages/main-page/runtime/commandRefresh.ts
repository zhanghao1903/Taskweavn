import type { ProductRecoveryAction } from "../../../shared/api/platoApi";
import type { CommandResponse } from "../../../shared/api/types";
import {
  normalizeProductRecoveryActions,
  productRecoveryActionsFromApiError,
} from "../../../shared/api/productErrors";

export type CommandHandlingResult = {
  errorMessage: string | null;
  recoveryActions: ProductRecoveryAction[];
  shouldRefetch: boolean;
};

export function handleCommandResponse(
  response: CommandResponse,
  fallbackRejectedMessage: string,
): CommandHandlingResult {
  if (!response.ok || response.result?.status !== "accepted") {
    const errorMessage = response.error?.message ?? fallbackRejectedMessage;
    return {
      errorMessage: readableCommandErrorMessage(errorMessage),
      recoveryActions: readableCommandRecoveryActions(
        errorMessage,
        productRecoveryActionsFromApiError(response.error),
      ),
      shouldRefetch: shouldRefetchFromRefreshHint(response),
    };
  }

  return {
    errorMessage: null,
    recoveryActions: [],
    shouldRefetch: shouldRefetchFromRefreshHint(response),
  };
}

function shouldRefetchFromRefreshHint(response: CommandResponse): boolean {
  if (response.refresh.waitForEvents === false) {
    return true;
  }

  return (
    response.refresh.suggestedQueries.length > 0 ||
    response.refresh.affectedTaskRefs.length > 0 ||
    response.refresh.affectedScopes.length > 0 ||
    (response.result?.emittedMessageIds.length ?? 0) !== 0 ||
    (response.result?.publishedTaskIds.length ?? 0) !== 0
  );
}

function readableCommandErrorMessage(message: string): string {
  if (isMissingLlmApiKeyError(message)) {
    return "LLM API key is missing. Open Settings and configure DEEPSEEK_API_KEY or LLM_API_KEY before sending a task.";
  }
  return message;
}

function readableCommandRecoveryActions(
  message: string,
  actions: ProductRecoveryAction[],
): ProductRecoveryAction[] {
  if (!isMissingLlmApiKeyError(message)) {
    return actions;
  }

  return normalizeProductRecoveryActions(["open_settings", ...actions]);
}

function isMissingLlmApiKeyError(message: string): boolean {
  const normalized = message.toLowerCase();
  return (
    normalized.includes("llm_api_key") &&
    (normalized.includes("api_key") || normalized.includes("api key")) &&
    (normalized.includes("required") || normalized.includes("missing"))
  );
}
