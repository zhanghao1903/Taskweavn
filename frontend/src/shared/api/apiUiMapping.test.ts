import { describe, expect, it } from "vitest";

import {
  actionAvailabilityForBoundary,
  mapApiErrorToUiBoundary,
  mapAuditSnapshotToUiBoundary,
  mapQueryResponseToUiBoundary,
} from "./apiUiMapping";
import { getAuditMockSnapshot } from "../../pages/audit-page/mockAuditScenarios";
import type { ApiError, QueryResponse } from "./types";

describe("API to UI boundary mapping", () => {
  it("maps resync-class API errors into stale/resync boundary state", () => {
    for (const code of ["version_conflict", "resync_required"] as const) {
      const boundary = mapApiErrorToUiBoundary(apiError(code));

      expect(boundary).toMatchObject({
        disableMutations: true,
        kind: "stale_resync",
        retryable: true,
        shouldResync: true,
      });
      expect(actionAvailabilityForBoundary(boundary)).toBe("disabled_stale");
    }
  });

  it("keeps permission denied distinct from generic errors", () => {
    const boundary = mapApiErrorToUiBoundary(
      apiError("permission_denied", "Cannot view audit."),
    );

    expect(boundary).toMatchObject({
      disableMutations: true,
      kind: "permission_denied",
      message: "Cannot view audit.",
      shouldResync: false,
    });
    expect(actionAvailabilityForBoundary(boundary)).toBe(
      "disabled_permission",
    );
  });

  it("maps backend busy to pending command availability", () => {
    const boundary = mapApiErrorToUiBoundary(apiError("backend_busy"));

    expect(boundary).toMatchObject({
      disableMutations: true,
      kind: "backend_busy",
      retryable: true,
    });
    expect(actionAvailabilityForBoundary(boundary)).toBe("pending_command");
  });

  it("maps query envelopes without exposing transport details to components", () => {
    const failed: QueryResponse<unknown> = {
      data: null,
      error: apiError("internal_error", "Projection failed."),
      generatedAt: "2026-05-24T10:00:00Z",
      ok: false,
      requestId: "request-failed",
    };
    const missingData: QueryResponse<unknown> = {
      data: null,
      error: null,
      generatedAt: "2026-05-24T10:00:00Z",
      ok: true,
      requestId: "request-empty",
    };

    expect(mapQueryResponseToUiBoundary(failed)).toMatchObject({
      kind: "recoverable_error",
      message: "Projection failed.",
    });
    expect(mapQueryResponseToUiBoundary(missingData)).toMatchObject({
      kind: "empty",
    });
  });

  it("maps Audit permission, stale, and query-error snapshots distinctly", () => {
    expect(
      mapAuditSnapshotToUiBoundary(getAuditMockSnapshot("a11-permission-denied")),
    ).toMatchObject({
      kind: "permission_denied",
      disableMutations: true,
    });

    expect(
      mapAuditSnapshotToUiBoundary(getAuditMockSnapshot("a12-stale-snapshot")),
    ).toMatchObject({
      kind: "stale_resync",
      shouldResync: true,
    });

    expect(
      mapAuditSnapshotToUiBoundary(getAuditMockSnapshot("a13-query-error")),
    ).toMatchObject({
      kind: "recoverable_error",
      retryable: true,
    });
  });
});

function apiError(
  code: ApiError["code"],
  message = `${code} message`,
): ApiError {
  return {
    code,
    details: {},
    message,
    retryable: true,
  };
}
