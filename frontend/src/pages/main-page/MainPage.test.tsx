import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { ApiResponseError } from "../../shared/api/productErrors";
import type { ApiError } from "../../shared/api/types";
import { NO_SESSION_AVAILABLE_MESSAGE } from "./httpMainPageAdapter";
import { MainPage } from "./MainPage";
import { createMainPageMockAdapter } from "./mockPlatoApi";
import type { LoadMainPageSnapshot, MainPageAdapter } from "./runtime/adapter";

describe("MainPage fallback states", () => {
  it("places the new session action on the workspace row", async () => {
    renderWithQueryClient(
      <MainPage
        adapter={testAdapter()}
        workspaceRuntime={{
          bridge: null,
          currentWorkspace: {
            id: "workspace-current",
            isCurrent: true,
            label: "Current Space",
            name: "Current Space",
            pathLabel: "Current Space",
          },
          isRequired: false,
        }}
      />,
    );

    expect(await screen.findByText("Current Space")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New" })).toBeInTheDocument();
    expect(screen.queryByText(/^Sessions$/i)).not.toBeInTheDocument();
  });

  it("uses user-facing loading copy without internal projection terms", () => {
    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot: vi.fn<LoadMainPageSnapshot>(
            () => new Promise(() => undefined),
          ),
        })}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Opening session" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Plato is preparing this workspace.")).toBeInTheDocument();
    expect(screen.queryByText(/projection/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/snapshot/i)).not.toBeInTheDocument();
  });

  it("keeps the workspace sidebar visible when the current workspace has no sessions", async () => {
    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot: vi.fn<LoadMainPageSnapshot>(async () => {
            throw new Error(NO_SESSION_AVAILABLE_MESSAGE);
          }),
        })}
        workspaceRuntime={{
          bridge: null,
          currentWorkspace: {
            id: "workspace-empty",
            isCurrent: true,
            label: "Empty Space",
            name: "Empty Space",
            pathLabel: "Empty Space",
          },
          isRequired: false,
        }}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Create your first session" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Workspace sessions")).toBeInTheDocument();
    expect(screen.getByLabelText("Workspaces")).toBeInTheDocument();
    expect(screen.getByText("Empty Space")).toBeInTheDocument();
    expect(screen.getByText("Open or add workspace")).toBeInTheDocument();
    expect(screen.queryByText(/^Sessions$/i)).not.toBeInTheDocument();
  });

  it("uses user-facing error copy without internal projection terms", async () => {
    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot: vi.fn<LoadMainPageSnapshot>(async () => {
            throw new Error("backend failed");
          }),
        })}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Unable to open session" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Plato could not load this session. Refresh the page or choose another session.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/backend failed/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/projection/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/snapshot/i)).not.toBeInTheDocument();
  });

  it("renders recovery labels from product error metadata on load errors", async () => {
    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot: vi.fn<LoadMainPageSnapshot>(async () => {
            throw new ApiResponseError(
              apiError({
                recoveryActions: ["refresh_snapshot", "open_settings"],
              }),
              "Unable to open session.",
            );
          }),
        })}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Unable to open session" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Unable to open session.")).not.toBeInTheDocument();
    expect(screen.getByText("Refresh session")).toBeInTheDocument();
    expect(screen.getByText("Open settings")).toBeInTheDocument();
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

function testAdapter(overrides: Partial<MainPageAdapter> = {}): MainPageAdapter {
  return createMainPageMockAdapter({
    showStatePicker: false,
    ...overrides,
  });
}

function apiError(details: Record<string, unknown>): ApiError {
  return {
    code: "internal_error",
    details,
    message: "Internal sidecar error.",
    retryable: true,
  };
}
