import { describe, expect, it } from "vitest";

import type { CommandResponse } from "../../../shared/api/types";
import { handleCommandResponse } from "./commandRefresh";

describe("command response handling", () => {
  it("asks the page to refetch after accepted commands with refresh hints", () => {
    expect(
      handleCommandResponse(
        acceptedCommandResponse({
          emittedMessageIds: ["message-1"],
          waitForEvents: true,
        }),
        "rejected",
      ),
    ).toEqual({
      errorMessage: null,
      shouldRefetch: true,
    });
  });

  it("asks the page to refetch when the backend does not expect events", () => {
    expect(
      handleCommandResponse(
        acceptedCommandResponse({
          emittedMessageIds: [],
          waitForEvents: false,
        }),
        "rejected",
      ),
    ).toEqual({
      errorMessage: null,
      shouldRefetch: true,
    });
  });

  it("returns a structured error for rejected commands", () => {
    expect(
      handleCommandResponse(
        {
          ...acceptedCommandResponse({
            emittedMessageIds: [],
            waitForEvents: true,
          }),
          ok: false,
          result: null,
          error: {
            code: "command_rejected",
            details: {},
            message: "No permission.",
            retryable: false,
          },
        },
        "fallback rejected",
      ),
    ).toEqual({
      errorMessage: "No permission.",
      shouldRefetch: false,
    });
  });
});

function acceptedCommandResponse({
  emittedMessageIds,
  waitForEvents,
}: {
  emittedMessageIds: string[];
  waitForEvents: boolean;
}): CommandResponse {
  return {
    requestId: "request-command",
    ok: true,
    result: {
      commandId: "command-1",
      status: "accepted",
      message: "accepted",
      affectedTaskRefs: [],
      objectRefs: [],
      affectedObjects: [],
      emittedMessageIds,
      publishedTaskIds: [],
      debugRefs: {},
    },
    error: null,
    refresh: {
      waitForEvents,
      suggestedQueries: [],
      affectedTaskRefs: [],
      affectedScopes: [],
    },
  };
}
