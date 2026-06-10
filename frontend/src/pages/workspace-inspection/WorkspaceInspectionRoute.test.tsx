import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { WorkspaceInspectionApi } from "../../shared/api/workspaceInspectionApi";
import { WorkspaceInspectionRoute } from "./WorkspaceInspectionRoute";

describe("WorkspaceInspectionRoute", () => {
  it("renders changed file status with file and diff links", async () => {
    render(
      <WorkspaceInspectionRoute
        api={inspectionApi()}
        location={{
          pathname: "/workspaces/ws-a/inspection",
          search: "?sessionId=session-1&taskNodeId=task-1",
        }}
      />,
    );

    expect(await screen.findByRole("heading", { name: "dirty" })).toBeInTheDocument();
    expect(screen.getByText("src/App.tsx")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open file" })).toHaveAttribute(
      "href",
      expect.stringContaining("view=file"),
    );
    expect(screen.getByRole("link", { name: "View diff" })).toHaveAttribute(
      "href",
      expect.stringContaining("view=diff"),
    );
  });

  it("renders text file content with line numbers", async () => {
    render(
      <WorkspaceInspectionRoute
        api={inspectionApi()}
        location={{
          pathname: "/workspaces/ws-a/inspection",
          search: "?view=file&path=src%2FApp.tsx",
        }}
      />,
    );

    expect(await screen.findByRole("heading", { name: "src/App.tsx" })).toBeInTheDocument();
    expect(screen.getByLabelText("File content")).toHaveTextContent("export function App");
  });

  it("renders structured diff hunks", async () => {
    render(
      <WorkspaceInspectionRoute
        api={inspectionApi()}
        location={{
          pathname: "/workspaces/ws-a/inspection",
          search: "?view=diff&path=src%2FApp.tsx",
        }}
      />,
    );

    expect(await screen.findByRole("heading", { name: "src/App.tsx" })).toBeInTheDocument();
    expect(screen.getByText("+2")).toBeInTheDocument();
    expect(screen.getByText("-1")).toBeInTheDocument();
    expect(screen.getByText("+export function App() {}")).toBeInTheDocument();
  });

  it("renders unavailable file states", async () => {
    const api = inspectionApi({
      fileUnavailableReason: "binary",
    });

    render(
      <WorkspaceInspectionRoute
        api={api}
        location={{
          pathname: "/workspaces/ws-a/inspection",
          search: "?view=file&path=asset.bin",
        }}
      />,
    );

    expect(await screen.findByRole("heading", { name: "File unavailable" })).toBeInTheDocument();
    expect(screen.getByText(/binary/)).toBeInTheDocument();
  });
});

function inspectionApi(options: { fileUnavailableReason?: "binary" } = {}) {
  const api: WorkspaceInspectionApi = {
    async getStatus() {
      return {
        data: {
          files: [
            {
              binary: false,
              changeKind: "modified",
              pathLabel: "workspace://ws-a/src/App.tsx",
              relatedTaskRefs: [],
              relativePath: "src/App.tsx",
              staged: false,
              unstaged: true,
            },
          ],
          generatedAt: "2026-06-10T00:00:00Z",
          repository: {
            branch: "main",
            headSha: "abc",
            isDetachedHead: false,
            rootLabel: "workspace://ws-a",
            status: "dirty",
          },
          schemaVersion: "plato.workspace_inspection.git_status.v1",
          summary: {
            changedFileCount: 1,
            hasMore: false,
            stagedFileCount: 0,
            unstagedFileCount: 1,
            untrackedFileCount: 0,
          },
          warnings: [],
          workspaceId: "ws-a",
        },
        error: null,
        ok: true,
      };
    },
    async getFileContent() {
      return {
        data:
          options.fileUnavailableReason === "binary"
            ? {
                content: { lines: [] },
                file: {
                  exists: true,
                  fileKind: "binary",
                  pathLabel: "workspace://ws-a/asset.bin",
                  relativePath: "asset.bin",
                },
                generatedAt: "2026-06-10T00:00:00Z",
                range: {
                  endLine: 0,
                  startLine: 1,
                  totalLines: null,
                  truncated: false,
                },
                schemaVersion: "plato.workspace_inspection.file_content.v1",
                source: "live",
                unavailableReason: "binary",
                warnings: [],
                workspaceId: "ws-a",
              }
            : {
                content: {
                  lines: [
                    {
                      lineNumber: 1,
                      text: "export function App() {}",
                    },
                  ],
                },
                file: {
                  encoding: "utf-8",
                  exists: true,
                  fileKind: "text",
                  pathLabel: "workspace://ws-a/src/App.tsx",
                  relativePath: "src/App.tsx",
                },
                generatedAt: "2026-06-10T00:00:00Z",
                range: {
                  endLine: 1,
                  startLine: 1,
                  totalLines: 1,
                  truncated: false,
                },
                schemaVersion: "plato.workspace_inspection.file_content.v1",
                source: "live",
                warnings: [],
                workspaceId: "ws-a",
              },
        error: null,
        ok: true,
      };
    },
    async getDiff() {
      return {
        data: {
          base: "head",
          file: {
            binary: false,
            changeKind: "modified",
            pathLabel: "workspace://ws-a/src/App.tsx",
            relativePath: "src/App.tsx",
          },
          generatedAt: "2026-06-10T00:00:00Z",
          hunks: [
            {
              header: "",
              hunkId: "hunk-1",
              lines: [
                {
                  kind: "delete",
                  newLine: null,
                  oldLine: 1,
                  text: "old",
                },
                {
                  kind: "add",
                  newLine: 1,
                  oldLine: null,
                  text: "export function App() {}",
                },
                {
                  kind: "add",
                  newLine: 2,
                  oldLine: null,
                  text: "export default App;",
                },
              ],
              newLines: 2,
              newStart: 1,
              oldLines: 1,
              oldStart: 1,
            },
          ],
          isAvailable: true,
          schemaVersion: "plato.workspace_inspection.diff.v1",
          stats: {
            additions: 2,
            deletions: 1,
            hunkCount: 1,
            truncated: false,
          },
          warnings: [],
          workspaceId: "ws-a",
        },
        error: null,
        ok: true,
      };
    },
  };
  return api;
}
