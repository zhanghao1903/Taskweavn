export type SettingsRouteSource = "first-run" | "settings";
export type SettingsTab = "configuration" | "data" | "usage";

export type SettingsRouteContext = {
  returnTo: string;
  source: SettingsRouteSource;
  tab: SettingsTab;
};

export function isSettingsPath(pathname: string): boolean {
  return pathname === "/settings";
}

export function buildSettingsRoute({
  returnTo = "/",
  source = "settings",
  tab = "configuration",
}: Partial<SettingsRouteContext> = {}): string {
  const params = new URLSearchParams();
  if (source !== "settings") {
    params.set("source", source);
  }
  if (tab !== "configuration") {
    params.set("tab", tab);
  }
  const safeReturnTo = sanitizeReturnTo(returnTo);
  if (safeReturnTo !== "/") {
    params.set("returnTo", safeReturnTo);
  } else if (source === "first-run") {
    params.set("returnTo", "/");
  }

  const query = params.toString();
  return query ? `/settings?${query}` : "/settings";
}

export function parseSettingsRouteLocation(
  pathname: string,
  search: string,
): SettingsRouteContext | null {
  if (!isSettingsPath(pathname)) {
    return null;
  }

  const params = new URLSearchParams(search);
  const source =
    params.get("source") === "first-run" ? "first-run" : "settings";
  return {
    returnTo: sanitizeReturnTo(params.get("returnTo") ?? "/"),
    source,
    tab: source === "first-run" ? "configuration" : parseSettingsTab(params.get("tab")),
  };
}

export function sanitizeReturnTo(value: string): string {
  const trimmed = value.trim();
  if (!trimmed.startsWith("/") || trimmed.startsWith("//")) {
    return "/";
  }
  if (trimmed.startsWith("/settings")) {
    return "/";
  }
  return trimmed;
}

function parseSettingsTab(raw: string | null): SettingsTab {
  return raw === "data" || raw === "usage" ? raw : "configuration";
}
