import path from "node:path";

export function resolveElectronWorkspaceRoot({
  env = process.env,
  isPackaged = false,
  repoRoot,
  sidecarLauncherPath = null,
  userDataPath = null,
}) {
  const explicitWorkspace = env.PLATO_ELECTRON_WORKSPACE;
  if (typeof explicitWorkspace === "string" && explicitWorkspace.length > 0) {
    return explicitWorkspace;
  }

  if (isPackaged || sidecarLauncherPath !== null) {
    if (typeof userDataPath !== "string" || userDataPath.length === 0) {
      throw new Error("userDataPath is required for packaged Electron workspace");
    }
    return path.join(userDataPath, "workspace");
  }

  return path.join(repoRoot, "plato-workspace");
}
