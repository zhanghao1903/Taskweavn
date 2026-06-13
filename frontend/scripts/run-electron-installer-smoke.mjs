#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const defaultInstallerManifest = path.join(
  frontendRoot,
  "dist-electron-installer",
  "installer-manifest.json",
);
const nodeBin = process.execPath;
const npmBin = process.platform === "win32" ? "npm.cmd" : "npm";

const options = parseArgs(process.argv.slice(2));
const runDir = mkdtempSync(path.join(tmpdir(), "taskweavn-electron-installer-smoke-"));
const mountPoint = path.join(runDir, "Plato");
let mounted = false;

try {
  if (process.platform !== "darwin") {
    throw new Error("electron:smoke:installer currently supports macOS only.");
  }

  if (!options.skipPackage) {
    await runCommand(npmBin, ["run", "electron:package:installer"], {
      label: "electron:package:installer",
    });
  }

  const installerManifest = readInstallerManifest(options);
  const dmgPath = options.installerPath ?? installerManifest.dmgPath;
  if (typeof dmgPath !== "string" || !existsSync(dmgPath)) {
    throw new Error(`Installer DMG not found: ${String(dmgPath)}`);
  }

  attachDmg(dmgPath, mountPoint);
  mounted = true;
  const smokePackageDir = prepareMountedInstallerSmokePackage({
    installerManifest,
    mountPoint,
  });

  await runSmoke({
    args: [
      "--launcher",
      "--package-dir",
      smokePackageDir,
      "--first-run-configured",
      "--packaged-default-workspace",
    ],
    label: "configured installer smoke with packaged default workspace",
  });
  await runSmoke({
    args: [
      "--launcher",
      "--package-dir",
      smokePackageDir,
      "--first-run-unconfigured",
    ],
    label: "first-run installer smoke",
  });
  await runSmoke({
    args: [
      "--launcher",
      "--package-dir",
      smokePackageDir,
      "--startup-diagnostics",
    ],
    label: "startup diagnostics installer smoke",
  });
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
} finally {
  if (mounted) {
    await detachDmg(mountPoint);
  }
  rmSync(runDir, {
    force: true,
    maxRetries: 5,
    recursive: true,
    retryDelay: 500,
  });
}

function parseArgs(args) {
  let installerManifestPath = defaultInstallerManifest;
  let installerPath = null;
  let skipPackage = false;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    }
    if (arg === "--installer") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--installer requires a path");
      }
      installerPath = path.resolve(value);
      index += 1;
      continue;
    }
    if (arg === "--manifest") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--manifest requires a path");
      }
      installerManifestPath = path.resolve(value);
      index += 1;
      continue;
    }
    if (arg === "--skip-package") {
      skipPackage = true;
      continue;
    }
    throw new Error(`unknown option for electron:smoke:installer: ${arg}`);
  }

  return {
    installerManifestPath,
    installerPath,
    skipPackage,
  };
}

function printUsage() {
  console.log(`Usage:
  npm run electron:smoke:installer
  npm run electron:smoke:installer -- --skip-package
  npm run electron:smoke:installer -- --installer ./dist-electron-installer/Plato-<version>-macos-arm64.dmg

Builds or reuses a local DMG installer candidate, mounts it read-only, and runs
configured, first-run, and startup diagnostics smoke through the mounted
launcher-backed bundled Python app.

Options:
  --installer <path>   DMG path. Defaults to installer-manifest.json dmgPath.
  --manifest <path>    Installer manifest path.
  --skip-package       Reuse the existing installer DMG.
  --help               Show this help.`);
}

function readInstallerManifest({ installerManifestPath }) {
  if (!existsSync(installerManifestPath)) {
    throw new Error(
      `Installer manifest not found: ${installerManifestPath}. Run npm run electron:package:installer first.`,
    );
  }
  return JSON.parse(readFileSync(installerManifestPath, "utf8"));
}

function attachDmg(dmgPath, targetMountPoint) {
  console.log(`[plato-electron-installer-smoke] mount ${dmgPath}`);
  runSync(
    "hdiutil",
    [
      "attach",
      dmgPath,
      "-nobrowse",
      "-readonly",
      "-mountpoint",
      targetMountPoint,
    ],
    { label: "hdiutil attach" },
  );
}

function prepareMountedInstallerSmokePackage({ installerManifest, mountPoint }) {
  const sourceManifestPath = installerManifest.packageManifestPath;
  if (typeof sourceManifestPath !== "string" || !existsSync(sourceManifestPath)) {
    throw new Error(
      `Package manifest not found for installer smoke: ${String(sourceManifestPath)}`,
    );
  }
  const packageManifest = JSON.parse(readFileSync(sourceManifestPath, "utf8"));
  const appName = packageManifest.appName ?? installerManifest.appName ?? "Plato";
  const mountedAppRoot = path.join(mountPoint, `${appName}.app`);
  if (!existsSync(mountedAppRoot)) {
    throw new Error(`Mounted installer app not found: ${mountedAppRoot}`);
  }

  const smokePackageDir = path.join(runDir, "mounted-package");
  mkdirSync(smokePackageDir, { recursive: true });
  cpSync(mountedAppRoot, path.join(smokePackageDir, `${appName}.app`), {
    recursive: true,
    verbatimSymlinks: true,
  });
  writeFileSync(
    path.join(smokePackageDir, "package-manifest.json"),
    `${JSON.stringify(packageManifest, null, 2)}\n`,
    "utf8",
  );
  return smokePackageDir;
}

async function detachDmg(targetMountPoint) {
  console.log(`[plato-electron-installer-smoke] detach ${targetMountPoint}`);
  const attempts = [
    ["detach", targetMountPoint, "-quiet"],
    ["detach", targetMountPoint, "-quiet"],
    ["detach", targetMountPoint, "-force", "-quiet"],
  ];
  for (const args of attempts) {
    const result = spawnSync("hdiutil", args, {
      cwd: frontendRoot,
      encoding: "utf8",
      stdio: "inherit",
    });
    if (result.status === 0) {
      return;
    }
    await delay(1_000);
  }
  throw new Error("hdiutil detach failed after retries");
}

async function runSmoke({ args, label }) {
  await runCommand(nodeBin, [path.join("scripts", "run-electron-smoke.mjs"), ...args], {
    label,
  });
}

function runSync(command, args, { label }) {
  console.log(`[plato-electron-installer-smoke] start ${label}`);
  const result = spawnSync(command, args, {
    cwd: frontendRoot,
    encoding: "utf8",
    stdio: "inherit",
  });
  if (result.status !== 0) {
    throw new Error(`${label} failed with exit code ${result.status ?? "null"}`);
  }
  console.log(`[plato-electron-installer-smoke] pass ${label}`);
}

function runCommand(command, args, { label }) {
  console.log(`[plato-electron-installer-smoke] start ${label}`);
  const child = spawn(command, args, {
    cwd: frontendRoot,
    env: process.env,
    stdio: "inherit",
  });

  return new Promise((resolve, reject) => {
    child.once("exit", (code, signal) => {
      if (signal !== null || code !== 0) {
        reject(
          new Error(
            `${label} failed: code=${code ?? "null"} signal=${signal ?? "null"}`,
          ),
        );
        return;
      }
      console.log(`[plato-electron-installer-smoke] pass ${label}`);
      resolve();
    });
  });
}
