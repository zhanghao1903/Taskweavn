#!/usr/bin/env node
import { spawn } from "node:child_process";
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { startPythonSidecar } from "../electron/sidecarProcess.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(frontendRoot, "..");
const runDir = mkdtempSync(path.join(tmpdir(), "taskweavn-sidecar-replay-"));
const workspaceDir = path.join(runDir, "workspace");
const readyFile = path.join(runDir, "seed-ready.json");
const commandId = "sidecar-restart-replay";

const options = parseArgs(process.argv.slice(2));
const children = new Set();
let activeRuntime = null;
let shuttingDown = false;

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    shuttingDown = true;
    void stopRuntime(activeRuntime);
    for (const child of children) {
      stopChild(child);
    }
    cleanup();
    process.kill(process.pid, signal);
  });
}

try {
  const fixture = await seedWorkspace();
  const targetFile = path.join(workspaceDir, fixture.inspectionFilePath);
  const beforeContent = readFileSync(targetFile, "utf8");

  const producer = await startFixtureRuntime("producer");
  await routeReadOnlyInquiry(producer.baseUrl, fixture);
  await stopFixtureRuntime(producer);

  activeRuntime = await startReplayRuntime("first");
  const beforeRestart = await captureReplayState(activeRuntime.baseUrl, fixture);
  await stopRuntime(activeRuntime);
  activeRuntime = null;

  activeRuntime = await startReplayRuntime("second");
  const afterRestart = await captureReplayState(activeRuntime.baseUrl, fixture);
  const afterContent = readFileSync(targetFile, "utf8");

  assertReplayStable({ afterRestart, beforeRestart, fixture });
  assertEqual(afterContent, beforeContent, "fixture file content changed");

  console.log("[plato-sidecar-restart-replay-smoke] pass");
} catch (error) {
  console.error(
    "[plato-sidecar-restart-replay-smoke] fail",
    error instanceof Error ? error.stack ?? error.message : String(error),
  );
  process.exitCode = 1;
} finally {
  shuttingDown = true;
  await stopRuntime(activeRuntime);
  for (const child of children) {
    stopChild(child);
  }
  cleanup();
}

function parseArgs(args) {
  let keepArtifacts = false;

  for (const arg of args) {
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    }
    if (arg === "--keep-artifacts") {
      keepArtifacts = true;
      continue;
    }
    throw new Error(`unknown option for sidecar restart replay smoke: ${arg}`);
  }

  return { keepArtifacts };
}

function printUsage() {
  console.log(`Usage:
  npm run electron:smoke:sidecar-restart
  npm run electron:smoke:sidecar-restart -- --keep-artifacts

Seeds deterministic Product 1.1 sidecar data, routes one read-only inquiry,
restarts the Electron sidecar lifecycle process against the same workspace, and
verifies durable Conversation / Activity / Audit replay.`);
}

async function seedWorkspace() {
  const child = spawn(
    "uv",
    [
      "run",
      "python",
      "-m",
      "tests.fixtures.sidecar_smoke",
      "--workspace",
      workspaceDir,
      "--ready-file",
      readyFile,
      "--first-run-configured",
    ],
    {
      cwd: repoRoot,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  children.add(child);
  child.stdout.on("data", (chunk) => process.stdout.write(chunk));
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  const exitCode = await waitForExit(child);
  children.delete(child);
  if (exitCode !== 0) {
    throw new Error(`sidecar seed failed with exit code ${exitCode}`);
  }
  if (!existsSync(readyFile)) {
    throw new Error(`sidecar seed did not write ready file: ${readyFile}`);
  }
  return JSON.parse(readFileSync(readyFile, "utf8"));
}

async function startFixtureRuntime(label) {
  const fixtureReadyFile = path.join(runDir, `${label}-ready.json`);
  console.log(`[plato-sidecar-restart-replay-smoke] start ${label} fixture`);
  const child = spawn(
    "uv",
    [
      "run",
      "python",
      "-m",
      "tests.fixtures.sidecar_smoke",
      "--workspace",
      workspaceDir,
      "--serve-existing",
      "--keep-alive",
      "--ready-file",
      fixtureReadyFile,
      "--first-run-configured",
    ],
    {
      cwd: repoRoot,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  children.add(child);
  child.stdout.on("data", (chunk) => process.stdout.write(chunk));
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  await waitForReadyFile(fixtureReadyFile);
  const payload = JSON.parse(readFileSync(fixtureReadyFile, "utf8"));
  if (typeof payload.baseUrl !== "string" || payload.baseUrl.length === 0) {
    throw new Error(`${label} fixture did not expose baseUrl`);
  }
  console.log(
    `[plato-sidecar-restart-replay-smoke] ready ${label} fixture ${payload.baseUrl}`,
  );
  return { baseUrl: payload.baseUrl, process: child };
}

async function startReplayRuntime(label) {
  console.log(`[plato-sidecar-restart-replay-smoke] start ${label} sidecar`);
  const runtime = await startPythonSidecar({
    appVersion: "sidecar-restart-replay-smoke",
    electronVersion: process.versions.electron ?? "node",
    env: {
      ...process.env,
      PLATO_ENABLE_READ_ONLY_INQUIRY_LLM: "0",
    },
    repoRoot,
    startupId: `sidecar-restart-replay-${label}`,
    timeoutMs: 20_000,
    workspaceRoot: workspaceDir,
  });
  console.log(
    `[plato-sidecar-restart-replay-smoke] ready ${label} sidecar ${runtime.baseUrl}`,
  );
  return runtime;
}

async function routeReadOnlyInquiry(baseUrl, fixture) {
  const response = await requestJson(
    baseUrl,
    "POST",
    (
      `/api/v1/workspaces/${encodeURIComponent(fixture.workspaceId)}` +
      `/sessions/${encodeURIComponent(fixture.sessionId)}/runtime-input/route`
    ),
    {
      commandId,
      sessionId: fixture.sessionId,
      content:
        "What changed in the diagnostics summary and what support diagnostics should I inspect?",
      mode: "ask",
      selection: {
        scopeKind: "task",
        taskNodeId: fixture.taskId,
      },
      clientState: {
        activeAskId: "sidecar-restart-replay-no-active-ask",
        activeConfirmationId: "sidecar-restart-replay-no-active-confirmation",
      },
      inquiryRefs: [
        {
          kind: "file",
          path: fixture.inspectionFilePath,
          label: fixture.inspectionFilePath,
        },
        {
          kind: "diff",
          path: fixture.inspectionFilePath,
          label: fixture.inspectionFilePath,
        },
        {
          kind: "audit_record",
          id: fixture.logRecordId,
          label: "Frontend error log record",
        },
        {
          kind: "audit_evidence",
          evidenceId: fixture.logEvidenceId,
          label: "Frontend error log evidence",
        },
        {
          kind: "result",
          id: `result:published:${fixture.taskId}`,
          label: "Task execution result",
        },
        {
          kind: "diagnostic",
          id: "diagnostic:bundle_export",
          label: "Diagnostic bundle export",
        },
      ],
    },
  );

  assertOk(response, "runtime input route");
  assertEqual(
    response.data?.outcome?.status,
    "answered",
    "runtime input route outcome",
  );
  assertEqual(
    response.data?.decision?.dispatchTarget,
    "read_only_inquiry",
    "runtime input dispatch target",
  );
  assertEqual(
    response.data?.decision?.sideEffect,
    "no_effect",
    "runtime input side effect",
  );
}

async function captureReplayState(baseUrl, fixture) {
  const sessionId = encodeURIComponent(fixture.sessionId);
  const logRecordId = encodeURIComponent(fixture.logRecordId);
  const logEvidenceId = encodeURIComponent(fixture.logEvidenceId);
  const snapshot = await requestJson(
    baseUrl,
    "GET",
    `/api/v1/sessions/${sessionId}/snapshot`,
  );
  const activity = await requestJson(
    baseUrl,
    "GET",
    `/api/v1/sessions/${sessionId}/activity`,
  );
  const auditRecord = await requestJson(
    baseUrl,
    "GET",
    `/api/v1/sessions/${sessionId}/audit/records/${logRecordId}?includeEvidence=true`,
  );
  const auditEvidence = await requestJson(
    baseUrl,
    "GET",
    `/api/v1/sessions/${sessionId}/audit/evidence/${logEvidenceId}`,
  );

  assertOk(snapshot, "snapshot");
  assertOk(activity, "activity");
  assertOk(auditRecord, "audit record");
  assertOk(auditEvidence, "audit evidence");

  const messages = Array.isArray(snapshot.data?.messages)
    ? snapshot.data.messages
    : [];
  const activityItems = Array.isArray(activity.data?.items)
    ? activity.data.items
    : [];
  const routeActivityId = `activity:inquiry:${commandId}`;
  const routeActivity = activityItems.find((item) => item.id === routeActivityId);

  if (!routeActivity) {
    throw new Error(`missing replay activity item: ${routeActivityId}`);
  }
  if (!messages.some((message) => String(message.id ?? "").includes(commandId))) {
    throw new Error("snapshot messages did not include routed runtime input records");
  }

  return {
    activityIds: sortedUnique(activityItems.map((item) => item.id)),
    auditEvidenceId: auditEvidence.data?.id ?? null,
    auditRecordId: auditRecord.data?.id ?? null,
    messageIds: sortedUnique(messages.map((message) => message.id)),
    routeActivity: normalizeActivity(routeActivity),
    sessionId: snapshot.data?.session?.id ?? null,
  };
}

function assertReplayStable({ afterRestart, beforeRestart, fixture }) {
  assertEqual(afterRestart.sessionId, fixture.sessionId, "session id after restart");
  assertJsonEqual(
    afterRestart.messageIds,
    beforeRestart.messageIds,
    "conversation message id replay",
  );
  assertJsonEqual(
    afterRestart.activityIds,
    beforeRestart.activityIds,
    "activity id replay",
  );
  assertJsonEqual(
    afterRestart.routeActivity,
    beforeRestart.routeActivity,
    "read-only inquiry activity replay",
  );
  assertEqual(
    afterRestart.auditRecordId,
    beforeRestart.auditRecordId,
    "audit record id replay",
  );
  assertEqual(
    afterRestart.auditEvidenceId,
    beforeRestart.auditEvidenceId,
    "audit evidence id replay",
  );
}

function normalizeActivity(item) {
  return {
    body: item.body,
    id: item.id,
    kind: item.kind,
    relatedRefs: (item.relatedRefs ?? []).map((ref) => ({
      href: ref.href ?? null,
      id: ref.id ?? null,
      kind: ref.kind,
      label: ref.label ?? null,
    })),
    scopeKind: item.scopeKind,
    sideEffect: item.sideEffect,
    sourceId: item.sourceId,
    title: item.title,
  };
}

async function requestJson(baseUrl, method, pathName, body = null) {
  const response = await fetch(`${baseUrl}${pathName}`, {
    body: body === null ? undefined : JSON.stringify(body),
    headers: body === null ? undefined : { "content-type": "application/json" },
    method,
    signal: AbortSignal.timeout(10_000),
  });
  const text = await response.text();
  let payload = null;
  try {
    payload = text.length === 0 ? null : JSON.parse(text);
  } catch (error) {
    throw new Error(
      `${method} ${pathName} returned non-JSON response: ${text.slice(0, 400)}`,
      { cause: error },
    );
  }
  if (!response.ok) {
    throw new Error(
      `${method} ${pathName} failed with ${response.status}: ${text.slice(0, 800)}`,
    );
  }
  return payload;
}

function assertOk(response, label) {
  if (response?.ok !== true) {
    throw new Error(`${label} response was not ok: ${JSON.stringify(response)}`);
  }
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(
      `${label} mismatch: expected ${JSON.stringify(expected)}, got ${JSON.stringify(
        actual,
      )}`,
    );
  }
}

function assertJsonEqual(actual, expected, label) {
  const actualJson = JSON.stringify(actual);
  const expectedJson = JSON.stringify(expected);
  if (actualJson !== expectedJson) {
    throw new Error(`${label} mismatch:\nexpected ${expectedJson}\ngot ${actualJson}`);
  }
}

function sortedUnique(values) {
  return [...new Set(values.map((value) => String(value)))].sort();
}

async function stopRuntime(runtime) {
  if (runtime === null) {
    return;
  }
  const child = runtime.process;
  runtime.stop();
  if (child) {
    await waitForExit(child, 5_000);
  }
}

async function stopFixtureRuntime(runtime) {
  if (runtime === null) {
    return;
  }
  const child = runtime.process;
  stopChild(child);
  await waitForExit(child, 5_000);
  children.delete(child);
}

function waitForExit(child, timeoutMs = 20_000) {
  if (child.exitCode !== null) {
    return Promise.resolve(child.exitCode ?? 0);
  }
  if (child.signalCode !== null) {
    return Promise.resolve(1);
  }
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      if (!shuttingDown) {
        stopChild(child);
      }
      reject(new Error(`timed out waiting for process exit: pid=${child.pid}`));
    }, timeoutMs);
    child.once("exit", (code, signal) => {
      clearTimeout(timeout);
      resolve(signal === null ? code ?? 0 : 1);
    });
  });
}

async function waitForReadyFile(filePath, timeoutMs = 20_000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (existsSync(filePath)) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`timed out waiting for ready file: ${filePath}`);
}

function stopChild(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) {
    return;
  }
  child.kill("SIGINT");
  setTimeout(() => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill("SIGKILL");
    }
  }, 2_000).unref();
}

function cleanup() {
  if (options.keepArtifacts) {
    console.log(`[plato-sidecar-restart-replay-smoke] kept artifacts at ${runDir}`);
    return;
  }
  rmSync(runDir, { force: true, recursive: true });
}
