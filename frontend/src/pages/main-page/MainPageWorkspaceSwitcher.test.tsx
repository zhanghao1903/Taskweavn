import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MainPageWorkspaceSwitcher } from "./MainPageWorkspaceSwitcher";

describe("MainPageWorkspaceSwitcher", () => {
  it("opens the native workspace picker from Main Page", async () => {
    const user = userEvent.setup();
    const bridge = bridgeFor({
      chooseWorkspace: vi.fn(async () => ({
        state: workspaceState({ status: "starting" }),
        status: "ready" as const,
      })),
    });

    render(
      <MainPageWorkspaceSwitcher
        runtime={{
          bridge,
          currentWorkspace: workspace("workspace-current", "Current Space"),
          isRequired: false,
        }}
      />,
    );

    expect(screen.getByText("Current Space")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Open or add workspace/i }));

    expect(bridge.chooseWorkspace).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Switching workspace.")).toBeInTheDocument();
  });

  it("switches to a recent workspace through the Electron bridge", async () => {
    const user = userEvent.setup();
    const bridge = bridgeFor({
      getState: vi.fn(async () =>
        workspaceState({
          currentWorkspace: workspace("workspace-current", "Current Space"),
          recentWorkspaces: [workspace("workspace-recent", "Recent Space")],
          status: "ready",
        }),
      ),
      useWorkspace: vi.fn(async () => ({
        state: workspaceState({ status: "starting" }),
        status: "ready" as const,
      })),
    });

    render(
      <MainPageWorkspaceSwitcher
        runtime={{
          bridge,
          currentWorkspace: workspace("workspace-current", "Current Space"),
          isRequired: false,
        }}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /Recent Space/i }));

    expect(bridge.getState).toHaveBeenCalledTimes(1);
    expect(bridge.useWorkspace).toHaveBeenCalledWith("workspace-recent");
  });

  it("uses safe workspace names instead of raw path labels", async () => {
    const bridge = bridgeFor({
      getState: vi.fn(async () =>
        workspaceState({
          currentWorkspace: workspace(
            "workspace-current",
            "Current Space",
            "/Users/name/private-project",
          ),
          recentWorkspaces: [
            workspace("workspace-recent", "Recent Space", "/Users/name/other"),
          ],
          status: "ready",
        }),
      ),
    });

    render(
      <MainPageWorkspaceSwitcher
        runtime={{
          bridge,
          currentWorkspace: workspace(
            "workspace-current",
            "Current Space",
            "/Users/name/private-project",
          ),
          isRequired: false,
        }}
      />,
    );

    await screen.findByRole("button", { name: /Recent Space/i });

    expect(screen.getAllByText("Current Space").length).toBeGreaterThan(0);
    expect(screen.getByText("Recent Space")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("/Users/name/private-project");
    expect(document.body).not.toHaveTextContent("/Users/name/other");
  });

  it("renders child sessions under the current workspace row", () => {
    render(
      <MainPageWorkspaceSwitcher
        actions={<button type="button">New</button>}
        runtime={{
          bridge: bridgeFor(),
          currentWorkspace: workspace("workspace-current", "Current Space"),
          isRequired: false,
        }}
      >
        <div>Session A</div>
      </MainPageWorkspaceSwitcher>,
    );

    expect(screen.getByText("Current Space")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New" })).toBeInTheDocument();
    expect(screen.getByText("Session A")).toBeInTheDocument();
  });
});

function bridgeFor(
  overrides: Partial<PlatoElectronWorkspaceBridge> = {},
): PlatoElectronWorkspaceBridge {
  return {
    chooseWorkspace: vi.fn(async () => ({
      state: workspaceState({ status: "starting" }),
      status: "ready" as const,
    })),
    getState: vi.fn(async () => workspaceState({ status: "ready" })),
    useWorkspace: vi.fn(async () => ({
      state: workspaceState({ status: "starting" }),
      status: "ready" as const,
    })),
    ...overrides,
  };
}

function workspaceState(
  overrides: Partial<PlatoWorkspaceEntryState> = {},
): PlatoWorkspaceEntryState {
  return {
    currentWorkspace: workspace("workspace-current", "Current Space"),
    error: null,
    recentWorkspaces: [],
    status: "ready",
    ...overrides,
  };
}

function workspace(
  id: string,
  name: string,
  pathLabel: string = name,
): PlatoWorkspaceEntrySummary {
  return {
    id,
    isCurrent: id === "workspace-current",
    label: name,
    name,
    pathLabel,
  };
}
