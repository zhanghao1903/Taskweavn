import { setTimeout as delay } from "node:timers/promises";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

const DEFAULT_TIMEOUT_MS = 15_000;

export async function runElectronSmoke({
  baseUrl,
  fixture,
  kind = "configured",
  window,
}) {
  if (kind === "workspace-git-init") {
    validateWorkspaceGitInitFixture(fixture);
    await smokeWorkspaceGitInit(window, fixture);
    return;
  }

  validateFixture(fixture);
  const appReloadUrl = await evaluate(window, "location.href");

  if (kind === "first-run") {
    await smokeSettingsFirstRun(window, fixture);
    return;
  }

  if (kind === "workspace-entry") {
    await smokeWorkspaceEntry(window, fixture);
    const runtimeBaseUrl = await evaluate(
      window,
      "window.platoRuntimeConfig && window.platoRuntimeConfig.apiBaseUrl",
    );
    if (typeof runtimeBaseUrl !== "string" || runtimeBaseUrl.length === 0) {
      throw new Error("Workspace entry did not expose an HTTP runtime base URL");
    }
    baseUrl = runtimeBaseUrl;
  }

  await waitForText(window, "Diagnostics smoke", {
    label: "Main Page seeded session title",
  });
  await waitForText(window, `Run ${fixture.taskId}`, {
    label: "Main Page seeded task",
  });

  await smokeAuditEvidence(window, fixture);
  await smokeWorkspaceInspection(window, fixture);
  await smokeDiagnosticsExport(window, fixture);
  await smokeReadOnlyInquiryActivity(window, { appReloadUrl, baseUrl, fixture });
  await smokeCommandFailureRecovery(window, { baseUrl, fixture });
}

async function smokeWorkspaceEntry(window, fixture) {
  await waitForText(window, "Open a workspace", {
    label: "Workspace Picker heading",
  });
  await waitForText(window, fixture.workspaceName, {
    label: "Workspace Picker recent workspace",
  });
  await clickByText(window, "button", fixture.workspaceName);
  await waitForText(window, "Starting Plato", {
    label: "Workspace-selected sidecar startup",
    timeoutMs: 20_000,
  });
  await waitForText(window, "Diagnostics smoke", {
    label: "Main Page after workspace selection",
    timeoutMs: 30_000,
  });
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");
}

async function smokeWorkspaceGitInit(window, fixture) {
  await waitForText(window, "Open a workspace", {
    label: "Workspace Picker heading",
  });
  await waitForText(window, fixture.workspaceName, {
    label: "Workspace Picker recent workspace",
  });
  await evaluate(
    window,
    "localStorage.setItem('plato.workspaceGit.initializeOnOpen', '1')",
  );
  await clickByText(window, "button", fixture.workspaceName);
  await waitForText(window, "Starting Plato", {
    label: "Workspace Git init sidecar startup",
    timeoutMs: 20_000,
  });
  await waitForFile(
    path.join(fixture.workspaceDir, ".git", "info", "exclude"),
    {
      label: "Git exclude after workspace initialization",
      timeoutMs: 10_000,
    },
  );

  const exclude = readFileSync(
    path.join(fixture.workspaceDir, ".git", "info", "exclude"),
    "utf8",
  );
  if (!exclude.split(/\r?\n/u).map((line) => line.trim()).includes(".plato/")) {
    throw new Error("Workspace Git init did not add .plato/ to .git/info/exclude");
  }

  const gitignorePath = path.join(fixture.workspaceDir, ".gitignore");
  if (existsSync(gitignorePath)) {
    const gitignore = readFileSync(gitignorePath, "utf8");
    if (gitignore.includes(".plato")) {
      throw new Error("Workspace Git init wrote .plato to project .gitignore");
    }
  }

  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");
}

export async function runElectronStartupDiagnosticsSmoke({ fixture = {}, window }) {
  const expectedFailureText =
    typeof fixture.expectedStartupDiagnosticText === "string"
      ? fixture.expectedStartupDiagnosticText
      : "Timed out waiting for Python sidecar health";

  await waitForText(window, "Plato startup diagnostics", {
    label: "Startup diagnostics heading",
  });
  await waitForText(window, "sidecar_failed", {
    label: "Startup diagnostics status",
  });
  await waitForText(window, expectedFailureText, {
    label: "Startup diagnostics failure reason",
  });
  await waitForText(window, "workspace://current", {
    label: "Startup diagnostics workspace alias",
  });
  await waitForText(window, "Timeout", {
    label: "Startup diagnostics timeout field",
  });

  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");
  await assertBodyDoesNotContain(window, fixture.repoRoot, "repository root");
  await assertBodyDoesNotContain(window, "LLM_API_KEY=", "raw LLM API key");
  await assertBodyDoesNotContain(window, "DEEPSEEK_API_KEY=", "raw DeepSeek API key");
  await assertBodyDoesNotContain(window, "OPENROUTER_API_KEY=", "raw OpenRouter API key");
  await assertBodyDoesNotContain(window, "Bearer ", "raw bearer token");
}

async function smokeSettingsFirstRun(window, fixture) {
  const secret = `sk-electron-first-run-${fixture.sessionId}`;

  await waitForText(window, "Setup required", {
    label: "First-run setup required",
  });
  await waitForText(window, "needs_configuration", {
    label: "First-run blocking issue",
  });
  await waitForText(window, "LLM_API_KEY", {
    label: "First-run missing API key hint",
  });
  await assertBodyDoesNotContain(
    window,
    "test-sidecar-readiness-key",
    "seeded configured secret",
  );

  await clickByText(window, "button", "Configure settings");
  await waitForText(window, "Complete first-run setup", {
    label: "Settings first-run modal",
  });
  await waitForControlValue(window, "Provider", "deepseek", {
    label: "first-run provider default",
  });

  await setLabeledControlValue(window, "API key", secret);
  await clickByText(window, "button", "Save and check");

  await waitForText(window, "First-run setup is ready.", {
    label: "Settings save/recheck success",
    timeoutMs: 20_000,
  });
  await assertBodyDoesNotContain(window, secret, "first-run API key text");
  await assertControlValuesDoNotContain(
    window,
    secret,
    "first-run API key input",
  );
  await assertBodyDoesNotContain(
    window,
    "test-sidecar-readiness-key",
    "seeded configured secret",
  );

  await clickByText(window, "button", "Continue to Main Page");
  await waitForText(window, "Diagnostics smoke", {
    label: "Main Page after first-run setup",
    timeoutMs: 20_000,
  });
  await waitForText(window, `Run ${fixture.taskId}`, {
    label: "Main Page task after first-run setup",
  });
  await assertBodyDoesNotContain(window, secret, "first-run API key text");
  await assertControlValuesDoNotContain(
    window,
    secret,
    "first-run API key input",
  );
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");
}

async function smokeAuditEvidence(window, fixture) {
  const auditHref = await evaluate(window, findHrefScript("View audit"));
  if (typeof auditHref !== "string" || !auditHref.includes("/audit")) {
    throw new Error(`View audit href was not available: ${String(auditHref)}`);
  }

  await navigate(window, withAuditFilter(auditHref, "all"));
  await waitForText(window, "Audit", { label: "Audit heading" });
  await waitForAccessibleText(window, "Audit record Task result available");
  await waitForAccessibleText(window, "Audit record File change recorded");
  await waitForAccessibleText(window, "Audit record FileWriteObservation observation");
  await waitForAccessibleText(window, "Audit record Logging config snapshot");
  await waitForAccessibleText(window, "Audit record Log evidence available");

  await clickByText(window, "button", "Audit record Task result available");
  await waitForText(window, "Why it matters", {
    label: "Task result audit detail",
  });
  await waitForText(window, "Evidence", {
    label: "Task result audit evidence heading",
  });
  await waitForText(window, "Timeline task result", {
    label: "Task result audit evidence source",
  });
  await waitForText(window, "Provider rate limit prevented task completion.", {
    label: "Task result audit body",
  });

  await clickByText(window, "button", "Audit record File change recorded");
  await waitForText(window, "diagnostics-summary.md", {
    label: "File change audit detail",
  });
  await waitForText(window, "No sanitized payload is available for this record.", {
    label: "Projected file sanitized payload boundary",
  });

  await clickByText(
    window,
    "button",
    "Audit record FileWriteObservation observation",
  );
  await waitForText(window, "FileWriteObservation payload", {
    label: "FileWriteObservation detail",
  });
  await waitForText(window, "Evidence payload · FileWriteObservation payload", {
    label: "FileWriteObservation sanitized payload",
  });
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");
}

async function smokeWorkspaceInspection(window, fixture) {
  await navigate(window, "/");
  await waitForText(window, "Diagnostics smoke", {
    label: "Main Page before workspace inspection",
  });

  const auditHref = await evaluate(window, findHrefScript("View audit"));
  if (typeof auditHref !== "string" || !auditHref.includes("/audit")) {
    throw new Error(`View audit href was not available: ${String(auditHref)}`);
  }

  await navigate(window, withAuditFilter(auditHref, "all"));
  await waitForText(window, "Audit", {
    label: "Audit heading for workspace inspection",
  });
  await clickByText(window, "button", "Audit record File change recorded");
  await waitForText(window, "Workspace evidence", {
    label: "Workspace evidence links",
  });
  await waitForText(window, fixture.inspectionFilePath, {
    label: "Workspace evidence file path",
  });

  await clickByText(window, "a", "View diff");
  await waitForText(window, "File diff", {
    label: "Workspace inspection diff heading",
  });
  await waitForText(window, fixture.inspectionFilePath, {
    label: "Workspace inspection diff file path",
  });
  await waitForText(window, "+Workspace inspection seeded change.", {
    label: "Workspace inspection seeded diff line",
  });
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");

  await navigate(
    window,
    workspaceInspectionPath(fixture, {
      view: "status",
    }),
  );
  await waitForText(window, "Changed files", {
    label: "Workspace inspection status heading",
  });
  await waitForText(window, fixture.inspectionFilePath, {
    label: "Workspace inspection changed file",
  });
  await waitForText(window, "Unstaged", {
    label: "Workspace inspection unstaged status",
  });
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");
}

async function smokeDiagnosticsExport(window, fixture) {
  const diagnosticsUrl = new URL(fixture.diagnosticsLogUrl);
  await navigate(window, `${diagnosticsUrl.pathname}${diagnosticsUrl.search}`);
  await waitForText(window, "Diagnostics", {
    label: "Diagnostics route heading",
  });
  await waitForText(window, fixture.sessionId, {
    label: "Diagnostics session id",
  });
  await waitForText(window, fixture.logRecordId, {
    label: "Diagnostics log record id",
  });

  await clickByText(window, "button", "Export diagnostics");
  await waitForText(window, "Bundle ready", {
    label: "Diagnostic bundle export success",
    timeoutMs: 20_000,
  });
  await waitForText(window, "product_1_0_default", {
    label: "Diagnostic bundle redaction profile",
  });
  await waitForText(window, "workspace://current/.plato/diagnostics/", {
    label: "Diagnostic bundle workspace label",
  });
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");
}

async function smokeReadOnlyInquiryActivity(
  window,
  { appReloadUrl, baseUrl, fixture },
) {
  await navigate(window, "/");
  await waitForText(window, "Diagnostics smoke", {
    label: "Main Page before read-only inquiry Activity",
  });

  const commandId = `route-electron-read-only-inquiry-${Date.now()}`;
  const routeUrl = `${baseUrl.replace(/\/$/, "")}/api/v1/workspaces/${encodeURIComponent(
    fixture.workspaceId,
  )}/sessions/${encodeURIComponent(fixture.sessionId)}/runtime-input/route`;
  const routeResponse = await evaluate(
    window,
    `fetch(${JSON.stringify(routeUrl)}, {
      body: JSON.stringify({
        commandId: ${JSON.stringify(commandId)},
        content: "What support diagnostics should I inspect for this audit evidence?",
        inquiryRefs: [
          {
            id: ${JSON.stringify(fixture.logRecordId)},
            kind: "audit_record",
            label: "Frontend error log record"
          },
          {
            evidenceId: ${JSON.stringify(fixture.logEvidenceId)},
            kind: "audit_evidence",
            label: "Frontend error log evidence"
          },
          {
            id: "diagnostic:bundle_export",
            kind: "diagnostic",
            label: "Diagnostic bundle export"
          }
        ],
        mode: "ask",
        selection: {
          scopeKind: "task",
          taskNodeId: ${JSON.stringify(fixture.taskId)}
        },
        sessionId: ${JSON.stringify(fixture.sessionId)}
      }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    }).then((response) => response.json())`,
  );
  if (
    routeResponse?.ok !== true ||
    routeResponse?.data?.decision?.sideEffect !== "no_effect" ||
    routeResponse?.data?.outcome?.status !== "answered"
  ) {
    throw new Error(
      `Read-only inquiry route did not answer with no_effect: ${JSON.stringify(
        routeResponse,
      )}`,
    );
  }
  const expectedAnswerText =
    fixture.readOnlyInquiryLlmEnabled === true
      ? "LLM rendered a read-only answer from cited safe evidence only."
      : "Diagnostic support 'Diagnostic bundle export'";
  if (
    fixture.readOnlyInquiryLlmEnabled === true &&
    routeResponse?.data?.inquiryResult?.answer?.body !== expectedAnswerText
  ) {
    throw new Error(
      `Read-only inquiry LLM smoke did not return the guarded answer: ${JSON.stringify(
        routeResponse,
      )}`,
    );
  }

  await load(
    window,
    `/sessions/${encodeURIComponent(
      fixture.sessionId,
    )}?taskNodeId=${encodeURIComponent(
      fixture.taskId,
    )}&workspaceId=${encodeURIComponent(fixture.workspaceId)}`,
    { appReloadUrl },
  );
  await waitForText(window, "Diagnostics smoke", {
    label: "Main Page after read-only inquiry Activity persistence",
  });
  await waitForText(window, "Read-only question answered", {
    label: "Main Page read-only inquiry Activity strip",
  });
  await clickByText(window, "button", "Activity");
  await clickByText(window, "button", "All activity", { optional: true });
  await waitForText(window, expectedAnswerText, {
    label: "Read-only inquiry diagnostic support Activity",
  });

  await clickByText(window, "button", "Export diagnostics");
  await waitForText(window, "Bundle ready", {
    label: "Read-only inquiry diagnostic Activity export success",
    timeoutMs: 20_000,
  });
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");

  const auditHref = await evaluate(window, findHrefScript("Open audit"));
  if (typeof auditHref !== "string" || !auditHref.includes("/audit")) {
    throw new Error(`Read-only inquiry Audit href was not available: ${String(auditHref)}`);
  }
  await navigate(window, auditHref);
  await waitForText(window, "Audit", {
    label: "Read-only inquiry Audit evidence navigation",
  });
  await waitForText(window, "Evidence payload · frontend-errors.jsonl", {
    label: "Read-only inquiry Audit evidence focus",
  });
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");
}

async function smokeCommandFailureRecovery(window, { baseUrl, fixture }) {
  await navigate(window, "/");
  await waitForText(window, "Diagnostics smoke", {
    label: "Main Page before retry rejection",
  });
  await waitForText(window, `Run ${fixture.taskId}`, {
    label: "Retry task before stale command",
  });
  await waitForText(window, "Retry", {
    label: "Retry action before stale command",
  });

  const primerResponse = await evaluate(
    window,
    `fetch(${JSON.stringify(
      `${baseUrl.replace(/\/$/, "")}/api/v1/sessions/${encodeURIComponent(
        fixture.sessionId,
      )}/tasks/${encodeURIComponent(fixture.taskId)}/retry`,
    )}, {
      body: JSON.stringify({
        commandId: ${JSON.stringify(`prime-electron-retry-${Date.now()}`)},
        payload: { startImmediately: true },
        sessionId: ${JSON.stringify(fixture.sessionId)}
      }),
      headers: {
        "Content-Type": "application/json"
      },
      method: "POST"
    }).then((response) => response.json())`,
  );
  if (primerResponse?.ok !== true) {
    throw new Error(
      `Retry primer did not return ok=true: ${JSON.stringify(primerResponse)}`,
    );
  }

  await clickByText(window, "button", "Retry");
  await waitForText(window, "only failed tasks can be retried", {
    label: "Rejected retry command text",
  });
  await waitForText(window, "Refresh session", {
    label: "Recovery label",
  });
  await assertBodyDoesNotContain(window, "command_rejected", "raw error code");
  await assertBodyDoesNotContain(window, "recoveryActions", "raw recovery key");
  await assertBodyDoesNotContain(window, "productCategory", "raw category key");
  await assertBodyDoesNotContain(window, "TaskStoreError", "raw exception type");
}

async function waitForText(window, text, { label, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  await waitFor(
    window,
    label ?? `text ${text}`,
    `document.body.textContent.includes(${JSON.stringify(text)})`,
    timeoutMs,
  );
}

async function waitForFile(filePath, { label, timeoutMs = DEFAULT_TIMEOUT_MS }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (existsSync(filePath)) {
      return;
    }
    await delay(100);
  }
  throw new Error(`Timed out waiting for ${label}: ${filePath}`);
}

async function waitForAccessibleText(
  window,
  text,
  { timeoutMs = DEFAULT_TIMEOUT_MS } = {},
) {
  await waitFor(
    window,
    `accessible text ${text}`,
    `Boolean(findElementByText("*", ${JSON.stringify(text)}))`,
    timeoutMs,
  );
}

async function clickByText(window, selector, text, { optional = false } = {}) {
  const clicked = await evaluate(
    window,
    `(() => {
      ${domHelperSource()}
      const element = findElementByText(${JSON.stringify(selector)}, ${JSON.stringify(
        text,
      )});
      if (!element) return false;
      element.click();
      return true;
    })()`,
  );
  if (clicked !== true) {
    if (optional) {
      return;
    }
    throw new Error(`Could not click ${selector} with text ${text}`);
  }
}

async function setLabeledControlValue(window, label, value) {
  const changed = await evaluate(
    window,
    `(() => {
      ${domHelperSource()}
      const control = findControlByLabel(${JSON.stringify(label)});
      if (!control) return false;
      const descriptor = Object.getOwnPropertyDescriptor(
        Object.getPrototypeOf(control),
        "value"
      );
      if (descriptor?.set) {
        descriptor.set.call(control, ${JSON.stringify(value)});
      } else {
        control.value = ${JSON.stringify(value)};
      }
      control.dispatchEvent(new Event("input", { bubbles: true }));
      control.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    })()`,
  );
  if (changed !== true) {
    throw new Error(`Could not set control with label ${label}`);
  }
}

async function waitForControlValue(
  window,
  label,
  value,
  { label: waitLabel, timeoutMs = DEFAULT_TIMEOUT_MS } = {},
) {
  await waitFor(
    window,
    waitLabel ?? `control ${label} value ${value}`,
    `(() => {
      const control = findControlByLabel(${JSON.stringify(label)});
      return control !== null && control.value === ${JSON.stringify(value)};
    })()`,
    timeoutMs,
  );
}

async function assertBodyDoesNotContain(window, text, label) {
  if (!text) {
    return;
  }
  const found = await evaluate(
    window,
    `document.body.textContent.includes(${JSON.stringify(text)})`,
  );
  if (found) {
    throw new Error(`UI exposed ${label}: ${text}`);
  }
}

async function assertControlValuesDoNotContain(window, text, label) {
  if (!text) {
    return;
  }
  const found = await evaluate(
    window,
    `Array.from(document.querySelectorAll("input, select, textarea")).some((control) =>
      String(control.value ?? "").includes(${JSON.stringify(text)})
    )`,
  );
  if (found) {
    throw new Error(`UI control exposed ${label}: ${text}`);
  }
}

async function navigate(window, path) {
  await evaluate(
    window,
    `(() => {
      history.pushState(null, "", ${JSON.stringify(path)});
      dispatchEvent(new Event("plato:navigation"));
    })()`,
  );
}

async function load(window, path, { appReloadUrl = null } = {}) {
  await evaluate(
    window,
    `(() => {
      if (navigator.userAgent.includes("jsdom")) {
        history.pushState(null, "", ${JSON.stringify(path)});
        dispatchEvent(new Event("plato:navigation"));
        return;
      }
      if (location.protocol === "file:") {
        location.assign(${JSON.stringify(appReloadUrl)});
        return;
      }
      location.assign(${JSON.stringify(path)});
    })()`,
  );
}

async function waitFor(window, label, predicateScript, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await evaluateWithDomHelpers(
      window,
      `Boolean(${predicateScript})`,
    );
    if (result === true) {
      return;
    }
    await delay(150);
  }

  const body = await evaluate(
    window,
    `document.body.textContent.replace(/\\s+/g, " ").slice(0, 1200)`,
  );
  throw new Error(`Timed out waiting for ${label}. Body: ${body}`);
}

async function evaluate(window, script) {
  await window.webContents.executeJavaScript("undefined", true);
  return await window.webContents.executeJavaScript(script, true);
}

async function evaluateWithDomHelpers(window, expression) {
  return await evaluate(
    window,
    `(() => {
      ${domHelperSource()}
      return ${expression};
    })()`,
  );
}

function findHrefScript(label) {
  return `(() => {
    ${domHelperSource()}
    const element = findElementByText("a", ${JSON.stringify(label)});
    return element ? element.getAttribute("href") : null;
  })()`;
}

function domHelperSource() {
  return `
    function findElementByText(selector, text) {
      const expected = String(text);
      const elements = Array.from(document.querySelectorAll(selector));
      return elements.find((element) => {
        const accessible = [
          element.getAttribute("aria-label"),
          element.getAttribute("title"),
          element.textContent
        ].filter(Boolean).join(" ").replace(/\\s+/g, " ").trim();
        return accessible.includes(expected);
      }) ?? null;
    }
    function findControlByLabel(text) {
      const expected = String(text);
      const labels = Array.from(document.querySelectorAll("label"));
      for (const label of labels) {
        const accessible = String(label.textContent ?? "")
          .replace(/\\s+/g, " ")
          .trim();
        if (!accessible.includes(expected)) continue;
        const labeledControl = label.control;
        if (labeledControl) return labeledControl;
        const nestedControl = label.querySelector("input, select, textarea");
        if (nestedControl) return nestedControl;
      }
      return Array.from(document.querySelectorAll("input, select, textarea")).find(
        (control) => {
          const accessible = [
            control.getAttribute("aria-label"),
            control.getAttribute("name"),
            control.getAttribute("placeholder")
          ].filter(Boolean).join(" ").replace(/\\s+/g, " ").trim();
          return accessible.includes(expected);
        },
      ) ?? null;
    }
  `;
}

function validateFixture(fixture) {
  const required = [
    "baseUrl",
    "diagnosticsLogUrl",
    "inspectionFilePath",
    "logEvidenceId",
    "logRecordId",
    "sessionId",
    "taskId",
    "workspaceDir",
    "workspaceId",
  ];
  const missing = required.filter((key) => !fixture[key]);
  if (missing.length > 0) {
    throw new Error(`Electron smoke fixture is missing: ${missing.join(", ")}`);
  }
}

function validateWorkspaceGitInitFixture(fixture) {
  const required = ["workspaceDir", "workspaceName"];
  const missing = required.filter((key) => !fixture[key]);
  if (missing.length > 0) {
    throw new Error(
      `Electron workspace Git smoke fixture is missing: ${missing.join(", ")}`,
    );
  }
}

function withAuditFilter(href, filter) {
  const url = new URL(href, "http://plato.local");
  url.searchParams.set("filter", filter);
  return `${url.pathname}${url.search}`;
}

function workspaceInspectionPath(fixture, { view }) {
  const params = new URLSearchParams();
  params.set("sessionId", fixture.sessionId);
  params.set("view", view);
  return `/workspaces/${encodeURIComponent(
    fixture.workspaceId,
  )}/inspection?${params.toString()}`;
}
