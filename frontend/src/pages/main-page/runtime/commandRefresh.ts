import type { ProductRecoveryAction } from "../../../shared/api/platoApi";
import type { CommandResponse } from "../../../shared/api/types";
import { productRecoveryActionsFromApiError } from "../../../shared/api/productErrors";

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
    return {
      errorMessage: response.error?.message ?? fallbackRejectedMessage,
      recoveryActions: productRecoveryActionsFromApiError(response.error),
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
