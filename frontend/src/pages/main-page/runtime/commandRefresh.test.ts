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
      recoveryActions: [],
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
      recoveryActions: [],
      shouldRefetch: true,
    });
  });

  it("returns a structured error and refetch hint for rejected commands", () => {
    expect(
      handleCommandResponse(
        {
          ...acceptedCommandResponse({
            emittedMessageIds: [],
            waitForEvents: false,
          }),
          ok: false,
          result: null,
          error: {
            code: "command_rejected",
            details: {
              recoveryActions: ["refresh_snapshot", "retry_command"],
            },
            message: "No permission.",
            retryable: false,
          },
        },
        "fallback rejected",
      ),
    ).toEqual({
      errorMessage: "No permission.",
      recoveryActions: ["refresh_snapshot", "retry_command"],
      shouldRefetch: true,
    });
  });

  it("maps missing LLM API key rejections to settings recovery", () => {
    expect(
      handleCommandResponse(
        {
          ...acceptedCommandResponse({
            emittedMessageIds: [],
            waitForEvents: false,
          }),
          ok: false,
          result: null,
          error: {
            code: "command_rejected",
            details: {
              recoveryActions: ["refresh_snapshot"],
            },
            message:
              "session message rejected: raw_task proposal failed: DEEPSEEK_API_KEY or LLM_API_KEY is required for LLM_PROVIDER=deepseek.",
            retryable: false,
          },
        },
        "fallback rejected",
      ),
    ).toEqual({
      errorMessage:
        "LLM API key is missing. Open Settings and configure DEEPSEEK_API_KEY or LLM_API_KEY before sending a task.",
      recoveryActions: ["open_settings", "refresh_snapshot"],
      shouldRefetch: true,
    });
  });

  it("does not refetch rejected commands without refresh hints", () => {
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
      recoveryActions: [],
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
