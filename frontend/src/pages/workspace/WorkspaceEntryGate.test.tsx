import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceEntryGate } from "./WorkspaceEntryGate";

describe("WorkspaceEntryGate", () => {
  it("loads workspace state and opens the native workspace picker", async () => {
    const user = userEvent.setup();
    const bridge = {
      chooseWorkspace: vi.fn(async () => ({
        state: state({ status: "ready" }),
        status: "ready" as const,
      })),
      getState: vi.fn(async () =>
        state({
          recentWorkspaces: [
            {
              id: "workspace-recent",
              isCurrent: false,
              label: "Recent Project",
              name: "Recent Project",
              pathLabel: "Recent Project",
            },
          ],
          status: "needs_selection",
        }),
      ),
      useWorkspace: vi.fn(),
    };

    render(<WorkspaceEntryGate bridge={bridge} />);

    expect(
      await screen.findByRole("button", { name: /Recent Project/i }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Open workspace/i }));

    expect(bridge.chooseWorkspace).toHaveBeenCalledTimes(1);
  });

  it("opens a recent workspace through the bridge", async () => {
    const user = userEvent.setup();
    const bridge = {
      chooseWorkspace: vi.fn(),
      getState: vi.fn(async () =>
        state({
          recentWorkspaces: [
            {
              id: "workspace-recent",
              isCurrent: false,
              label: "Recent Project",
              name: "Recent Project",
              pathLabel: "Recent Project",
            },
          ],
          status: "needs_selection",
        }),
      ),
      useWorkspace: vi.fn(async () => ({
        state: state({ status: "ready" }),
        status: "ready" as const,
      })),
    };

    render(<WorkspaceEntryGate bridge={bridge} />);

    await user.click(await screen.findByRole("button", { name: /Recent Project/i }));

    expect(bridge.useWorkspace).toHaveBeenCalledWith("workspace-recent");
  });

  it("shows an unavailable state outside Electron", async () => {
    render(<WorkspaceEntryGate bridge={null} />);

    expect(
      await screen.findByText(/only available in the Plato desktop app/i),
    ).toBeInTheDocument();
  });
});

function state(
  overrides: Partial<PlatoWorkspaceEntryState> = {},
): PlatoWorkspaceEntryState {
  return {
    currentWorkspace: null,
    error: null,
    recentWorkspaces: [],
    status: "needs_selection",
    ...overrides,
  };
}
