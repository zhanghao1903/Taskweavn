#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { deflateSync, inflateSync } from "node:zlib";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
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
const appIconMask = {
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
    const appIconSvg = path.join(tempRoot, "plato-app-icon.svg");
    writeFileSync(appIconSvg, buildRoundedAppIconSvg(), "utf8");
    const basePng = renderSvgThumbnail(appIconSvg, tempRoot);
    applyRoundedPngAlphaMask(basePng, appIconMask);
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

function buildRoundedAppIconSvg() {
  const productMarkSvg = readFileSync(sourceSvg, "utf8");
  const productMarkHref = `data:image/svg+xml;base64,${Buffer.from(
    productMarkSvg,
    "utf8",
  ).toString("base64")}`;
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="plato-app-tile" x1="192" y1="144" x2="832" y2="880" gradientUnits="userSpaceOnUse">
      <stop stop-color="#F7FAFC"/>
      <stop offset="1" stop-color="#E8EEF4"/>
    </linearGradient>
  </defs>
  <rect x="${appIconMask.x}" y="${appIconMask.y}" width="${appIconMask.width}" height="${appIconMask.height}" rx="${appIconMask.radius}" fill="url(#plato-app-tile)" stroke="#FFFFFF" stroke-width="16"/>
  <image href="${productMarkHref}" x="248" y="250" width="528" height="472" preserveAspectRatio="xMidYMid meet"/>
</svg>
`;
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
