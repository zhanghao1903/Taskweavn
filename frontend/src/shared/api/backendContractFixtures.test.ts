import { describe, expect, it } from "vitest";

import commandResponseFixture from "../../../../tests/fixtures/ui_contract/command_response.accepted.json";
import snapshotResponseFixture from "../../../../tests/fixtures/ui_contract/main_page_snapshot.min.json";
import uiEventFixture from "../../../../tests/fixtures/ui_contract/ui_event.message_appended.json";
import type {
  CommandResponse,
  MainPageSnapshot,
  QueryResponse,
  UiEvent,
} from "./types";

describe("backend-generated UI contract fixtures", () => {
  it("loads the MainPageSnapshot query fixture through frontend types", () => {
    const response: unknown = snapshotResponseFixture;
    expectMainPageSnapshotResponse(response);

    expect(response.ok).toBe(true);
    expect(response.error).toBeNull();

    const snapshot = expectPresent(response.data);
    expect(snapshot.session.status).toBe("draft_ready");
    expect(snapshot.taskTree?.nodes[0]).toMatchObject({
      id: "draft-1",
      planId: "plan:legacy:session-1",
      taskIndex: "1",
      taskRef: {
        id: "draft-1",
        kind: "draft",
      },
    });
    expect(snapshot.activePlan).toMatchObject({
      id: "plan:legacy:session-1",
      status: "draft",
      taskNodeIds: ["draft-1"],
    });
    expect(snapshot.activePlan?.taskNodes[0]).toMatchObject({
      id: "draft-1",
      planId: "plan:legacy:session-1",
      taskIndex: "1",
    });
    expect(snapshot.activePlan?.taskTreeProjection?.nodes[0]).toMatchObject({
      id: "draft-1",
      planId: "plan:legacy:session-1",
      taskIndex: "1",
    });
    expect(snapshot.pendingConfirmations[0].defaultOptionValue).toBe("yes");
  });

  it("loads the CommandResponse fixture through frontend types", () => {
    const response: unknown = commandResponseFixture;
    expectCommandResponse(response);

    expect(response.ok).toBe(true);
    expect(response.error).toBeNull();
    expect(response.result?.objectRefs).toEqual([
      {
        id: "raw-1",
        kind: "raw_task",
      },
    ]);
    expect(response.refresh.affectedScopes[0]).toMatchObject({
      kind: "task_tree",
      reason: "Draft tree changed.",
    });
  });

  it("loads the UiEvent fixture through frontend types", () => {
    const event: unknown = uiEventFixture;
    expectUiEvent(event);

    expect(event.eventType).toBe("message.appended");
    expect(event.taskRefs?.[0]).toEqual({
      id: "draft-1",
      kind: "draft",
    });
    expect(event.payload).toMatchObject({
      agent_id: "collaborator",
      message_type: "informational",
    });
  });
});

function expectMainPageSnapshotResponse(
  value: unknown,
): asserts value is QueryResponse<MainPageSnapshot> {
  expectRecord(value);
  expect(value.ok).toBe(true);
  expect(value.data).toEqual(
    expect.objectContaining({
      project: expect.objectContaining({ id: "project-local" }),
      session: expect.objectContaining({ status: "draft_ready" }),
      taskTree: expect.objectContaining({ id: "tree-1" }),
    }),
  );
}

function expectCommandResponse(value: unknown): asserts value is CommandResponse {
  expectRecord(value);
  expect(value.ok).toBe(true);
  expect(value.result).toEqual(
    expect.objectContaining({
      commandId: "command-1",
      status: "accepted",
    }),
  );
}

function expectUiEvent(value: unknown): asserts value is UiEvent {
  expectRecord(value);
  expect(value.eventType).toBe("message.appended");
  expect(value.sessionId).toBe("session-1");
}

function expectPresent<T>(value: T | null | undefined): T {
  expect(value).not.toBeNull();
  expect(value).not.toBeUndefined();
  if (value === null || value === undefined) {
    throw new Error("Expected value to be present.");
  }
  return value;
}

function expectRecord(value: unknown): asserts value is Record<string, unknown> {
  expect(typeof value).toBe("object");
  expect(value).not.toBeNull();
  if (typeof value !== "object" || value === null) {
    throw new Error("Expected object.");
  }
}
