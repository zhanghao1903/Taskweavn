export type SettingsRouteSource = "first-run" | "settings";

export type SettingsRouteContext = {
  returnTo: string;
  source: SettingsRouteSource;
};

export function isSettingsPath(pathname: string): boolean {
  return pathname === "/settings";
}

export function buildSettingsRoute({
  returnTo = "/",
  source = "settings",
}: Partial<SettingsRouteContext> = {}): string {
  const params = new URLSearchParams();
  if (source !== "settings") {
    params.set("source", source);
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
