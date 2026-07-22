import { describe, expect, it } from "vitest";

import { ApiClientError } from "./client";
import {
  ApiResponseError,
  apiErrorFromUnknown,
  normalizeProductRecoveryActions,
  productRecoveryActionLabel,
  productRecoveryActionText,
  productRecoveryActionsFromApiError,
  productRecoveryActionsFromUnknown,
} from "./productErrors";
import type { ApiError } from "./types";
import { zhCN } from "../ui-text";

describe("product error recovery metadata", () => {
  it("keeps only known recovery actions and removes duplicates", () => {
    expect(
      normalizeProductRecoveryActions([
        "retry_command",
        "raw_provider_payload",
        "retry_command",
        "open_settings",
      ]),
    ).toEqual(["retry_command", "open_settings"]);
  });

  it("keeps none only when there are no concrete recovery actions", () => {
    expect(normalizeProductRecoveryActions(["none"])).toEqual(["none"]);
    expect(normalizeProductRecoveryActions(["none", "open_audit"])).toEqual([
      "open_audit",
    ]);
  });

  it("extracts recovery actions from ApiError details", () => {
    expect(
      productRecoveryActionsFromApiError(
        apiError({
          recoveryActions: ["refresh_snapshot", "export_diagnostics"],
        }),
      ),
    ).toEqual(["refresh_snapshot", "export_diagnostics"]);
  });

  it("keeps helper-specific macOS recovery actions", () => {
    expect(
      normalizeProductRecoveryActions([
        "open_macos_privacy_accessibility",
        "restart_helper",
        "rerun_readiness_check",
      ]),
    ).toEqual([
      "open_macos_privacy_accessibility",
      "restart_helper",
      "rerun_readiness_check",
    ]);
  });

  it("extracts ApiError details from query and HTTP client failures", () => {
    const error = apiError({ recoveryActions: ["open_settings"] });

    expect(
      productRecoveryActionsFromUnknown(new ApiResponseError(error, "fallback")),
    ).toEqual(["open_settings"]);
    expect(
      apiErrorFromUnknown(
        new ApiClientError({
          method: "GET",
          path: "/api/v1/sessions/session-1/snapshot",
          responseBody: {
            error,
          },
          status: 503,
        }),
      ),
    ).toBe(error);
  });

  it("maps recovery action ids to user-facing labels", () => {
    expect(productRecoveryActionLabel("open_audit")).toBe("View audit");
    expect(productRecoveryActionLabel("none")).toBe(
      "No safe recovery action",
    );
  });

  it("maps recovery action ids through the active UI text catalog", () => {
    expect(productRecoveryActionText("open_audit", zhCN)).toEqual({
      description: "查看受影响会话或任务的审计证据。",
      label: "查看审计",
    });
  });
});

function apiError(details: Record<string, unknown>): ApiError {
  return {
    code: "command_rejected",
    details,
    message: "Command rejected.",
    retryable: false,
  };
}
