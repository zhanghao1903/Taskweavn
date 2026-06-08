import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

const PACKAGED_APP_NAME = "@taskweavn/plato-packaged";
const SIDECAR_LAUNCHER_RELATIVE_PATH = path.join(
  "sidecar",
  "plato-sidecar-launcher.mjs",
);

export function resolvePackagedSidecarLauncherPath({
  appIsPackaged,
  env = process.env,
  exists = existsSync,
  frontendRoot,
  readFile = readFileSync,
  resourcesPath = process.resourcesPath,
}) {
  const explicitLauncherPath = env.PLATO_ELECTRON_SIDECAR_LAUNCHER_PATH;
  if (explicitLauncherPath) {
    return explicitLauncherPath;
  }

  const candidates = [];
  if (appIsPackaged || isPackagedAppResourceDir(frontendRoot, { exists, readFile })) {
    candidates.push(path.join(frontendRoot, SIDECAR_LAUNCHER_RELATIVE_PATH));
  }

  if (resourcesPath) {
    const resourceAppRoot = path.join(resourcesPath, "app");
    if (resourceAppRoot !== frontendRoot) {
      candidates.push(path.join(resourceAppRoot, SIDECAR_LAUNCHER_RELATIVE_PATH));
    }
  }

  for (const candidate of candidates) {
    if (exists(candidate)) {
      return candidate;
    }
  }
  return null;
}

function isPackagedAppResourceDir(directory, { exists, readFile }) {
  const packageJsonPath = path.join(directory, "package.json");
  if (!exists(packageJsonPath)) {
    return false;
  }
  try {
    const packageJson = JSON.parse(readFile(packageJsonPath, "utf8"));
    return packageJson.name === PACKAGED_APP_NAME;
  } catch {
    return false;
  }
}
