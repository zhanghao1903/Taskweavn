import { describe, expect, it } from "vitest";

import {
  isWorkspaceInspectionPath,
  parseWorkspaceInspectionLocation,
} from "./workspaceInspectionRouteModel";

describe("workspace inspection route model", () => {
  it("parses status routes", () => {
    expect(isWorkspaceInspectionPath("/workspaces/ws-a/inspection")).toBe(true);
    expect(parseWorkspaceInspectionLocation("/workspaces/ws-a/inspection")).toEqual({
      evidenceId: null,
      mode: "status",
      path: null,
      returnSessionId: null,
      returnTaskNodeId: null,
      sessionId: null,
      taskNodeId: null,
      workspaceId: "ws-a",
    });
  });

  it("parses file and diff route context", () => {
    expect(
      parseWorkspaceInspectionLocation(
        "/workspaces/ws%2Fa/inspection",
        "?view=diff&path=src%2FApp.tsx&sessionId=session-1&taskNodeId=task-1",
      ),
    ).toEqual({
      evidenceId: null,
      mode: "diff",
      path: "src/App.tsx",
      returnSessionId: null,
      returnTaskNodeId: null,
      sessionId: "session-1",
      taskNodeId: "task-1",
      workspaceId: "ws/a",
    });
  });

  it("defaults evidence routes to file mode", () => {
    expect(
      parseWorkspaceInspectionLocation(
        "/workspaces/current/inspection",
        "?evidenceId=inspection-1",
      )?.mode,
    ).toBe("file");
  });
});
