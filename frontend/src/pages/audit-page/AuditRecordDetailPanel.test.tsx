import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AuditRecordDetail } from "../../shared/api/types";
import { DetailPanel } from "./AuditRecordDetailPanel";

describe("AuditRecordDetailPanel", () => {
  it("links file-change records to workspace inspection file and diff views", () => {
    render(
      <DetailPanel
        detailState={{ isLoading: false }}
        effectiveConfig={null}
        record={fileChangeRecord}
        relatedLogs={[]}
        workspaceId="ws-a"
      />,
    );

    expect(screen.getByText("Workspace evidence")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open file" })).toHaveAttribute(
      "href",
      "/workspaces/ws-a/inspection?path=src%2FApp.tsx&returnFocus=file_change&returnSessionId=session-1&returnTaskNodeId=task-1&sessionId=session-1&taskNodeId=task-1&view=file",
    );
    expect(screen.getByRole("link", { name: "View diff" })).toHaveAttribute(
      "href",
      expect.stringContaining("view=diff"),
    );
  });
});

const fileChangeRecord: AuditRecordDetail = {
  actionId: null,
  actor: "system",
  body: "File changed.",
  completeness: "complete",
  confidence: "high",
  configKey: null,
  confirmationId: null,
  disclosure: {
    rawPayloadAvailable: false,
    rawPayloadShown: false,
  },
  evidence: [],
  evidenceRefs: [],
  filePath: "src/App.tsx",
  filterKind: "files",
  flags: {
    hidden: false,
    partial: false,
    redacted: false,
    stale: false,
    userVisible: true,
  },
  id: "record-file-1",
  kind: "file_change",
  occurredAt: "2026-06-10T00:00:00Z",
  outcome: null,
  rawPayload: null,
  references: [],
  relatedLogs: [],
  relatedRecordIds: [],
  resultId: null,
  scope: {
    kind: "file",
    path: "src/App.tsx",
    sessionId: "session-1",
    taskNodeId: "task-1",
  },
  severity: "info",
  sourceLabel: "Workspace",
  summary: "src/App.tsx changed.",
  taskNodeId: "task-1",
  taskRef: null,
  title: "File changed",
  verdict: "warning",
  whyItMatters: "The user can inspect the exact file change.",
};
