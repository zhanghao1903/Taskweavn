import { describe, expect, it } from "vitest";

import { resolvePackagedSidecarLauncherPath } from "./sidecarLauncherPath.mjs";

describe("Electron sidecar launcher path resolution", () => {
  it("uses an explicit launcher path first", () => {
    expect(
      resolvePackagedSidecarLauncherPath({
        appIsPackaged: false,
        env: { PLATO_ELECTRON_SIDECAR_LAUNCHER_PATH: "/custom/launcher.mjs" },
        exists: () => false,
        frontendRoot: "/repo/frontend",
        readFile: () => "{}",
        resourcesPath: "/electron/resources",
      }),
    ).toBe("/custom/launcher.mjs");
  });

  it("does not use the repo sidecar launcher in dev mode", () => {
    expect(
      resolvePackagedSidecarLauncherPath({
        appIsPackaged: false,
        env: {},
        exists: (filePath) =>
          filePath === "/repo/frontend/package.json" ||
          filePath === "/repo/frontend/sidecar/plato-sidecar-launcher.mjs",
        frontendRoot: "/repo/frontend",
        readFile: () =>
          JSON.stringify({
            name: "@taskweavn/plato-frontend",
          }),
        resourcesPath: "/electron/resources",
      }),
    ).toBeNull();
  });

  it("finds the packaged resource launcher even when Electron reports unpackaged", () => {
    expect(
      resolvePackagedSidecarLauncherPath({
        appIsPackaged: false,
        env: {},
        exists: (filePath) =>
          filePath === "/Volume/Plato.app/Contents/Resources/app/package.json" ||
          filePath ===
            "/Volume/Plato.app/Contents/Resources/app/sidecar/plato-sidecar-launcher.mjs",
        frontendRoot: "/Volume/Plato.app/Contents/Resources/app",
        readFile: () =>
          JSON.stringify({
            name: "@taskweavn/plato-packaged",
          }),
        resourcesPath: "/Volume/Plato.app/Contents/Resources",
      }),
    ).toBe(
      "/Volume/Plato.app/Contents/Resources/app/sidecar/plato-sidecar-launcher.mjs",
    );
  });

  it("falls back to resourcesPath/app launcher for packaged Electron", () => {
    expect(
      resolvePackagedSidecarLauncherPath({
        appIsPackaged: true,
        env: {},
        exists: (filePath) =>
          filePath ===
          "/Volume/Plato.app/Contents/Resources/app/sidecar/plato-sidecar-launcher.mjs",
        frontendRoot: "/unexpected/app/root",
        readFile: () => "{}",
        resourcesPath: "/Volume/Plato.app/Contents/Resources",
      }),
    ).toBe(
      "/Volume/Plato.app/Contents/Resources/app/sidecar/plato-sidecar-launcher.mjs",
    );
  });
});
