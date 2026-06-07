#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const defaultPackageDir = path.join(frontendRoot, "dist-electron-launcher");
const defaultOutputDir = path.join(frontendRoot, "dist-electron-installer");
const npmBin = process.platform === "win32" ? "npm.cmd" : "npm";
const appVersion = JSON.parse(
  readFileSync(path.join(frontendRoot, "package.json"), "utf8"),
).version;

const options = parseArgs(process.argv.slice(2));

try {
  if (process.platform !== "darwin") {
    throw new Error("electron:package:installer currently supports macOS only.");
  }
  const signing = resolveSigningOptions(options);

  if (!options.skipPackage) {
    runCommand(npmBin, ["run", "electron:package:launcher-dir"], {
      label: "electron:package:launcher-dir",
    });
  }
  runCommand(
    npmBin,
    [
      "run",
      "electron:check:release-assets",
      "--",
      "--package-dir",
      options.packageDir,
    ],
    { label: "electron:check:release-assets" },
  );

  const packageManifestPath = path.join(options.packageDir, "package-manifest.json");
  const packageManifest = readJson(packageManifestPath);
  const sourceAppRoot = resolvePackagedAppRoot(packageManifest, options.packageDir);
  if (!existsSync(sourceAppRoot)) {
    throw new Error(`Packaged app not found: ${sourceAppRoot}`);
  }

  const stagingRoot = path.join(options.outputDir, "staging", "Plato");
  const stagedAppRoot = path.join(stagingRoot, "Plato.app");
  const dmgPath = path.join(
    options.outputDir,
    `Plato-${appVersion}-macos-${process.arch}.dmg`,
  );
  rmSync(stagingRoot, { force: true, recursive: true });
  mkdirSync(stagingRoot, { recursive: true });
  mkdirSync(options.outputDir, { recursive: true });
  cpSync(sourceAppRoot, stagedAppRoot, {
    recursive: true,
    verbatimSymlinks: true,
  });
  cpSync(packageManifestPath, path.join(stagingRoot, "package-manifest.json"));

  if (signing.sign) {
    signApp(stagedAppRoot, signing);
  }

  createDmg(stagingRoot, dmgPath);

  if (signing.sign) {
    signDmg(dmgPath, signing);
  }
  if (signing.notarize) {
    notarizeDmg(dmgPath, signing);
  }

  const installerManifest = {
    appName: packageManifest.appName ?? "Plato",
    appVersion,
    createdAt: new Date().toISOString(),
    dmgPath,
    notarized: signing.notarize,
    packageDir: options.packageDir,
    packageManifestPath,
    runtimeKind: readRuntimeKind(packageManifest),
    signed: signing.sign,
    signingIdentity: signing.sign ? signing.identity : null,
    stagingRoot,
    type: "local-dmg-installer-candidate",
  };
  const installerManifestPath = path.join(options.outputDir, "installer-manifest.json");
  writeFileSync(
    installerManifestPath,
    `${JSON.stringify(installerManifest, null, 2)}\n`,
    "utf8",
  );

  console.log(`[plato-electron-installer] dmg=${dmgPath}`);
  console.log(`[plato-electron-installer] manifest=${installerManifestPath}`);
  console.log(`[plato-electron-installer] signed=${String(signing.sign)}`);
  console.log(`[plato-electron-installer] notarized=${String(signing.notarize)}`);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

function parseArgs(args) {
  let notarize = process.env.PLATO_ELECTRON_NOTARIZE === "1";
  let outputDir = defaultOutputDir;
  let packageDir = defaultPackageDir;
  let sign = process.env.PLATO_ELECTRON_SIGN === "1";
  let skipPackage = false;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    }
    if (arg === "--notarize") {
      notarize = true;
      sign = true;
      continue;
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
    if (arg === "--package-dir") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--package-dir requires a path");
      }
      packageDir = path.resolve(value);
      index += 1;
      continue;
    }
    if (arg === "--sign") {
      sign = true;
      continue;
    }
    if (arg === "--skip-package") {
      skipPackage = true;
      continue;
    }
    throw new Error(`unknown option for electron:package:installer: ${arg}`);
  }

  return {
    notarize,
    outputDir: path.resolve(outputDir),
    packageDir: path.resolve(packageDir),
    sign,
    skipPackage,
  };
}

function printUsage() {
  console.log(`Usage:
  npm run electron:package:installer
  npm run electron:package:installer -- --skip-package
  npm run electron:package:installer -- --sign
  npm run electron:package:installer -- --sign --notarize

Builds a macOS DMG installer candidate from the launcher-backed bundled Python
package. By default this creates an unsigned local DMG for installer smoke.
Signing requires PLATO_ELECTRON_CODESIGN_IDENTITY or CSC_NAME. Notarization
requires either PLATO_ELECTRON_NOTARY_KEYCHAIN_PROFILE or Apple ID credentials.

Options:
  --package-dir <path>   Launcher package root. Defaults to dist-electron-launcher.
  --output-dir <path>    Installer output root. Defaults to dist-electron-installer.
  --skip-package         Reuse the existing launcher package directory.
  --sign                 Codesign the staged app and DMG.
  --notarize             Submit and staple the DMG after signing.
  --help                 Show this help.`);
}

function resolveSigningOptions({ notarize, sign }) {
  const identity =
    process.env.PLATO_ELECTRON_CODESIGN_IDENTITY ?? process.env.CSC_NAME ?? null;
  if (sign && !identity) {
    throw new Error(
      "--sign requires PLATO_ELECTRON_CODESIGN_IDENTITY or CSC_NAME.",
    );
  }
  if (notarize && !sign) {
    throw new Error("--notarize requires --sign.");
  }

  const keychainProfile = process.env.PLATO_ELECTRON_NOTARY_KEYCHAIN_PROFILE ?? null;
  const appleId = process.env.PLATO_ELECTRON_NOTARY_APPLE_ID ?? null;
  const password = process.env.PLATO_ELECTRON_NOTARY_PASSWORD ?? null;
  const teamId = process.env.PLATO_ELECTRON_NOTARY_TEAM_ID ?? null;
  if (
    notarize &&
    !keychainProfile &&
    !(appleId && password && teamId)
  ) {
    throw new Error(
      "--notarize requires PLATO_ELECTRON_NOTARY_KEYCHAIN_PROFILE or PLATO_ELECTRON_NOTARY_APPLE_ID, PLATO_ELECTRON_NOTARY_PASSWORD, and PLATO_ELECTRON_NOTARY_TEAM_ID.",
    );
  }

  return {
    appleId,
    entitlements: process.env.PLATO_ELECTRON_CODESIGN_ENTITLEMENTS ?? null,
    identity,
    keychainProfile,
    notarize,
    password,
    sign,
    teamId,
  };
}

function signApp(appRoot, signing) {
  const args = [
    "--force",
    "--deep",
    "--options",
    "runtime",
    "--timestamp",
  ];
  if (signing.entitlements) {
    args.push("--entitlements", signing.entitlements);
  }
  args.push("--sign", signing.identity, appRoot);
  runCommand("codesign", args, { label: "codesign app" });
  runCommand("codesign", ["--verify", "--deep", "--strict", appRoot], {
    label: "codesign verify app",
  });
}

function signDmg(dmgPath, signing) {
  runCommand(
    "codesign",
    ["--force", "--timestamp", "--sign", signing.identity, dmgPath],
    { label: "codesign dmg" },
  );
  runCommand("codesign", ["--verify", "--strict", dmgPath], {
    label: "codesign verify dmg",
  });
}

function notarizeDmg(dmgPath, signing) {
  const submitArgs = ["notarytool", "submit", dmgPath, "--wait"];
  if (signing.keychainProfile) {
    submitArgs.push("--keychain-profile", signing.keychainProfile);
  } else {
    submitArgs.push(
      "--apple-id",
      signing.appleId,
      "--password",
      signing.password,
      "--team-id",
      signing.teamId,
    );
  }
  runCommand("xcrun", submitArgs, { label: "notarytool submit" });
  runCommand("xcrun", ["stapler", "staple", dmgPath], {
    label: "stapler staple",
  });
}

function createDmg(stagingRoot, dmgPath) {
  rmSync(dmgPath, { force: true });
  runCommand(
    "hdiutil",
    [
      "create",
      "-volname",
      "Plato",
      "-srcfolder",
      stagingRoot,
      "-ov",
      "-format",
      "UDZO",
      dmgPath,
    ],
    { label: "hdiutil create" },
  );
}

function readRuntimeKind(packageManifest) {
  const runtimeManifestPath = packageManifest.sidecarRuntimeManifestPath;
  if (typeof runtimeManifestPath !== "string" || !existsSync(runtimeManifestPath)) {
    return null;
  }
  return readJson(runtimeManifestPath).runtimeKind ?? null;
}

function resolvePackagedAppRoot(packageManifest, packageDir) {
  const appName = packageManifest.appName ?? "Plato";
  const localAppRoot = path.join(packageDir, `${appName}.app`);
  return existsSync(localAppRoot) ? localAppRoot : packageManifest.appRoot;
}

function readJson(filePath) {
  return JSON.parse(readFileSync(filePath, "utf8"));
}

function runCommand(command, args, { label }) {
  console.log(`[plato-electron-installer] start ${label}`);
  const result = spawnSync(command, args, {
    cwd: frontendRoot,
    encoding: "utf8",
    stdio: "inherit",
  });
  if (result.status !== 0) {
    throw new Error(`${label} failed with exit code ${result.status ?? "null"}`);
  }
  console.log(`[plato-electron-installer] pass ${label}`);
}
