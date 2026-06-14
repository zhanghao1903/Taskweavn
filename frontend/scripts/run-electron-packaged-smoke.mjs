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
    await runCommand(npmBin, ["run", "electron:package:dir", "--", "--include-smoke"], {
      label: "electron:package:dir",
    });
  }

  if (options.readOnlyInquiryLlmOnly) {
    await runSmoke({
      args: ["--packaged", "--first-run-configured", "--read-only-inquiry-llm"],
      label: "read-only inquiry LLM packaged smoke",
    });
    process.exitCode = 0;
  } else {
    await runSmoke({
      args: ["--packaged", "--first-run-configured"],
      label: "configured packaged smoke",
    });
    await runSmoke({
      args: ["--packaged", "--first-run-unconfigured"],
      label: "first-run packaged smoke",
    });
    await runSmoke({
      args: ["--packaged", "--startup-diagnostics"],
      label: "startup diagnostics packaged smoke",
    });
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

function parseArgs(args) {
  let skipPackage = false;
  let readOnlyInquiryLlmOnly = false;

  for (const arg of args) {
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    }
    if (arg === "--skip-package") {
      skipPackage = true;
      continue;
    }
    if (arg === "--read-only-inquiry-llm-only") {
      readOnlyInquiryLlmOnly = true;
      continue;
    }
    throw new Error(`unknown option for electron:smoke:packaged: ${arg}`);
  }

  return { readOnlyInquiryLlmOnly, skipPackage };
}

function printUsage() {
  console.log(`Usage:
  npm run electron:smoke:packaged
  npm run electron:smoke:packaged -- --skip-package
  npm run electron:smoke:packaged-read-only-inquiry-llm

Builds an unsigned local app directory, then runs configured, first-run, and
startup diagnostics Product 1.0 smoke paths against the packaged app without
Vite. The package built by this command includes smoke-only files and is not a
public release artifact.

Options:
  --read-only-inquiry-llm-only
                    Run only the packaged guarded Read-Only Inquiry LLM smoke.
  --skip-package    Reuse the existing dist-electron package directory.
  --help            Show this help.`);
}

async function runSmoke({ args, label }) {
  await runCommand(nodeBin, [path.join("scripts", "run-electron-smoke.mjs"), ...args], {
    label,
  });
}

function runCommand(command, args, { label }) {
  console.log(`[plato-electron-packaged-smoke] start ${label}`);
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
      console.log(`[plato-electron-packaged-smoke] pass ${label}`);
      resolve();
    });
  });
}
