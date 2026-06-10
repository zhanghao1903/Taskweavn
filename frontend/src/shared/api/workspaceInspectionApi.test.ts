import { describe, expect, it, vi } from "vitest";

import type { FetchFn } from "./client";
import { createHttpWorkspaceInspectionApi } from "./workspaceInspectionApi";

describe("workspace inspection API", () => {
  it("builds workspace-scoped status, diff, and file routes", async () => {
    const fetcher = vi.fn<FetchFn>(async () =>
      jsonResponse({
        data: null,
        error: null,
        ok: true,
      }),
    );
    const api = createHttpWorkspaceInspectionApi({
      baseUrl: "https://plato.test",
      fetcher,
    });

    await api.getStatus({ maxFiles: 50, workspaceId: "ws/a" });
    await api.getDiff({
      base: "head",
      contextLines: 4,
      path: "src/App.tsx",
      workspaceId: "ws/a",
    });
    await api.getFileContent({
      lineCount: 25,
      path: "src/App.tsx",
      startLine: 5,
      workspaceId: "ws/a",
    });

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "https://plato.test/api/v1/workspaces/ws%2Fa/inspection/status?maxFiles=50",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "https://plato.test/api/v1/workspaces/ws%2Fa/inspection/diff?base=head&contextLines=4&path=src%2FApp.tsx",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      3,
      "https://plato.test/api/v1/workspaces/ws%2Fa/files/content?lineCount=25&path=src%2FApp.tsx&startLine=5",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("loads captured file evidence without requiring a path", async () => {
    const fetcher = vi.fn<FetchFn>(async () =>
      jsonResponse({
        data: null,
        error: null,
        ok: true,
      }),
    );
    const api = createHttpWorkspaceInspectionApi({
      baseUrl: "https://plato.test",
      fetcher,
    });

    await api.getFileContent({
      evidenceId: "inspection-1",
      workspaceId: "ws-a",
    });

    expect(fetcher).toHaveBeenCalledWith(
      "https://plato.test/api/v1/workspaces/ws-a/files/content?evidenceId=inspection-1",
      expect.objectContaining({ method: "GET" }),
    );
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    headers: {
      "Content-Type": "application/json",
    },
    status,
  });
}
