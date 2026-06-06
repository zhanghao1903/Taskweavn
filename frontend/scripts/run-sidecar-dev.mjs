#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(frontendRoot, "..");
const npmBin = process.platform === "win32" ? "npm.cmd" : "npm";

const options = parseArgs(process.argv.slice(2));
const runDir = mkdtempSync(path.join(tmpdir(), "taskweavn-sidecar-dev-"));
const workspaceDir = options.workspaceDir ?? path.join(runDir, "workspace");
const readyFile = path.join(runDir, "sidecar-ready.json");

let sidecarFixture = null;
let viteChild = null;
let shuttingDown = false;

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    shuttingDown = true;
    stopChild(viteChild);
    stopChild(sidecarFixture?.child ?? null);
    cleanup();
    process.kill(process.pid, signal);
  });
}

try {
  sidecarFixture = startSidecarFixture();
  const sidecarInfo = await waitForReadyFile(sidecarFixture, 20_000);
  printReadyInfo(sidecarInfo);
  viteChild = startVite(sidecarInfo);
  process.exitCode = await waitForDevExit(sidecarFixture, viteChild);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
} finally {
  shuttingDown = true;
  stopChild(viteChild);
  stopChild(sidecarFixture?.child ?? null);
  cleanup();
}

function parseArgs(args) {
  let fixtureFlag = "--first-run-unconfigured";
  let workspaceDir = null;
  const viteArgs = [];

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    }
    if (arg === "--first-run-unconfigured" || arg === "--first-run-configured") {
      fixtureFlag = arg;
      continue;
    }
    if (arg === "--workspace") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--workspace requires a path");
      }
      workspaceDir = path.resolve(value);
      index += 1;
      continue;
    }
    if (arg === "--") {
      viteArgs.push(...args.slice(index + 1));
      break;
    }
    viteArgs.push(arg);
  }

  return {
    fixtureFlag,
    viteArgs,
    workspaceDir,
  };
}

function printUsage() {
  console.log(`Usage:
  npm run dev:sidecar:first-run
  npm run dev:sidecar:configured
  npm run dev:sidecar:first-run -- --port 5174
  npm run dev:sidecar:first-run -- --workspace /tmp/plato-first-run --port 5174

Starts a seeded Product 1.0 sidecar fixture, waits for its ready descriptor,
then launches Vite in HTTP mode with the correct sidecar env vars.

Options:
  --first-run-unconfigured  Start with Settings first-run blocked. Default.
  --first-run-configured    Start with deterministic configured readiness.
  --workspace <path>        Use a specific sidecar workspace path.
  --help                    Show this help.

Unknown args are forwarded to Vite.`);
}

function startSidecarFixture() {
  const child = spawn(
    "uv",
    [
      "run",
      "python",
      "-m",
      "tests.fixtures.sidecar_smoke",
      "--workspace",
      workspaceDir,
      "--keep-alive",
      "--ready-file",
      readyFile,
      options.fixtureFlag,
    ],
    {
      cwd: repoRoot,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  const fixture = {
    child,
    exited: null,
    readyFile,
    workspaceDir,
  };
  child.stdout.on("data", (chunk) => process.stdout.write(chunk));
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  child.on("exit", (code, signal) => {
    fixture.exited = { code, signal };
  });
  return fixture;
}

async function waitForReadyFile(fixture, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (existsSync(fixture.readyFile)) {
      return {
        ...JSON.parse(readFileSync(fixture.readyFile, "utf8")),
        workspaceDir: fixture.workspaceDir,
      };
    }
    if (fixture.exited !== null) {
      throw new Error(
        `sidecar smoke exited before ready file was written: ${JSON.stringify(
          fixture.exited,
        )}`,
      );
    }
    await delay(100);
  }
  throw new Error(`timed out waiting for sidecar ready file: ${fixture.readyFile}`);
}

function printReadyInfo(sidecarInfo) {
  console.log("\n[plato-sidecar-dev] sidecar ready");
  console.log(`[plato-sidecar-dev] baseUrl=${sidecarInfo.baseUrl}`);
  console.log(`[plato-sidecar-dev] sessionId=${sidecarInfo.sessionId}`);
  console.log(`[plato-sidecar-dev] workspace=${sidecarInfo.workspaceDir}`);
  console.log("[plato-sidecar-dev] launching Vite with HTTP runtime\n");
}

function startVite(sidecarInfo) {
  return spawn(npmBin, ["run", "dev", "--", ...options.viteArgs], {
    cwd: frontendRoot,
    env: {
      ...process.env,
      VITE_PLATO_API_BASE_URL: sidecarInfo.baseUrl,
      VITE_PLATO_API_MODE: "http",
      VITE_PLATO_SESSION_ID: sidecarInfo.sessionId,
    },
    stdio: "inherit",
  });
}

function waitForDevExit(fixture, vite) {
  return new Promise((resolve) => {
    vite.once("exit", (code, signal) => {
      resolve(signal === null ? code ?? 1 : 1);
    });
    fixture.child.once("exit", (code, signal) => {
      if (shuttingDown) {
        return;
      }
      console.error(
        `sidecar exited while Vite was running: ${JSON.stringify({ code, signal })}`,
      );
      resolve(code ?? 1);
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

function cleanup() {
  rmSync(runDir, { force: true, recursive: true });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
