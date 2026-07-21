import { EventEmitter } from "node:events";
import {
  chmodSync,
  existsSync,
  mkdtempSync,
  mkdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { PassThrough } from "node:stream";
import { describe, expect, it } from "vitest";

import {
  APP_CONTROL_SERVICE_MANIFEST_SCHEMA,
  buildHelperLaunchArgs,
  startComputerUseHelper,
} from "./computerUseHelperProcess.mjs";

describe("computer use Helper process", () => {
  it("passes only fixed Helper service inputs", () => {
  const args = buildHelperLaunchArgs({
    allowedAppBundleIds: { WeChat: "com.tencent.xinWeChat" },
    allowedApps: ["WeChat"],
    allowCoordinateClick: false,
    appPath: "/Applications/Helper.app",
    bundleId: "com.taskweavn.plato.computer-use-helper.dev",
    manifestPath: "/tmp/service.json",
    screenRecordingRequired: false,
    socketPath: "/tmp/service.sock",
    timeoutMs: 10_000,
    tokenPath: "/tmp/service.token",
  });

  expect(args.slice(0, 3)).toEqual(["-n", "/Applications/Helper.app", "--args"]);
    expect(args).toContain("--socket-path");
    expect(args).toContain("--allowed-app-bundle-ids-json");
    expect(args.slice(args.indexOf("--app-path"), args.indexOf("--app-path") + 2)).toEqual([
      "--app-path",
      "/Applications/Helper.app",
    ]);
    expect(args).not.toContain("--allow-coordinate-click");
  });

  it("waits for a validated Unix socket manifest", async () => {
  const root = mkdtempSync("/tmp/plato-helper-test-");
  const appPath = path.join(root, "Helper.app");
  const runtimeRoot = path.join(root, "runtime");
  mkdirSync(appPath);
  chmodSync(appPath, 0o700);
  const killed = [];

  const spawnProcess = (_command, args) => {
    const child = new EventEmitter();
    child.stderr = new PassThrough();
    const valueAfter = (flag) => args[args.indexOf(flag) + 1];
    const socketPath = valueAfter("--socket-path");
    const tokenPath = valueAfter("--token-path");
    const manifestPath = valueAfter("--manifest-path");
    writeFileSync(socketPath, "test endpoint", { mode: 0o600 });
    writeFileSync(tokenPath, "secret\n", { mode: 0o600 });
    writeFileSync(
      manifestPath,
      JSON.stringify({
        schema: APP_CONTROL_SERVICE_MANIFEST_SCHEMA,
        transport: "unix_socket",
        endpoint: socketPath,
        tokenPath,
        pid: 4321,
        bundleId: "com.taskweavn.plato.computer-use-helper.dev",
        serviceVersion: "0.3.0",
      }),
      { mode: 0o600 },
    );
    queueMicrotask(() => child.emit("exit", 0, null));
    return child;
  };

  try {
    const helper = await startComputerUseHelper({
      allowedApps: ["WeChat"],
      appPath,
      bundleId: "com.taskweavn.plato.computer-use-helper.dev",
      killProcess: (pid, signal) => killed.push([pid, signal]),
      pollIntervalMs: 10,
      runtimeRoot,
      spawnProcess,
      timeoutMs: 2_000,
      validateEndpoint: () => true,
    });

    expect(helper.pid).toBe(4321);
    expect(helper.manifest.transport).toBe("unix_socket");
    helper.stop();
    expect(killed[0]).toEqual([4321, "SIGTERM"]);
    expect(existsSync(path.join(runtimeRoot, "app-control-service.json"))).toBe(false);
    expect(existsSync(path.join(runtimeRoot, "app-control.sock"))).toBe(false);
    expect(existsSync(path.join(runtimeRoot, "app-control.token"))).toBe(false);
  } finally {
    rmSync(root, { force: true, recursive: true });
  }
  });
});
