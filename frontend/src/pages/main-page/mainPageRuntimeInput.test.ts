import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  MainPageSnapshot,
  RuntimeInputRouteResult,
  SessionActivityItemView,
} from "../../shared/api/types";
import {
  buildRuntimeInputRouteRequest,
  prependRuntimeActivityItems,
  runtimeInputModeFor,
  runtimeInputNotice,
  runtimeInputUserActivity,
} from "./mainPageRuntimeInput";

describe("mainPageRuntimeInput", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("routes obvious questions as read-only ASK input", () => {
    expect(runtimeInputModeFor("What is next?", "append_session_input")).toBe(
      "ask",
    );
    expect(runtimeInputModeFor("是否已经完成", "append_task_input")).toBe("ask");
  });

  it("maps command modes to runtime route modes", () => {
    expect(runtimeInputModeFor("Build the page", "generate_task_tree")).toBe(
      "change",
    );
    expect(runtimeInputModeFor("Use warmer copy", "append_plan_input")).toBe(
      "guide",
    );
    expect(
      runtimeInputModeFor("Continue", "unknown_mode" as never),
    ).toBe("auto");
  });

  it("builds task-scoped runtime input route requests", () => {
    vi.spyOn(Date, "now").mockReturnValue(123);

    const request = buildRuntimeInputRouteRequest({
      content: "Please continue",
      mode: "guide",
      sessionId: "session-1",
      snapshot: {
        activeAsk: { id: "ask-1" },
        activePlan: { id: "plan-1" },
        pendingConfirmations: [{ id: "confirmation-1" }],
      } as MainPageSnapshot,
      target: "task",
      taskNodeId: "task-1",
    });

    expect(request).toMatchObject({
      commandId: "route-input-123",
      content: "Please continue",
      mode: "guide",
      sessionId: "session-1",
      selection: {
        planId: "plan-1",
        scopeKind: "task",
        taskNodeId: "task-1",
      },
      clientState: {
        activeAskId: "ask-1",
        activeConfirmationId: "confirmation-1",
      },
    });
  });

  it("uses an explicit runtime input command id when provided", () => {
    vi.spyOn(Date, "now").mockReturnValue(123);

    const request = buildRuntimeInputRouteRequest({
      commandId: "route-input-explicit",
      content: "Please continue",
      mode: "guide",
      sessionId: "session-1",
      snapshot: null,
      target: "session",
      taskNodeId: null,
    });

    expect(request.commandId).toBe("route-input-explicit");
  });

  it("uses answer content as the runtime notice", () => {
    const result = {
      inquiryResult: {
        answer: {
          body: "Answer body",
          title: "Answer title",
        },
      },
      outcome: {
        userMessage: "Outcome message",
      },
    } as RuntimeInputRouteResult;

    expect(runtimeInputNotice(result)).toBe("Answer title: Answer body");
  });

  it("prepends runtime activity items without duplicating ids", () => {
    const existing = [
      { id: "old-1" },
      { id: "same-1" },
    ] as SessionActivityItemView[];
    const next = [{ id: "same-1" }, { id: "new-1" }] as SessionActivityItemView[];

    expect(prependRuntimeActivityItems(existing, next).map((item) => item.id)).toEqual(
      ["same-1", "new-1", "old-1"],
    );
  });

  it("projects synthetic user activity from route decisions", () => {
    const activity = runtimeInputUserActivity(
      {
        commandId: "command-1",
        content: "Question",
        sessionId: "session-1",
      } as ReturnType<typeof buildRuntimeInputRouteRequest>,
      {
        decision: {
          relatedRefs: [{ id: "session-1", kind: "session" }],
          scope: {
            kind: "session",
            planId: null,
            taskNodeId: null,
          },
        },
        generatedAt: "2026-06-26T00:00:00Z",
      } as RuntimeInputRouteResult,
    );

    expect(activity).toMatchObject({
      body: "Question",
      disclosureLevel: "public",
      kind: "user_input",
      scopeKind: "session",
      sessionId: "session-1",
      sourceId: "command-1",
      sourceKind: "router",
    });
  });
});
