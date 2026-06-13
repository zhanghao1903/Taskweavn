#!/usr/bin/env node
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const nodeBin = process.execPath;
const npmBin = process.platform === "win32" ? "npm.cmd" : "npm";

const options = parseArgs(process.argv.slice(2));

try {
  if (!options.skipPackage) {
    await runCommand(npmBin, ["run", "electron:package:launcher-dir", "--", "--include-smoke"], {
      label: "electron:package:launcher-dir",
    });
  }

  await runSmoke({
    args: ["--launcher", "--first-run-configured"],
    label: "configured launcher smoke",
  });
  await runSmoke({
    args: ["--launcher", "--first-run-unconfigured"],
    label: "first-run launcher smoke",
  });
  await runSmoke({
    args: ["--launcher", "--startup-diagnostics"],
    label: "startup diagnostics launcher smoke",
  });
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

function parseArgs(args) {
  let skipPackage = false;

  for (const arg of args) {
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    }
    if (arg === "--skip-package") {
      skipPackage = true;
      continue;
    }
    throw new Error(`unknown option for electron:smoke:launcher: ${arg}`);
  }

  return { skipPackage };
}

function printUsage() {
  console.log(`Usage:
  npm run electron:smoke:launcher
  npm run electron:smoke:launcher -- --skip-package

Builds an unsigned launcher-backed local app directory, then runs configured,
first-run, and startup diagnostics Product 1.0 smoke paths through the packaged
sidecar launcher. The package built by this command includes smoke-only files
and is not a public release artifact.

Options:
  --skip-package    Reuse the existing dist-electron-launcher package directory.
  --help            Show this help.`);
}

async function runSmoke({ args, label }) {
  await runCommand(nodeBin, [path.join("scripts", "run-electron-smoke.mjs"), ...args], {
    label,
  });
}

function runCommand(command, args, { label }) {
  console.log(`[plato-electron-launcher-smoke] start ${label}`);
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
      console.log(`[plato-electron-launcher-smoke] pass ${label}`);
      resolve();
    });
  });
}
