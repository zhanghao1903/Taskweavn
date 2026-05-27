import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getMainPageMockSnapshot } from "../pages/main-page/mockPlatoApi";
import { MainPageRoute } from "./MainPageRoute";

describe("MainPageRoute", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("preserves the default fixture MainPage behavior", async () => {
    renderWithQueryClient(<MainPageRoute runtimeEnv={{}} />);

    expect(await screen.findByText("Personal Website")).toBeInTheDocument();
    expect(screen.getByLabelText("State")).toBeInTheDocument();
    expect(screen.getByText("TaskTree")).toBeInTheDocument();
  });

  it("creates an HTTP runtime adapter from route env without exposing the state picker", async () => {
    const calls: string[] = [];
    const snapshot = getMainPageMockSnapshot("s3-draft-ready").snapshot;

    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      calls.push(String(input));
      return new Response(
        JSON.stringify({
          cursor: snapshot.cursor,
          data: snapshot,
          error: null,
          generatedAt: snapshot.generatedAt,
          ok: true,
          requestId: "request-route-snapshot",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });

    renderWithQueryClient(
      <MainPageRoute
        runtimeEnv={{
          VITE_PLATO_API_BASE_URL: "https://plato.example",
          VITE_PLATO_API_MODE: "http",
          VITE_PLATO_SESSION_ID: "session-live",
        }}
      />,
    );

    expect(await screen.findByText("Personal Website")).toBeInTheDocument();
    expect(screen.queryByLabelText("State")).not.toBeInTheDocument();
    expect(calls).toContain(
      "https://plato.example/api/v1/sessions/session-live/snapshot",
    );
  });
});

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
