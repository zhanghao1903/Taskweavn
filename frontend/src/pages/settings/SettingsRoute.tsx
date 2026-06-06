import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { navigateApp } from "../../app/navigation";
import type { PlatoRuntimeEnv } from "../../app/platoRuntime";
import { ApiClientError } from "../../shared/api/client";
import type {
  DiagnosticBundleExportResult,
  PlatoApi,
  SettingsConfigSummary,
  SettingsConfigUpdateResult,
  SettingsReadinessReport,
} from "../../shared/api/platoApi";
import { createHttpPlatoApi } from "../../shared/api/platoApi";
import type { ApiError, QueryResponse, SessionId } from "../../shared/api/types";
import { Button } from "../../shared/components";
import { formatRecoveryAction, settingsProviderLabel } from "./settingsCopy";
import type { SettingsRouteContext } from "./settingsRouteModel";
import { parseSettingsRouteLocation } from "./settingsRouteModel";
import {
  apiKeyHint,
  fieldErrorFor,
  fieldErrorsFromApiError,
  formStateFromConfig,
  providerOptions,
  type SettingsFieldError,
  type SettingsFormState,
} from "./settingsViewModel";
import styles from "./SettingsRoute.module.css";

export type SettingsRouteApi = Pick<
  PlatoApi,
  | "exportDiagnosticBundle"
  | "getSettingsConfig"
  | "listSessions"
  | "recheckSettingsReadiness"
  | "updateSettingsConfig"
>;

export type SettingsRouteProps = {
  api?: SettingsRouteApi;
  location?: Pick<Location, "pathname" | "search">;
  runtimeEnv?: PlatoRuntimeEnv;
};

type SaveState =
  | { kind: "idle" | "saving" | "success" | "rechecking" }
  | { error: ApiError | null; kind: "error"; message: string };

type DiagnosticExportState =
  | { kind: "idle" | "exporting" | "error" }
  | { kind: "success"; result: DiagnosticBundleExportResult };

export function SettingsRoute({
  api,
  location,
  runtimeEnv = import.meta.env,
}: SettingsRouteProps = {}) {
  const routeLocation = location ?? globalThis.location;
  const routeContext = useMemo(
    () =>
      parseSettingsRouteLocation(routeLocation.pathname, routeLocation.search) ?? {
        returnTo: "/",
        source: "settings" as const,
      },
    [routeLocation.pathname, routeLocation.search],
  );
  const settingsApi = useMemo(
    () => api ?? createSettingsApi(runtimeEnv),
    [api, runtimeEnv],
  );
  const apiBaseUrl =
    runtimeEnv.VITE_PLATO_API_BASE_URL ?? globalThis.location.origin;
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SettingsFormState | null>(null);
  const [saveState, setSaveState] = useState<SaveState>({ kind: "idle" });
  const [lastReadiness, setLastReadiness] =
    useState<SettingsReadinessReport | null>(null);
  const [diagnosticExportState, setDiagnosticExportState] =
    useState<DiagnosticExportState>({ kind: "idle" });

  const configQuery = useQuery({
    enabled: settingsApi !== null,
    queryFn: () => settingsApi!.getSettingsConfig(),
    queryKey: ["settings-config", apiBaseUrl],
    retry: false,
  });
  const sessionsQuery = useQuery({
    enabled: settingsApi !== null,
    queryFn: () => settingsApi!.listSessions(),
    queryKey: ["settings-sessions", apiBaseUrl],
    retry: false,
  });

  const config = unwrapQueryData(configQuery.data);
  useEffect(() => {
    if (config !== null && form === null) {
      setForm(formStateFromConfig(config));
    }
  }, [config, form]);

  if (settingsApi === null) {
    return (
      <SettingsShell
        heading="Settings unavailable"
        routeContext={routeContext}
        status="Sidecar required"
      >
        <p className={styles.helperText}>
          Start Plato in local sidecar HTTP mode to edit Product 1.0 settings.
        </p>
      </SettingsShell>
    );
  }

  if (configQuery.status === "pending" || form === null) {
    return (
      <SettingsShell
        heading="Loading settings"
        routeContext={routeContext}
        status="Checking"
      >
        <p className={styles.helperText}>Loading local sidecar settings.</p>
      </SettingsShell>
    );
  }

  if (configQuery.status === "error" || config === null) {
    return (
      <SettingsShell
        heading="Settings unavailable"
        routeContext={routeContext}
        status="Retry available"
      >
        <p className={styles.helperText}>
          The local sidecar did not return the settings config contract.
        </p>
        <div className={styles.footerActions}>
          <Button onClick={() => void configQuery.refetch()} variant="primary">
            Retry load
          </Button>
          <Button onClick={() => navigateApp(routeContext.returnTo)}>
            Return
          </Button>
        </div>
      </SettingsShell>
    );
  }

  const fieldErrors =
    saveState.kind === "error" ? fieldErrorsFromApiError(saveState.error) : [];
  const readiness = lastReadiness;
  const canContinue = readiness?.firstRun.ready === true;
  const diagnosticSessionId = resolveDiagnosticSessionId(
    runtimeEnv.VITE_PLATO_SESSION_ID,
    unwrapQueryData(sessionsQuery.data)?.sessions ?? [],
  );

  async function saveAndCheck() {
    if (settingsApi === null || form === null) {
      return;
    }
    setSaveState({ kind: "saving" });
    setDiagnosticExportState({ kind: "idle" });

    try {
      const update = await settingsApi.updateSettingsConfig({
        llm: {
          ...(form.apiKey.trim() ? { apiKey: form.apiKey.trim() } : {}),
          model: form.model.trim(),
          provider: form.provider,
        },
        logging: {
          selectedProfile: form.selectedProfile || null,
        },
      });
      const updateData = unwrapRequiredQueryData(update);
      setForm(formStateFromConfig(updateData.config));
      setLastReadiness(updateData.readiness);
      cacheSettingsResults(queryClient, apiBaseUrl, updateData);

      setSaveState({ kind: "rechecking" });
      const recheck = await settingsApi.recheckSettingsReadiness();
      const recheckData = unwrapRequiredQueryData(recheck);
      setLastReadiness(recheckData);
      queryClient.setQueryData(["settings-readiness", apiBaseUrl], recheck);
      setSaveState({ kind: "success" });
    } catch (error) {
      const apiError = apiErrorFromUnknown(error);
      setForm((current) => (current === null ? null : { ...current, apiKey: "" }));
      setSaveState({
        error: apiError,
        kind: "error",
        message: apiError?.message ?? "Settings save failed.",
      });
    }
  }

  async function recheckReadiness() {
    if (settingsApi === null) {
      return;
    }
    setSaveState({ kind: "rechecking" });
    try {
      const response = await settingsApi.recheckSettingsReadiness();
      const readinessData = unwrapRequiredQueryData(response);
      setLastReadiness(readinessData);
      queryClient.setQueryData(["settings-readiness", apiBaseUrl], response);
      setSaveState({ kind: "success" });
    } catch {
      setSaveState({
        error: null,
        kind: "error",
        message: "Readiness recheck failed.",
      });
    }
  }

  async function exportDiagnostics() {
    if (settingsApi === null || diagnosticSessionId === null) {
      return;
    }
    setDiagnosticExportState({ kind: "exporting" });
    try {
      const response = await settingsApi.exportDiagnosticBundle(diagnosticSessionId);
      const result = unwrapRequiredQueryData(response);
      setDiagnosticExportState({ kind: "success", result });
    } catch {
      setDiagnosticExportState({ kind: "error" });
    }
  }

  return (
    <SettingsShell
      heading={
        routeContext.source === "first-run"
          ? "Complete first-run setup"
          : "Settings"
      }
      routeContext={routeContext}
      status={statusLabel(readiness, saveState)}
    >
      <SettingsSummary config={config} readiness={readiness} />
      <form
        aria-label="Settings setup form"
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          void saveAndCheck();
        }}
      >
        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span>Provider</span>
            <select
              aria-label="Provider"
              disabled={saveState.kind === "saving" || saveState.kind === "rechecking"}
              name="provider"
              onChange={(event) =>
                setForm({
                  ...form,
                  provider: event.target.value as SettingsFormState["provider"],
                })
              }
              value={form.provider}
            >
              {providerOptions(config).map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span>Model</span>
            <input
              aria-label="Model"
              disabled={saveState.kind === "saving" || saveState.kind === "rechecking"}
              name="model"
              onChange={(event) => setForm({ ...form, model: event.target.value })}
              required
              type="text"
              value={form.model}
            />
            <FieldError errors={fieldErrors} path="llm.model" />
          </label>
          <label className={styles.field}>
            <span>API key</span>
            <input
              aria-label="API key"
              autoComplete="off"
              disabled={saveState.kind === "saving" || saveState.kind === "rechecking"}
              name="apiKey"
              onChange={(event) => setForm({ ...form, apiKey: event.target.value })}
              type="password"
              value={form.apiKey}
            />
            <small>
              {config.llm.apiKeyConfigured
                ? `Configured via ${config.llm.apiKeySource}; leave empty to keep it.`
                : `Required: ${apiKeyHint(form.provider, config)}.`}
            </small>
            <FieldError errors={fieldErrors} path="llm.apiKey" />
          </label>
          <label className={styles.field}>
            <span>Logging profile</span>
            <select
              aria-label="Logging profile"
              disabled={saveState.kind === "saving" || saveState.kind === "rechecking"}
              name="loggingProfile"
              onChange={(event) =>
                setForm({ ...form, selectedProfile: event.target.value })
              }
              value={form.selectedProfile}
            >
              <option value="">Default profile</option>
              {config.logging.profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.id}
                </option>
              ))}
            </select>
            <FieldError errors={fieldErrors} path="logging.selectedProfile" />
          </label>
        </div>
        <SaveStatus state={saveState} />
        <ReadinessIssues readiness={readiness} />
        <div className={styles.footerActions}>
          <Button
            disabled={saveState.kind === "saving" || saveState.kind === "rechecking"}
            type="submit"
            variant="primary"
          >
            {saveState.kind === "saving" ? "Saving" : "Save and check"}
          </Button>
          <Button
            disabled={saveState.kind === "saving" || saveState.kind === "rechecking"}
            onClick={() => void recheckReadiness()}
          >
            {saveState.kind === "rechecking" ? "Checking" : "Retry check"}
          </Button>
          <Button
            disabled={!canContinue}
            onClick={() => navigateApp(routeContext.returnTo)}
            variant={canContinue ? "primary" : "secondary"}
          >
            Continue to Main Page
          </Button>
        </div>
      </form>
      <DiagnosticsPanel
        diagnosticsAvailable={config.diagnostics.httpExportRouteAvailable}
        onExport={() => void exportDiagnostics()}
        sessionId={diagnosticSessionId}
        state={diagnosticExportState}
      />
    </SettingsShell>
  );
}

function SettingsShell({
  children,
  heading,
  routeContext,
  status,
}: {
  children: ReactNode;
  heading: string;
  routeContext: SettingsRouteContext;
  status: string;
}) {
  return (
    <main className={styles.page}>
      <section aria-label="Settings" className={styles.panel}>
        <div className={styles.headerRow}>
          <div>
            <span className={styles.eyebrow}>
              {routeContext.source === "first-run" ? "First run" : "Local setup"}
            </span>
            <h1>{heading}</h1>
            <p>Configure the local LLM setup used by Product 1.0 workflows.</p>
          </div>
          <span className={styles.statusBadge}>{status}</span>
        </div>
        {children}
      </section>
    </main>
  );
}

function SettingsSummary({
  config,
  readiness,
}: {
  config: SettingsConfigSummary;
  readiness: SettingsReadinessReport | null;
}) {
  return (
    <dl className={styles.summaryGrid}>
      <div>
        <dt>Provider</dt>
        <dd>{settingsProviderLabel(config.llm.provider)}</dd>
      </div>
      <div>
        <dt>Model</dt>
        <dd>{config.llm.model}</dd>
      </div>
      <div>
        <dt>API key</dt>
        <dd>{config.llm.apiKeyConfigured ? "configured" : "missing"}</dd>
      </div>
      <div>
        <dt>Readiness</dt>
        <dd>{readiness?.status ?? "not checked"}</dd>
      </div>
    </dl>
  );
}

function FieldError({
  errors,
  path,
}: {
  errors: SettingsFieldError[];
  path: string;
}) {
  const message = fieldErrorFor(errors, path);
  if (message === null) {
    return null;
  }
  return (
    <small className={styles.fieldError} role="alert">
      {message}
    </small>
  );
}

function SaveStatus({ state }: { state: SaveState }) {
  if (state.kind === "idle") {
    return null;
  }
  if (state.kind === "error") {
    return (
      <div className={styles.errorBanner} role="alert">
        {state.message}
      </div>
    );
  }
  const message =
    state.kind === "saving"
      ? "Saving settings."
      : state.kind === "rechecking"
        ? "Checking readiness."
        : "Settings saved.";
  return <div className={styles.infoBanner}>{message}</div>;
}

function ReadinessIssues({
  readiness,
}: {
  readiness: SettingsReadinessReport | null;
}) {
  if (readiness === null) {
    return null;
  }
  const issues = readiness.firstRun.ready
    ? readiness.warnings
    : readiness.blockingIssues;
  if (issues.length === 0) {
    return (
      <section className={styles.issueSection} aria-label="Readiness result">
        <h2>Readiness result</h2>
        <p className={styles.helperText}>First-run setup is ready.</p>
      </section>
    );
  }
  return (
    <section className={styles.issueSection} aria-label="Readiness issues">
      <h2>{readiness.firstRun.ready ? "Warnings" : "Blocking issues"}</h2>
      <ul className={styles.issueList}>
        {issues.map((issue) => (
          <li key={issue.code}>
            <strong>{issue.code}</strong>
            <span>{issue.message}</span>
            {issue.recoveryActions.filter((action) => action !== "none").length > 0 && (
              <span>
                {issue.recoveryActions
                  .filter((action) => action !== "none")
                  .map(formatRecoveryAction)
                  .join(" ")}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function DiagnosticsPanel({
  diagnosticsAvailable,
  onExport,
  sessionId,
  state,
}: {
  diagnosticsAvailable: boolean;
  onExport: () => void;
  sessionId: SessionId | null;
  state: DiagnosticExportState;
}) {
  const disabled = !diagnosticsAvailable || sessionId === null || state.kind === "exporting";
  return (
    <section className={styles.diagnosticsPanel} aria-label="Setup diagnostics">
      <div>
        <h2>Diagnostics</h2>
        <p>
          Export a redacted local bundle when setup still fails and a session is
          available.
        </p>
      </div>
      <Button disabled={disabled} onClick={onExport}>
        {state.kind === "exporting" ? "Exporting" : "Export diagnostics"}
      </Button>
      {sessionId === null && (
        <p className={styles.helperText}>
          No session is available for diagnostics export yet.
        </p>
      )}
      <DiagnosticExportStatus state={state} />
    </section>
  );
}

function DiagnosticExportStatus({ state }: { state: DiagnosticExportState }) {
  if (state.kind === "error") {
    return (
      <div className={styles.errorBanner} role="alert">
        Diagnostic export failed.
      </div>
    );
  }
  if (state.kind !== "success") {
    return null;
  }
  return (
    <dl className={styles.exportResult}>
      <div>
        <dt>Bundle</dt>
        <dd>{state.result.bundleId}</dd>
      </div>
      <div>
        <dt>Zip path</dt>
        <dd>{state.result.zipPathLabel ?? "Not created"}</dd>
      </div>
    </dl>
  );
}

function createSettingsApi(runtimeEnv: PlatoRuntimeEnv): SettingsRouteApi | null {
  if (runtimeEnv.VITE_PLATO_API_MODE !== "http") {
    return null;
  }

  return createHttpPlatoApi({
    baseUrl: runtimeEnv.VITE_PLATO_API_BASE_URL ?? globalThis.location.origin,
  });
}

function unwrapQueryData<T>(response: QueryResponse<T> | undefined): T | null {
  if (response?.ok !== true || response.data === null) {
    return null;
  }
  return response.data;
}

function unwrapRequiredQueryData<T>(response: QueryResponse<T>): T {
  if (!response.ok || response.data === null) {
    throw new Error(response.error?.message ?? "Settings request failed.");
  }
  return response.data;
}

function apiErrorFromUnknown(error: unknown): ApiError | null {
  if (error instanceof ApiClientError) {
    const body = error.responseBody;
    if (isQueryResponseBody(body) && body.error !== null) {
      return body.error;
    }
  }
  return null;
}

function isQueryResponseBody(value: unknown): value is QueryResponse<unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    "ok" in value &&
    "error" in value
  );
}

function resolveDiagnosticSessionId(
  preferredSessionId: SessionId | undefined,
  sessions: Array<{ id: SessionId }>,
): SessionId | null {
  return preferredSessionId ?? sessions[0]?.id ?? null;
}

function cacheSettingsResults(
  queryClient: QueryClient,
  apiBaseUrl: string,
  update: SettingsConfigUpdateResult,
): void {
  queryClient.setQueryData(["settings-config", apiBaseUrl], {
    data: update.config,
    error: null,
    ok: true,
  });
  queryClient.setQueryData(["settings-readiness", apiBaseUrl], {
    data: update.readiness,
    error: null,
    ok: true,
  });
}

function statusLabel(
  readiness: SettingsReadinessReport | null,
  saveState: SaveState,
): string {
  if (saveState.kind === "saving") {
    return "Saving";
  }
  if (saveState.kind === "rechecking") {
    return "Checking";
  }
  if (readiness !== null) {
    return readiness.status;
  }
  return "Editable";
}
