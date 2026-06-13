#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  rmSync,
  statSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const iconRoot = path.join(frontendRoot, "assets", "icons");
const sourceSvg = path.join(frontendRoot, "src", "assets", "icons", "plato-product-mark.svg");
const iconsetDir = path.join(iconRoot, "plato.iconset");
const outputIcns = path.join(iconRoot, "plato.icns");

const iconsetSpecs = [
  ["icon_16x16.png", 16],
  ["icon_16x16@2x.png", 32],
  ["icon_32x32.png", 32],
  ["icon_32x32@2x.png", 64],
  ["icon_128x128.png", 128],
  ["icon_128x128@2x.png", 256],
  ["icon_256x256.png", 256],
  ["icon_256x256@2x.png", 512],
  ["icon_512x512.png", 512],
  ["icon_512x512@2x.png", 1024],
];

try {
  if (process.platform !== "darwin") {
    throw new Error("electron icon generation currently requires macOS iconutil.");
  }
  if (!existsSync(sourceSvg)) {
    throw new Error(`Icon SVG source not found: ${sourceSvg}`);
  }

  const tempRoot = mkdtempSync(path.join(os.tmpdir(), "plato-electron-icon-"));
  try {
    const basePng = renderSvgThumbnail(sourceSvg, tempRoot);
    rmSync(iconsetDir, { force: true, recursive: true });
    mkdirSync(iconsetDir, { recursive: true });
    for (const [fileName, size] of iconsetSpecs) {
      execFileSync(
        "sips",
        ["-z", String(size), String(size), basePng, "--out", path.join(iconsetDir, fileName)],
        { stdio: "ignore" },
      );
    }
    execFileSync("iconutil", ["-c", "icns", iconsetDir, "-o", outputIcns], {
      stdio: "inherit",
    });
  } finally {
    rmSync(tempRoot, { force: true, recursive: true });
  }

  console.log(`[plato-electron-icon] source=${sourceSvg}`);
  console.log(`[plato-electron-icon] iconset=${iconsetDir}`);
  console.log(`[plato-electron-icon] icns=${outputIcns}`);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

function renderSvgThumbnail(inputSvg, outputDir) {
  execFileSync("qlmanage", ["-t", "-s", "1024", "-o", outputDir, inputSvg], {
    stdio: "ignore",
  });
  const pngs = readdirSync(outputDir)
    .filter((entry) => entry.endsWith(".png"))
    .map((entry) => path.join(outputDir, entry))
    .filter((entryPath) => statSync(entryPath).isFile());
  if (pngs.length === 0) {
    throw new Error("Quick Look did not render a PNG thumbnail for the SVG icon.");
  }
  return pngs[0];
}
