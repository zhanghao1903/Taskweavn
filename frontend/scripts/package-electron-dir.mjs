#!/usr/bin/env node
import {
  chmodSync,
  cpSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  realpathSync,
  rmSync,
  symlinkSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  normalizeReleaseVersion,
  toDarwinBundleVersion,
  toPackageVersion,
} from "./release-version.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(frontendRoot, "..");
const electronDir = path.join(frontendRoot, "electron");
const sidecarSourceDir = path.join(frontendRoot, "sidecar");
const rendererDistDir = path.join(frontendRoot, "dist");
const electronDistDir = path.join(frontendRoot, "node_modules", "electron", "dist");
const pythonEnvSourceDir = path.join(repoRoot, ".venv");
const appName = "Plato";
const appIconName = "plato.icns";
const appIconSourcePath = path.join(frontendRoot, "assets", "icons", appIconName);
const bundleIdentifier = "com.taskweavn.plato";
const frontendPackageJson = JSON.parse(
  readFileSync(path.join(frontendRoot, "package.json"), "utf8"),
);
const defaultReleaseVersion = normalizeReleaseVersion(
  process.env.PLATO_ELECTRON_RELEASE_VERSION ?? frontendPackageJson.version,
);

const options = parseArgs(process.argv.slice(2));

try {
  if (!existsSync(path.join(rendererDistDir, "index.html"))) {
    throw new Error("Renderer dist not found. Run npm run build first.");
  }
  if (!existsSync(electronDistDir)) {
    throw new Error("Electron runtime not found. Run npm install in frontend first.");
  }

  const target = resolvePackageTarget(options.outputDir);
  rmSync(target.appRoot, { force: true, recursive: true });
  mkdirSync(options.outputDir, { recursive: true });

  cpSync(target.templateRoot, target.appRoot, {
    recursive: true,
    verbatimSymlinks: true,
  });
  preparePlatformBundle(target, options);
  copyAppPayload(target.appResourceDir, options);

  const manifest = {
    appName,
    appResourceDir: target.appResourceDir,
    appRoot: target.appRoot,
    bundleVersion: options.bundleVersion,
    bundleIdentifier,
    createdAt: new Date().toISOString(),
    executablePath: target.executablePath,
    packageVersion: options.packageVersion,
    platform: process.platform,
    releaseVersion: options.releaseVersion,
    renderer: "dist/index.html",
    smokeAssetsIncluded: options.includeSmoke,
    sidecarLauncherPath: options.withLauncher
      ? path.join(target.appResourceDir, "sidecar", "plato-sidecar-launcher.mjs")
      : null,
    sidecarRuntimeManifestPath: options.withLauncher
      ? path.join(target.appResourceDir, "sidecar", "runtime", "launcher-runtime.json")
      : null,
    type: options.withLauncher
      ? "unsigned-local-directory-launcher-runtime-candidate"
      : "unsigned-local-directory",
  };
  const manifestPath = path.join(options.outputDir, "package-manifest.json");
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

  console.log(`[plato-electron-package] app=${target.appRoot}`);
  console.log(`[plato-electron-package] executable=${target.executablePath}`);
  console.log(`[plato-electron-package] manifest=${manifestPath}`);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

function parseArgs(args) {
  let includeSmoke = false;
  let outputDir = path.join(frontendRoot, "dist-electron");
  let releaseVersion = defaultReleaseVersion;
  let withLauncher = false;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    }
    if (arg === "--output-dir") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--output-dir requires a path");
      }
      outputDir = path.resolve(value);
      index += 1;
      continue;
    }
    if (arg === "--release-version") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--release-version requires a version");
      }
      releaseVersion = normalizeReleaseVersion(value);
      index += 1;
      continue;
    }
    if (arg === "--with-launcher") {
      withLauncher = true;
      continue;
    }
    if (arg === "--include-smoke") {
      includeSmoke = true;
      continue;
    }
    throw new Error(`unknown option for electron:package:dir: ${arg}`);
  }

  const packageVersion = toPackageVersion(releaseVersion);
  return {
    bundleVersion: toDarwinBundleVersion(packageVersion),
    includeSmoke,
    outputDir,
    packageVersion,
    releaseVersion,
    withLauncher,
  };
}

function printUsage() {
  console.log(`Usage:
  npm run electron:package:dir
  npm run electron:package:dir -- --output-dir ./dist-electron
  npm run electron:package:dir -- --output-dir ./dist-electron-launcher --with-launcher
  npm run electron:package:dir -- --release-version 1.1-beta
  npm run electron:package:dir -- --include-smoke

Builds an unsigned local Electron app directory from the current renderer dist.
Signing, notarization, and installers are out of scope. Launcher packages copy
a package-local Python runtime candidate for deterministic smoke only.

Options:
  --output-dir <path>       Package output root. Defaults to frontend/dist-electron.
  --release-version <ver>   Public release version, for example 1.1-beta.
  --with-launcher           Include the release-local sidecar launcher contract.
  --include-smoke           Include packaged smoke runner files for test-only builds.
  --help                    Show this help.`);
}

function resolvePackageTarget(outputDir) {
  if (process.platform === "darwin") {
    const appRoot = path.join(outputDir, `${appName}.app`);
    return {
      appResourceDir: path.join(appRoot, "Contents", "Resources", "app"),
      appRoot,
      executablePath: path.join(appRoot, "Contents", "MacOS", "Electron"),
      templateRoot: path.join(electronDistDir, "Electron.app"),
    };
  }

  const folderName =
    process.platform === "win32"
      ? `${appName}-win32-${process.arch}`
      : `${appName}-linux-${process.arch}`;
  const appRoot = path.join(outputDir, folderName);
  return {
    appResourceDir: path.join(appRoot, "resources", "app"),
    appRoot,
    executablePath: path.join(
      appRoot,
      process.platform === "win32" ? "electron.exe" : "electron",
    ),
    templateExecutablePath: null,
    templateRoot: electronDistDir,
  };
}

function preparePlatformBundle(target, options) {
  if (process.platform !== "darwin") {
    chmodSync(target.executablePath, 0o755);
    return;
  }

  chmodSync(target.executablePath, 0o755);
  if (!existsSync(appIconSourcePath)) {
    throw new Error(`Plato app icon not found: ${appIconSourcePath}. Run npm run electron:generate:icon.`);
  }
  cpSync(
    appIconSourcePath,
    path.join(target.appRoot, "Contents", "Resources", appIconName),
  );
  const infoPlistPath = path.join(target.appRoot, "Contents", "Info.plist");
  const original = readFileSync(infoPlistPath, "utf8");
  const updated = original
    .replace(
      /(<key>CFBundleDisplayName<\/key>\s*<string>)Electron(<\/string>)/,
      `$1${appName}$2`,
    )
    .replace(
      /(<key>CFBundleIdentifier<\/key>\s*<string>)com\.github\.Electron(<\/string>)/,
      `$1${bundleIdentifier}$2`,
    )
    .replace(
      /(<key>CFBundleName<\/key>\s*<string>)Electron(<\/string>)/,
      `$1${appName}$2`,
    );
  const versioned = replaceOrInsertPlistString(
    replaceOrInsertPlistString(
      replaceOrInsertPlistString(updated, "CFBundleIconFile", appIconName),
      "CFBundleShortVersionString",
      options.bundleVersion,
    ),
    "CFBundleVersion",
    options.bundleVersion,
  );
  writeFileSync(infoPlistPath, versioned, "utf8");
}

function copyAppPayload(appResourceDir, options) {
  rmSync(appResourceDir, { force: true, recursive: true });
  mkdirSync(appResourceDir, { recursive: true });
  cpSync(rendererDistDir, path.join(appResourceDir, "dist"), {
    recursive: true,
  });
  rewritePackagedIndexHtml(path.join(appResourceDir, "dist", "index.html"));
  cpSync(electronDir, path.join(appResourceDir, "electron"), {
    recursive: true,
    filter: (source) => shouldCopyElectronFile(source, options),
  });
  writeFileSync(
    path.join(appResourceDir, "package.json"),
    `${JSON.stringify(
      {
        main: "electron/main.mjs",
        name: "@taskweavn/plato-packaged",
        platoIncludeSmokeAssets: options.includeSmoke,
        platoReleaseVersion: options.releaseVersion,
        private: true,
        type: "module",
        version: options.packageVersion,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
  if (options.withLauncher) {
    copySidecarLauncher(appResourceDir);
  }
}

function copySidecarLauncher(appResourceDir) {
  const sidecarDir = path.join(appResourceDir, "sidecar");
  const runtimeDir = path.join(sidecarDir, "runtime");
  const launcherSourcePath = path.join(sidecarSourceDir, "plato-sidecar-launcher.mjs");
  const launcherTargetPath = path.join(sidecarDir, "plato-sidecar-launcher.mjs");
  if (!existsSync(launcherSourcePath)) {
    throw new Error(`Sidecar launcher source not found: ${launcherSourcePath}`);
  }

  mkdirSync(runtimeDir, { recursive: true });
  cpSync(launcherSourcePath, launcherTargetPath);
  chmodSync(launcherTargetPath, 0o755);
  copyLauncherRuntimeAssets(runtimeDir);
  writeFileSync(
    path.join(runtimeDir, "launcher-runtime.json"),
    `${JSON.stringify(buildLauncherRuntimeManifest(), null, 2)}\n`,
    "utf8",
  );
}

function buildLauncherRuntimeManifest() {
  const sitePackages = resolveVenvSitePackages(pythonEnvSourceDir);
  return {
    createdAt: new Date().toISOString(),
    mode: "sidecar",
    pythonExecutable:
      process.platform === "win32"
        ? path.join("python-env", "Scripts", "python.exe")
        : path.join("python-base", "bin", "python3"),
    pythonPathEntries: [
      sitePackages.relativePathInRuntimeEnv,
      path.join("python-src", "src"),
      "python-src",
    ],
    runtimeKind: "bundled-python",
    schemaVersion: "plato.sidecar_launcher_runtime.v1",
  };
}

function copyLauncherRuntimeAssets(runtimeDir) {
  if (!existsSync(pythonEnvSourceDir)) {
    throw new Error(
      `Python environment source not found: ${pythonEnvSourceDir}. Run uv sync first.`,
    );
  }

  const pythonEnvTargetDir = path.join(runtimeDir, "python-env");
  const pythonBaseTargetDir = path.join(runtimeDir, "python-base");
  const pythonSourceTargetDir = path.join(runtimeDir, "python-src");
  const sitePackages = resolveVenvSitePackages(pythonEnvSourceDir);
  const sourcePythonBase = resolveSourcePythonBase(pythonEnvSourceDir, sitePackages);
  copyBundledPythonBase(sourcePythonBase, pythonBaseTargetDir, sitePackages);
  copyPythonEnvCandidate(pythonEnvTargetDir, sitePackages);
  copyRuntimeSourceAssets(pythonSourceTargetDir);
  copyBundledNativeDependencies({
    dependencyRoots: [
      sourcePythonBase.stdlibDir,
      sitePackages.absolutePath,
    ],
    sourceLibDir: sourcePythonBase.libDir,
    targetLibDir: path.join(pythonBaseTargetDir, "lib"),
  });
}

function copyPythonEnvCandidate(targetDir, sitePackages) {
  const sitePackagesTarget = path.join(targetDir, sitePackages.relativePath);

  mkdirSync(path.dirname(sitePackagesTarget), { recursive: true });
  cpSync(sitePackages.absolutePath, sitePackagesTarget, {
    recursive: true,
    verbatimSymlinks: true,
    filter: shouldCopyRuntimeFile,
  });
  removeEditableRepoPath(sitePackagesTarget);
  removeEditableDirectUrlMetadata(sitePackagesTarget);
}

function copyBundledPythonBase(sourcePythonBase, targetDir, sitePackages) {
  if (process.platform === "win32") {
    throw new Error("Bundled Python runtime packaging is not implemented for Windows yet.");
  }

  const binTargetDir = path.join(targetDir, "bin");
  const libTargetDir = path.join(targetDir, "lib");
  mkdirSync(binTargetDir, { recursive: true });
  mkdirSync(libTargetDir, { recursive: true });

  const pythonTarget = path.join(binTargetDir, "python3");
  cpSync(sourcePythonBase.executablePath, pythonTarget, { dereference: true });
  chmodSync(pythonTarget, 0o755);
  createRelativeSymlink("python3", path.join(binTargetDir, "python"));
  if (sitePackages.pythonExecutableName !== "python3") {
    createRelativeSymlink("python3", path.join(binTargetDir, sitePackages.pythonExecutableName));
  }

  cpSync(
    sourcePythonBase.stdlibDir,
    path.join(libTargetDir, sitePackages.pythonLibName),
    {
      recursive: true,
      filter: shouldCopyPythonStdlibFile,
    },
  );
}

function copyBundledNativeDependencies({ dependencyRoots, sourceLibDir, targetLibDir }) {
  if (process.platform !== "darwin") {
    return;
  }

  const queue = collectDarwinNativeFiles(dependencyRoots);
  const copied = new Set();
  while (queue.length > 0) {
    const nativePath = queue.pop();
    for (const linkedPath of readDarwinLinkedLibraries(nativePath)) {
      const sourcePath = resolveBundledDarwinLibrary(linkedPath, sourceLibDir);
      if (sourcePath === null) {
        continue;
      }
      if (isRuntimeTestFile(sourcePath)) {
        continue;
      }

      const targetPath = path.join(targetLibDir, path.basename(sourcePath));
      if (copied.has(targetPath)) {
        continue;
      }
      mkdirSync(path.dirname(targetPath), { recursive: true });
      cpSync(realpathSync(sourcePath), targetPath);
      copied.add(targetPath);
      queue.push(sourcePath);
    }
  }
}

function copyRuntimeSourceAssets(targetDir) {
  mkdirSync(targetDir, { recursive: true });
  cpSync(path.join(repoRoot, "src"), path.join(targetDir, "src"), {
    recursive: true,
    filter: shouldCopyRuntimeFile,
  });
}

function resolveVenvSitePackages(venvDir) {
  if (process.platform === "win32") {
    const relativePath = path.join("Lib", "site-packages");
    const absolutePath = path.join(venvDir, relativePath);
    if (existsSync(absolutePath)) {
      return {
        absolutePath,
        pythonExecutableName: "python.exe",
        pythonLibName: "python",
        relativePath,
        relativePathInRuntimeEnv: path.join("python-env", relativePath),
      };
    }
  }

  const libDir = path.join(venvDir, "lib");
  if (existsSync(libDir)) {
    for (const entry of readdirSync(libDir)) {
      const relativePath = path.join("lib", entry, "site-packages");
      const absolutePath = path.join(venvDir, relativePath);
      if (entry.startsWith("python") && existsSync(absolutePath)) {
        return {
          absolutePath,
          pythonExecutableName: entry,
          pythonLibName: entry,
          relativePath,
          relativePathInRuntimeEnv: path.join("python-env", relativePath),
        };
      }
    }
  }

  throw new Error(`Could not resolve site-packages under ${venvDir}`);
}

function resolveSourcePythonBase(venvDir, sitePackages) {
  const config = readPyvenvConfig(path.join(venvDir, "pyvenv.cfg"));
  const home = config.get("home");
  const homeDir = home && path.isAbsolute(home) ? home : path.dirname(resolveVenvPython(venvDir));
  const basePrefix = path.resolve(homeDir, "..");
  const libDir = path.join(basePrefix, "lib");
  const stdlibDir = path.join(libDir, sitePackages.pythonLibName);
  if (!existsSync(stdlibDir)) {
    throw new Error(`Python stdlib source not found: ${stdlibDir}`);
  }

  const executableCandidates = [
    path.join(homeDir, sitePackages.pythonExecutableName),
    path.join(homeDir, "python3"),
    path.join(homeDir, "python"),
  ];
  const executablePath = executableCandidates.find((candidate) => existsSync(candidate));
  if (!executablePath) {
    throw new Error(`Python executable source not found under ${homeDir}`);
  }

  return {
    executablePath,
    libDir,
    stdlibDir,
  };
}

function resolveVenvPython(venvDir) {
  const executablePath = path.join(
    venvDir,
    process.platform === "win32" ? "Scripts" : "bin",
    process.platform === "win32" ? "python.exe" : "python",
  );
  if (!existsSync(executablePath)) {
    throw new Error(`Python executable not found: ${executablePath}`);
  }
  return realpathSync(executablePath);
}

function readPyvenvConfig(configPath) {
  const result = new Map();
  if (!existsSync(configPath)) {
    return result;
  }
  const text = readFileSync(configPath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Za-z0-9_.-]+)\s*=\s*(.*?)\s*$/);
    if (match) {
      result.set(match[1].toLowerCase(), match[2]);
    }
  }
  return result;
}

function collectDarwinNativeFiles(roots) {
  const nativeFiles = [];
  const stack = roots.filter((root) => existsSync(root));
  while (stack.length > 0) {
    const current = stack.pop();
    let stat;
    try {
      stat = lstatSync(current);
    } catch {
      continue;
    }
    if (stat.isSymbolicLink()) {
      continue;
    }
    if (stat.isDirectory()) {
      for (const entry of readdirSync(current)) {
        stack.push(path.join(current, entry));
      }
      continue;
    }
    if (stat.isFile() && isDarwinNativeFile(current)) {
      nativeFiles.push(current);
    }
  }
  return nativeFiles;
}

function isDarwinNativeFile(filePath) {
  const ext = path.extname(filePath);
  return ext === ".so" || ext === ".dylib";
}

function readDarwinLinkedLibraries(filePath) {
  let output;
  try {
    output = execFileSync("otool", ["-L", filePath], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
  } catch {
    return [];
  }

  return output
    .split(/\r?\n/)
    .slice(1)
    .map((line) => line.match(/^\s+(.+?)\s+\(/)?.[1])
    .filter((value) => typeof value === "string" && value.length > 0);
}

function resolveBundledDarwinLibrary(linkedPath, sourceLibDir) {
  if (linkedPath.startsWith("/usr/lib/") || linkedPath.startsWith("/System/Library/")) {
    return null;
  }
  if (path.isAbsolute(linkedPath) && isInside(sourceLibDir, linkedPath)) {
    return existsSync(linkedPath) ? linkedPath : null;
  }

  const candidate = path.join(sourceLibDir, path.basename(linkedPath));
  return existsSync(candidate) ? candidate : null;
}

function createRelativeSymlink(target, linkPath) {
  try {
    lstatSync(linkPath);
    unlinkSync(linkPath);
  } catch {
    // Nothing to replace.
  }
  symlinkSync(target, linkPath);
}

function removeEditableRepoPath(sitePackagesDir) {
  for (const entry of readdirSync(sitePackagesDir)) {
    if (isEditableInstallPointer(entry)) {
      unlinkSync(path.join(sitePackagesDir, entry));
    }
  }
}

function isEditableInstallPointer(basename) {
  return (
    basename.endsWith(".egg-link") ||
    /^_editable_impl_.+\.pth$/.test(basename) ||
    /^__editable__.+\.pth$/.test(basename)
  );
}

function removeEditableDirectUrlMetadata(sitePackagesDir) {
  for (const entry of readdirSync(sitePackagesDir)) {
    if (!entry.endsWith(".dist-info")) {
      continue;
    }
    const directUrlPath = path.join(sitePackagesDir, entry, "direct_url.json");
    if (existsSync(directUrlPath)) {
      unlinkSync(directUrlPath);
    }
  }
}

function shouldCopyRuntimeFile(source) {
  const basename = path.basename(source);
  if (isRuntimeTestDirectory(source)) {
    return false;
  }
  if (isRuntimeDevToolDirectory(source)) {
    return false;
  }
  if (basename === "__pycache__" || basename === ".pytest_cache") {
    return false;
  }
  if (isRuntimeTestFile(source)) {
    return false;
  }
  return !basename.endsWith(".pyc") && !basename.endsWith(".pyo");
}

function shouldCopyElectronFile(source, options) {
  const basename = path.basename(source);
  if (isTestAssetName(basename)) {
    return false;
  }
  if (!options.includeSmoke && basename.startsWith("smokeRunner.")) {
    return false;
  }
  return true;
}

function isTestAssetName(basename) {
  return /\.test\.[cm]?[jt]sx?$/.test(basename) || /\.spec\.[cm]?[jt]sx?$/.test(basename);
}

function isRuntimeTestDirectory(source) {
  let stat;
  try {
    stat = lstatSync(source);
  } catch {
    return false;
  }
  if (!stat.isDirectory()) {
    return false;
  }
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
  ]).has(path.basename(source));
}

function isRuntimeDevToolDirectory(source) {
  let stat;
  try {
    stat = lstatSync(source);
  } catch {
    return false;
  }
  if (!stat.isDirectory()) {
    return false;
  }
  const basename = path.basename(source);
  return (
    basename === "pytest" ||
    basename === "_pytest" ||
    basename === "pytest_asyncio" ||
    basename === "mypy" ||
    basename === "mypyc" ||
    /^pytest(_|-)/.test(basename) ||
    /^mypy[c]?-.+\.dist-info$/.test(basename)
  );
}

function isRuntimeTestFile(source) {
  const basename = path.basename(source);
  return (
    /^test_.+\.pyi?$/.test(basename) ||
    /^_test/.test(basename) ||
    /^_xxtest/.test(basename) ||
    /_test(\.|$)/.test(basename) ||
    /Test(\.|$)/.test(basename) ||
    /_test\.pyi?$/.test(basename) ||
    /_testing\.pyi?$/.test(basename) ||
    basename === "conftest.py" ||
    basename === "pytest_plugin.py" ||
    basename === "testing.py" ||
    basename === "testing_refleaks.py" ||
    basename === "testclient.py" ||
    basename === "tests.py"
  );
}

function shouldCopyPythonStdlibFile(source) {
  if (path.basename(source) === "site-packages") {
    return false;
  }
  return shouldCopyRuntimeFile(source);
}

function isInside(parent, child) {
  const relative = path.relative(parent, child);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function rewritePackagedIndexHtml(indexHtmlPath) {
  const original = readFileSync(indexHtmlPath, "utf8");
  const updated = original
    .replaceAll('src="/assets/', 'src="./assets/')
    .replaceAll('href="/assets/', 'href="./assets/');
  writeFileSync(indexHtmlPath, updated, "utf8");
}

function replaceOrInsertPlistString(text, key, value) {
  const pattern = new RegExp(`(<key>${key}</key>\\s*<string>)([^<]*)(</string>)`);
  if (pattern.test(text)) {
    return text.replace(pattern, `$1${value}$3`);
  }
  return text.replace(
    /\s*<\/dict>/,
    `\n\t<key>${key}</key>\n\t<string>${value}</string>\n</dict>`,
  );
}
