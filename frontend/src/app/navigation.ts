export const PLATO_NAVIGATION_EVENT = "plato:navigation";

export function navigateApp(path: string): void {
  globalThis.history.pushState(null, "", path);
  globalThis.dispatchEvent(new Event(PLATO_NAVIGATION_EVENT));
}

export function resolveAppNavigationHref(
  href: string,
  currentHref = globalThis.location.href,
): string | null {
  let url: URL;
  let currentUrl: URL;

  try {
    currentUrl = new URL(currentHref);
    url = new URL(href, currentUrl);
  } catch {
    return null;
  }

  if (!isSameAppOrigin(url, currentUrl)) {
    return null;
  }

  if (!isAppRoutePath(url.pathname)) {
    return null;
  }

  return `${url.pathname}${url.search}${url.hash}`;
}

function isSameAppOrigin(url: URL, currentUrl: URL): boolean {
  if (url.protocol !== currentUrl.protocol) {
    return false;
  }

  if (currentUrl.protocol === "file:") {
    return true;
  }

  return url.origin === currentUrl.origin;
}

function isAppRoutePath(pathname: string): boolean {
  return (
    pathname === "/" ||
    pathname.startsWith("/projects/") ||
    pathname.startsWith("/sessions/") ||
    pathname === "/settings" ||
    pathname.startsWith("/settings/") ||
    pathname.startsWith("/workspaces/")
  );
}
