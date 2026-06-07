import { randomUUID } from "node:crypto";

const DEFAULT_LOG_LIMIT = 24;
const MAX_LOG_LINE_LENGTH = 500;
const SECRET_PATTERNS = [
  /(LLM_API_KEY|DEEPSEEK_API_KEY|OPENROUTER_API_KEY|API_KEY|TOKEN|AUTHORIZATION)=([^\s]+)/gi,
  /(Bearer)\s+([A-Za-z0-9._~+/=-]+)/gi,
  /("?(?:apiKey|token|authorization)"?\s*:\s*")([^"]+)(")/gi,
];

export function createStartupId() {
  return `startup-${randomUUID()}`;
}

export function createStartupLogBuffer({
  limit = DEFAULT_LOG_LIMIT,
  redactionPaths = [],
} = {}) {
  const lines = [];

  return {
    append(chunk) {
      const text = String(chunk);
      for (const rawLine of text.split(/\r?\n/)) {
        const line = redactStartupLine(rawLine, { redactionPaths });
        if (!line) {
          continue;
        }
        lines.push(line);
        while (lines.length > limit) {
          lines.shift();
        }
      }
    },
    snapshot() {
      return [...lines];
    },
  };
}

export function redactStartupLine(line, { redactionPaths = [] } = {}) {
  let result = String(line).trim();
  if (!result) {
    return "";
  }

  for (const rawPath of redactionPaths) {
    if (!rawPath) {
      continue;
    }
    result = result.split(String(rawPath)).join("workspace://current");
  }

  for (const pattern of SECRET_PATTERNS) {
    result = result.replace(pattern, (_match, prefix, _secret, suffix = "") => {
      if (suffix) {
        return `${prefix}[redacted]${suffix}`;
      }
      return `${prefix}=[redacted]`;
    });
  }

  if (result.length > MAX_LOG_LINE_LENGTH) {
    return `${result.slice(0, MAX_LOG_LINE_LENGTH)}...`;
  }
  return result;
}

export function buildStartupDiagnostics({
  appVersion,
  baseUrl = null,
  electronVersion = process.versions.electron ?? "unknown",
  exitCode = null,
  healthUrl = null,
  message,
  pid = null,
  signal = null,
  startupId,
  status,
  stderr = [],
  stdout = [],
  timeoutMs = null,
  workspaceLabel = "workspace://current",
}) {
  return {
    appVersion,
    baseUrl,
    electronVersion,
    exitCode,
    healthUrl,
    message,
    pid,
    signal,
    startupId,
    status,
    stderr,
    stdout,
    timeoutMs,
    updatedAt: new Date().toISOString(),
    workspace: workspaceLabel,
  };
}

export function renderStartupDiagnosticsHtml(diagnostics) {
  const title =
    diagnostics.status === "ready"
      ? "Plato is starting"
      : "Plato startup diagnostics";
  const detailRows = [
    ["Status", diagnostics.status],
    ["Message", diagnostics.message],
    ["Workspace", diagnostics.workspace],
    ["Base URL", diagnostics.baseUrl],
    ["Health", diagnostics.healthUrl],
    ["Process", diagnostics.pid === null ? null : `pid ${diagnostics.pid}`],
    ["Exit", formatExit(diagnostics)],
    ["Timeout", diagnostics.timeoutMs === null ? null : `${diagnostics.timeoutMs}ms`],
    ["Startup ID", diagnostics.startupId],
    ["Updated", diagnostics.updatedAt],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(title)}</title>
    <style>
      :root {
        color-scheme: light;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      body {
        align-items: center;
        background: #eef5f8;
        color: #172033;
        display: flex;
        margin: 0;
        min-height: 100vh;
        padding: 48px;
      }
      main {
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid rgba(124, 141, 165, 0.32);
        border-radius: 8px;
        box-shadow: 0 24px 70px rgba(54, 73, 95, 0.18);
        box-sizing: border-box;
        margin: 0 auto;
        max-width: 880px;
        padding: 32px;
        width: 100%;
      }
      .eyebrow {
        color: #657186;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0;
        text-transform: uppercase;
      }
      h1 {
        font-size: 28px;
        line-height: 1.2;
        margin: 8px 0 8px;
      }
      p {
        color: #5d697d;
        line-height: 1.55;
        margin: 0 0 24px;
      }
      dl {
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        margin: 0 0 24px;
      }
      dt {
        color: #667186;
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 4px;
        text-transform: uppercase;
      }
      dd {
        background: #f7f9fb;
        border: 1px solid #dfe6ef;
        border-radius: 6px;
        margin: 0;
        min-height: 24px;
        overflow-wrap: anywhere;
        padding: 10px 12px;
      }
      h2 {
        font-size: 14px;
        margin: 24px 0 8px;
        text-transform: uppercase;
      }
      pre {
        background: #172033;
        border-radius: 6px;
        color: #f8fafc;
        max-height: 220px;
        overflow: auto;
        padding: 14px;
        white-space: pre-wrap;
      }
      @media (max-width: 720px) {
        body {
          padding: 20px;
        }
        main {
          padding: 24px;
        }
      }
    </style>
  </head>
  <body>
    <main>
      <span class="eyebrow">Desktop startup</span>
      <h1>${escapeHtml(title)}</h1>
      <p>${escapeHtml(diagnostics.message)}</p>
      <dl>
        ${detailRows
          .map(
            ([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(
              String(value),
            )}</dd></div>`,
          )
          .join("\n        ")}
      </dl>
      ${renderLogBlock("Recent sidecar output", diagnostics.stdout)}
      ${renderLogBlock("Recent sidecar errors", diagnostics.stderr)}
    </main>
  </body>
</html>`;
}

export function startupDiagnosticsDataUrl(diagnostics) {
  return `data:text/html;charset=utf-8,${encodeURIComponent(
    renderStartupDiagnosticsHtml(diagnostics),
  )}`;
}

function renderLogBlock(label, lines) {
  if (!Array.isArray(lines) || lines.length === 0) {
    return "";
  }
  return `<h2>${escapeHtml(label)}</h2><pre>${escapeHtml(lines.join("\n"))}</pre>`;
}

function formatExit(diagnostics) {
  if (diagnostics.exitCode === null && diagnostics.signal === null) {
    return null;
  }
  return `code=${diagnostics.exitCode ?? "null"} signal=${
    diagnostics.signal ?? "null"
  }`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
