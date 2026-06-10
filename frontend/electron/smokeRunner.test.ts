import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mkdirSync, writeFileSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { runElectronSmoke } from "./smokeRunner.mjs";

const fixture = {
  baseUrl: "http://127.0.0.1:53100",
  diagnosticsLogUrl:
    "http://127.0.0.1:53100/sessions/session-1/diagnostics/logs?category=audit&recordId=record-log.jsonl",
  inspectionFilePath: "diagnostics-summary.md",
  logRecordId: "record-log.jsonl",
  sessionId: "session-1",
  taskId: "task-1",
  workspaceDir: "/private/tmp/plato-workspace",
  workspaceId: "workspace-1",
};

const navigations: string[] = [];
const tempDirs: string[] = [];

describe("runElectronSmoke", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    installTestLocalStorage();
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.history.pushState(null, "", "/");
    navigations.length = 0;
    renderMainPage();
    globalThis.addEventListener("plato:navigation", handleNavigation);
  });

  afterEach(() => {
    globalThis.removeEventListener("plato:navigation", handleNavigation);
    globalThis.fetch = originalFetch;
    globalThis.localStorage?.clear();
  });

  it("covers Audit file evidence, workspace diff, status, diagnostics, and recovery labels", async () => {
    await runElectronSmoke({
      baseUrl: fixture.baseUrl,
      fixture,
      kind: "configured",
      window: fakeBrowserWindow(),
    });

    expect(navigations).toContain("/");
    expect(navigations).toContain(
      "/workspaces/workspace-1/inspection?sessionId=session-1&view=status",
    );
    expect(navigations.some((path) => path.includes("/diagnostics/logs"))).toBe(
      true,
    );
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${fixture.baseUrl}/api/v1/sessions/session-1/tasks/task-1/retry`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(document.body).not.toHaveTextContent(fixture.workspaceDir);
  });

  it("covers Workspace Picker opt-in Git initialization", async () => {
    const workspaceDir = await tempDir();
    await mkdir(workspaceDir, { recursive: true });
    renderWorkspaceEntryPage("Plain Workspace", workspaceDir);

    await runElectronSmoke({
      baseUrl: null,
      fixture: {
        workspaceDir,
        workspaceName: "Plain Workspace",
      },
      kind: "workspace-git-init",
      window: fakeBrowserWindow(),
    });

    await expect(
      readFile(path.join(workspaceDir, ".git", "info", "exclude"), "utf8"),
    ).resolves.toContain(".plato/");
    expect(document.body).not.toHaveTextContent(workspaceDir);
  });
});

function fakeBrowserWindow() {
  return {
    webContents: {
      async executeJavaScript(script: string) {
        return globalThis.eval(script);
      },
    },
  };
}

function handleNavigation() {
  const path = `${globalThis.location.pathname}${globalThis.location.search}`;
  navigations.push(path);

  if (path === "/") {
    renderMainPage();
    return;
  }
  if (path.includes("/audit")) {
    renderAuditPage();
    return;
  }
  if (path.includes("/inspection") && path.includes("view=status")) {
    renderWorkspaceStatus();
    return;
  }
  if (path.includes("/diagnostics/logs")) {
    renderDiagnosticsPage();
  }
}

function renderMainPage() {
  document.body.innerHTML = `
    <main>
      <h1>Diagnostics smoke</h1>
      <a href="/sessions/session-1/audit">View audit</a>
      <button type="button">Retry</button>
      <p>Run task-1</p>
    </main>
  `;
  const retryButton = getButton("Retry");
  retryButton.addEventListener("click", () => {
    document.body.insertAdjacentHTML(
      "beforeend",
      `
        <p>only failed tasks can be retried</p>
        <p>Refresh session</p>
      `,
    );
  });
}

function renderWorkspaceEntryPage(workspaceName: string, workspaceDir: string) {
  document.body.innerHTML = `
    <main>
      <h1>Open a workspace</h1>
      <button type="button">${workspaceName}</button>
    </main>
  `;
  getButton(workspaceName).addEventListener("click", () => {
    const excludeDir = path.join(workspaceDir, ".git", "info");
    mkdirSync(excludeDir, { recursive: true });
    writeFileSync(path.join(excludeDir, "exclude"), ".plato/\n", "utf8");
    document.body.insertAdjacentHTML(
      "beforeend",
      "<p>Starting the local Python sidecar.</p>",
    );
  });
}

function renderAuditPage() {
  document.body.innerHTML = `
    <main>
      <h1>Audit</h1>
      <button type="button">Audit record Task result available</button>
      <button type="button">Audit record File change recorded</button>
      <button type="button">Audit record FileWriteObservation observation</button>
      <button type="button">Audit record Logging config snapshot</button>
      <button type="button">Audit record Log evidence available</button>
      <section id="detail"></section>
    </main>
  `;
  getButton("Audit record Task result available").addEventListener("click", () => {
    setDetail(`
      <h2>Why it matters</h2>
      <h3>Evidence</h3>
      <p>Timeline task result</p>
      <p>Provider rate limit prevented task completion.</p>
    `);
  });
  getButton("Audit record File change recorded").addEventListener("click", () => {
    setDetail(`
      <p>diagnostics-summary.md</p>
      <p>No sanitized payload is available for this record.</p>
      <h3>Workspace evidence</h3>
      <a href="/workspaces/workspace-1/inspection?path=diagnostics-summary.md&view=file">Open file</a>
      <a href="/workspaces/workspace-1/inspection?path=diagnostics-summary.md&view=diff">View diff</a>
    `);
    const diffLink = document.querySelector<HTMLAnchorElement>(
      'a[href*="view=diff"]',
    );
    diffLink?.addEventListener("click", (event) => {
      event.preventDefault();
      renderWorkspaceDiff();
    });
  });
  getButton("Audit record FileWriteObservation observation").addEventListener(
    "click",
    () => {
      setDetail(`
        <h2>FileWriteObservation payload</h2>
        <p>Evidence payload · FileWriteObservation payload</p>
      `);
    },
  );
}

function renderWorkspaceDiff() {
  document.body.innerHTML = `
    <main>
      <h1>File diff</h1>
      <h2>diagnostics-summary.md</h2>
      <pre>+Workspace inspection seeded change.</pre>
    </main>
  `;
}

function renderWorkspaceStatus() {
  document.body.innerHTML = `
    <main>
      <h1>Changed files</h1>
      <p>diagnostics-summary.md</p>
      <p>Unstaged</p>
    </main>
  `;
}

function renderDiagnosticsPage() {
  document.body.innerHTML = `
    <main>
      <h1>Diagnostics</h1>
      <p>session-1</p>
      <p>record-log.jsonl</p>
      <button type="button">Export diagnostics</button>
    </main>
  `;
  getButton("Export diagnostics").addEventListener("click", () => {
    document.body.insertAdjacentHTML(
      "beforeend",
      `
        <p>Bundle ready</p>
        <p>product_1_0_default</p>
        <p>workspace://current/.plato/diagnostics/</p>
      `,
    );
  });
}

function getButton(label: string) {
  const button = Array.from(document.querySelectorAll("button")).find((item) =>
    item.textContent?.includes(label),
  );
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`Missing test button: ${label}`);
  }
  return button;
}

function setDetail(html: string) {
  const detail = document.querySelector("#detail");
  if (detail === null) {
    throw new Error("Missing test detail region");
  }
  detail.innerHTML = html;
}

function installTestLocalStorage(): void {
  const storage = new Map<string, string>();
  const storageLike = {
    clear: () => storage.clear(),
    getItem: (key: string) => storage.get(key) ?? null,
    key: (index: number) => Array.from(storage.keys())[index] ?? null,
    get length() {
      return storage.size;
    },
    removeItem: (key: string) => storage.delete(key),
    setItem: (key: string, value: string) => storage.set(key, value),
  };
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storageLike,
  });
  Object.defineProperty(globalThis.window, "localStorage", {
    configurable: true,
    value: storageLike,
  });
}

async function tempDir() {
  const dir = await mkdtemp(path.join(os.tmpdir(), "plato-smoke-runner-"));
  tempDirs.push(dir);
  return dir;
}

afterEach(async () => {
  await Promise.all(
    tempDirs.map((dir) => rm(dir, { force: true, recursive: true })),
  );
  tempDirs.length = 0;
});
