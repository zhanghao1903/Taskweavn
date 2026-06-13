#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";

const launcherStartedAt = performance.now();
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
markStartupTiming("launcher_args_parsed");

if (forcedFailure) {
  markStartupTiming("launcher_forced_failure", { category: forcedFailure });
  fail(forcedFailure, `forced launcher failure: ${forcedFailure}`);
}

const manifestPath =
  process.env.PLATO_SIDECAR_LAUNCHER_RUNTIME_MANIFEST ?? DEFAULT_RUNTIME_MANIFEST;
const { manifest, manifestDir } = readRuntimeManifest(manifestPath);
const mode =
  process.env.PLATO_SIDECAR_LAUNCHER_MODE ?? manifest.mode ?? "sidecar";
const runtimeKind = manifest.runtimeKind ?? "bundled-python";
markStartupTiming("launcher_manifest_ready", { mode, runtimeKind });

if (mode !== "sidecar") {
  fail("runtime_unsupported", `unsupported launcher mode: ${mode}`);
}
if (
  ![
    "bundled-python",
    "self-contained-python-env-candidate",
  ].includes(runtimeKind)
) {
  fail("runtime_unsupported", `unsupported runtime kind: ${runtimeKind}`);
}

const pythonExecutable = resolveManifestPath(manifest.pythonExecutable, manifestDir);
if (typeof pythonExecutable !== "string" || !existsSync(pythonExecutable)) {
  markStartupTiming("launcher_runtime_missing", { mode, runtimeKind });
  fail("runtime_missing", "packaged Python runtime is unavailable");
}

markStartupTiming("launcher_python_spawn_begin", { mode, runtimeKind });
const child = spawn(pythonExecutable, buildSidecarArgs(options), {
  cwd: launcherDir,
  env: buildRuntimeEnv(manifest),
  stdio: ["ignore", "inherit", "inherit"],
});
markStartupTiming("launcher_python_spawned", {
  mode,
  pid: child.pid ?? null,
  runtimeKind,
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill(signal);
    }
  });
}

child.once("error", (error) => {
  markStartupTiming("launcher_python_spawn_error", { mode, runtimeKind });
  console.error(`runtime_failed: ${error.message}`);
  process.exit(1);
});

child.once("exit", (code, signal) => {
  markStartupTiming("launcher_python_exit", {
    code: code ?? null,
    hasSignal: signal !== null,
    mode,
    runtimeKind,
  });
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
    workspaceRegistryJson: null,
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
    if (arg === "--workspace-registry-json") {
      result.workspaceRegistryJson = requireValue(args, index, arg);
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

function buildSidecarArgs({ host, port, workspace, workspaceRegistryJson }) {
  const args = [
    "-m",
    "taskweavn.server.plato_sidecar",
    "--workspace",
    workspace,
    "--host",
    host,
    "--port",
    String(port),
  ];
  if (workspaceRegistryJson !== null) {
    args.push("--workspace-registry-json", workspaceRegistryJson);
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
  applyFirstRunSmokeEnv(env);
  return env;
}

function applyFirstRunSmokeEnv(env) {
  const firstRun = process.env.PLATO_SIDECAR_LAUNCHER_FIRST_RUN;
  if (firstRun === "configured") {
    env.LLM_PROVIDER = "deepseek";
    env.LLM_MODEL = "deepseek-v4-pro";
    env["DEEPSEEK_" + "API_KEY"] = "test-sidecar-readiness-key";
    return;
  }
  if (firstRun === "unconfigured") {
    delete env["LLM_" + "API_KEY"];
    delete env["DEEPSEEK_" + "API_KEY"];
    delete env["OPENROUTER_" + "API_KEY"];
  }
}

function markStartupTiming(event, attributes = {}) {
  const payload = {
    schemaVersion: "plato.startup_timing.v1",
    event,
    source: "sidecar-launcher",
    startupId: process.env.PLATO_STARTUP_ID ?? null,
    pid: process.pid,
    timestamp: new Date().toISOString(),
    elapsedMs: Math.round((performance.now() - launcherStartedAt) * 100) / 100,
    ...sanitizeAttributes(attributes),
  };
  console.log(`[plato-startup-timing] ${JSON.stringify(payload)}`);
}

function sanitizeAttributes(attributes) {
  const sanitized = {};
  for (const [key, value] of Object.entries(attributes)) {
    if (!/^[A-Za-z0-9_.:-]{1,64}$/.test(key)) {
      continue;
    }
    if (typeof value === "string") {
      sanitized[key] = value.length > 160 ? `${value.slice(0, 157)}...` : value;
      continue;
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      sanitized[key] = Math.round(value * 100) / 100;
      continue;
    }
    if (typeof value === "boolean" || value === null) {
      sanitized[key] = value;
    }
  }
  return sanitized;
}

function fail(category, message) {
  const exitCode = FAILURE_EXIT_CODES[category] ?? 1;
  console.error(`${category}: ${message}`);
  process.exit(exitCode);
}
