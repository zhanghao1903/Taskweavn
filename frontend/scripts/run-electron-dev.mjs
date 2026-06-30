#!/usr/bin/env node
import { spawn } from "node:child_process";
import net from "node:net";
import { existsSync } from "node:fs";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(frontendRoot, "..");
const npmBin = process.platform === "win32" ? "npm.cmd" : "npm";
const electronBin =
  process.platform === "win32"
    ? path.join(frontendRoot, "node_modules", ".bin", "electron.cmd")
    : path.join(frontendRoot, "node_modules", ".bin", "electron");

const options = parseArgs(process.argv.slice(2));
let viteChild = null;
let electronChild = null;

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    stopChild(electronChild);
    stopChild(viteChild);
    process.kill(process.pid, signal);
  });
}

try {
  if (!existsSync(electronBin)) {
    throw new Error("Electron binary not found. Run npm install in frontend first.");
  }

  const rendererPort = options.rendererPort ?? (await findAvailablePort("127.0.0.1"));
  const rendererUrl = `http://127.0.0.1:${rendererPort}/`;
  viteChild = startVite(rendererPort);
  await waitForHttp(rendererUrl, 20_000);
  electronChild = startElectron(rendererUrl);
  process.exitCode = await waitForDevExit(electronChild);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
} finally {
  stopChild(electronChild);
  stopChild(viteChild);
}

function parseArgs(args) {
  let openDevtools = false;
  let rendererPort = null;
  let sidecarTimeoutMs = null;
  let workspace = path.join(repoRoot, "plato-workspace");
  let computerUseBackend = null;
  let computerUseAllowedApps = null;
  let computerUseHelperManifest = null;
  let computerUseHelperAppPath = null;
  let computerUseHelperAutoLaunch = null;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    }
    if (arg === "--open-devtools") {
      openDevtools = true;
      continue;
    }
    if (arg === "--renderer-port") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--renderer-port requires a number");
      }
      rendererPort = Number(value);
      index += 1;
      continue;
    }
    if (arg === "--sidecar-timeout-ms") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--sidecar-timeout-ms requires a number");
      }
      sidecarTimeoutMs = Number(value);
      index += 1;
      continue;
    }
    if (arg === "--workspace") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--workspace requires a path");
      }
      workspace = path.resolve(value);
      index += 1;
      continue;
    }
    if (arg === "--computer-use-backend") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--computer-use-backend requires a backend name");
      }
      computerUseBackend = value;
      index += 1;
      continue;
    }
    if (arg === "--computer-use-allowed-apps") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--computer-use-allowed-apps requires a comma-separated value");
      }
      computerUseAllowedApps = value;
      index += 1;
      continue;
    }
    if (arg === "--computer-use-helper-manifest") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--computer-use-helper-manifest requires a path");
      }
      computerUseHelperManifest = path.resolve(value);
      index += 1;
      continue;
    }
    if (arg === "--computer-use-helper-app-path") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--computer-use-helper-app-path requires a path");
      }
      computerUseHelperAppPath = path.resolve(value);
      index += 1;
      continue;
    }
    if (arg === "--computer-use-helper-auto-launch") {
      computerUseHelperAutoLaunch = "1";
      continue;
    }
    if (arg === "--no-computer-use-helper-auto-launch") {
      computerUseHelperAutoLaunch = "0";
      continue;
    }
    throw new Error(`unknown option for electron:dev: ${arg}`);
  }

  if (rendererPort !== null && !Number.isInteger(rendererPort)) {
    throw new Error("--renderer-port must be an integer");
  }
  if (sidecarTimeoutMs !== null && !Number.isInteger(sidecarTimeoutMs)) {
    throw new Error("--sidecar-timeout-ms must be an integer");
  }

  return {
    openDevtools,
    rendererPort,
    sidecarTimeoutMs,
    workspace,
    computerUseBackend,
    computerUseAllowedApps,
    computerUseHelperManifest,
    computerUseHelperAppPath,
    computerUseHelperAutoLaunch,
  };
}

function printUsage() {
  console.log(`Usage:
  npm run electron:dev
  npm run electron:dev -- --workspace ./plato-workspace
  npm run electron:dev -- --renderer-port 5174 --open-devtools

Starts Vite, launches Electron, and lets Electron main own the Python sidecar.

Options:
  --workspace <path>          Workspace root passed to the Python sidecar.
  --renderer-port <number>    Vite dev-server port. Defaults to a free port.
  --sidecar-timeout-ms <n>    Sidecar health timeout. Defaults to 20000.
  --open-devtools             Open detached Electron devtools.
  --computer-use-backend <n>  Optional sidecar backend: disabled, helper, macos.
  --computer-use-allowed-apps <csv>
                              Comma-separated app allowlist, e.g. WeChat,TextEdit.
  --computer-use-helper-manifest <path>
                              Helper endpoint manifest path for helper backend.
  --computer-use-helper-app-path <path>
                              Helper app path for opt-in auto-launch.
  --computer-use-helper-auto-launch
                              Launch helper when its manifest is missing.
  --no-computer-use-helper-auto-launch
                              Disable helper auto-launch.
  --help                      Show this help.`);
}

function startVite(port) {
  const child = spawn(
    npmBin,
    [
      "run",
      "dev",
      "--",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
      "--strictPort",
    ],
    {
      cwd: frontendRoot,
      env: process.env,
      stdio: "inherit",
    },
  );
  return child;
}

function startElectron(rendererUrl) {
  const env = {
    ...process.env,
    PLATO_ELECTRON_RENDERER_URL: rendererUrl,
    PLATO_ELECTRON_REPO_ROOT: repoRoot,
    PLATO_ELECTRON_WORKSPACE: options.workspace,
  };
  if (options.openDevtools) {
    env.PLATO_ELECTRON_OPEN_DEVTOOLS = "1";
  }
  if (options.sidecarTimeoutMs !== null) {
    env.PLATO_ELECTRON_SIDECAR_TIMEOUT_MS = String(options.sidecarTimeoutMs);
  }
  if (options.computerUseBackend !== null) {
    env.PLATO_COMPUTER_USE_BACKEND = options.computerUseBackend;
  }
  if (options.computerUseAllowedApps !== null) {
    env.PLATO_COMPUTER_USE_ALLOWED_APPS = options.computerUseAllowedApps;
  }
  if (options.computerUseHelperManifest !== null) {
    env.PLATO_COMPUTER_USE_HELPER_MANIFEST = options.computerUseHelperManifest;
  }
  if (options.computerUseHelperAppPath !== null) {
    env.PLATO_COMPUTER_USE_HELPER_APP_PATH = options.computerUseHelperAppPath;
  }
  if (options.computerUseHelperAutoLaunch !== null) {
    env.PLATO_COMPUTER_USE_HELPER_AUTO_LAUNCH =
      options.computerUseHelperAutoLaunch;
  }

  console.log(`[plato-electron-dev] renderer=${rendererUrl}`);
  console.log(`[plato-electron-dev] workspace=${options.workspace}`);
  if (options.computerUseBackend !== null) {
    console.log(
      `[plato-electron-dev] computerUseBackend=${options.computerUseBackend}`,
    );
  }
  console.log("[plato-electron-dev] launching Electron");

  return spawn(electronBin, [path.join(frontendRoot, "electron", "main.mjs")], {
    cwd: frontendRoot,
    env,
    stdio: "inherit",
  });
}

async function findAvailablePort(host) {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, host, () => {
      const address = server.address();
      const port =
        typeof address === "object" && address !== null ? address.port : null;
      server.close(() => {
        if (port === null) {
          reject(new Error("could not resolve a free Vite port"));
          return;
        }
        resolve(port);
      });
    });
  });
}

async function waitForHttp(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (viteChild?.exitCode !== null || viteChild?.signalCode !== null) {
      throw new Error("Vite exited before Electron could start.");
    }
    try {
      const response = await fetch(url, {
        signal: AbortSignal.timeout(1_000),
      });
      if (response.ok) {
        return;
      }
    } catch {
      // Vite can take a moment to bind the port.
    }
    await delay(150);
  }
  throw new Error(`timed out waiting for Vite dev server: ${url}`);
}

function waitForDevExit(child) {
  return new Promise((resolve) => {
    child.once("exit", (code, signal) => {
      resolve(signal === null ? code ?? 1 : 1);
    });
  });
}

function stopChild(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) {
    return;
  }
  child.kill("SIGINT");
  setTimeout(() => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill("SIGKILL");
    }
  }, 2_000).unref();
}
