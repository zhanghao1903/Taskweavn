import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createMainPageMockAdapter,
  getMainPageMockSnapshot,
} from "../pages/main-page/mockPlatoApi";
import type { LoadMainPageSnapshot } from "../pages/main-page/runtime/adapter";
import { MainPageRoute } from "./MainPageRoute";

describe("MainPageRoute", () => {
  afterEach(() => {
    globalThis.history.pushState(null, "", "/");
    vi.unstubAllGlobals();
  });

  it("preserves default fixture data without exposing the state picker", async () => {
    renderWithQueryClient(<MainPageRoute runtimeEnv={{}} />);

    expect(await screen.findByText("Personal Website")).toBeInTheDocument();
    expect(screen.queryByLabelText("State")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Task workspace")).toBeInTheDocument();
    expect(screen.getByText("Requirement analysis")).toBeInTheDocument();
  });

  it("opens the Settings route from the Main Page top bar", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<MainPageRoute runtimeEnv={{}} />);

    await screen.findByText("Personal Website");

    await user.click(screen.getByRole("button", { name: "Settings" }));

    expect(globalThis.location.pathname).toBe("/settings");
  });

  it("creates an HTTP runtime adapter from route env without exposing the state picker", async () => {
    const calls: string[] = [];
    const snapshot = getMainPageMockSnapshot("s3-draft-ready").snapshot;

    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      const url = String(input);
      calls.push(url);
      if (url === "https://plato.example/api/v1/workspaces") {
        return new Response(
          JSON.stringify({
            cursor: null,
            data: {
              currentWorkspaceId: null,
              workspaces: [],
            },
            error: null,
            generatedAt: snapshot.generatedAt,
            ok: true,
            requestId: "request-route-workspaces",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );
      }

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

  it("treats an explicit adapter as the route boundary and forwards the initial state", async () => {
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(async (stateId) =>
      getMainPageMockSnapshot(
        stateId as Parameters<typeof getMainPageMockSnapshot>[0],
      ),
    );
    const adapter = createMainPageMockAdapter({
      loadSnapshot,
      showStatePicker: false,
    });

    renderWithQueryClient(
      <MainPageRoute
        adapter={adapter}
        initialStateId="s1-empty"
        runtimeEnv={{
          VITE_PLATO_API_BASE_URL: "https://plato.example",
          VITE_PLATO_API_MODE: "http",
          VITE_PLATO_SESSION_ID: "session-live",
        }}
      />,
    );

    expect(await screen.findByText("No task plan yet")).toBeInTheDocument();
    expect(screen.queryByLabelText("State")).not.toBeInTheDocument();
    expect(loadSnapshot).toHaveBeenCalledWith("s1-empty", null, null);
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
