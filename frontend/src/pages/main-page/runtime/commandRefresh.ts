import type { CommandResponse } from "../../../shared/api/types";

export type CommandHandlingResult = {
  errorMessage: string | null;
  shouldRefetch: boolean;
};

export function handleCommandResponse(
  response: CommandResponse,
  fallbackRejectedMessage: string,
): CommandHandlingResult {
  if (!response.ok || response.result?.status !== "accepted") {
    return {
      errorMessage: response.error?.message ?? fallbackRejectedMessage,
      shouldRefetch: shouldRefetchFromRefreshHint(response),
    };
  }

  return {
    errorMessage: null,
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
