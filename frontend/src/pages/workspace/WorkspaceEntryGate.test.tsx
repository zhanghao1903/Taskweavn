import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { writeWorkspaceGitInitializeOnOpenPreference } from "../../shared/workspace/workspaceGitPreference";
import { WorkspaceEntryGate } from "./WorkspaceEntryGate";

describe("WorkspaceEntryGate", () => {
  beforeEach(() => {
    installTestLocalStorage();
  });

  afterEach(() => {
    globalThis.localStorage?.clear();
  });

  it("loads workspace state and opens the native workspace picker", async () => {
    const user = userEvent.setup();
    const bridge = {
      chooseWorkspace: vi.fn(async () => ({
        state: state({ status: "ready" }),
        status: "ready" as const,
      })),
      getGitStatus: vi.fn(),
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
      getGitStatus: vi.fn(),
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

    expect(bridge.useWorkspace).toHaveBeenCalledWith("workspace-recent", undefined);
  });

  it("passes the Git initialization preference to workspace selection", async () => {
    const user = userEvent.setup();
    writeWorkspaceGitInitializeOnOpenPreference(true);
    const bridge = {
      chooseWorkspace: vi.fn(async () => ({
        state: state({ status: "ready" }),
        status: "ready" as const,
      })),
      getGitStatus: vi.fn(),
      getState: vi.fn(async () => state({ status: "needs_selection" })),
      useWorkspace: vi.fn(),
    };

    render(<WorkspaceEntryGate bridge={bridge} />);

    await user.click(await screen.findByRole("button", { name: /Open workspace/i }));

    expect(bridge.chooseWorkspace).toHaveBeenCalledWith({
      initializeGitOnOpen: true,
    });
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
