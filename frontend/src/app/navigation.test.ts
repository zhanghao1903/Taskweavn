import { describe, expect, it } from "vitest";

import { resolveAppNavigationHref } from "./navigation";

describe("app navigation helpers", () => {
  it("resolves packaged file:// workspace inspection links back to SPA paths", () => {
    expect(
      resolveAppNavigationHref(
        "file:///workspaces/current/inspection?view=diff&path=src%2FApp.tsx",
        "file:///Applications/Plato.app/Contents/Resources/app/dist/index.html",
      ),
    ).toBe("/workspaces/current/inspection?view=diff&path=src%2FApp.tsx");
  });

  it("resolves same-origin dev server links", () => {
    expect(
      resolveAppNavigationHref(
        "http://127.0.0.1:5173/sessions/session-1/audit",
        "http://127.0.0.1:5173/",
      ),
    ).toBe("/sessions/session-1/audit");
  });

  it("does not intercept external links or non-app file paths", () => {
    expect(
      resolveAppNavigationHref("https://example.com/workspaces/current/inspection"),
    ).toBeNull();
    expect(
      resolveAppNavigationHref(
        "file:///Users/example/report.pdf",
        "file:///Applications/Plato.app/Contents/Resources/app/dist/index.html",
      ),
    ).toBeNull();
  });
});
