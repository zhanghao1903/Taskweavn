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
import { useUiText } from "../../shared/ui-text";
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
  const uiText = useUiText();
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
          <h1>{uiText.diagnostics.labels.diagnostics}</h1>
          <p>{uiText.diagnostics.messages.contextUnavailable}</p>
          <Button onClick={() => navigateApp("/")}>
            {uiText.settings.actions.return}
          </Button>
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
        aria-label={uiText.diagnostics.labels.diagnostics}
        className={styles.panel}
      >
        <div className={styles.headerRow}>
          <div>
            <h1>{uiText.diagnostics.labels.diagnostics}</h1>
            <p>{uiText.diagnostics.messages.handoffReady}</p>
          </div>
          <span className={styles.badge}>{uiText.diagnostics.labels.readOnly}</span>
        </div>
        <dl className={styles.contextGrid}>
          <div>
            <dt>{uiText.diagnostics.labels.session}</dt>
            <dd>{context.sessionId}</dd>
          </div>
          {context.taskNodeId !== null && (
            <div>
              <dt>{uiText.diagnostics.labels.task}</dt>
              <dd>{context.taskNodeId}</dd>
            </div>
          )}
          {context.recordId !== null && (
            <div>
              <dt>{uiText.diagnostics.labels.auditRecord}</dt>
              <dd>{context.recordId}</dd>
            </div>
          )}
        </dl>
        <pre className={styles.command}>
          {`uv run taskweavn diagnostics export --workspace <workspace> --session-id ${context.sessionId} --output <dir>`}
        </pre>
        <div className={styles.exportPanel}>
          <div>
            <h2>{uiText.diagnostics.labels.exportBundle}</h2>
            <p>
              {uiText.diagnostics.messages.exportBody}
            </p>
          </div>
          <Button
            disabled={!exportAvailable || isExporting}
            onClick={exportDiagnostics}
            variant="primary"
          >
            {isExporting
              ? uiText.settings.actions.exportingDiagnostics
              : uiText.diagnostics.actions.exportBundle}
          </Button>
          {!exportAvailable && (
            <p className={styles.helperText}>
              {uiText.diagnostics.messages.sidecarRequired}
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
            {uiText.diagnostics.actions.returnToSession}
          </Button>
          <Button onClick={() => navigateApp(auditHref)}>
            {uiText.diagnostics.actions.returnToAudit}
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
  const uiText = useUiText();

  if (state.kind === "error") {
    return (
      <div className={styles.errorState} role="alert">
        {uiText.diagnostics.messages.exportFailed}
      </div>
    );
  }

  if (state.kind !== "success") {
    return null;
  }

  const result = state.result;
  const zipPath =
    result.zipPathLabel ?? result.zipPath ?? uiText.settings.labels.notCreated;
  const warningCount =
    result.warnings.length +
    result.sections.reduce(
      (total, section) => total + section.warnings.length,
      0,
    );

  return (
    <section
      className={styles.exportResult}
      aria-label={uiText.diagnostics.labels.diagnosticExportResult}
    >
      <div className={styles.resultHeader}>
        <h2>{uiText.diagnostics.labels.bundleReady}</h2>
        <span>
          {uiText.diagnostics.messages.fileCount({ count: result.fileCount })}
        </span>
      </div>
      <dl className={styles.resultGrid}>
        <div>
          <dt>{uiText.diagnostics.labels.bundle}</dt>
          <dd>{result.bundleId}</dd>
        </div>
        <div>
          <dt>{uiText.diagnostics.labels.zipPath}</dt>
          <dd>{zipPath}</dd>
        </div>
        <div>
          <dt>{uiText.diagnostics.labels.manifest}</dt>
          <dd>{result.manifestPathLabel}</dd>
        </div>
        <div>
          <dt>{uiText.diagnostics.labels.redaction}</dt>
          <dd>{result.redactionProfile}</dd>
        </div>
      </dl>
      <p className={styles.helperText}>
        {uiText.diagnostics.messages.includedSections({
          sections:
            result.includedSections.join(", ") ||
            uiText.diagnostics.messages.noSections,
        })}
      </p>
      {warningCount > 0 && (
        <p className={styles.warningText}>
          {uiText.diagnostics.messages.warningCount({ count: warningCount })}
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
