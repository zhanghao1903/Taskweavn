import { ApiClientError } from "./client";
import type { ProductRecoveryAction } from "./platoApi";
import type { ApiError } from "./types";

export const PRODUCT_RECOVERY_ACTIONS = [
  "edit_input",
  "answer_ask",
  "retry_command",
  "retry_task",
  "refresh_snapshot",
  "wait_for_events",
  "open_audit",
  "open_settings",
  "export_diagnostics",
  "none",
] as const satisfies readonly ProductRecoveryAction[];

const PRODUCT_RECOVERY_ACTION_SET: ReadonlySet<string> = new Set(
  PRODUCT_RECOVERY_ACTIONS,
);

export class ApiResponseError extends Error {
  readonly apiError: ApiError;

  constructor(apiError: ApiError, fallbackMessage: string) {
    super(apiError.message || fallbackMessage);
    this.name = "ApiResponseError";
    this.apiError = apiError;
  }
}

export function apiErrorFromUnknown(error: unknown): ApiError | null {
  if (error instanceof ApiResponseError) {
    return error.apiError;
  }

  if (error instanceof ApiClientError) {
    return apiErrorFromResponseBody(error.responseBody);
  }

  return null;
}

export function productRecoveryActionsFromApiError(
  error: ApiError | null | undefined,
): ProductRecoveryAction[] {
  const rawActions = error?.details.recoveryActions;

  if (!Array.isArray(rawActions)) {
    return [];
  }

  return normalizeProductRecoveryActions(rawActions);
}

export function productRecoveryActionsFromUnknown(
  error: unknown,
): ProductRecoveryAction[] {
  return productRecoveryActionsFromApiError(apiErrorFromUnknown(error));
}

export function normalizeProductRecoveryActions(
  actions: readonly unknown[],
): ProductRecoveryAction[] {
  const normalized: ProductRecoveryAction[] = [];

  for (const action of actions) {
    if (!isProductRecoveryAction(action)) {
      continue;
    }

    if (!normalized.includes(action)) {
      normalized.push(action);
    }
  }

  if (normalized.length > 1 && normalized.includes("none")) {
    return normalized.filter((action) => action !== "none");
  }

  return normalized;
}

export function productRecoveryActionLabel(
  action: ProductRecoveryAction,
): string {
  switch (action) {
    case "edit_input":
      return "Edit input";
    case "answer_ask":
      return "Answer question";
    case "retry_command":
      return "Retry command";
    case "retry_task":
      return "Retry task";
    case "refresh_snapshot":
      return "Refresh session";
    case "wait_for_events":
      return "Wait for updates";
    case "open_audit":
      return "View audit";
    case "open_settings":
      return "Open settings";
    case "export_diagnostics":
      return "Export diagnostics";
    case "none":
      return "No safe recovery action";
  }
}

export function productRecoveryActionDescription(
  action: ProductRecoveryAction,
): string {
  switch (action) {
    case "edit_input":
      return "Change the input and submit again.";
    case "answer_ask":
      return "Answer the pending question before continuing.";
    case "retry_command":
      return "Run the command again after resolving the issue.";
    case "retry_task":
      return "Retry the affected task when retry is available.";
    case "refresh_snapshot":
      return "Refresh the session view to get the latest state.";
    case "wait_for_events":
      return "Wait for sidecar events before taking another action.";
    case "open_audit":
      return "Inspect Audit evidence for the affected session or task.";
    case "open_settings":
      return "Open local provider settings.";
    case "export_diagnostics":
      return "Export a redacted diagnostic bundle.";
    case "none":
      return "No safe product recovery action is available.";
  }
}

function apiErrorFromResponseBody(responseBody: unknown): ApiError | null {
  if (!isObject(responseBody)) {
    return null;
  }

  const error = responseBody.error;
  return isApiError(error) ? error : null;
}

function isApiError(value: unknown): value is ApiError {
  return (
    isObject(value) &&
    typeof value.code === "string" &&
    typeof value.message === "string" &&
    typeof value.retryable === "boolean" &&
    isObject(value.details)
  );
}

function isProductRecoveryAction(
  value: unknown,
): value is ProductRecoveryAction {
  return typeof value === "string" && PRODUCT_RECOVERY_ACTION_SET.has(value);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
