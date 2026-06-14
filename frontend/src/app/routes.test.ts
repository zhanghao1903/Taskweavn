import { describe, expect, it } from "vitest";

import {
  buildAuditSessionRoute,
  buildAuditTaskRoute,
  buildDiagnosticsLogsRoute,
  buildMainSessionFallbackRoute,
  buildMainSessionRoute,
  buildWorkspaceInspectionRoute,
  buildWorkspaceUsageRoute,
  routes,
} from "./routes";

describe("route builders", () => {
  it("keeps legacy root route while exposing target route patterns", () => {
    expect(routes.main).toBe("/");
    expect(routes.mainSession).toBe(
      "/projects/:projectId/workflows/:workflowId/sessions/:sessionId",
    );
    expect(routes.auditTask).toBe(
      "/sessions/:sessionId/tasks/:taskNodeId/audit",
    );
    expect(routes.workspaceInspection).toBe("/workspaces/:workspaceId/inspection");
    expect(routes.workspaceUsage).toBe("/workspaces/:workspaceId/usage");
  });

  it("builds contextual Main Page session routes", () => {
    expect(
      buildMainSessionRoute({
        projectId: "project local",
        sessionId: "session-1",
        taskNodeId: "task/a",
        workflowId: "workflow-main",
      }),
    ).toBe(
      "/projects/project%20local/workflows/workflow-main/sessions/session-1?taskNodeId=task%2Fa",
    );
  });

  it("builds fallback Main Page session routes", () => {
    expect(
      buildMainSessionFallbackRoute({
        sessionId: "session-1",
        taskNodeId: "task-2",
      }),
    ).toBe("/sessions/session-1?taskNodeId=task-2");
  });

  it("builds session-scoped Audit routes with return context", () => {
    expect(
      buildAuditSessionRoute("session-1", {
        entry: "from_session",
        filter: "risks",
        recordId: "record-1",
        returnFocus: "session",
      }),
    ).toBe(
      "/sessions/session-1/audit?entry=from_session&filter=risks&recordId=record-1&returnFocus=session",
    );
  });

  it("builds task-scoped Audit routes with preserved task context", () => {
    expect(
      buildAuditTaskRoute("session-1", "task-1", {
        entry: "from_confirmation",
        evidenceId: "evidence-1",
        filter: "confirmations",
        returnFocus: "confirmation",
        returnTaskNodeId: "task-1",
      }),
    ).toBe(
      "/sessions/session-1/tasks/task-1/audit?entry=from_confirmation&evidenceId=evidence-1&filter=confirmations&returnFocus=confirmation&returnTaskNodeId=task-1",
    );
  });

  it("builds diagnostics log links as reserved routes", () => {
    expect(
      buildDiagnosticsLogsRoute({
        category: "audit",
        recordId: "record-1",
        sessionId: "session-1",
        taskNodeId: "task-1",
      }),
    ).toBe(
      "/sessions/session-1/diagnostics/logs?category=audit&recordId=record-1&taskNodeId=task-1",
    );
  });

  it("builds workspace inspection links with return context", () => {
    expect(
      buildWorkspaceInspectionRoute({
        path: "src/App.tsx",
        returnSessionId: "session-1",
        returnTaskNodeId: "task-1",
        sessionId: "session-1",
        taskNodeId: "task-1",
        view: "diff",
        workspaceId: "workspace/a",
      }),
    ).toBe(
      "/workspaces/workspace%2Fa/inspection?path=src%2FApp.tsx&returnSessionId=session-1&returnTaskNodeId=task-1&sessionId=session-1&taskNodeId=task-1&view=diff",
    );
  });

  it("builds workspace usage links with optional focus context", () => {
    expect(
      buildWorkspaceUsageRoute({
        planId: "plan/1",
        sessionId: "session-1",
        taskNodeId: "task-1",
        workspaceId: "workspace/a",
      }),
    ).toBe(
      "/workspaces/workspace%2Fa/usage?planId=plan%2F1&sessionId=session-1&taskNodeId=task-1",
    );
  });
});
