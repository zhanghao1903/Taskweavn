import { describe, expect, it } from "vitest";

import { createComputerUseHelperManager } from "./computerUseHelperManager.mjs";

function fakeApp({ isPackaged = false } = {}) {
  return {
    isPackaged,
    getPath(name) {
      if (name === "userData") {
        return "/tmp/plato-user-data";
      }
      if (name === "home") {
        return "/Users/tester";
      }
      throw new Error(`unexpected path: ${name}`);
    },
  };
}

describe("computer use Helper manager", () => {
it("starts the Dev Helper once and injects its manifest", async () => {
  const starts = [];
  let stopped = false;
  const manager = createComputerUseHelperManager({
    app: fakeApp(),
    env: {
      PLATO_COMPUTER_USE_ALLOWED_APPS: "WeChat",
      PLATO_COMPUTER_USE_BACKEND: "helper",
    },
    platform: "darwin",
    startHelper: async (config) => {
      starts.push(config);
      return {
        manifestPath: "/tmp/plato-user-data/computer-use-helper/app-control-service.json",
        stop() {
          stopped = true;
        },
      };
    },
  });

  await manager.ensureStarted();
  await manager.ensureStarted();

  expect(starts).toHaveLength(1);
  expect(
    starts[0].appPath,
  ).toBe("/Users/tester/Applications/Plato Computer Use Helper Dev.app");
  expect(starts[0].allowedAppBundleIds).toEqual({
    WeChat: "com.tencent.xinWeChat",
  });
  expect(starts[0].allowCoordinateClick).toBe(true);
  expect(
    manager.buildSidecarEnv().PLATO_COMPUTER_USE_HELPER_MANIFEST,
  ).toBe("/tmp/plato-user-data/computer-use-helper/app-control-service.json");
  expect(
    manager.buildSidecarEnv().PLATO_COMPUTER_USE_ALLOW_COORDINATE_CLICK,
  ).toBe("true");
  manager.stop();
  expect(stopped).toBe(true);
});

it("keeps Plato bootable and injects failure diagnostics", async () => {
  const manager = createComputerUseHelperManager({
    app: fakeApp(),
    env: { PLATO_COMPUTER_USE_BACKEND: "helper" },
    platform: "darwin",
    startHelper: async () => {
      const error = new Error("helper app is missing");
      error.diagnostics = { failureKind: "helper_app_missing" };
      throw error;
    },
  });

  const status = await manager.ensureStarted();
  const sidecarEnv = manager.buildSidecarEnv();

  expect(status.available).toBe(false);
  expect(status.startupFailure.failureKind).toBe("helper_app_missing");
  expect(
    sidecarEnv.PLATO_COMPUTER_USE_HELPER_MANIFEST,
  ).toMatch(/app-control-service\.json$/);
  expect(
    JSON.parse(sidecarEnv.PLATO_COMPUTER_USE_HELPER_STARTUP_FAILURE),
  ).toEqual({
      failureKind: "helper_app_missing",
      message: "helper app is missing",
    });
});

it("keeps legacy direct mode out of the macOS product process", async () => {
  const starts = [];
  const manager = createComputerUseHelperManager({
    app: fakeApp(),
    env: { PLATO_COMPUTER_USE_BACKEND: "macos" },
    platform: "darwin",
    startHelper: async (config) => {
      starts.push(config);
      return {
        manifestPath: "/tmp/plato-user-data/computer-use-helper/app-control-service.json",
        stop() {},
      };
    },
  });

  await manager.ensureStarted();

  expect(starts).toHaveLength(1);
  expect(manager.buildSidecarEnv().PLATO_COMPUTER_USE_BACKEND).toBe("helper");
  expect(manager.snapshot().manifestPath).toBe(
    "/tmp/plato-user-data/computer-use-helper/app-control-service.json",
  );
});

it("forces an explicit direct backend off outside macOS", async () => {
  let starts = 0;
  const manager = createComputerUseHelperManager({
    app: fakeApp(),
    env: { PLATO_COMPUTER_USE_BACKEND: "macos" },
    platform: "linux",
    startHelper: async () => {
      starts += 1;
    },
  });

  await manager.ensureStarted();

  expect(starts).toBe(0);
  expect(manager.buildSidecarEnv().PLATO_COMPUTER_USE_BACKEND).toBe("disabled");
});

it("defaults macOS Plato to the Helper-hosted WeChat service", async () => {
  const starts = [];
  const manager = createComputerUseHelperManager({
    app: fakeApp(),
    env: {},
    platform: "darwin",
    startHelper: async (config) => {
      starts.push(config);
      return {
        manifestPath: "/tmp/plato-user-data/computer-use-helper/app-control-service.json",
        stop() {},
      };
    },
  });

  await manager.ensureStarted();

  expect(starts[0].allowedApps).toEqual(["WeChat"]);
  expect(
    manager.buildSidecarEnv().PLATO_COMPUTER_USE_BACKEND,
  ).toBe("helper");
  expect(
    manager.buildSidecarEnv().PLATO_COMPUTER_USE_ALLOWED_APPS,
  ).toBe("WeChat");
});

it("keeps computer use disabled by default off macOS", async () => {
  let starts = 0;
  const manager = createComputerUseHelperManager({
    app: fakeApp(),
    env: {},
    platform: "linux",
    startHelper: async () => {
      starts += 1;
    },
  });

  await manager.ensureStarted();

  expect(starts).toBe(0);
  expect(manager.buildSidecarEnv().PLATO_COMPUTER_USE_BACKEND).toBeUndefined();
});

it("preserves an explicit coordinate-click opt-out", async () => {
  const starts = [];
  const manager = createComputerUseHelperManager({
    app: fakeApp(),
    env: {
      PLATO_COMPUTER_USE_ALLOW_COORDINATE_CLICK: "false",
      PLATO_COMPUTER_USE_BACKEND: "helper",
    },
    platform: "darwin",
    startHelper: async (config) => {
      starts.push(config);
      return {
        manifestPath: "/tmp/plato-user-data/computer-use-helper/app-control-service.json",
        stop() {},
      };
    },
  });

  await manager.ensureStarted();

  expect(starts[0].allowCoordinateClick).toBe(false);
  expect(
    manager.buildSidecarEnv().PLATO_COMPUTER_USE_ALLOW_COORDINATE_CLICK,
  ).toBe("false");
});
});
