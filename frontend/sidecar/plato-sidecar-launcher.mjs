#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const launcherDir = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_RUNTIME_MANIFEST = path.join(
  launcherDir,
  "runtime",
  "launcher-runtime.json",
);
const FAILURE_EXIT_CODES = {
  launcher_invalid_args: 64,
  runtime_missing: 66,
  runtime_unsupported: 67,
};

const options = parseArgs(process.argv.slice(2));
const forcedFailure = process.env.PLATO_SIDECAR_LAUNCHER_FAILURE;

if (forcedFailure) {
  fail(forcedFailure, `forced launcher failure: ${forcedFailure}`);
}

const manifestPath =
  process.env.PLATO_SIDECAR_LAUNCHER_RUNTIME_MANIFEST ?? DEFAULT_RUNTIME_MANIFEST;
const { manifest, manifestDir } = readRuntimeManifest(manifestPath);
const mode =
  process.env.PLATO_SIDECAR_LAUNCHER_MODE ?? manifest.mode ?? "fixture";
const runtimeKind = manifest.runtimeKind ?? "repo-local-python-fixture";

if (mode !== "fixture") {
  fail("runtime_unsupported", `unsupported launcher mode: ${mode}`);
}
if (
  ![
    "bundled-python",
    "repo-local-python-fixture",
    "self-contained-python-env-candidate",
  ].includes(runtimeKind)
) {
  fail("runtime_unsupported", `unsupported runtime kind: ${runtimeKind}`);
}

const pythonExecutable = resolveManifestPath(manifest.pythonExecutable, manifestDir);
if (typeof pythonExecutable !== "string" || !existsSync(pythonExecutable)) {
  fail("runtime_missing", "packaged Python runtime is unavailable");
}

const child = spawn(pythonExecutable, buildFixtureArgs(options), {
  cwd: launcherDir,
  env: buildRuntimeEnv(manifest),
  stdio: ["ignore", "inherit", "inherit"],
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill(signal);
    }
  });
}

child.once("error", (error) => {
  console.error(`runtime_failed: ${error.message}`);
  process.exit(1);
});

child.once("exit", (code, signal) => {
  if (signal !== null) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});

function parseArgs(args) {
  const result = {
    host: "127.0.0.1",
    port: null,
    workspace: null,
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--workspace") {
      result.workspace = requireValue(args, index, arg);
      index += 1;
      continue;
    }
    if (arg === "--host") {
      result.host = requireValue(args, index, arg);
      index += 1;
      continue;
    }
    if (arg === "--port") {
      result.port = requireValue(args, index, arg);
      index += 1;
      continue;
    }
    fail("launcher_invalid_args", `unknown launcher option: ${arg}`);
  }

  if (result.workspace === null) {
    fail("launcher_invalid_args", "--workspace is required");
  }
  if (result.port === null) {
    fail("launcher_invalid_args", "--port is required");
  }

  return result;
}

function requireValue(args, index, flag) {
  const value = args[index + 1];
  if (!value) {
    fail("launcher_invalid_args", `${flag} requires a value`);
  }
  return value;
}

function readRuntimeManifest(manifestPath) {
  if (!existsSync(manifestPath)) {
    fail("runtime_missing", "launcher runtime manifest is missing");
  }
  try {
    return {
      manifest: JSON.parse(readFileSync(manifestPath, "utf8")),
      manifestDir: path.dirname(manifestPath),
    };
  } catch (error) {
    fail(
      "runtime_missing",
      error instanceof Error
        ? `launcher runtime manifest is invalid: ${error.message}`
        : "launcher runtime manifest is invalid",
    );
  }
}

function resolveManifestPath(value, manifestDir) {
  if (typeof value !== "string" || value.length === 0) {
    return value;
  }
  return path.isAbsolute(value) ? value : path.resolve(manifestDir, value);
}

function buildFixtureArgs({ host, port, workspace }) {
  const args = [
    "-m",
    "tests.fixtures.sidecar_smoke",
    "--serve-existing",
    "--keep-alive",
    "--workspace",
    workspace,
    "--host",
    host,
    "--port",
    String(port),
  ];
  const firstRun = process.env.PLATO_SIDECAR_LAUNCHER_FIRST_RUN;
  if (firstRun === "configured") {
    args.push("--first-run-configured");
  } else if (firstRun === "unconfigured") {
    args.push("--first-run-unconfigured");
  }
  return args;
}

function buildRuntimeEnv(manifest) {
  const pythonPathEntries = Array.isArray(manifest.pythonPathEntries)
    ? manifest.pythonPathEntries.filter((entry) => typeof entry === "string")
    : [];
  const env = {
    ...process.env,
    PYTHONDONTWRITEBYTECODE: "1",
    PYTHONNOUSERSITE: "1",
    PYTHONPATH: pythonPathEntries
      .map((entry) => resolveManifestPath(entry, manifestDir))
      .join(path.delimiter),
  };
  delete env.PYTHONHOME;
  delete env.VIRTUAL_ENV;
  for (const key of Object.keys(env)) {
    if (key.startsWith("UV_")) {
      delete env[key];
    }
  }
  return env;
}

function fail(category, message) {
  const exitCode = FAILURE_EXIT_CODES[category] ?? 1;
  console.error(`${category}: ${message}`);
  process.exit(exitCode);
}
