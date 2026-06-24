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
  const activeBaseUrl =
    typeof baseUrl === "string" && baseUrl.length > 0 ? baseUrl : fixture.baseUrl;
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
  baseUrl =
    typeof baseUrl === "string" && baseUrl.length > 0 ? baseUrl : activeBaseUrl;

  await waitForText(window, "Diagnostics smoke", {
    label: "Main Page seeded session title",
  });
  await waitForText(window, `Run ${fixture.taskId}`, {
    label: "Main Page seeded task",
  });

  if (kind === "runtime-input-wechat") {
    await smokeRuntimeInputWeChat(window, { appReloadUrl, baseUrl, fixture });
    return;
  }

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
  const auditHref = sessionAuditPath(fixture);

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

  const auditHref = sessionAuditPath(fixture);

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

  await clickByText(window, "a", "Open file");
  await waitForText(window, "File viewer", {
    label: "Workspace inspection file viewer heading",
  });
  await waitForText(window, "Initial sidecar fixture content.", {
    label: "Workspace inspection file viewer content",
  });
  await waitForText(window, "Workspace inspection seeded change.", {
    label: "Workspace inspection file viewer changed content",
  });
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");

  await navigate(
    window,
    workspaceInspectionPath(fixture, {
      view: "status",
    }),
  );
  await waitForText(window, "Changed files", {
    label: "Workspace inspection status before link-click diff",
  });
  await waitForText(window, fixture.inspectionFilePath, {
    label: "Workspace inspection changed file before link-click diff",
  });
  await waitForText(window, "Unstaged", {
    label: "Workspace inspection unstaged status before link-click diff",
  });
  await clickByText(window, "a", "View diff");
  await waitForText(window, "File diff", {
    label: "Workspace inspection link-click diff heading",
  });
  await waitForText(window, "+Workspace inspection seeded change.", {
    label: "Workspace inspection link-click diff line",
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

async function smokeRuntimeInputWeChat(
  window,
  { appReloadUrl, baseUrl, fixture },
) {
  await clearSeededRuntimeInputGates(window, { appReloadUrl, baseUrl, fixture });

  await setLabeledControlValue(
    window,
    "Context message",
    "给微信文件传输助手发消息",
  );
  await waitForControlValue(window, "Context message", "给微信文件传输助手发消息", {
    label: "WeChat missing-message input value",
  });
  await clickByText(window, "button", "Send message");
  await waitForText(
    window,
    "要发送给文件传输助手的消息内容是什么？没有创建发送任务。",
    {
      label: "WeChat send missing-message clarification",
    },
  );

  await setLabeledControlValue(
    window,
    "Context message",
    "Plato runtime input smoke message; computer-use remains disabled.",
  );
  await waitForControlValue(
    window,
    "Context message",
    "Plato runtime input smoke message; computer-use remains disabled.",
    {
      label: "WeChat follow-up input value",
    },
  );
  await clickByText(window, "button", "Send message");
  await waitForText(window, "当前执行环境不支持微信发送能力。没有发送消息。", {
    label: "WeChat send capability-disabled feedback",
  });
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");
}

async function clearSeededRuntimeInputGates(
  window,
  { appReloadUrl, baseUrl, fixture },
) {
  const askResponse = await postRuntimeInputRoute(window, { baseUrl, fixture }, {
    clientState: {
      activeAskId: fixture.askId,
    },
    commandId: `route-electron-wechat-setup-ask-${Date.now()}`,
    content: "Runtime input WeChat smoke setup answer.",
    selection: {
      scopeKind: "task",
      taskNodeId: fixture.taskId,
    },
    sessionId: fixture.sessionId,
  });
  if (
    askResponse?.ok !== true ||
    askResponse?.data?.decision?.dispatchTarget !== "resolve_ask" ||
    askResponse?.data?.outcome?.status !== "dispatched"
  ) {
    throw new Error(
      `Runtime input WeChat smoke could not clear seeded ASK: ${JSON.stringify(
        askResponse,
      )}`,
    );
  }

  const confirmationResponse = await postRuntimeInputRoute(
    window,
    { baseUrl, fixture },
    {
      clientState: {
        activeConfirmationId: fixture.confirmationId,
      },
      commandId: `route-electron-wechat-setup-confirm-${Date.now()}`,
      content: "no",
      selection: {
        scopeKind: "task",
        taskNodeId: fixture.taskId,
      },
      sessionId: fixture.sessionId,
    },
  );
  if (
    confirmationResponse?.ok !== true ||
    confirmationResponse?.data?.decision?.dispatchTarget !==
      "resolve_confirmation" ||
    confirmationResponse?.data?.outcome?.status !== "dispatched"
  ) {
    throw new Error(
      `Runtime input WeChat smoke could not clear seeded confirmation: ${JSON.stringify(
        confirmationResponse,
      )}`,
    );
  }

  await load(
    window,
    `/sessions/${encodeURIComponent(fixture.sessionId)}?workspaceId=${encodeURIComponent(
      fixture.workspaceId,
    )}`,
    { appReloadUrl },
  );
  await waitForText(window, "Diagnostics smoke", {
    label: "Main Page after clearing runtime-input gates",
    timeoutMs: 20_000,
  });
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
  const routeResponse = await postRuntimeInputRoute(window, { baseUrl, fixture }, {
    clientState: {
      activeAskId: "runtime-input-smoke-no-active-ask",
      activeConfirmationId: "runtime-input-smoke-no-active-confirmation",
    },
    commandId,
    content: "What support diagnostics should I inspect for this audit evidence?",
    inquiryRefs: [
      {
        id: fixture.logRecordId,
        kind: "audit_record",
        label: "Frontend error log record",
      },
      {
        evidenceId: fixture.logEvidenceId,
        kind: "audit_evidence",
        label: "Frontend error log evidence",
      },
      {
        id: "diagnostic:bundle_export",
        kind: "diagnostic",
        label: "Diagnostic bundle export",
      },
    ],
    mode: "ask",
    selection: {
      scopeKind: "task",
      taskNodeId: fixture.taskId,
    },
    sessionId: fixture.sessionId,
  });
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

  const guidanceResponse = await postRuntimeInputRoute(
    window,
    { baseUrl, fixture },
    {
      clientState: {
        activeAskId: "runtime-input-smoke-no-active-ask",
        activeConfirmationId: "runtime-input-smoke-no-active-confirmation",
      },
      commandId: `route-electron-guidance-${Date.now()}`,
      content: "Keep Product 1.1 release evidence concise and inspectable.",
      mode: "guide",
      selection: {
        scopeKind: "session",
      },
      sessionId: fixture.sessionId,
    },
  );
  if (
    guidanceResponse?.ok !== true ||
    guidanceResponse?.data?.decision?.dispatchTarget !== "record_guidance" ||
    guidanceResponse?.data?.outcome?.status !== "dispatched"
  ) {
    throw new Error(
      `Guidance route did not dispatch through record_guidance: ${JSON.stringify(
        guidanceResponse,
      )}`,
    );
  }

  const askResponse = await postRuntimeInputRoute(
    window,
    { baseUrl, fixture },
    {
      clientState: {
        activeAskId: fixture.askId,
      },
      commandId: `route-electron-ask-${Date.now()}`,
      content: "Ship Product 1.1 as beta.",
      selection: {
        scopeKind: "task",
        taskNodeId: fixture.taskId,
      },
      sessionId: fixture.sessionId,
    },
  );
  if (
    askResponse?.ok !== true ||
    askResponse?.data?.decision?.dispatchTarget !== "resolve_ask" ||
    askResponse?.data?.outcome?.status !== "dispatched"
  ) {
    throw new Error(
      `ASK route did not dispatch through resolve_ask: ${JSON.stringify(
        askResponse,
      )}`,
    );
  }

  const confirmationClarificationResponse = await postRuntimeInputRoute(
    window,
    { baseUrl, fixture },
    {
      clientState: {
        activeConfirmationId: fixture.confirmationId,
      },
      commandId: `route-electron-confirm-clarify-${Date.now()}`,
      content: "maybe after evidence",
      selection: {
        scopeKind: "task",
        taskNodeId: fixture.taskId,
      },
      sessionId: fixture.sessionId,
    },
  );
  if (
    confirmationClarificationResponse?.ok !== true ||
    confirmationClarificationResponse?.data?.decision?.dispatchTarget !==
      "clarification" ||
    confirmationClarificationResponse?.data?.outcome?.status !==
      "needs_clarification" ||
    confirmationClarificationResponse?.data?.decision?.sideEffect !== "no_effect"
  ) {
    throw new Error(
      `Confirmation clarification route did not fail closed: ${JSON.stringify(
        confirmationClarificationResponse,
      )}`,
    );
  }

  const confirmationResponse = await postRuntimeInputRoute(
    window,
    { baseUrl, fixture },
    {
      clientState: {
        activeConfirmationId: fixture.confirmationId,
      },
      commandId: `route-electron-confirm-${Date.now()}`,
      content: "yes",
      selection: {
        scopeKind: "task",
        taskNodeId: fixture.taskId,
      },
      sessionId: fixture.sessionId,
    },
  );
  if (
    confirmationResponse?.ok !== true ||
    confirmationResponse?.data?.decision?.dispatchTarget !==
      "resolve_confirmation" ||
    confirmationResponse?.data?.outcome?.status !== "dispatched"
  ) {
    throw new Error(
      `Confirmation route did not dispatch through resolve_confirmation: ${JSON.stringify(
        confirmationResponse,
      )}`,
    );
  }

  const executionResponse = await postRuntimeInputRoute(
    window,
    { baseUrl, fixture },
    {
      clientState: {
        activeAskId: "runtime-input-smoke-no-active-ask",
        activeConfirmationId: "runtime-input-smoke-no-active-confirmation",
      },
      commandId: `route-electron-execution-${Date.now()}`,
      content: "Create a release evidence follow-up task.",
      mode: "change",
      selection: {
        scopeKind: "session",
      },
      sessionId: fixture.sessionId,
    },
  );
  if (
    executionResponse?.ok !== true ||
    executionResponse?.data?.decision?.dispatchTarget !== "execution_handoff" ||
    executionResponse?.data?.decision?.sideEffect !== "state_effect" ||
    executionResponse?.data?.outcome?.status !== "dispatched"
  ) {
    throw new Error(
      `Execution handoff route did not create contract work: ${JSON.stringify(
        executionResponse,
      )}`,
    );
  }

  const unsupportedResponse = await postRuntimeInputRoute(
    window,
    { baseUrl, fixture },
    {
      clientState: {
        activeAskId: "runtime-input-smoke-no-active-ask",
        activeConfirmationId: "runtime-input-smoke-no-active-confirmation",
      },
      commandId: `route-electron-unsupported-${Date.now()}`,
      content: "blue banana release whisper",
      selection: {
        scopeKind: "session",
      },
      sessionId: fixture.sessionId,
    },
  );
  if (
    unsupportedResponse?.ok !== true ||
    unsupportedResponse?.data?.decision?.dispatchTarget !== "unsupported" ||
    unsupportedResponse?.data?.outcome?.status !== "unsupported" ||
    unsupportedResponse?.data?.decision?.sideEffect !== "no_effect"
  ) {
    throw new Error(
      `Unsupported route did not fail closed with no_effect: ${JSON.stringify(
        unsupportedResponse,
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
  await waitForText(window, "Guidance recorded", {
    label: "Guidance Runtime Input Activity",
  });
  await waitForText(window, "ASK answered", {
    label: "ASK Runtime Input Activity",
  });
  await waitForText(window, "Please answer the active confirmation", {
    label: "Confirmation clarification Runtime Input Activity",
  });
  await waitForText(window, "Confirmation resolved", {
    label: "Confirmation Runtime Input Activity",
  });
  await waitForText(window, "Execution work created", {
    label: "Execution handoff Runtime Input Activity",
  });
  await waitForText(window, "I could not route this input safely yet", {
    label: "Unsupported Runtime Input Activity",
  });

  await exportRuntimeInputDiagnostics(window, { baseUrl, fixture });
  await assertWorkspaceStatusOnlySeededChange(window, { baseUrl, fixture });
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");

  const auditHref = sessionAuditPath(fixture, {
    evidenceId: fixture.logEvidenceId,
    recordId: fixture.logRecordId,
  });
  await navigate(window, auditHref);
  await waitForText(window, "Audit", {
    label: "Read-only inquiry Audit evidence navigation",
  });
  await waitForText(window, "Evidence payload · frontend-errors.jsonl", {
    label: "Read-only inquiry Audit evidence focus",
  });
  await assertBodyDoesNotContain(window, fixture.workspaceDir, "workspace root");
}

async function postRuntimeInputRoute(window, { baseUrl, fixture }, payload) {
  const routeUrl = `${baseUrl.replace(/\/$/, "")}/api/v1/workspaces/${encodeURIComponent(
    fixture.workspaceId,
  )}/sessions/${encodeURIComponent(fixture.sessionId)}/runtime-input/route`;
  return await evaluate(
    window,
    `fetch(${JSON.stringify(routeUrl)}, {
      body: JSON.stringify(${JSON.stringify(payload)}),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    }).then((response) => response.json())`,
  );
}

async function assertWorkspaceStatusOnlySeededChange(window, { baseUrl, fixture }) {
  const statusUrl = `${baseUrl.replace(
    /\/$/,
    "",
  )}/api/v1/workspaces/${encodeURIComponent(
    fixture.workspaceId,
  )}/inspection/status?maxFiles=50`;
  const statusResponse = await evaluate(
    window,
    `fetch(${JSON.stringify(statusUrl)}).then((response) => response.json())`,
  );
  if (statusResponse?.ok !== true || statusResponse?.data == null) {
    throw new Error(
      `Workspace inspection status did not return ok=true: ${JSON.stringify(
        statusResponse,
      )}`,
    );
  }
  const files = statusResponse.data.files;
  if (!Array.isArray(files) || files.length !== 1) {
    throw new Error(
      `Runtime Input routes changed unexpected workspace files: ${JSON.stringify(
        files,
      )}`,
    );
  }
  const changedPath = files[0]?.relativePath ?? files[0]?.path;
  if (changedPath !== fixture.inspectionFilePath) {
    throw new Error(
      `Unexpected workspace status path after Runtime Input routes: ${JSON.stringify(
        files,
      )}`,
    );
  }
}

async function exportRuntimeInputDiagnostics(window, { baseUrl, fixture }) {
  const exportUrl =
    typeof baseUrl === "string" && baseUrl.length > 0
      ? `${baseUrl.replace(/\/$/, "")}/api/v1/sessions/${encodeURIComponent(
          fixture.sessionId,
        )}/diagnostics/export`
      : fixture.diagnosticExportUrl;
  if (typeof exportUrl !== "string" || exportUrl.length === 0) {
    throw new Error("Runtime input diagnostic export URL is unavailable");
  }
  const exportResponse = await evaluate(
    window,
    `fetch(${JSON.stringify(exportUrl)}, {
      headers: { "Content-Type": "application/json" },
      method: "POST"
    }).then((response) => response.json())`,
  );
  if (exportResponse?.ok !== true || exportResponse?.data == null) {
    throw new Error(
      `Runtime input diagnostic export did not return ok=true: ${JSON.stringify(
        exportResponse,
      )}`,
    );
  }
  const includedSections = exportResponse.data.includedSections;
  if (
    !Array.isArray(includedSections) ||
    !includedSections.includes("runtime_input")
  ) {
    throw new Error(
      `Runtime input diagnostic export did not include runtime_input: ${JSON.stringify(
        exportResponse,
      )}`,
    );
  }
}

async function smokeCommandFailureRecovery(window, { baseUrl, fixture }) {
  await navigate(
    window,
    `/sessions/${encodeURIComponent(
      fixture.sessionId,
    )}?taskNodeId=${encodeURIComponent(
      fixture.taskId,
    )}&workspaceId=${encodeURIComponent(fixture.workspaceId)}`,
  );
  await waitForText(window, "Diagnostics smoke", {
    label: "Main Page before retry rejection",
  });
  await waitForText(window, `Run ${fixture.taskId}`, {
    label: "Retry task before stale command",
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

  const staleRetryResponse = await evaluate(
    window,
    `fetch(${JSON.stringify(
      `${baseUrl.replace(/\/$/, "")}/api/v1/sessions/${encodeURIComponent(
        fixture.sessionId,
      )}/tasks/${encodeURIComponent(fixture.taskId)}/retry`,
    )}, {
      body: JSON.stringify({
        commandId: ${JSON.stringify(`stale-electron-retry-${Date.now()}`)},
        payload: { startImmediately: true },
        sessionId: ${JSON.stringify(fixture.sessionId)}
      }),
      headers: {
        "Content-Type": "application/json"
      },
      method: "POST"
    }).then((response) => response.json())`,
  );
  if (
    staleRetryResponse?.ok !== false ||
    !String(staleRetryResponse?.error?.message ?? "").includes(
      "only failed tasks can be retried",
    )
  ) {
    throw new Error(
      `Stale retry command did not return a product-safe rejection: ${JSON.stringify(
        staleRetryResponse,
      )}`,
    );
  }
  const recoveryActions = staleRetryResponse?.error?.details?.recoveryActions;
  if (
    !Array.isArray(recoveryActions) ||
    !recoveryActions.some((action) =>
      ["refresh_session", "refresh_snapshot"].includes(action),
    )
  ) {
    throw new Error(
      `Stale retry rejection did not expose refresh recovery action: ${JSON.stringify(
        staleRetryResponse,
      )}`,
    );
  }
  await assertBodyDoesNotContain(window, "TaskStoreError", "raw exception type");
  await assertBodyDoesNotContain(window, "Traceback", "raw traceback");
  await waitForText(window, "Diagnostics smoke", {
    label: "Main Page after stale retry rejection",
  });
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
    "askId",
    "confirmationId",
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

function sessionAuditPath(fixture, params = {}) {
  const searchParams = new URLSearchParams();
  searchParams.set("workspaceId", fixture.workspaceId);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, String(value));
    }
  }
  return `/sessions/${encodeURIComponent(fixture.sessionId)}/audit?${searchParams.toString()}`;
}

function workspaceInspectionPath(fixture, { view }) {
  const params = new URLSearchParams();
  params.set("sessionId", fixture.sessionId);
  params.set("view", view);
  return `/workspaces/${encodeURIComponent(
    fixture.workspaceId,
  )}/inspection?${params.toString()}`;
}
