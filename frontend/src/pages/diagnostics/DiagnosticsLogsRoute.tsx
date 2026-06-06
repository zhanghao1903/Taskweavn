import { useMemo, useState } from "react";

import { Button } from "../../shared/components";
import { navigateApp } from "../../app/navigation";
import type { PlatoRuntimeEnv } from "../../app/platoRuntime";
import {
  buildAuditSessionRoute,
  buildAuditTaskRoute,
  buildMainSessionFallbackRoute,
} from "../../app/routes";
import type {
  DiagnosticBundleExportResult,
  PlatoApi,
} from "../../shared/api/platoApi";
import { createHttpPlatoApi } from "../../shared/api/platoApi";
import type { DiagnosticsLogsRouteLocation } from "./diagnosticsRouteModel";
import { parseDiagnosticsLogsLocation } from "./diagnosticsRouteModel";
import styles from "./DiagnosticsLogsRoute.module.css";

export type DiagnosticsLogsRouteProps = {
  api?: Pick<PlatoApi, "exportDiagnosticBundle">;
  location?: DiagnosticsLogsRouteLocation;
  runtimeEnv?: PlatoRuntimeEnv;
};

export function DiagnosticsLogsRoute({
  api,
  location,
  runtimeEnv = import.meta.env,
}: DiagnosticsLogsRouteProps = {}) {
  const resolvedLocation = location ?? globalThis.location;
  const context = useMemo(
    () => parseDiagnosticsLogsLocation(resolvedLocation.pathname, resolvedLocation.search),
    [resolvedLocation.pathname, resolvedLocation.search],
  );
  const exportApi = useMemo(
    () => api ?? createDiagnosticsApi(runtimeEnv),
    [api, runtimeEnv],
  );
  const [exportState, setExportState] = useState<DiagnosticExportState>({
    kind: "idle",
  });

  if (context === null) {
    return (
      <main className={styles.page}>
        <section className={styles.panel}>
          <h1>Diagnostics</h1>
          <p>Diagnostic context is unavailable for this route.</p>
          <Button onClick={() => navigateApp("/")}>Return</Button>
        </section>
      </main>
    );
  }

  const auditHref =
    context.taskNodeId === null
      ? buildAuditSessionRoute(context.sessionId, {
          filter: context.category === "audit" ? "logs" : undefined,
          recordId: context.recordId ?? undefined,
        })
      : buildAuditTaskRoute(context.sessionId, context.taskNodeId, {
          filter: context.category === "audit" ? "logs" : undefined,
          recordId: context.recordId ?? undefined,
      });
  const exportAvailable = exportApi !== null;
  const isExporting = exportState.kind === "exporting";

  async function exportDiagnostics() {
    if (exportApi === null || context === null) {
      return;
    }

    setExportState({ kind: "exporting" });
    try {
      const response = await exportApi.exportDiagnosticBundle(context.sessionId);
      if (!response.ok || response.data === null) {
        setExportState({ kind: "error" });
        return;
      }
      setExportState({ kind: "success", result: response.data });
    } catch {
      setExportState({ kind: "error" });
    }
  }

  return (
    <main className={styles.page}>
      <section
        aria-label="Diagnostics log handoff"
        className={styles.panel}
      >
        <div className={styles.headerRow}>
          <div>
            <h1>Diagnostics</h1>
            <p>Session log references are ready for local export.</p>
          </div>
          <span className={styles.badge}>Read-only</span>
        </div>
        <dl className={styles.contextGrid}>
          <div>
            <dt>Session</dt>
            <dd>{context.sessionId}</dd>
          </div>
          {context.taskNodeId !== null && (
            <div>
              <dt>Task</dt>
              <dd>{context.taskNodeId}</dd>
            </div>
          )}
          {context.recordId !== null && (
            <div>
              <dt>Audit record</dt>
              <dd>{context.recordId}</dd>
            </div>
          )}
        </dl>
        <pre className={styles.command}>
          {`uv run taskweavn diagnostics export --workspace <workspace> --session-id ${context.sessionId} --output <dir>`}
        </pre>
        <div className={styles.exportPanel}>
          <div>
            <h2>Export bundle</h2>
            <p>
              Create a redacted local bundle for this session without exposing raw logs in the UI.
            </p>
          </div>
          <Button
            disabled={!exportAvailable || isExporting}
            onClick={exportDiagnostics}
            variant="primary"
          >
            {isExporting ? "Exporting" : "Export diagnostics"}
          </Button>
          {!exportAvailable && (
            <p className={styles.helperText}>
              Start Plato with the local sidecar to export diagnostics from the UI.
            </p>
          )}
          <DiagnosticExportStatus state={exportState} />
        </div>
        <div className={styles.actions}>
          <Button
            onClick={() =>
              navigateApp(
                buildMainSessionFallbackRoute({
                  sessionId: context.sessionId,
                  taskNodeId: context.taskNodeId ?? undefined,
                }),
              )
            }
            variant="secondary"
          >
            Return to session
          </Button>
          <Button onClick={() => navigateApp(auditHref)}>
            Return to audit
          </Button>
        </div>
      </section>
    </main>
  );
}

type DiagnosticExportState =
  | {
      kind: "idle" | "exporting" | "error";
    }
  | {
      kind: "success";
      result: DiagnosticBundleExportResult;
    };

function DiagnosticExportStatus({ state }: { state: DiagnosticExportState }) {
  if (state.kind === "error") {
    return (
      <div className={styles.errorState} role="alert">
        Diagnostic export failed. Retry or use the CLI command.
      </div>
    );
  }

  if (state.kind !== "success") {
    return null;
  }

  const result = state.result;
  const zipPath = result.zipPathLabel ?? result.zipPath ?? "Not created";
  const warningCount =
    result.warnings.length +
    result.sections.reduce(
      (total, section) => total + section.warnings.length,
      0,
    );

  return (
    <section className={styles.exportResult} aria-label="Diagnostic export result">
      <div className={styles.resultHeader}>
        <h2>Bundle ready</h2>
        <span>{result.fileCount} files</span>
      </div>
      <dl className={styles.resultGrid}>
        <div>
          <dt>Bundle</dt>
          <dd>{result.bundleId}</dd>
        </div>
        <div>
          <dt>Zip path</dt>
          <dd>{zipPath}</dd>
        </div>
        <div>
          <dt>Manifest</dt>
          <dd>{result.manifestPathLabel}</dd>
        </div>
        <div>
          <dt>Redaction</dt>
          <dd>{result.redactionProfile}</dd>
        </div>
      </dl>
      <p className={styles.helperText}>
        Included sections: {result.includedSections.join(", ") || "none"}.
      </p>
      {warningCount > 0 && (
        <p className={styles.warningText}>
          {warningCount === 1 ? "1 warning" : `${warningCount} warnings`} recorded in the manifest.
        </p>
      )}
    </section>
  );
}

function createDiagnosticsApi(
  runtimeEnv: PlatoRuntimeEnv,
): Pick<PlatoApi, "exportDiagnosticBundle"> | null {
  if (runtimeEnv.VITE_PLATO_API_MODE !== "http") {
    return null;
  }

  return createHttpPlatoApi({
    baseUrl: runtimeEnv.VITE_PLATO_API_BASE_URL ?? globalThis.location.origin,
  });
}
