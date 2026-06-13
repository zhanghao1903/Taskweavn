#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { deflateSync, inflateSync } from "node:zlib";
import {
  cpSync,
  existsSync,
  mkdtempSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  normalizeReleaseVersion,
  toDarwinBundleVersion,
  toPackageVersion,
} from "./release-version.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const defaultPackageDir = path.join(frontendRoot, "dist-electron-launcher");
const defaultOutputDir = path.join(frontendRoot, "dist-electron-installer");
const appIconName = "plato.icns";
const appIconSourcePath = path.join(frontendRoot, "assets", "icons", appIconName);
const productMarkSvgSourcePath = path.join(
  frontendRoot,
  "src",
  "assets",
  "icons",
  "plato-product-mark.svg",
);
const dmgFileIconMask = {
  height: 760,
  radius: 172,
  width: 760,
  x: 132,
  y: 116,
};
const crc32Table = Array.from({ length: 256 }, (_, value) => {
  let crc = value;
  for (let index = 0; index < 8; index += 1) {
    crc = crc & 1 ? 0xedb88320 ^ (crc >>> 1) : crc >>> 1;
  }
  return crc >>> 0;
});
const npmBin = process.platform === "win32" ? "npm.cmd" : "npm";
const frontendPackageJson = JSON.parse(
  readFileSync(path.join(frontendRoot, "package.json"), "utf8"),
);
const defaultReleaseVersion = normalizeReleaseVersion(frontendPackageJson.version);

const options = parseArgs(process.argv.slice(2));

try {
  if (process.platform !== "darwin") {
    throw new Error("electron:package:installer currently supports macOS only.");
  }
  const signing = resolveSigningOptions(options);

  if (!options.skipPackage) {
    const forwardedPackageArgs = [];
    if (options.releaseVersion !== null) {
      forwardedPackageArgs.push("--release-version", options.releaseVersion);
    }
    if (options.includeSmoke) {
      forwardedPackageArgs.push("--include-smoke");
    }
    const packageArgs = ["run", "electron:package:launcher-dir"];
    if (forwardedPackageArgs.length > 0) {
      packageArgs.push("--", ...forwardedPackageArgs);
    }
    runCommand(npmBin, packageArgs, {
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
      ...(options.includeSmoke ? ["--allow-smoke-assets"] : []),
    ],
    { label: "electron:check:release-assets" },
  );

  const packageManifestPath = path.join(options.packageDir, "package-manifest.json");
  const packageManifest = readJson(packageManifestPath);
  const sourceAppRoot = resolvePackagedAppRoot(packageManifest, options.packageDir);
  if (!existsSync(sourceAppRoot)) {
    throw new Error(`Packaged app not found: ${sourceAppRoot}`);
  }
  const releaseVersion = resolveInstallerReleaseVersion(packageManifest, options);
  const packageVersion = resolveInstallerPackageVersion(
    packageManifest,
    releaseVersion,
  );
  const bundleVersion = resolveInstallerBundleVersion(
    packageManifest,
    packageVersion,
  );

  const stagingRoot = path.join(options.outputDir, "staging", "Plato");
  const stagedAppRoot = path.join(stagingRoot, "Plato.app");
  const dmgPath = path.join(
    options.outputDir,
    `Plato-${releaseVersion}-macos-${process.arch}.dmg`,
  );
  rmSync(stagingRoot, { force: true, recursive: true });
  mkdirSync(stagingRoot, { recursive: true });
  mkdirSync(options.outputDir, { recursive: true });
  cpSync(sourceAppRoot, stagedAppRoot, {
    recursive: true,
    verbatimSymlinks: true,
  });
  prepareDmgVolumeIcon(stagingRoot);

  if (signing.sign) {
    signApp(stagedAppRoot, signing);
  }

  createDmg(stagingRoot, dmgPath);
  applyDmgFileIcon(dmgPath);

  if (signing.sign) {
    signDmg(dmgPath, signing);
  }
  if (signing.notarize) {
    notarizeDmg(dmgPath, signing);
  }

  const installerManifest = {
    appName: packageManifest.appName ?? "Plato",
    appVersion: releaseVersion,
    bundleVersion,
    createdAt: new Date().toISOString(),
    dmgPath,
    dmgFileIcon: "rounded-plato-product-mark",
    notarized: signing.notarize,
    packageDir: options.packageDir,
    packageManifestPath,
    packageVersion,
    releaseVersion,
    runtimeKind: readRuntimeKind(packageManifest),
    smokeAssetsIncluded: options.includeSmoke,
    signed: signing.sign,
    signingIdentity: signing.sign ? signing.identity : null,
    stagingRoot,
    type: "local-dmg-installer-candidate",
    volumeIcon: ".VolumeIcon.icns",
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
  let releaseVersion =
    process.env.PLATO_ELECTRON_RELEASE_VERSION === undefined
      ? null
      : normalizeReleaseVersion(process.env.PLATO_ELECTRON_RELEASE_VERSION);
  let sign = process.env.PLATO_ELECTRON_SIGN === "1";
  let includeSmoke = false;
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
    if (arg === "--release-version") {
      const value = args[index + 1];
      if (!value) {
        throw new Error("--release-version requires a version");
      }
      releaseVersion = normalizeReleaseVersion(value);
      index += 1;
      continue;
    }
    if (arg === "--sign") {
      sign = true;
      continue;
    }
    if (arg === "--include-smoke") {
      includeSmoke = true;
      continue;
    }
    if (arg === "--skip-package") {
      skipPackage = true;
      continue;
    }
    throw new Error(`unknown option for electron:package:installer: ${arg}`);
  }

  return {
    includeSmoke,
    notarize,
    outputDir: path.resolve(outputDir),
    packageDir: path.resolve(packageDir),
    releaseVersion,
    sign,
    skipPackage,
  };
}

function printUsage() {
  console.log(`Usage:
  npm run electron:package:installer
  npm run electron:package:installer -- --release-version 1.1-beta
  npm run electron:package:installer -- --skip-package
  npm run electron:package:installer -- --include-smoke
  npm run electron:package:installer -- --sign
  npm run electron:package:installer -- --sign --notarize

Builds a macOS DMG installer candidate from the launcher-backed bundled Python
package. By default this creates an unsigned local DMG for installer smoke.
Signing requires PLATO_ELECTRON_CODESIGN_IDENTITY or CSC_NAME. Notarization
requires either PLATO_ELECTRON_NOTARY_KEYCHAIN_PROFILE or Apple ID credentials.

Options:
  --package-dir <path>   Launcher package root. Defaults to dist-electron-launcher.
  --output-dir <path>    Installer output root. Defaults to dist-electron-installer.
  --release-version <v>  Public release version used for package metadata and DMG name.
  --include-smoke        Include packaged smoke runner files for test-only DMGs.
  --skip-package         Reuse the existing launcher package directory.
  --sign                 Codesign the staged app and DMG.
  --notarize             Submit and staple the DMG after signing.
  --help                 Show this help.`);
}

function resolveInstallerReleaseVersion(packageManifest, options) {
  const manifestReleaseVersion =
    typeof packageManifest.releaseVersion === "string"
      ? normalizeReleaseVersion(packageManifest.releaseVersion)
      : null;
  if (
    options.releaseVersion !== null &&
    manifestReleaseVersion !== null &&
    options.releaseVersion !== manifestReleaseVersion
  ) {
    throw new Error(
      `--release-version ${options.releaseVersion} does not match package manifest releaseVersion ${manifestReleaseVersion}`,
    );
  }
  return options.releaseVersion ?? manifestReleaseVersion ?? defaultReleaseVersion;
}

function resolveInstallerPackageVersion(packageManifest, releaseVersion) {
  const expectedPackageVersion = toPackageVersion(releaseVersion);
  if (
    typeof packageManifest.packageVersion === "string" &&
    packageManifest.packageVersion !== expectedPackageVersion
  ) {
    throw new Error(
      `package manifest packageVersion ${packageManifest.packageVersion} does not match releaseVersion ${releaseVersion}`,
    );
  }
  return expectedPackageVersion;
}

function resolveInstallerBundleVersion(packageManifest, packageVersion) {
  const expectedBundleVersion = toDarwinBundleVersion(packageVersion);
  if (
    typeof packageManifest.bundleVersion === "string" &&
    packageManifest.bundleVersion !== expectedBundleVersion
  ) {
    throw new Error(
      `package manifest bundleVersion ${packageManifest.bundleVersion} does not match packageVersion ${packageVersion}`,
    );
  }
  return expectedBundleVersion;
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
  const tempRoot = mkdtempSync(path.join(tmpdir(), "plato-dmg-build-"));
  const readWriteDmgPath = path.join(tempRoot, "Plato-rw.dmg");
  const mountPoint = path.join(tempRoot, "mount");
  let mounted = false;
  rmSync(dmgPath, { force: true });
  mkdirSync(mountPoint, { recursive: true });
  try {
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
        "UDRW",
        readWriteDmgPath,
      ],
      { label: "hdiutil create read-write dmg" },
    );
    runCommand(
      "hdiutil",
      [
        "attach",
        readWriteDmgPath,
        "-nobrowse",
        "-readwrite",
        "-mountpoint",
        mountPoint,
      ],
      { label: "hdiutil attach read-write dmg" },
    );
    mounted = true;
    stampMountedDmgVolumeIcon(mountPoint);
    runCommand("hdiutil", ["detach", mountPoint, "-quiet"], {
      label: "hdiutil detach read-write dmg",
    });
    mounted = false;
    runCommand(
      "hdiutil",
      [
        "convert",
        readWriteDmgPath,
        "-format",
        "UDZO",
        "-imagekey",
        "zlib-level=1",
        "-o",
        dmgPath,
        "-ov",
      ],
      { label: "hdiutil convert compressed dmg" },
    );
  } finally {
    if (mounted) {
      forceDetachDmg(mountPoint);
    }
    rmSync(tempRoot, { force: true, recursive: true });
  }
}

function prepareDmgVolumeIcon(stagingRoot) {
  ensureAppIconExists();
  const volumeIconPath = path.join(stagingRoot, ".VolumeIcon.icns");
  cpSync(appIconSourcePath, volumeIconPath);
  runCommand("SetFile", ["-a", "C", stagingRoot], {
    label: "SetFile dmg volume icon flag",
  });
  runCommand("SetFile", ["-a", "V", volumeIconPath], {
    label: "SetFile hide dmg volume icon file",
  });
}

function applyDmgFileIcon(dmgPath) {
  ensureAppIconExists();
  ensureProductMarkSvgExists();
  const tempRoot = mkdtempSync(path.join(tmpdir(), "plato-dmg-file-icon-"));
  const iconSvgPath = path.join(tempRoot, "plato-dmg-icon.svg");
  const iconResourcePath = path.join(tempRoot, "plato-dmg-icon.rsrc");
  try {
    writeFileSync(iconSvgPath, buildRoundedDmgFileIconSvg(), "utf8");
    const iconPngPath = renderSvgThumbnail(iconSvgPath, tempRoot);
    applyRoundedPngAlphaMask(iconPngPath, dmgFileIconMask);
    runCommand("sips", ["-i", iconPngPath], {
      label: "sips dmg file icon resource",
    });
    writeFileSync(
      iconResourcePath,
      runCapture("DeRez", ["-only", "icns", iconPngPath], {
        label: "DeRez dmg file icon resource",
      }),
    );
    runCommand("Rez", ["-append", iconResourcePath, "-o", dmgPath], {
      label: "Rez dmg file icon",
    });
    runCommand("SetFile", ["-a", "C", dmgPath], {
      label: "SetFile dmg file icon flag",
    });
  } finally {
    rmSync(tempRoot, { force: true, recursive: true });
  }
}

function ensureAppIconExists() {
  if (!existsSync(appIconSourcePath)) {
    throw new Error(
      `Plato app icon not found: ${appIconSourcePath}. Run npm run electron:generate:icon.`,
    );
  }
}

function ensureProductMarkSvgExists() {
  if (!existsSync(productMarkSvgSourcePath)) {
    throw new Error(`Plato product mark SVG not found: ${productMarkSvgSourcePath}`);
  }
}

function buildRoundedDmgFileIconSvg() {
  const productMarkSvg = readFileSync(productMarkSvgSourcePath, "utf8");
  const productMarkHref = `data:image/svg+xml;base64,${Buffer.from(
    productMarkSvg,
    "utf8",
  ).toString("base64")}`;
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="plato-dmg-tile" x1="192" y1="144" x2="832" y2="880" gradientUnits="userSpaceOnUse">
      <stop stop-color="#F7FAFC"/>
      <stop offset="1" stop-color="#E8EEF4"/>
    </linearGradient>
  </defs>
  <rect x="${dmgFileIconMask.x}" y="${dmgFileIconMask.y}" width="${dmgFileIconMask.width}" height="${dmgFileIconMask.height}" rx="${dmgFileIconMask.radius}" fill="url(#plato-dmg-tile)" stroke="#FFFFFF" stroke-width="16"/>
  <image href="${productMarkHref}" x="248" y="250" width="528" height="472" preserveAspectRatio="xMidYMid meet"/>
</svg>
`;
}

function renderSvgThumbnail(inputSvg, outputDir) {
  runCommand("qlmanage", ["-t", "-s", "1024", "-o", outputDir, inputSvg], {
    label: "qlmanage dmg file icon png",
  });
  const pngs = readdirSync(outputDir)
    .filter((entry) => entry.endsWith(".png"))
    .map((entry) => path.join(outputDir, entry))
    .filter((entryPath) => statSync(entryPath).isFile())
    .sort((left, right) => statSync(right).mtimeMs - statSync(left).mtimeMs);
  if (pngs.length === 0) {
    throw new Error("Quick Look did not render a PNG for the DMG file icon.");
  }
  return pngs[0];
}

function applyRoundedPngAlphaMask(filePath, mask) {
  const png = readPng(filePath);
  for (let y = 0; y < png.height; y += 1) {
    for (let x = 0; x < png.width; x += 1) {
      if (!isInsideRoundedRect(x + 0.5, y + 0.5, mask)) {
        png.data[(y * png.width + x) * 4 + 3] = 0;
      }
    }
  }
  writeFileSync(filePath, writePng(png));
}

function isInsideRoundedRect(x, y, { height, radius, width, x: left, y: top }) {
  const right = left + width;
  const bottom = top + height;
  if (x < left || x >= right || y < top || y >= bottom) {
    return false;
  }
  const innerLeft = left + radius;
  const innerRight = right - radius;
  const innerTop = top + radius;
  const innerBottom = bottom - radius;
  if ((x >= innerLeft && x < innerRight) || (y >= innerTop && y < innerBottom)) {
    return true;
  }
  const centerX = x < innerLeft ? innerLeft : innerRight;
  const centerY = y < innerTop ? innerTop : innerBottom;
  return (x - centerX) ** 2 + (y - centerY) ** 2 <= radius ** 2;
}

function readPng(filePath) {
  const buffer = readFileSync(filePath);
  const signature = buffer.subarray(0, 8);
  if (!signature.equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
    throw new Error(`PNG signature is invalid: ${filePath}`);
  }

  let offset = 8;
  let width = 0;
  let height = 0;
  let bitDepth = 0;
  let colorType = 0;
  const idatChunks = [];
  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.toString("ascii", offset + 4, offset + 8);
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    offset += length + 12;
    if (type === "IHDR") {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
      const compression = data[10];
      const filter = data[11];
      const interlace = data[12];
      if (
        bitDepth !== 8 ||
        colorType !== 6 ||
        compression !== 0 ||
        filter !== 0 ||
        interlace !== 0
      ) {
        throw new Error(
          `Unsupported PNG format for alpha mask: bitDepth=${bitDepth} colorType=${colorType} interlace=${interlace}`,
        );
      }
    } else if (type === "IDAT") {
      idatChunks.push(data);
    } else if (type === "IEND") {
      break;
    }
  }
  if (width <= 0 || height <= 0 || idatChunks.length === 0) {
    throw new Error(`PNG is missing image data: ${filePath}`);
  }

  const inflated = inflateSync(Buffer.concat(idatChunks));
  const bytesPerPixel = 4;
  const stride = width * bytesPerPixel;
  const data = Buffer.alloc(width * height * bytesPerPixel);
  let inputOffset = 0;
  for (let row = 0; row < height; row += 1) {
    const filterType = inflated[inputOffset];
    inputOffset += 1;
    const rowData = Buffer.from(inflated.subarray(inputOffset, inputOffset + stride));
    inputOffset += stride;
    const previousRow =
      row === 0 ? Buffer.alloc(stride) : data.subarray((row - 1) * stride, row * stride);
    unfilterPngRow(rowData, previousRow, filterType, bytesPerPixel);
    rowData.copy(data, row * stride);
  }

  return {
    data,
    height,
    width,
  };
}

function unfilterPngRow(rowData, previousRow, filterType, bytesPerPixel) {
  if (filterType === 0) {
    return;
  }
  for (let index = 0; index < rowData.length; index += 1) {
    const left = index >= bytesPerPixel ? rowData[index - bytesPerPixel] : 0;
    const up = previousRow[index] ?? 0;
    const upperLeft =
      index >= bytesPerPixel ? previousRow[index - bytesPerPixel] ?? 0 : 0;
    if (filterType === 1) {
      rowData[index] = (rowData[index] + left) & 0xff;
    } else if (filterType === 2) {
      rowData[index] = (rowData[index] + up) & 0xff;
    } else if (filterType === 3) {
      rowData[index] = (rowData[index] + Math.floor((left + up) / 2)) & 0xff;
    } else if (filterType === 4) {
      rowData[index] = (rowData[index] + paethPredictor(left, up, upperLeft)) & 0xff;
    } else {
      throw new Error(`Unsupported PNG row filter: ${filterType}`);
    }
  }
}

function paethPredictor(left, up, upperLeft) {
  const estimate = left + up - upperLeft;
  const distanceLeft = Math.abs(estimate - left);
  const distanceUp = Math.abs(estimate - up);
  const distanceUpperLeft = Math.abs(estimate - upperLeft);
  if (distanceLeft <= distanceUp && distanceLeft <= distanceUpperLeft) {
    return left;
  }
  if (distanceUp <= distanceUpperLeft) {
    return up;
  }
  return upperLeft;
}

function writePng({ data, height, width }) {
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;
  const stride = width * 4;
  const raw = Buffer.alloc((stride + 1) * height);
  for (let row = 0; row < height; row += 1) {
    raw[row * (stride + 1)] = 0;
    data.copy(raw, row * (stride + 1) + 1, row * stride, (row + 1) * stride);
  }
  return Buffer.concat([
    signature,
    pngChunk("IHDR", ihdr),
    pngChunk("IDAT", deflateSync(raw)),
    pngChunk("IEND", Buffer.alloc(0)),
  ]);
}

function pngChunk(type, data) {
  const typeBuffer = Buffer.from(type, "ascii");
  const chunk = Buffer.alloc(12 + data.length);
  chunk.writeUInt32BE(data.length, 0);
  typeBuffer.copy(chunk, 4);
  data.copy(chunk, 8);
  chunk.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])), 8 + data.length);
  return chunk;
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc = crc32Table[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function stampMountedDmgVolumeIcon(mountPoint) {
  const mountedVolumeIconPath = path.join(mountPoint, ".VolumeIcon.icns");
  if (!existsSync(mountedVolumeIconPath)) {
    throw new Error(`Mounted DMG volume icon is missing: ${mountedVolumeIconPath}`);
  }
  runCommand("SetFile", ["-a", "V", mountedVolumeIconPath], {
    label: "SetFile mounted dmg volume icon file",
  });
  runCommand("SetFile", ["-a", "C", mountPoint], {
    label: "SetFile mounted dmg volume icon flag",
  });
}

function forceDetachDmg(mountPoint) {
  const result = spawnSync("hdiutil", ["detach", mountPoint, "-force", "-quiet"], {
    cwd: frontendRoot,
    encoding: "utf8",
    stdio: "inherit",
  });
  if (result.status !== 0) {
    console.warn(
      `[plato-electron-installer] warning hdiutil force detach failed for ${mountPoint}`,
    );
  }
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

function runCapture(command, args, { label }) {
  console.log(`[plato-electron-installer] start ${label}`);
  const result = spawnSync(command, args, {
    cwd: frontendRoot,
    maxBuffer: 8 * 1024 * 1024,
    stdio: ["ignore", "pipe", "inherit"],
  });
  if (result.status !== 0) {
    throw new Error(`${label} failed with exit code ${result.status ?? "null"}`);
  }
  console.log(`[plato-electron-installer] pass ${label}`);
  return result.stdout;
}
