import { describe, expect, it } from "vitest";

import { resolveElectronWorkspaceRoot } from "./workspacePaths.mjs";

describe("Electron workspace paths", () => {
  it("uses an explicit workspace override first", () => {
    expect(
      resolveElectronWorkspaceRoot({
        env: { PLATO_ELECTRON_WORKSPACE: "/tmp/plato-explicit-workspace" },
        isPackaged: true,
        repoRoot: "/repo",
        sidecarLauncherPath: "/app/sidecar/plato-sidecar-launcher.mjs",
        userDataPath: "/Users/example/Library/Application Support/Plato",
      }),
    ).toBe("/tmp/plato-explicit-workspace");
  });

  it("keeps the repo workspace default for dev sidecar startup", () => {
    expect(
      resolveElectronWorkspaceRoot({
        env: {},
        isPackaged: false,
        repoRoot: "/repo",
        sidecarLauncherPath: null,
        userDataPath: "/Users/example/Library/Application Support/Plato",
      }),
    ).toBe("/repo/plato-workspace");
  });

  it("uses Application Support for packaged launcher startup", () => {
    expect(
      resolveElectronWorkspaceRoot({
        env: {},
        isPackaged: true,
        repoRoot: "/app/Contents/Resources",
        sidecarLauncherPath: "/app/Contents/Resources/app/sidecar/plato-sidecar-launcher.mjs",
        userDataPath: "/Users/example/Library/Application Support/Plato",
      }),
    ).toBe("/Users/example/Library/Application Support/Plato/workspace");
  });
});
