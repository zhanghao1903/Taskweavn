#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(frontendRoot, "..");
const runDir = mkdtempSync(path.join(tmpdir(), "taskweavn-sidecar-e2e-"));
const npmBin = process.platform === "win32" ? "npm.cmd" : "npm";

const configuredSidecar = startSidecarFixture({
  flag: "--first-run-configured",
  name: "configured",
});
const unconfiguredSidecar = startSidecarFixture({
  flag: "--first-run-unconfigured",
  name: "unconfigured",
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    stopSidecars();
    process.kill(process.pid, signal);
  });
}

try {
  const [configuredInfo, unconfiguredInfo] = await Promise.all([
    waitForReadyFile(configuredSidecar, 20_000),
    waitForReadyFile(unconfiguredSidecar, 20_000),
  ]);
  const testCode = await runFrontendE2E({
    configured: configuredInfo,
    unconfigured: unconfiguredInfo,
  });
  process.exitCode = testCode;
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
} finally {
  stopSidecars();
  rmSync(runDir, { force: true, recursive: true });
}

function startSidecarFixture({ flag, name }) {
  const workspaceDir = path.join(runDir, `${name}-workspace`);
  const readyFile = path.join(runDir, `${name}-sidecar-ready.json`);
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
      flag,
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
    name,
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

async function runFrontendE2E({ configured, unconfigured }) {
  const child = spawn(
    npmBin,
    [
      "test",
      "--",
      "--run",
      "src/e2e/auditEvidence.e2e.test.tsx",
      "src/e2e/commandFailureRecovery.e2e.test.tsx",
      "src/e2e/diagnosticsBundleExport.e2e.test.tsx",
      "src/e2e/settingsFirstRun.e2e.test.tsx",
    ],
    {
      cwd: frontendRoot,
      env: {
        ...process.env,
        PLATO_E2E_DIAGNOSTICS_LOG_URL: configured.diagnosticsLogUrl,
        PLATO_E2E_FIRST_RUN_CONFIGURED_BASE_URL: configured.baseUrl,
        PLATO_E2E_FIRST_RUN_CONFIGURED_SESSION_ID: configured.sessionId,
        PLATO_E2E_FIRST_RUN_UNCONFIGURED_BASE_URL: unconfigured.baseUrl,
        PLATO_E2E_FIRST_RUN_UNCONFIGURED_SESSION_ID: unconfigured.sessionId,
        PLATO_E2E_LOG_RECORD_ID: configured.logRecordId,
        PLATO_E2E_SESSION_ID: configured.sessionId,
        PLATO_E2E_SIDECAR_BASE_URL: configured.baseUrl,
        PLATO_E2E_TASK_ID: configured.taskId,
        PLATO_E2E_WORKSPACE_ROOT: configured.workspaceDir,
      },
      stdio: "inherit",
    },
  );
  return await waitForExit(child);
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
        `${fixture.name} sidecar smoke exited before ready file was written: ${JSON.stringify(
          fixture.exited,
        )}`,
      );
    }
    await delay(100);
  }
  throw new Error(
    `timed out waiting for ${fixture.name} sidecar ready file: ${fixture.readyFile}`,
  );
}

function waitForExit(child) {
  return new Promise((resolve) => {
    child.once("exit", (code, signal) => {
      if (signal !== null) {
        resolve(1);
        return;
      }
      resolve(code ?? 1);
    });
  });
}

function stopSidecars() {
  stopSidecar(configuredSidecar);
  stopSidecar(unconfiguredSidecar);
}

function stopSidecar(fixture) {
  const { child } = fixture;
  if (child.exitCode !== null || child.signalCode !== null) {
    return;
  }
  child.kill("SIGINT");
  setTimeout(() => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill("SIGKILL");
    }
  }, 2_000).unref();
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
