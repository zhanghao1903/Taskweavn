import { describe, expect, it } from "vitest";

import type { SessionMessageView } from "../../shared/api/types";
import { activityItemsFromMessages } from "./mainPageActivityProjection";

describe("mainPageActivityProjection", () => {
  it("preserves durable read-only inquiry evidence refs from message context", () => {
    const activity = activityItemsFromMessages([
      message({
        activityRelatedRefs: [
          {
            id: "session:session-1:status",
            kind: "session",
            label: "Session status",
          },
          {
            id: "record-1",
            kind: "audit",
            label: "Audit record",
          },
        ],
        id: "runtime-input-answer-route-1",
        relatedCommandId: "route-1",
        title: "Read-only question answered",
      }),
    ]);

    expect(activity).toHaveLength(1);
    expect(activity[0]).toMatchObject({
      id: "activity:inquiry:route-1",
      kind: "answer",
      relatedRefs: [
        { id: "session:session-1:status", kind: "session" },
        { id: "record-1", kind: "audit" },
      ],
      sourceId: "route-1",
      sourceKind: "router",
    });
  });

  it("projects archived plan messages as plan update activity", () => {
    const activity = activityItemsFromMessages([
      message({
        body: "**Stored plan**\n\nStored durable plan summary.",
        id: "message-archived-plan",
        title: "Plan archived",
      }),
    ]);

    expect(activity[0]).toMatchObject({
      id: "activity:message:message-archived-plan",
      kind: "plan_updated",
      scopeKind: "session",
      title: "Plan archived",
    });
  });
});

function message(
  overrides: Partial<SessionMessageView> = {},
): SessionMessageView {
  return {
    body: "Session status answer.",
    createdAt: "2026-06-14T00:00:00.000Z",
    id: "message-1",
    kind: "informational",
    relatedCommandId: null,
    relatedConfirmationId: null,
    sessionId: "session-1",
    taskNodeId: null,
    taskRef: null,
    title: "Agent message",
    ...overrides,
  };
}
