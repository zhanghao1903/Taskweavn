#!/usr/bin/env node
import {
  existsSync,
  lstatSync,
  readFileSync,
  readlinkSync,
  readdirSync,
  realpathSync,
  statSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(frontendRoot, "..");
const defaultPackageDir = path.join(frontendRoot, "dist-electron-launcher");
const nativeExtensions = new Set([
  ".app",
  ".dylib",
  ".framework",
  ".node",
  ".so",
]);
const textExtensions = new Set([
  ".cfg",
  ".css",
  ".html",
  ".js",
  ".json",
  ".mjs",
  ".md",
  ".pth",
  ".py",
  ".txt",
  ".toml",
  ".yaml",
  ".yml",
]);
const textBasenames = new Set([
  "package.json",
  "package-manifest.json",
  "launcher-runtime.json",
  "pyvenv.cfg",
]);
const secretLikePatterns = [
  { label: "raw bearer token", pattern: /\bBearer\s+[A-Za-z0-9._~+/=-]{8,}/ },
  { label: "raw OpenAI-style secret", pattern: /\bsk-[A-Za-z0-9_-]{8,}/ },
  { label: "raw LLM API key assignment", pattern: /\b[A-Z0-9_]*API_KEY\s*=/ },
];

const options = parseArgs(process.argv.slice(2));
const redactor = createRedactor();
const failures = [];
const summary = {
  appRoot: null,
  counts: {
    executableFiles: 0,
    externalSymlinks: 0,
    files: 0,
    nativeFiles: 0,
    scannedTextFiles: 0,
    symlinks: 0,
  },
  executableSamples: [],
  failureCount: 0,
  failures,
  nativeSamples: [],
  ok: false,
  packageDir: redactor.redact(options.packageDir),
  packageManifest: null,
  redactionSummary: {
    appPaths: "package://app",
    externalPaths: "external://<n>",
    outputPaths: "package://output",
    repoPaths: "repo://root",
    userHomePaths: "home://current",
  },
  runtime: null,
};

try {
  checkPackage();
  summary.failureCount = failures.length;
  summary.ok = failures.length === 0;
  writeSummary(summary);
  process.exitCode = summary.ok ? 0 : 1;
} catch (error) {
  addFailure(
    "checker_error",
    options.packageDir,
    error instanceof Error ? error.message : String(error),
  );
  summary.failureCount = failures.length;
  summary.ok = false;
  writeSummary(summary);
  process.exitCode = 1;
}

function parseArgs(args) {
  let allowSmokeAssets = false;
  let json = false;
  let packageDir = defaultPackageDir;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    }
    if (arg === "--json") {
      json = true;
      continue;
    }
    if (arg === "--allow-smoke-assets") {
      allowSmokeAssets = true;
      continue;
    }
    if (arg === "--package-dir") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--package-dir requires a path");
      }
      packageDir = path.resolve(value);
      index += 1;
      continue;
    }
    throw new Error(`unknown option for electron:check:release-assets: ${arg}`);
  }

  return {
    allowSmokeAssets,
    json,
    packageDir: path.resolve(packageDir),
  };
}

function printUsage() {
  console.log(`Usage:
  npm run electron:check:release-assets
  npm run electron:check:release-assets -- --package-dir ./dist-electron-launcher
  npm run electron:check:release-assets -- --allow-smoke-assets
  npm run electron:check:release-assets -- --json

Checks the launcher-backed Electron app directory before signing. The command
validates package-local runtime paths, symlink containment, executable/native
inventory, runtime write-location boundaries, and manifest redaction rules.

Options:
  --package-dir <path>  Package output root. Defaults to dist-electron-launcher.
  --allow-smoke-assets  Permit smoke runner files for test-only packages.
  --json                Print only the machine-readable JSON summary.
  --help                Show this help.`);
}

function checkPackage() {
  const packageManifestPath = path.join(options.packageDir, "package-manifest.json");
  if (!existsSync(packageManifestPath)) {
    addFailure(
      "package_manifest_missing",
      packageManifestPath,
      "package-manifest.json is missing; build electron:package:launcher-dir first",
    );
    return;
  }

  const packageManifest = readJson(packageManifestPath, "package_manifest_invalid");
  if (packageManifest === null) {
    return;
  }

  const appRoot = requireExistingPath(
    packageManifest.appRoot,
    "app_root_missing",
    "package manifest appRoot is missing",
  );
  if (appRoot === null) {
    return;
  }

  redactor.setAppRoot(appRoot);
  summary.appRoot = redactor.redact(appRoot);
  summary.packageManifest = redactor.redact(packageManifestPath);

  const appResourceDir = requireExistingPath(
    packageManifest.appResourceDir,
    "app_resource_dir_missing",
    "package manifest appResourceDir is missing",
  );
  const executablePath = requireExistingPath(
    packageManifest.executablePath,
    "app_executable_missing",
    "package manifest executablePath is missing",
  );
  const launcherPath = requireExistingPath(
    packageManifest.sidecarLauncherPath,
    "launcher_missing",
    "package manifest sidecarLauncherPath is missing",
  );
  const runtimeManifestPath = requireExistingPath(
    packageManifest.sidecarRuntimeManifestPath,
    "runtime_manifest_missing",
    "package manifest sidecarRuntimeManifestPath is missing",
  );

  assertInside(options.packageDir, appRoot, "app_root_outside_package");
  if (appResourceDir !== null) {
    assertInside(appRoot, appResourceDir, "app_resource_dir_outside_app");
  }
  if (executablePath !== null) {
    assertInside(appRoot, executablePath, "app_executable_outside_app");
    assertExecutable(executablePath, "app_executable_not_executable");
  }
  if (launcherPath !== null) {
    assertInside(appRoot, launcherPath, "launcher_outside_app");
    assertExecutable(launcherPath, "launcher_not_executable");
  }
  if (runtimeManifestPath !== null) {
    assertInside(appRoot, runtimeManifestPath, "runtime_manifest_outside_app");
    checkRuntimeManifest(runtimeManifestPath, appRoot);
  }

  checkTree(appRoot);
}

function checkRuntimeManifest(manifestPath, appRoot) {
  const runtimeManifest = readJson(manifestPath, "runtime_manifest_invalid");
  if (runtimeManifest === null) {
    return;
  }

  const runtimeDir = path.dirname(manifestPath);
  if (runtimeManifest.mode !== "sidecar") {
    addFailure(
      "runtime_mode_invalid",
      manifestPath,
      `unsupported runtime mode: ${String(runtimeManifest.mode)}`,
    );
  }
  const allowedRuntimeKinds = new Set([
    "self-contained-python-env-candidate",
    "bundled-python",
  ]);
  if (!allowedRuntimeKinds.has(runtimeManifest.runtimeKind)) {
    addFailure(
      "runtime_kind_invalid",
      manifestPath,
      `unsupported runtimeKind: ${String(runtimeManifest.runtimeKind)}`,
    );
  }

  const pythonExecutable = resolveRuntimeManifestPath(
    runtimeManifest.pythonExecutable,
    runtimeDir,
    manifestPath,
    "python_executable",
  );
  const pythonPathEntries = Array.isArray(runtimeManifest.pythonPathEntries)
    ? runtimeManifest.pythonPathEntries.map((entry, index) =>
        resolveRuntimeManifestPath(
          entry,
          runtimeDir,
          manifestPath,
          `pythonPathEntries[${index}]`,
        ),
      )
    : [];

  if (!Array.isArray(runtimeManifest.pythonPathEntries)) {
    addFailure(
      "runtime_pythonpath_invalid",
      manifestPath,
      "pythonPathEntries must be an array of package-local relative paths",
    );
  }

  if (pythonExecutable !== null) {
    assertInside(appRoot, pythonExecutable, "runtime_python_outside_app");
    if (existsSync(pythonExecutable)) {
      assertExecutable(pythonExecutable, "runtime_python_not_executable");
    } else {
      addFailure(
        "runtime_python_missing",
        pythonExecutable,
        "runtime python executable does not exist",
      );
    }
  }

  for (const entry of pythonPathEntries) {
    if (entry === null) {
      continue;
    }
    assertInside(appRoot, entry, "runtime_pythonpath_outside_app");
    if (!existsSync(entry)) {
      addFailure(
        "runtime_pythonpath_missing",
        entry,
        "runtime PYTHONPATH entry does not exist",
      );
    }
  }

  summary.runtime = {
    manifest: redactor.redact(manifestPath),
    pythonExecutable: pythonExecutable === null ? null : redactor.redact(pythonExecutable),
    pythonPathEntries: pythonPathEntries
      .filter((entry) => entry !== null)
      .map((entry) => redactor.redact(entry)),
    runtimeKind: runtimeManifest.runtimeKind ?? null,
  };
}

function resolveRuntimeManifestPath(value, runtimeDir, manifestPath, field) {
  if (typeof value !== "string" || value.length === 0) {
    addFailure(
      "runtime_manifest_path_invalid",
      manifestPath,
      `${field} must be a package-local relative path`,
    );
    return null;
  }
  if (path.isAbsolute(value)) {
    addFailure(
      "runtime_manifest_path_absolute",
      manifestPath,
      `${field} must not be absolute`,
    );
    return path.resolve(value);
  }
  const normalized = path.normalize(value);
  if (normalized === ".." || normalized.startsWith(`..${path.sep}`)) {
    addFailure(
      "runtime_manifest_path_escape",
      manifestPath,
      `${field} must not escape the runtime directory`,
    );
  }
  return path.resolve(runtimeDir, normalized);
}

function checkTree(appRoot) {
  walk(appRoot, (filePath, stat, linkTarget) => {
    if (stat.isSymbolicLink()) {
      summary.counts.symlinks += 1;
      checkSymlink(appRoot, filePath, linkTarget);
      return;
    }

    if (stat.isFile()) {
      summary.counts.files += 1;
      if (isExecutable(stat)) {
        summary.counts.executableFiles += 1;
        pushSample(summary.executableSamples, filePath);
      }
      if (isNativePath(filePath)) {
        summary.counts.nativeFiles += 1;
        pushSample(summary.nativeSamples, filePath);
      }
      checkSpecialFile(filePath, stat, appRoot);
      if (shouldScanText(filePath, stat)) {
        scanTextFile(filePath, appRoot);
      }
    }
  });
}

function checkSymlink(appRoot, filePath, linkTarget) {
  let resolvedTarget = null;
  try {
    resolvedTarget = realpathSync(filePath);
  } catch {
    addFailure(
      "symlink_broken",
      filePath,
      "symlink target cannot be resolved",
      { target: linkTarget },
    );
    return;
  }
  if (!isInside(appRoot, resolvedTarget)) {
    summary.counts.externalSymlinks += 1;
    addFailure(
      "symlink_external",
      filePath,
      "symlink resolves outside the app bundle",
      { target: resolvedTarget },
    );
  }
}

function checkSpecialFile(filePath, stat, appRoot) {
  const basename = path.basename(filePath);
  if (isEditableInstallPointer(basename)) {
    addFailure(
      "editable_install_reference",
      filePath,
      "editable install references are not allowed in release assets",
    );
  }
  if (basename === "pyvenv.cfg" && shouldScanText(filePath, stat)) {
    checkPyvenvConfig(filePath, appRoot);
  }
}

function isEditableInstallPointer(basename) {
  return (
    basename.endsWith(".egg-link") ||
    /^_editable_impl_.+\.pth$/.test(basename) ||
    /^__editable__.+\.pth$/.test(basename)
  );
}

function checkPyvenvConfig(filePath, appRoot) {
  const text = readFileSync(filePath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^\s*(home|executable|command)\s*=\s*(.+?)\s*$/i);
    if (!match) {
      continue;
    }
    const value = match[2];
    for (const token of value.split(/\s+/)) {
      if (!isAbsolutePathLike(token)) {
        continue;
      }
      const resolved = path.resolve(token);
      if (!isInside(appRoot, resolved)) {
        addFailure(
          "pyvenv_external_runtime_reference",
          filePath,
          `pyvenv.cfg ${match[1]} points outside the app bundle`,
          { target: resolved },
        );
      }
    }
  }
}

function scanTextFile(filePath, appRoot) {
  summary.counts.scannedTextFiles += 1;
  const text = readFileSync(filePath, "utf8");
  const forbiddenPaths = [
    { label: "repository root", value: repoRoot },
    { label: "frontend root", value: frontendRoot },
    { label: "developer virtualenv", value: path.join(repoRoot, ".venv") },
    { label: "repo src", value: path.join(repoRoot, "src") },
    { label: "repo tests", value: path.join(repoRoot, "tests") },
  ];
  if (process.env.HOME) {
    forbiddenPaths.push({ label: "user home path", value: process.env.HOME });
  }

  for (const { label, value } of forbiddenPaths) {
    if (value && text.includes(value)) {
      addFailure(
        "raw_local_path_reference",
        filePath,
        `text asset contains ${label}`,
      );
    }
  }

  if (text.includes("Contents/Resources/.plato")) {
    addFailure(
      "runtime_write_inside_app",
      filePath,
      "runtime write target points inside Contents/Resources",
    );
  }

  if (shouldScanSecrets(filePath)) {
    for (const { label, pattern } of secretLikePatterns) {
      if (pattern.test(text)) {
        addFailure("raw_secret_reference", filePath, `text asset contains ${label}`);
      }
    }
  }

  if (!isInside(appRoot, filePath)) {
    addFailure("text_scan_outside_app", filePath, "text scan escaped app bundle");
  }
}

function walk(root, visit) {
  const stack = [root];
  while (stack.length > 0) {
    const current = stack.pop();
    let stat;
    try {
      stat = lstatSync(current);
    } catch {
      addFailure("path_unreadable", current, "asset path cannot be read");
      continue;
    }

    if (stat.isSymbolicLink()) {
      let linkTarget = "";
      try {
        linkTarget = readlink(current);
      } catch {
        linkTarget = "";
      }
      visit(current, stat, linkTarget);
      continue;
    }

    visit(current, stat, null);
    checkProhibitedReleaseAsset(current, stat, root);
    if (!stat.isDirectory()) {
      continue;
    }

    for (const entry of readdirSync(current)) {
      stack.push(path.join(current, entry));
    }
  }
}

function checkProhibitedReleaseAsset(filePath, stat, appRoot) {
  if (options.allowSmokeAssets) {
    return;
  }
  const relative = path.relative(appRoot, filePath);
  const segments = relative.split(path.sep);
  const basename = path.basename(filePath);
  if (segments.includes("electron")) {
    if (basename.startsWith("smokeRunner.") || isTestAssetName(basename)) {
      addFailure(
        "prohibited_test_asset",
        filePath,
        "release package must not include Electron test or smoke assets",
      );
    }
  }
  if (segments.includes("python-src") && segments.some(isTestDirectoryName)) {
    addFailure(
      "prohibited_test_asset",
      filePath,
      "release package must not include repository test assets",
    );
  }
  if (segments.includes("site-packages")) {
    const sitePackagesIndex = segments.indexOf("site-packages");
    const packageSegment = segments[sitePackagesIndex + 1] ?? "";
    if (
      isRuntimeDevToolName(packageSegment) ||
      isRuntimeTestFileName(basename) ||
      segments.slice(sitePackagesIndex + 1).some(isTestDirectoryName)
    ) {
      addFailure(
        "prohibited_third_party_test_asset",
        filePath,
        "release package must not include obvious third-party test/dev assets",
      );
    }
  }
}

function isTestAssetName(basename) {
  return /\.test\.[cm]?[jt]sx?$/.test(basename) || /\.spec\.[cm]?[jt]sx?$/.test(basename);
}

function isTestDirectoryName(name) {
  return new Set([
    "__tests__",
    "_experimental",
    "_tests",
    "benchmarks",
    "example_config_yaml",
    "idle_test",
    "test",
    "test-key",
    "testdata",
    "test_prompts",
    "tests",
    "testing",
  ]).has(name);
}

function isRuntimeTestFileName(name) {
  return (
    /^test_.+\.pyi?$/.test(name) ||
    /^_test/.test(name) ||
    /^_xxtest/.test(name) ||
    /_test(\.|$)/.test(name) ||
    /Test(\.|$)/.test(name) ||
    /_test\.pyi?$/.test(name) ||
    /_testing\.pyi?$/.test(name) ||
    name === "conftest.py" ||
    name === "pytest_plugin.py" ||
    name === "testing.py" ||
    name === "testing_refleaks.py" ||
    name === "testclient.py" ||
    name === "tests.py"
  );
}

function isRuntimeDevToolName(name) {
  return (
    name === "pytest" ||
    name === "_pytest" ||
    name === "pytest_asyncio" ||
    name === "mypy" ||
    name === "mypyc" ||
    /^pytest(_|-)/.test(name) ||
    /^mypy[c]?-.+\.dist-info$/.test(name)
  );
}

function readlink(filePath) {
  return readlinkSync(filePath);
}

function readJson(filePath, rule) {
  try {
    return JSON.parse(readFileSync(filePath, "utf8"));
  } catch (error) {
    addFailure(
      rule,
      filePath,
      error instanceof Error ? error.message : "invalid JSON",
    );
    return null;
  }
}

function requireExistingPath(value, rule, message) {
  if (typeof value !== "string" || value.length === 0) {
    addFailure(rule, options.packageDir, message);
    return null;
  }
  const resolved = path.resolve(value);
  if (!existsSync(resolved)) {
    addFailure(rule, resolved, message);
    return null;
  }
  return resolved;
}

function assertInside(parent, child, rule) {
  if (!isInside(parent, child)) {
    addFailure(rule, child, "path must stay inside the expected package boundary");
  }
}

function assertExecutable(filePath, rule) {
  let stat;
  try {
    stat = statSync(filePath);
  } catch {
    addFailure(rule, filePath, "executable path cannot be read");
    return;
  }
  if (!isExecutable(stat)) {
    addFailure(rule, filePath, "expected executable bit to be set");
  }
}

function isInside(parent, child) {
  const relative = path.relative(parent, child);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function isExecutable(stat) {
  return (stat.mode & 0o111) !== 0;
}

function isNativePath(filePath) {
  const ext = path.extname(filePath);
  if (nativeExtensions.has(ext)) {
    return true;
  }
  return path.basename(filePath) === "Electron" || path.basename(filePath) === "Plato";
}

function shouldScanText(filePath, stat) {
  if (!stat.isFile() || stat.size > 2 * 1024 * 1024) {
    return false;
  }
  return textExtensions.has(path.extname(filePath)) || textBasenames.has(path.basename(filePath));
}

function shouldScanSecrets(filePath) {
  const basename = path.basename(filePath);
  return (
    basename.startsWith(".env") ||
    basename === "launcher-runtime.json" ||
    basename === "package-manifest.json" ||
    basename === "pyvenv.cfg" ||
    basename === "plato-sidecar-launcher.mjs"
  );
}

function isAbsolutePathLike(value) {
  return path.isAbsolute(value) || /^[A-Za-z]:[\\/]/.test(value);
}

function pushSample(samples, filePath) {
  if (samples.length >= 50) {
    return;
  }
  samples.push(redactor.redact(filePath));
}

function addFailure(rule, filePath, message, extra = {}) {
  failures.push({
    ...Object.fromEntries(
      Object.entries(extra).map(([key, value]) => [key, redactor.redact(String(value))]),
    ),
    message,
    path: redactor.redact(filePath),
    rule,
  });
}

function writeSummary(result) {
  if (options.json) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  console.log(`[plato-release-assets] ok=${String(result.ok)}`);
  console.log(`[plato-release-assets] package=${result.packageDir}`);
  if (result.runtime !== null) {
    console.log(`[plato-release-assets] runtime=${result.runtime.runtimeKind}`);
    console.log(
      `[plato-release-assets] python=${result.runtime.pythonExecutable ?? "missing"}`,
    );
  }
  console.log(
    `[plato-release-assets] files=${result.counts.files} executables=${result.counts.executableFiles} native=${result.counts.nativeFiles} symlinks=${result.counts.symlinks} externalSymlinks=${result.counts.externalSymlinks}`,
  );
  if (result.failures.length > 0) {
    console.log("[plato-release-assets] failures:");
    for (const failure of result.failures) {
      const target = failure.target ? ` target=${failure.target}` : "";
      console.log(
        `  - ${failure.rule}: ${failure.message} path=${failure.path}${target}`,
      );
    }
  }
  console.log("[plato-release-assets] json:");
  console.log(JSON.stringify(result, null, 2));
}

function createRedactor() {
  let appRoot = null;
  const externalAliases = new Map();
  return {
    redact(value) {
      if (typeof value !== "string" || value.length === 0) {
        return value;
      }
      const normalized = path.resolve(value);
      if (appRoot !== null && isInside(appRoot, normalized)) {
        return toAlias("package://app", path.relative(appRoot, normalized));
      }
      if (isInside(options.packageDir, normalized)) {
        return toAlias("package://output", path.relative(options.packageDir, normalized));
      }
      if (isInside(repoRoot, normalized)) {
        return toAlias("repo://root", path.relative(repoRoot, normalized));
      }
      if (process.env.HOME && isInside(process.env.HOME, normalized)) {
        return toAlias("home://current", path.relative(process.env.HOME, normalized));
      }
      if (path.isAbsolute(value) || /^[A-Za-z]:[\\/]/.test(value)) {
        if (!externalAliases.has(normalized)) {
          externalAliases.set(normalized, `external://${externalAliases.size + 1}`);
        }
        return externalAliases.get(normalized);
      }
      return value;
    },
    setAppRoot(value) {
      appRoot = value;
    },
  };
}

function toAlias(prefix, relativePath) {
  if (!relativePath) {
    return prefix;
  }
  return `${prefix}/${relativePath.split(path.sep).join("/")}`;
}
