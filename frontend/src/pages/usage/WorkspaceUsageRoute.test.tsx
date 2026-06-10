import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import type { WorkspaceUsageApi } from "./WorkspaceUsageRoute";
import { WorkspaceUsageRoute } from "./WorkspaceUsageRoute";
import type {
  TokenUsageSummaryRequest,
  TokenUsageSummaryResponse,
} from "../../shared/api/tokenUsageTypes";
import type { QueryResponse } from "../../shared/api/types";

describe("WorkspaceUsageRoute", () => {
  it("renders token usage summaries for workspace, session, plan, and task", async () => {
    const api: WorkspaceUsageApi = {
      getTokenUsageSummary: vi.fn(async (request) =>
        tokenUsageResponse(request),
      ),
    };

    renderWithQueryClient(
      <WorkspaceUsageRoute
        api={api}
        location={{
          pathname: "/workspaces/workspace-a/usage",
          search: "?sessionId=session-1&planId=plan-1&taskNodeId=task-1",
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Token usage" })).toBeInTheDocument();
    await waitFor(() =>
      expect(api.getTokenUsageSummary).toHaveBeenCalledTimes(4),
    );
    expect(await screen.findByText("workspace row")).toBeInTheDocument();
    expect(screen.getByText("session row")).toBeInTheDocument();
    expect(screen.getByText("plan row")).toBeInTheDocument();
    expect(screen.getByText("task row")).toBeInTheDocument();
    expect(screen.getAllByText("1,500").length).toBeGreaterThan(0);
    expect(api.getTokenUsageSummary).toHaveBeenCalledWith(
      { dimension: "task", sessionId: "session-1", taskNodeId: "task-1" },
      { workspaceId: "workspace-a" },
    );
  });
});

function tokenUsageResponse(
  request: TokenUsageSummaryRequest,
): QueryResponse<TokenUsageSummaryResponse> {
  const now = "2026-06-10T00:01:00Z";
  return {
    data: {
      dimension: request.dimension,
      totals: {
        dimension: request.dimension,
        id: "total",
        label: "Total",
        workspaceId: "workspace-a",
        sessionId: request.sessionId ?? null,
        planId: request.planId ?? null,
        taskNodeId: request.taskNodeId ?? null,
        callCount: 2,
        unknownUsageCallCount: 0,
        inputTokens: 1200,
        outputTokens: 300,
        totalTokens: 1500,
        reasoningTokens: null,
        cachedTokens: 500,
        cacheHitTokens: 500,
        cacheMissTokens: 700,
        cacheHitRatio: 0.4166666667,
        cacheRateSource: "hit_miss_tokens",
        firstOccurredAt: "2026-06-10T00:00:00Z",
        lastOccurredAt: now,
      },
      rows: [
        {
          dimension: request.dimension,
          id: `${request.dimension}-row`,
          label: `${request.dimension} row`,
          workspaceId: "workspace-a",
          sessionId: request.sessionId ?? null,
          planId: request.planId ?? null,
          taskNodeId: request.taskNodeId ?? null,
          callCount: 2,
          unknownUsageCallCount: 0,
          inputTokens: 1200,
          outputTokens: 300,
          totalTokens: 1500,
          reasoningTokens: null,
          cachedTokens: 500,
          cacheHitTokens: 500,
          cacheMissTokens: 700,
          cacheHitRatio: 0.4166666667,
          cacheRateSource: "hit_miss_tokens",
          firstOccurredAt: "2026-06-10T00:00:00Z",
          lastOccurredAt: now,
        },
      ],
    },
    error: null,
    generatedAt: now,
    ok: true,
    requestId: "request-token-usage",
  };
}

function renderWithQueryClient(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>,
  );
}
