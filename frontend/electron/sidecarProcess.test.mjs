import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";

import { describe, expect, it, vi } from "vitest";

import {
  buildLauncherSidecarArgs,
  buildSidecarArgs,
  SidecarStartupError,
  startPythonSidecar,
} from "./sidecarProcess.mjs";

describe("Electron Python sidecar lifecycle", () => {
  it("starts the sidecar on a selected loopback port and stops it on request", async () => {
    const child = createFakeChild();
    const spawnProcess = vi.fn(() => child);

    const runtime = await startPythonSidecar({
      appVersion: "0.1.0-test",
      electronVersion: "42.0.0-test",
      fetchHealth: vi.fn(async () => true),
      findPort: vi.fn(async () => 53226),
      repoRoot: "/workspace/taskweavn",
      spawnProcess,
      startupId: "startup-test",
      workspaceRoot: "/workspace/taskweavn/plato-workspace",
    });

    expect(spawnProcess).toHaveBeenCalledWith(
      "uv",
      buildSidecarArgs({
        host: "127.0.0.1",
        port: 53226,
        workspaceRoot: "/workspace/taskweavn/plato-workspace",
      }),
      expect.objectContaining({
        cwd: "/workspace/taskweavn",
        stdio: ["ignore", "pipe", "pipe"],
      }),
    );
    expect(runtime.baseUrl).toBe("http://127.0.0.1:53226");
    expect(runtime.diagnostics).toMatchObject({
      baseUrl: "http://127.0.0.1:53226",
      status: "ready",
    });

    runtime.stop();

    expect(child.kill).toHaveBeenCalledWith("SIGINT");
  });

  it("starts the sidecar through a release-local launcher without a repo root", async () => {
    const child = createFakeChild();
    const spawnProcess = vi.fn(() => child);
    const workspaceRegistry = [
      {
        workspaceId: "current",
        rootPath: "/workspace/taskweavn/plato-workspace",
        label: "plato-workspace",
        isCurrent: true,
        lastOpenedAt: null,
      },
    ];

    const runtime = await startPythonSidecar({
      appVersion: "0.1.0-test",
      electronVersion: "42.0.0-test",
      fetchHealth: vi.fn(async () => true),
      findPort: vi.fn(async () => 53228),
      env: {
        PATH: "/usr/bin:/bin:/usr/sbin:/sbin",
      },
      launcherEnv: {
        PLATO_SIDECAR_LAUNCHER_MODE: "sidecar",
      },
      launcherNodePath: "/app/Contents/MacOS/Electron",
      launcherPath: "/app/sidecar/plato-sidecar-launcher.mjs",
      spawnProcess,
      startupId: "startup-launcher-test",
      validateLauncher: false,
      workspaceRegistry,
      workspaceRoot: "/workspace/taskweavn/plato-workspace",
    });

    expect(spawnProcess).toHaveBeenCalledWith(
      "/app/Contents/MacOS/Electron",
      [
        "/app/sidecar/plato-sidecar-launcher.mjs",
        ...buildLauncherSidecarArgs({
          host: "127.0.0.1",
          port: 53228,
          workspaceRegistry,
          workspaceRoot: "/workspace/taskweavn/plato-workspace",
        }),
      ],
      expect.objectContaining({
        cwd: "/app/sidecar",
        env: expect.objectContaining({
          ELECTRON_RUN_AS_NODE: "1",
          PATH: "/usr/bin:/bin:/usr/sbin:/sbin",
          PLATO_SIDECAR_LAUNCHER_MODE: "sidecar",
          PLATO_STARTUP_ID: "startup-launcher-test",
        }),
        stdio: ["ignore", "pipe", "pipe"],
      }),
    );
    expect(runtime.baseUrl).toBe("http://127.0.0.1:53228");
  });

  it("returns redacted diagnostics when the sidecar exits before readiness", async () => {
    const child = createFakeChild();
    const spawnProcess = vi.fn(() => {
      queueMicrotask(() => {
        child.stderr.write(
          "LLM_API_KEY=secret-value /workspace/taskweavn/plato-workspace/db.sqlite\n",
        );
        child.exitCode = 1;
        child.emit("exit", 1, null);
      });
      return child;
    });

    await expect(
      startPythonSidecar({
        appVersion: "0.1.0-test",
        electronVersion: "42.0.0-test",
        fetchHealth: vi.fn(async () => false),
        findPort: vi.fn(async () => 53226),
        healthPollIntervalMs: 1,
        repoRoot: "/workspace/taskweavn",
        spawnProcess,
        startupId: "startup-test",
        timeoutMs: 50,
        workspaceRoot: "/workspace/taskweavn/plato-workspace",
      }),
    ).rejects.toBeInstanceOf(SidecarStartupError);

    try {
      await startPythonSidecar({
        appVersion: "0.1.0-test",
        electronVersion: "42.0.0-test",
        fetchHealth: vi.fn(async () => false),
        findPort: vi.fn(async () => 53227),
        healthPollIntervalMs: 1,
        repoRoot: "/workspace/taskweavn",
        spawnProcess: vi.fn(() => {
          const retryChild = createFakeChild();
          queueMicrotask(() => {
            retryChild.stderr.write(
              "OPENROUTER_API_KEY=another-secret /workspace/taskweavn/plato-workspace/log.txt\n",
            );
            retryChild.exitCode = 1;
            retryChild.emit("exit", 1, null);
          });
          return retryChild;
        }),
        startupId: "startup-redaction",
        timeoutMs: 50,
        workspaceRoot: "/workspace/taskweavn/plato-workspace",
      });
    } catch (error) {
      expect(error).toBeInstanceOf(SidecarStartupError);
      expect(error.diagnostics.status).toBe("sidecar_failed");
      expect(error.diagnostics.stderr.join("\n")).toContain("OPENROUTER_API_KEY=[redacted]");
      expect(error.diagnostics.stderr.join("\n")).toContain("workspace://current");
      expect(error.diagnostics.stderr.join("\n")).not.toContain("another-secret");
      expect(error.diagnostics.stderr.join("\n")).not.toContain(
        "/workspace/taskweavn/plato-workspace",
      );
    }
  });
});

function createFakeChild() {
  const child = new EventEmitter();
  child.exitCode = null;
  child.kill = vi.fn();
  child.pid = 1234;
  child.signalCode = null;
  child.stderr = new PassThrough();
  child.stdout = new PassThrough();
  return child;
}
