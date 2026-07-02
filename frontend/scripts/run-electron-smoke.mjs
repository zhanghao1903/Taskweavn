#!/usr/bin/env node
import { spawn } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import net from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

import { summarizeWorkspace } from "../electron/workspaceEntry.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(frontendRoot, "..");
const runDir = mkdtempSync(path.join(tmpdir(), "taskweavn-electron-smoke-"));
const npmBin = process.platform === "win32" ? "npm.cmd" : "npm";
const finderLikePath =
  process.platform === "darwin" ? "/usr/bin:/bin:/usr/sbin:/sbin" : process.env.PATH;
const smokeUiLocale = "en-US";
const smokeConfiguredEnv = {
  DEEPSEEK_API_KEY: "test-sidecar-readiness-key",
  LLM_API_KEY: "test-sidecar-readiness-key",
  LLM_MODEL: "deepseek-v4-pro",
  LLM_PROVIDER: "deepseek",
};
const smokeRunnerPath = path.join(frontendRoot, "electron", "smokeRunner.mjs");
const electronBin =
  process.platform === "win32"
    ? path.join(frontendRoot, "node_modules", ".bin", "electron.cmd")
    : path.join(frontendRoot, "node_modules", ".bin", "electron");

const options = parseArgs(process.argv.slice(2));
let sidecarFixture = null;
let seedChild = null;
let viteChild = null;
let electronChild = null;

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    stopAll();
    process.kill(process.pid, signal);
  });
}

try {
  if (!options.packaged && !existsSync(electronBin)) {
    throw new Error("Electron binary not found. Run npm install in frontend first.");
  }

  if (options.kind === "startup-diagnostics" && options.launcher) {
    const smokeFixture = createStartupDiagnosticsFixture();
    electronChild = startPackagedLauncherStartupDiagnosticsSmoke({
      fixture: smokeFixture,
      packageManifest: readPackageManifest(options.packageDir),
    });
  } else if (options.kind === "startup-diagnostics") {
    const smokeFixture = createStartupDiagnosticsFixture();
    electronChild = startPackagedStartupDiagnosticsSmoke({
      fixture: smokeFixture,
      packageManifest: readPackageManifest(options.packageDir),
    });
  } else if (options.kind === "workspace-entry") {
    const smokeFixture = await seedWorkspaceEntryWorkspace(options);
    const rendererPort =
      options.rendererPort ?? (await findAvailablePort("127.0.0.1"));
    const rendererUrl = `http://127.0.0.1:${rendererPort}/`;
    viteChild = startVite(rendererPort);
    await waitForHttp(rendererUrl, 20_000, () => viteChild);
    electronChild = startDevElectronWorkspaceEntrySmoke({
      rendererUrl,
      sidecarInfo: smokeFixture,
    });
  } else if (options.kind === "workspace-git-init") {
    const smokeFixture = seedWorkspaceGitInitWorkspace();
    const rendererPort =
      options.rendererPort ?? (await findAvailablePort("127.0.0.1"));
    const rendererUrl = `http://127.0.0.1:${rendererPort}/`;
    viteChild = startVite(rendererPort);
    await waitForHttp(rendererUrl, 20_000, () => viteChild);
    electronChild = startDevElectronWorkspaceGitInitSmoke({
      rendererUrl,
      sidecarInfo: smokeFixture,
    });
  } else if (options.launcher) {
    const packageManifest = readPackageManifest(options.packageDir);
    validateLauncherPackageManifest(packageManifest);
    const smokeFixture = await seedLauncherWorkspace(options);
    electronChild = startPackagedLauncherElectronSmoke({
      kind: options.kind,
      packageManifest,
      sidecarInfo: smokeFixture,
    });
  } else {
    sidecarFixture = startSidecarFixture(options);
    const sidecarInfo = await waitForReadyFile(sidecarFixture, 20_000);
    const smokeFixture = {
      ...sidecarInfo,
      workspaceDir: sidecarFixture.workspaceDir,
    };
    if (options.packaged) {
      electronChild = startPackagedElectronSmoke({
        kind: options.kind,
        packageManifest: readPackageManifest(options.packageDir),
        sidecarInfo: smokeFixture,
      });
    } else {
      const rendererPort =
        options.rendererPort ?? (await findAvailablePort("127.0.0.1"));
      const rendererUrl = `http://127.0.0.1:${rendererPort}/`;
      viteChild = startVite(rendererPort);
      await waitForHttp(rendererUrl, 20_000, () => viteChild);
      electronChild = startDevElectronSmoke({
        kind: options.kind,
        rendererUrl,
        sidecarInfo: smokeFixture,
      });
    }
  }
  process.exitCode = await waitForExit(electronChild);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
} finally {
  stopAll();
  rmSync(runDir, {
    force: true,
    maxRetries: 5,
    recursive: true,
    retryDelay: 500,
  });
}

function parseArgs(args) {
  let kind = "configured";
  let launcher = false;
  let packaged = false;
  let packagedDefaultWorkspace = false;
  let packageDir = path.join(frontendRoot, "dist-electron");
  let packageDirExplicit = false;
  let readOnlyInquiryLlm = false;
  let rendererPort = null;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
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
    if (arg === "--packaged") {
      packaged = true;
      continue;
    }
    if (arg === "--launcher") {
      launcher = true;
      packaged = true;
      continue;
    }
    if (arg === "--package-dir") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--package-dir requires a path");
      }
      packageDir = path.resolve(value);
      packageDirExplicit = true;
      index += 1;
      continue;
    }
    if (arg === "--packaged-default-workspace") {
      packagedDefaultWorkspace = true;
      continue;
    }
    if (arg === "--first-run-configured") {
      kind = "configured";
      continue;
    }
    if (arg === "--first-run-unconfigured") {
      kind = "first-run";
      continue;
    }
    if (arg === "--startup-diagnostics") {
      kind = "startup-diagnostics";
      continue;
    }
    if (arg === "--workspace-entry") {
      kind = "workspace-entry";
      continue;
    }
    if (arg === "--workspace-git-init") {
      kind = "workspace-git-init";
      continue;
    }
    if (arg === "--read-only-inquiry-llm") {
      readOnlyInquiryLlm = true;
      continue;
    }
    throw new Error(`unknown option for electron:smoke: ${arg}`);
  }

  if (rendererPort !== null && !Number.isInteger(rendererPort)) {
    throw new Error("--renderer-port must be an integer");
  }
  if (launcher && !packageDirExplicit) {
    packageDir = path.join(frontendRoot, "dist-electron-launcher");
  }
  if (kind === "startup-diagnostics" && !packaged) {
    throw new Error("--startup-diagnostics requires --packaged");
  }
  if (kind === "startup-diagnostics" && rendererPort !== null) {
    throw new Error("--startup-diagnostics cannot use --renderer-port");
  }
  if (kind === "workspace-entry" && packaged) {
    throw new Error("--workspace-entry currently supports the Electron dev shell");
  }
  if (kind === "workspace-git-init" && packaged) {
    throw new Error("--workspace-git-init currently supports the Electron dev shell");
  }
  if (packagedDefaultWorkspace && !launcher) {
    throw new Error("--packaged-default-workspace requires --launcher");
  }
  if (readOnlyInquiryLlm && launcher) {
    throw new Error("--read-only-inquiry-llm requires a seeded sidecar fixture, not --launcher");
  }
  if (
    readOnlyInquiryLlm &&
    ["first-run", "startup-diagnostics", "workspace-entry", "workspace-git-init"].includes(
      kind,
    )
  ) {
    throw new Error(
      "--read-only-inquiry-llm currently supports the configured seeded sidecar smoke only",
    );
  }

  return {
    kind,
    launcher,
    packageDir,
    packaged,
    packagedDefaultWorkspace,
    readOnlyInquiryLlm,
    rendererPort,
  };
}

function printUsage() {
  console.log(`Usage:
  npm run electron:smoke
  npm run electron:smoke:first-run
  npm run electron:smoke -- --packaged --first-run-configured
  npm run electron:smoke -- --launcher --first-run-configured
  npm run electron:smoke -- --packaged --startup-diagnostics
  npm run electron:smoke -- --workspace-entry
  npm run electron:smoke -- --workspace-git-init
  npm run electron:smoke -- --renderer-port 5174

Starts a seeded sidecar fixture, opens Electron in smoke mode, and verifies
Product 1.0 desktop acceptance paths. Dev mode launches Vite; packaged mode
loads the local app directory generated by electron:package:dir. Startup
diagnostics mode intentionally skips the seeded sidecar fixture and validates
main-owned sidecar startup failure handling. Launcher mode seeds a workspace,
then lets Electron main start the sidecar through the packaged launcher.

Options:
  --first-run-configured     Run configured Main/Audit/Diagnostics smoke. Default.
  --first-run-unconfigured   Run Settings first-run setup smoke.
  --startup-diagnostics      Run packaged sidecar startup-failure diagnostics smoke.
  --workspace-entry          Run Workspace Picker -> selected workspace smoke.
  --workspace-git-init       Run Settings preference -> Workspace Picker Git init smoke.
  --read-only-inquiry-llm    Enable guarded LLM-rendered Read-Only Inquiry fixture answers.
  --launcher                 Use the launcher-backed package directory.
  --packaged                 Launch the unsigned packaged app directory.
  --packaged-default-workspace
                             Use packaged Application Support workspace instead of PLATO_ELECTRON_WORKSPACE.
  --package-dir <path>       Package output root. Defaults to dist-electron.
  --renderer-port <number>    Vite dev-server port. Defaults to a free port.
  --help                      Show this help.`);
}

async function seedWorkspaceEntryWorkspace({ kind }) {
  const userDataDir = path.join(runDir, "user-data-workspace-entry");
  const workspaceDir = path.join(runDir, "workspace-entry-project");
  const readyFile = path.join(runDir, "workspace-entry-seed-ready.json");
  const workspaceRegistry = workspaceRegistryForWorkspace(workspaceDir);
  const workspaceId = workspaceRegistry[0].workspaceId;
  mkdirSync(userDataDir, { recursive: true });
  mkdirSync(workspaceDir, { recursive: true });
  seedChild = spawn(
    "uv",
    [
      "run",
      "python",
      "-m",
      "tests.fixtures.sidecar_smoke",
      "--workspace",
      workspaceDir,
      "--ready-file",
      readyFile,
      "--workspace-registry-json",
      JSON.stringify(workspaceRegistry),
      kind === "first-run" ? "--first-run-unconfigured" : "--first-run-configured",
    ],
    {
      cwd: repoRoot,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  seedChild.stdout.on("data", (chunk) => process.stdout.write(chunk));
  seedChild.stderr.on("data", (chunk) => process.stderr.write(chunk));
  const exitCode = await waitForExit(seedChild);
  if (exitCode !== 0) {
    throw new Error(`workspace entry seed failed with exit code ${exitCode}`);
  }
  seedChild = null;
  const sidecarInfo = await waitForJsonFile(readyFile, 1_000);
  const workspaceName = path.basename(workspaceDir);
  writeFileSync(
    path.join(userDataDir, "workspace-entry.json"),
    `${JSON.stringify(workspaceEntrySeedStore(workspaceDir), null, 2)}\n`,
    "utf8",
  );
  return {
    ...sidecarInfo,
    userDataDir,
    workspaceDir,
    workspaceId,
    workspaceName,
  };
}

function seedWorkspaceGitInitWorkspace() {
  const userDataDir = path.join(runDir, "user-data-workspace-git-init");
  const workspaceDir = path.join(runDir, "workspace-git-init-project");
  mkdirSync(userDataDir, { recursive: true });
  mkdirSync(workspaceDir, { recursive: true });
  writeFileSync(
    path.join(workspaceDir, "README.md"),
    "# Workspace Git initialization smoke\n",
    "utf8",
  );
  writeFileSync(
    path.join(userDataDir, "workspace-entry.json"),
    `${JSON.stringify(workspaceEntrySeedStore(workspaceDir), null, 2)}\n`,
    "utf8",
  );
  return {
    userDataDir,
    workspaceDir,
    workspaceName: path.basename(workspaceDir),
  };
}

function workspaceEntrySeedStore(workspaceDir) {
  return {
    currentPath: null,
    preferences: {
      initializeGitOnOpen: null,
    },
    schemaVersion: 3,
    workspaces: [
      {
        addedAt: null,
        archived: false,
        archivedAt: null,
        lastOpenedAt: null,
        path: workspaceDir,
      },
    ],
  };
}

async function seedLauncherWorkspace({ kind, packagedDefaultWorkspace }) {
  const userDataDir = path.join(runDir, "user-data");
  const workspaceDir = packagedDefaultWorkspace
    ? path.join(userDataDir, "workspace")
    : path.join(runDir, "workspace-launcher");
  const readyFile = path.join(runDir, "launcher-seed-ready.json");
  const workspaceRegistry = workspaceRegistryForWorkspace(workspaceDir);
  const workspaceId = workspaceRegistry[0].workspaceId;
  mkdirSync(workspaceDir, { recursive: true });
  const firstRunFlag =
    kind === "first-run" ? "--first-run-unconfigured" : "--first-run-configured";
  seedChild = spawn(
    "uv",
    [
      "run",
      "python",
      "-m",
      "tests.fixtures.sidecar_smoke",
      "--workspace",
      workspaceDir,
      "--ready-file",
      readyFile,
      "--workspace-registry-json",
      JSON.stringify(workspaceRegistry),
      firstRunFlag,
    ],
    {
      cwd: repoRoot,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  seedChild.stdout.on("data", (chunk) => process.stdout.write(chunk));
  seedChild.stderr.on("data", (chunk) => process.stderr.write(chunk));
  const exitCode = await waitForExit(seedChild);
  if (exitCode !== 0) {
    throw new Error(`launcher workspace seed failed with exit code ${exitCode}`);
  }
  seedChild = null;
  const sidecarInfo = await waitForJsonFile(readyFile, 1_000);
  return {
    ...sidecarInfo,
    userDataDir,
    workspaceDir,
    workspaceId,
  };
}

function workspaceRegistryForWorkspace(workspaceDir) {
  const workspaceSummary = summarizeWorkspace(workspaceDir, workspaceDir);
  return [
    {
      isCurrent: true,
      label: workspaceSummary.name,
      rootPath: workspaceDir,
      workspaceId: workspaceSummary.id,
    },
  ];
}

function createStartupDiagnosticsFixture() {
  const workspaceDir = path.join(runDir, "workspace-startup-failure");
  mkdirSync(workspaceDir, { recursive: true });
  return {
    repoRoot,
    workspaceDir,
  };
}

function startSidecarFixture({ kind, readOnlyInquiryLlm }) {
  const workspaceDir = path.join(runDir, "workspace");
  const readyFile = path.join(runDir, "sidecar-ready.json");
  const firstRunFlag =
    kind === "first-run" ? "--first-run-unconfigured" : "--first-run-configured";
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
      firstRunFlag,
      ...(readOnlyInquiryLlm ? ["--enable-read-only-inquiry-llm"] : []),
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

function startVite(port) {
  return spawn(
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
}

function startDevElectronSmoke({ kind, rendererUrl, sidecarInfo }) {
  const baseUrl = sidecarInfo.baseUrl;
  console.log(`[plato-electron-smoke] renderer=${rendererUrl}`);
  console.log(`[plato-electron-smoke] sidecar=${baseUrl}`);
  console.log(`[plato-electron-smoke] session=${sidecarInfo.sessionId}`);
  console.log(`[plato-electron-smoke] kind=${kind}`);
  console.log("[plato-electron-smoke] mode=dev");

  return spawn(electronBin, [path.join(frontendRoot, "electron", "main.mjs")], {
    cwd: frontendRoot,
    env: {
      ...process.env,
      PLATO_ELECTRON_DISABLE_EVENTS: "1",
      PLATO_ELECTRON_RENDERER_URL: rendererUrl,
      PLATO_ELECTRON_REPO_ROOT: repoRoot,
      PLATO_ELECTRON_SIDECAR_BASE_URL: baseUrl,
      PLATO_ELECTRON_SMOKE: "1",
      PLATO_ELECTRON_SMOKE_FIXTURE: JSON.stringify(sidecarInfo),
      PLATO_ELECTRON_SMOKE_KIND: kind,
      PLATO_ELECTRON_SMOKE_RUNNER_PATH: smokeRunnerPath,
      PLATO_ELECTRON_UI_LOCALE: smokeUiLocale,
      PLATO_ELECTRON_WORKSPACE: sidecarInfo.workspaceDir,
    },
    stdio: "inherit",
  });
}

function startDevElectronWorkspaceEntrySmoke({ rendererUrl, sidecarInfo }) {
  console.log(`[plato-electron-smoke] renderer=${rendererUrl}`);
  console.log(`[plato-electron-smoke] workspace=${sidecarInfo.workspaceName}`);
  console.log("[plato-electron-smoke] kind=workspace-entry");
  console.log("[plato-electron-smoke] mode=dev");

  const env = {
    ...process.env,
    ...smokeConfiguredEnv,
    PLATO_ELECTRON_DISABLE_EVENTS: "1",
    PLATO_ELECTRON_RENDERER_URL: rendererUrl,
    PLATO_ELECTRON_REPO_ROOT: repoRoot,
    PLATO_ELECTRON_REQUIRE_WORKSPACE_SELECTION: "1",
    PLATO_ELECTRON_SMOKE: "1",
    PLATO_ELECTRON_SMOKE_FIXTURE: JSON.stringify(sidecarInfo),
    PLATO_ELECTRON_SMOKE_KIND: "workspace-entry",
    PLATO_ELECTRON_UI_LOCALE: smokeUiLocale,
    PLATO_ELECTRON_USER_DATA_DIR: sidecarInfo.userDataDir,
  };
  delete env.PLATO_ELECTRON_SIDECAR_BASE_URL;
  delete env.PLATO_ELECTRON_WORKSPACE;

  return spawn(electronBin, [path.join(frontendRoot, "electron", "main.mjs")], {
    cwd: frontendRoot,
    env,
    stdio: "inherit",
  });
}

function startDevElectronWorkspaceGitInitSmoke({ rendererUrl, sidecarInfo }) {
  console.log(`[plato-electron-smoke] renderer=${rendererUrl}`);
  console.log(`[plato-electron-smoke] workspace=${sidecarInfo.workspaceName}`);
  console.log("[plato-electron-smoke] kind=workspace-git-init");
  console.log("[plato-electron-smoke] mode=dev");

  const env = {
    ...process.env,
    ...smokeConfiguredEnv,
    PLATO_ELECTRON_DISABLE_EVENTS: "1",
    PLATO_ELECTRON_RENDERER_URL: rendererUrl,
    PLATO_ELECTRON_REPO_ROOT: repoRoot,
    PLATO_ELECTRON_REQUIRE_WORKSPACE_SELECTION: "1",
    PLATO_ELECTRON_SMOKE: "1",
    PLATO_ELECTRON_SMOKE_FIXTURE: JSON.stringify(sidecarInfo),
    PLATO_ELECTRON_SMOKE_KIND: "workspace-git-init",
    PLATO_ELECTRON_UI_LOCALE: smokeUiLocale,
    PLATO_ELECTRON_USER_DATA_DIR: sidecarInfo.userDataDir,
  };
  delete env.PLATO_ELECTRON_SIDECAR_BASE_URL;
  delete env.PLATO_ELECTRON_WORKSPACE;

  return spawn(electronBin, [path.join(frontendRoot, "electron", "main.mjs")], {
    cwd: frontendRoot,
    env,
    stdio: "inherit",
  });
}

function startPackagedElectronSmoke({ kind, packageManifest, sidecarInfo }) {
  const baseUrl = sidecarInfo.baseUrl;
  console.log(`[plato-electron-smoke] app=${packageManifest.appRoot}`);
  console.log(`[plato-electron-smoke] executable=${packageManifest.executablePath}`);
  console.log(`[plato-electron-smoke] sidecar=${baseUrl}`);
  console.log(`[plato-electron-smoke] session=${sidecarInfo.sessionId}`);
  console.log(`[plato-electron-smoke] kind=${kind}`);
  console.log("[plato-electron-smoke] mode=packaged");

  return spawn(packageManifest.executablePath, [], {
    cwd: frontendRoot,
    env: {
      ...process.env,
      PLATO_ELECTRON_DISABLE_EVENTS: "1",
      PLATO_ELECTRON_REPO_ROOT: repoRoot,
      PLATO_ELECTRON_SIDECAR_BASE_URL: baseUrl,
      PLATO_ELECTRON_SMOKE: "1",
      PLATO_ELECTRON_SMOKE_FIXTURE: JSON.stringify(sidecarInfo),
      PLATO_ELECTRON_SMOKE_KIND: kind,
      PLATO_ELECTRON_UI_LOCALE: smokeUiLocale,
      PLATO_ELECTRON_WORKSPACE: sidecarInfo.workspaceDir,
    },
    stdio: "inherit",
  });
}

function startPackagedLauncherElectronSmoke({ kind, packageManifest, sidecarInfo }) {
  validateLauncherPackageManifest(packageManifest);
  console.log(`[plato-electron-smoke] app=${packageManifest.appRoot}`);
  console.log(`[plato-electron-smoke] executable=${packageManifest.executablePath}`);
  console.log("[plato-electron-smoke] sidecar=launcher-owned");
  console.log(`[plato-electron-smoke] session=${sidecarInfo.sessionId}`);
  console.log(`[plato-electron-smoke] kind=${kind}`);
  console.log("[plato-electron-smoke] mode=launcher-packaged");

  const env = launcherElectronEnv({
    explicitWorkspace: !options.packagedDefaultWorkspace,
    firstRun: kind === "first-run" ? "unconfigured" : "configured",
    packageManifest,
    sidecarInfo,
  });

  return spawn(packageManifest.executablePath, [], {
    cwd: frontendRoot,
    env,
    stdio: "inherit",
  });
}

function startPackagedStartupDiagnosticsSmoke({ fixture, packageManifest }) {
  console.log(`[plato-electron-smoke] app=${packageManifest.appRoot}`);
  console.log(`[plato-electron-smoke] executable=${packageManifest.executablePath}`);
  console.log("[plato-electron-smoke] sidecar=main-owned startup failure");
  console.log("[plato-electron-smoke] kind=startup-diagnostics");
  console.log("[plato-electron-smoke] mode=packaged");

  const env = {
    ...process.env,
    PLATO_ELECTRON_DISABLE_EVENTS: "1",
    PLATO_ELECTRON_REPO_ROOT: fixture.repoRoot,
    PLATO_ELECTRON_SIDECAR_TIMEOUT_MS: "1",
    PLATO_ELECTRON_SMOKE: "1",
    PLATO_ELECTRON_SMOKE_FIXTURE: JSON.stringify(fixture),
    PLATO_ELECTRON_SMOKE_KIND: "startup-diagnostics",
    PLATO_ELECTRON_SMOKE_RUNNER_PATH: smokeRunnerPath,
    PLATO_ELECTRON_UI_LOCALE: smokeUiLocale,
    PLATO_ELECTRON_WORKSPACE: fixture.workspaceDir,
  };
  delete env.PLATO_ELECTRON_SIDECAR_BASE_URL;
  delete env.PLATO_ELECTRON_RENDERER_URL;

  return spawn(packageManifest.executablePath, [], {
    cwd: frontendRoot,
    env,
    stdio: "inherit",
  });
}

function startPackagedLauncherStartupDiagnosticsSmoke({
  fixture,
  packageManifest,
}) {
  validateLauncherPackageManifest(packageManifest);
  console.log(`[plato-electron-smoke] app=${packageManifest.appRoot}`);
  console.log(`[plato-electron-smoke] executable=${packageManifest.executablePath}`);
  console.log("[plato-electron-smoke] sidecar=launcher startup failure");
  console.log("[plato-electron-smoke] kind=startup-diagnostics");
  console.log("[plato-electron-smoke] mode=launcher-packaged");

  const env = launcherElectronEnv({
    failure: "runtime_missing",
    firstRun: "configured",
    packageManifest,
    sidecarInfo: {
      ...fixture,
      expectedStartupDiagnosticText: "runtime_missing",
    },
  });

  return spawn(packageManifest.executablePath, [], {
    cwd: frontendRoot,
    env,
    stdio: "inherit",
  });
}

function launcherElectronEnv({
  explicitWorkspace = true,
  failure = null,
  firstRun,
  packageManifest,
  sidecarInfo,
}) {
  const env = {
    ...process.env,
    PATH: finderLikePath,
    PLATO_ELECTRON_DISABLE_EVENTS: "1",
    PLATO_ELECTRON_SIDECAR_LAUNCHER_PATH: packageManifest.sidecarLauncherPath,
    PLATO_ELECTRON_SIDECAR_TIMEOUT_MS:
      process.env.PLATO_ELECTRON_SIDECAR_TIMEOUT_MS ?? "120000",
    PLATO_ELECTRON_SMOKE: "1",
    PLATO_ELECTRON_SMOKE_FIXTURE: JSON.stringify(sidecarInfo),
    PLATO_ELECTRON_SMOKE_KIND:
      sidecarInfo.expectedStartupDiagnosticText === undefined
        ? firstRun === "unconfigured"
          ? "first-run"
          : "configured"
        : "startup-diagnostics",
    PLATO_ELECTRON_SMOKE_RUNNER_PATH: smokeRunnerPath,
    PLATO_ELECTRON_UI_LOCALE: smokeUiLocale,
    // Keep launcher release smoke provider-independent. The dedicated
    // read-only inquiry LLM smokes cover provider-rendered answers with a
    // seeded fake provider.
    PLATO_ENABLE_READ_ONLY_INQUIRY_LLM: "0",
    PLATO_SIDECAR_LAUNCHER_FIRST_RUN: firstRun,
    PLATO_SIDECAR_LAUNCHER_RUNTIME_MANIFEST:
      packageManifest.sidecarRuntimeManifestPath,
  };
  if (explicitWorkspace) {
    env.PLATO_ELECTRON_WORKSPACE = sidecarInfo.workspaceDir;
    if (typeof sidecarInfo.userDataDir === "string") {
      env.PLATO_ELECTRON_USER_DATA_DIR = sidecarInfo.userDataDir;
    }
  } else {
    env.PLATO_ELECTRON_ALLOW_DEFAULT_WORKSPACE = "1";
    env.PLATO_ELECTRON_USER_DATA_DIR = sidecarInfo.userDataDir;
    delete env.PLATO_ELECTRON_WORKSPACE;
  }
  if (failure !== null) {
    env.PLATO_SIDECAR_LAUNCHER_FAILURE = failure;
  }
  delete env.PLATO_ELECTRON_RENDERER_URL;
  delete env.PLATO_ELECTRON_REPO_ROOT;
  delete env.PLATO_ELECTRON_SIDECAR_BASE_URL;
  deleteRuntimeEnvLeakKeys(env);
  return env;
}

function readPackageManifest(packageDir) {
  const manifestPath = path.join(packageDir, "package-manifest.json");
  if (!existsSync(manifestPath)) {
    throw new Error(
      `Packaged Electron manifest not found: ${manifestPath}. Run npm run electron:package:dir first.`,
    );
  }
  const manifest = normalizePackageManifest(
    JSON.parse(readFileSync(manifestPath, "utf8")),
    path.dirname(manifestPath),
  );
  const executablePath = manifest.executablePath;
  if (typeof executablePath !== "string" || !existsSync(executablePath)) {
    throw new Error(
      `Packaged Electron executable not found: ${String(executablePath)}`,
    );
  }
  return manifest;
}

function normalizePackageManifest(manifest, packageDir) {
  if (process.platform !== "darwin") {
    return manifest;
  }

  const appName = manifest.appName ?? "Plato";
  const appRoot = path.join(packageDir, `${appName}.app`);
  if (!existsSync(appRoot)) {
    return manifest;
  }

  const appResourceDir = path.join(appRoot, "Contents", "Resources", "app");
  const sidecarLauncherPath = path.join(
    appResourceDir,
    "sidecar",
    "plato-sidecar-launcher.mjs",
  );
  const sidecarRuntimeManifestPath = path.join(
    appResourceDir,
    "sidecar",
    "runtime",
    "launcher-runtime.json",
  );
  return {
    ...manifest,
    appResourceDir,
    appRoot,
    executablePath: path.join(appRoot, "Contents", "MacOS", "Electron"),
    sidecarLauncherPath: existsSync(sidecarLauncherPath)
      ? sidecarLauncherPath
      : manifest.sidecarLauncherPath,
    sidecarRuntimeManifestPath: existsSync(sidecarRuntimeManifestPath)
      ? sidecarRuntimeManifestPath
      : manifest.sidecarRuntimeManifestPath,
  };
}

function validateLauncherPackageManifest(manifest) {
  for (const key of ["sidecarLauncherPath", "sidecarRuntimeManifestPath"]) {
    if (typeof manifest[key] !== "string" || !existsSync(manifest[key])) {
      throw new Error(`Launcher package manifest is missing ${key}`);
    }
  }
  return readPackagedLauncherRuntime(manifest);
}

function readPackagedLauncherRuntime(packageManifest) {
  const manifestPath = packageManifest.sidecarRuntimeManifestPath;
  const manifestText = readFileSync(manifestPath, "utf8");
  if (manifestText.includes(path.join(repoRoot, ".venv"))) {
    throw new Error("Launcher runtime manifest still references the repo .venv");
  }
  if (manifestText.includes(path.join(repoRoot, "src"))) {
    throw new Error("Launcher runtime manifest still references repo src");
  }
  if (manifestText.includes(path.join(repoRoot, "tests"))) {
    throw new Error("Launcher runtime manifest still references repo tests");
  }

  const runtimeManifest = JSON.parse(manifestText);
  if (runtimeManifest.mode !== "sidecar") {
    throw new Error(
      `Launcher runtime mode must be sidecar, got ${String(runtimeManifest.mode)}`,
    );
  }
  if (
    ![
      "bundled-python",
      "self-contained-python-env-candidate",
    ].includes(runtimeManifest.runtimeKind)
  ) {
    throw new Error(
      `Launcher runtime kind is not package-local: ${String(
        runtimeManifest.runtimeKind,
      )}`,
    );
  }

  const manifestDir = path.dirname(manifestPath);
  const runtimeDir = manifestDir;
  const pythonExecutable = resolveRuntimeManifestPath(
    runtimeManifest.pythonExecutable,
    manifestDir,
  );
  const pythonPathEntries = Array.isArray(runtimeManifest.pythonPathEntries)
    ? runtimeManifest.pythonPathEntries.map((entry) =>
        resolveRuntimeManifestPath(entry, manifestDir),
      )
    : [];

  if (!existsSync(pythonExecutable)) {
    throw new Error(`Packaged launcher Python executable missing: ${pythonExecutable}`);
  }
  if (pythonPathEntries.length === 0) {
    throw new Error("Packaged launcher runtime has no pythonPathEntries");
  }
  for (const entry of pythonPathEntries) {
    if (!existsSync(entry)) {
      throw new Error(`Packaged launcher PYTHONPATH entry missing: ${entry}`);
    }
  }
  for (const entry of [pythonExecutable, ...pythonPathEntries]) {
    assertPackageLocalRuntimePath(entry, packageManifest);
    assertNotRepoPythonRuntimePath(entry);
  }

  return {
    manifest: runtimeManifest,
    manifestDir,
    pythonExecutable,
    pythonPathEntries,
    runtimeDir,
  };
}

function resolveRuntimeManifestPath(value, manifestDir) {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error("Launcher runtime manifest contains an invalid path");
  }
  return path.isAbsolute(value) ? value : path.resolve(manifestDir, value);
}

function assertPackageLocalRuntimePath(filePath, packageManifest) {
  const relativePath = path.relative(packageManifest.appResourceDir, filePath);
  if (
    relativePath === "" ||
    relativePath.startsWith("..") ||
    path.isAbsolute(relativePath)
  ) {
    throw new Error(`Launcher runtime path is not package-local: ${filePath}`);
  }
}

function assertNotRepoPythonRuntimePath(filePath) {
  for (const forbiddenPath of [
    path.join(repoRoot, ".venv"),
    path.join(repoRoot, "src"),
    path.join(repoRoot, "tests"),
  ]) {
    if (isSameOrInside(filePath, forbiddenPath)) {
      throw new Error(`Launcher runtime path still depends on repo Python: ${filePath}`);
    }
  }
}

function isSameOrInside(filePath, directory) {
  const relativePath = path.relative(directory, filePath);
  return (
    relativePath === "" ||
    (!relativePath.startsWith("..") && !path.isAbsolute(relativePath))
  );
}

function deleteRuntimeEnvLeakKeys(env) {
  delete env.PYTHONHOME;
  delete env.PYTHONPATH;
  delete env.VIRTUAL_ENV;
  for (const key of Object.keys(env)) {
    if (key.startsWith("UV_")) {
      delete env[key];
    }
  }
}

async function waitForReadyFile(fixture, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (existsSync(fixture.readyFile)) {
      return JSON.parse(readFileSync(fixture.readyFile, "utf8"));
    }
    if (fixture.exited !== null) {
      throw new Error(
        `sidecar fixture exited before ready file was written: ${JSON.stringify(
          fixture.exited,
        )}`,
      );
    }
    await delay(100);
  }
  throw new Error(`timed out waiting for sidecar ready file: ${fixture.readyFile}`);
}

async function waitForJsonFile(filePath, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (existsSync(filePath)) {
      return JSON.parse(readFileSync(filePath, "utf8"));
    }
    await delay(50);
  }
  throw new Error(`timed out waiting for JSON file: ${filePath}`);
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

async function waitForHttp(url, timeoutMs, childRef) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const child = childRef();
    if (child?.exitCode !== null || child?.signalCode !== null) {
      throw new Error("Vite exited before Electron smoke could start.");
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

function waitForExit(child) {
  return new Promise((resolve) => {
    child.once("exit", (code, signal) => {
      resolve(signal === null ? code ?? 1 : 1);
    });
  });
}

function stopAll() {
  stopChild(electronChild);
  stopChild(seedChild);
  stopChild(viteChild);
  stopChild(sidecarFixture?.child ?? null);
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
