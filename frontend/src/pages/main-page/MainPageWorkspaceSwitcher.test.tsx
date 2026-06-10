import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { writeWorkspaceGitInitializeOnOpenPreference } from "../../shared/workspace/workspaceGitPreference";
import { MainPageWorkspaceSwitcher } from "./MainPageWorkspaceSwitcher";

describe("MainPageWorkspaceSwitcher", () => {
  beforeEach(() => {
    installTestLocalStorage();
  });

  afterEach(() => {
    globalThis.localStorage?.clear();
  });

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
    expect(bridge.useWorkspace).toHaveBeenCalledWith("workspace-recent", undefined);
  });

  it("passes Git initialization preference when opening or switching workspaces", async () => {
    const user = userEvent.setup();
    writeWorkspaceGitInitializeOnOpenPreference(true);
    const bridge = bridgeFor({
      getState: vi.fn(async () =>
        workspaceState({
          currentWorkspace: workspace("workspace-current", "Current Space"),
          recentWorkspaces: [workspace("workspace-recent", "Recent Space")],
          status: "ready",
        }),
      ),
      useWorkspace: vi.fn(async () => ({
        state: workspaceState({ status: "ready" }),
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
    await user.click(screen.getByRole("button", { name: /Open or add workspace/i }));

    expect(bridge.useWorkspace).toHaveBeenCalledWith("workspace-recent", {
      initializeGitOnOpen: true,
    });
    expect(bridge.chooseWorkspace).toHaveBeenCalledWith({
      initializeGitOnOpen: true,
    });
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
    getGitStatus: vi.fn(async () => ({
      status: "available" as const,
      version: "git version 2.45.0",
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

function installTestLocalStorage(): void {
  const storage = new Map<string, string>();
  const storageLike = {
    clear: () => storage.clear(),
    getItem: (key: string) => storage.get(key) ?? null,
    key: (index: number) => Array.from(storage.keys())[index] ?? null,
    get length() {
      return storage.size;
    },
    removeItem: (key: string) => storage.delete(key),
    setItem: (key: string, value: string) => storage.set(key, value),
  };
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storageLike,
  });
  Object.defineProperty(globalThis.window, "localStorage", {
    configurable: true,
    value: storageLike,
  });
}
