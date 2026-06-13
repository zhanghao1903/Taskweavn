import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
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
  SettingsWebSearchStatus,
} from "../../shared/api/platoApi";
import { createHttpPlatoApi } from "../../shared/api/platoApi";
import type { ApiError, QueryResponse, SessionId } from "../../shared/api/types";
import { Button } from "../../shared/components";
import {
  SUPPORTED_UI_LOCALES,
  useUiLocale,
  useUiText,
  writeUiLocalePreference,
  type UiLocale,
  type UiTextCatalog,
} from "../../shared/ui-text";
import { formatRecoveryAction, settingsProviderLabel } from "./settingsCopy";
import { SettingsDataManagementTab } from "./SettingsDataManagementTab";
import { SettingsUsageInformationTab } from "./SettingsUsageInformationTab";
import type { SettingsRouteContext, SettingsTab } from "./settingsRouteModel";
import { buildSettingsRoute, parseSettingsRouteLocation } from "./settingsRouteModel";
import {
  apiKeyHint,
  fieldErrorFor,
  fieldErrorsFromApiError,
  formStateFromConfig,
  loggingProfileOptions,
  normalizeWebSearchMaxResults,
  providerOptions,
  webSearchApiKeyHint,
  webSearchProviderOptions,
  type SettingsFieldError,
  type SettingsFormState,
} from "./settingsViewModel";
import { WorkspaceGitSettingsPanel } from "./WorkspaceGitSettingsPanel";
import styles from "./SettingsRoute.module.css";

export type SettingsRouteApi = Pick<
  PlatoApi,
  | "exportDiagnosticBundle"
  | "getSettingsConfig"
  | "getTokenUsageSummary"
  | "listSessions"
  | "recheckSettingsReadiness"
  | "updateSettingsConfig"
>;

export type SettingsRouteProps = {
  api?: SettingsRouteApi;
  location?: Pick<Location, "pathname" | "search">;
  presentation?: "modal" | "page";
  runtimeEnv?: PlatoRuntimeEnv;
  workspaceBridge?: PlatoElectronWorkspaceBridge | null;
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
  presentation = "page",
  runtimeEnv = import.meta.env,
  workspaceBridge,
}: SettingsRouteProps = {}) {
  const uiText = useUiText();
  const activeUiLocale = useUiLocale();
  const routeLocation = location ?? globalThis.location;
  const routeContext = useMemo(
    () =>
      parseSettingsRouteLocation(routeLocation.pathname, routeLocation.search) ?? {
        returnTo: "/",
        source: "settings" as const,
        tab: "configuration" as const,
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
  const [selectedUiLocale, setSelectedUiLocale] =
    useState<UiLocale>(activeUiLocale);
  const [saveState, setSaveState] = useState<SaveState>({ kind: "idle" });
  const [lastReadiness, setLastReadiness] =
    useState<SettingsReadinessReport | null>(null);
  const [diagnosticExportState, setDiagnosticExportState] =
    useState<DiagnosticExportState>({ kind: "idle" });

  useEffect(() => {
    if (presentation !== "modal") {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        navigateApp(routeContext.returnTo);
      }
    };
    globalThis.addEventListener("keydown", handleKeyDown);
    return () => globalThis.removeEventListener("keydown", handleKeyDown);
  }, [presentation, routeContext.returnTo]);

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

  useEffect(() => {
    setSelectedUiLocale(activeUiLocale);
  }, [activeUiLocale]);

  if (routeContext.tab === "data") {
    return (
      <SettingsShell
        activeTab={routeContext.tab}
        heading={uiText.settings.labels.settings}
        presentation={presentation}
        routeContext={routeContext}
        status={uiText.settings.tabs.dataManagement}
      >
        <SettingsDataManagementTab workspaceBridge={workspaceBridge} />
      </SettingsShell>
    );
  }

  if (settingsApi === null) {
    return (
      <SettingsShell
        activeTab={routeContext.tab}
        heading={uiText.settings.labels.settingsUnavailable}
        presentation={presentation}
        routeContext={routeContext}
        status={uiText.settings.labels.sidecarRequired}
      >
        <p className={styles.helperText}>
          {uiText.settings.messages.settingsUnavailableHelp}
        </p>
      </SettingsShell>
    );
  }

  if (configQuery.status === "pending" || form === null) {
    return (
      <SettingsShell
        activeTab={routeContext.tab}
        heading={uiText.settings.messages.loadingSettings}
        presentation={presentation}
        routeContext={routeContext}
        status={uiText.settings.labels.checkingSetup}
      >
        <p className={styles.helperText}>
          {uiText.settings.messages.loadingSettingsHelp}
        </p>
      </SettingsShell>
    );
  }

  if (configQuery.status === "error" || config === null) {
    return (
      <SettingsShell
        activeTab={routeContext.tab}
        heading={uiText.settings.labels.settingsUnavailable}
        presentation={presentation}
        routeContext={routeContext}
        status={uiText.common.actions.retry}
      >
        <p className={styles.helperText}>
          {uiText.settings.messages.settingsContractUnavailable}
        </p>
        <div className={styles.footerActions}>
          <Button onClick={() => void configQuery.refetch()} variant="primary">
            {uiText.settings.actions.retryLoad}
          </Button>
          <Button onClick={() => navigateApp(routeContext.returnTo)}>
            {uiText.settings.actions.return}
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
        webSearch: {
          ...(form.webSearchApiKey.trim()
            ? { apiKey: form.webSearchApiKey.trim() }
            : {}),
          enabled: form.webSearchEnabled,
          maxResults: form.webSearchMaxResults,
          mode: "basic",
          provider: form.webSearchProvider,
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
      setForm((current) =>
        current === null
          ? null
          : { ...current, apiKey: "", webSearchApiKey: "" },
      );
      setSaveState({
        error: apiError,
        kind: "error",
        message: apiError?.message ?? uiText.settings.messages.saveFailed,
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
        message: uiText.settings.messages.readinessRecheckFailed,
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
      activeTab={routeContext.tab}
      heading={
        routeContext.source === "first-run"
          ? uiText.settings.labels.completeFirstRunSetup
          : uiText.settings.labels.settings
      }
      presentation={presentation}
      routeContext={routeContext}
      status={statusLabel(readiness, saveState, uiText)}
    >
      {routeContext.tab === "usage" ? (
        <SettingsUsageInformationTab
          api={settingsApi}
          workspaceBridge={workspaceBridge}
        />
      ) : (
        <>
          <SettingsSummary config={config} readiness={readiness} />
          <form
            aria-label={uiText.settings.labels.settingsSetupForm}
            className={styles.form}
            onSubmit={(event) => {
              event.preventDefault();
              void saveAndCheck();
            }}
          >
            <div className={styles.formGrid}>
              <label className={styles.field}>
                <span>{uiText.settings.fields.provider}</span>
                <select
                  aria-label={uiText.settings.fields.provider}
                  disabled={
                    saveState.kind === "saving" ||
                    saveState.kind === "rechecking"
                  }
                  name="provider"
                  onChange={(event) =>
                    setForm({
                      ...form,
                      provider: event.target
                        .value as SettingsFormState["provider"],
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
                <span>{uiText.settings.fields.model}</span>
                <input
                  aria-label={uiText.settings.fields.model}
                  disabled={
                    saveState.kind === "saving" ||
                    saveState.kind === "rechecking"
                  }
                  name="model"
                  onChange={(event) =>
                    setForm({ ...form, model: event.target.value })
                  }
                  required
                  type="text"
                  value={form.model}
                />
                <FieldError errors={fieldErrors} path="llm.model" />
              </label>
              <label className={styles.field}>
                <span>{uiText.settings.fields.apiKey}</span>
                <input
                  aria-label={uiText.settings.fields.apiKey}
                  autoComplete="off"
                  disabled={
                    saveState.kind === "saving" ||
                    saveState.kind === "rechecking"
                  }
                  name="apiKey"
                  onChange={(event) =>
                    setForm({ ...form, apiKey: event.target.value })
                  }
                  type="password"
                  value={form.apiKey}
                />
                <small>
                  {config.llm.apiKeyConfigured
                    ? uiText.settings.messages.apiKeyConfigured({
                        source: config.llm.apiKeySource,
                      })
                    : uiText.settings.messages.apiKeyRequired({
                        hint: apiKeyHint(form.provider, config),
                      })}
                </small>
                <FieldError errors={fieldErrors} path="llm.apiKey" />
              </label>
              <label className={styles.field}>
                <span>{uiText.settings.fields.loggingProfile}</span>
                <select
                  aria-label={uiText.settings.fields.loggingProfile}
                  disabled={
                    saveState.kind === "saving" ||
                    saveState.kind === "rechecking"
                  }
                  name="loggingProfile"
                  onChange={(event) =>
                    setForm({ ...form, selectedProfile: event.target.value })
                  }
                  value={form.selectedProfile}
                >
                  <option value="">{uiText.settings.fields.defaultProfile}</option>
                  {loggingProfileOptions(config).map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.label}
                    </option>
                  ))}
                </select>
                <FieldError errors={fieldErrors} path="logging.selectedProfile" />
              </label>
              <label className={`${styles.field} ${styles.wideField}`}>
                <span>{uiText.settings.fields.interfaceLanguage}</span>
                <select
                  aria-label={uiText.settings.fields.interfaceLanguage}
                  name="interfaceLanguage"
                  onChange={(event) => {
                    const nextLocale = event.target.value as UiLocale;
                    setSelectedUiLocale(nextLocale);
                    writeUiLocalePreference(nextLocale);
                  }}
                  value={selectedUiLocale}
                >
                  {SUPPORTED_UI_LOCALES.map((locale) => (
                    <option key={locale} value={locale}>
                      {uiText.settings.localeOptions[locale]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <section
              aria-label={uiText.settings.fields.webSearch}
              className={styles.settingsSubsection}
            >
              <div>
                <h2>{uiText.settings.fields.webSearch}</h2>
                <dl className={styles.inlineStatusList}>
                  <div>
                    <dt>{uiText.settings.fields.webSearchStatus}</dt>
                    <dd>{webSearchStatusLabel(config.webSearch.status, uiText)}</dd>
                  </div>
                </dl>
                <p className={styles.helperText}>
                  {uiText.settings.messages.webSearchDescription}
                </p>
              </div>
              <label className={styles.checkboxField}>
                <input
                  checked={form.webSearchEnabled}
                  disabled={
                    saveState.kind === "saving" ||
                    saveState.kind === "rechecking"
                  }
                  onChange={(event) =>
                    setForm({ ...form, webSearchEnabled: event.target.checked })
                  }
                  type="checkbox"
                />
                <span>{uiText.settings.fields.webSearch}</span>
              </label>
              <div className={styles.formGrid}>
                <label className={styles.field}>
                  <span>{uiText.settings.fields.webSearchProvider}</span>
                  <select
                    aria-label={uiText.settings.fields.webSearchProvider}
                    disabled={
                      saveState.kind === "saving" ||
                      saveState.kind === "rechecking"
                    }
                    onChange={(event) =>
                      setForm({
                        ...form,
                        webSearchProvider: event.target
                          .value as SettingsFormState["webSearchProvider"],
                      })
                    }
                    value={form.webSearchProvider}
                  >
                    {webSearchProviderOptions(config).map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <FieldError errors={fieldErrors} path="webSearch.provider" />
                </label>
                <label className={styles.field}>
                  <span>{uiText.settings.fields.webSearchMaxResults}</span>
                  <select
                    aria-label={uiText.settings.fields.webSearchMaxResults}
                    disabled={
                      saveState.kind === "saving" ||
                      saveState.kind === "rechecking"
                    }
                    onChange={(event) =>
                      setForm({
                        ...form,
                        webSearchMaxResults: normalizeWebSearchMaxResults(
                          Number(event.target.value),
                        ),
                      })
                    }
                    value={form.webSearchMaxResults}
                  >
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((count) => (
                      <option key={count} value={count}>
                        {count}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={styles.field}>
                  <span>{uiText.settings.fields.webSearchMode}</span>
                  <input
                    aria-label={uiText.settings.fields.webSearchMode}
                    disabled
                    readOnly
                    type="text"
                    value="basic"
                  />
                </label>
                <label className={styles.field}>
                  <span>{uiText.settings.fields.webSearchApiKey}</span>
                  <input
                    aria-label={uiText.settings.fields.webSearchApiKey}
                    autoComplete="off"
                    disabled={
                      saveState.kind === "saving" ||
                      saveState.kind === "rechecking"
                    }
                    onChange={(event) =>
                      setForm({ ...form, webSearchApiKey: event.target.value })
                    }
                    type="password"
                    value={form.webSearchApiKey}
                  />
                  <small>
                    {config.webSearch.apiKeyConfigured
                      ? uiText.settings.messages.webSearchApiKeyConfigured({
                          source: config.webSearch.apiKeySource,
                        })
                      : uiText.settings.messages.webSearchApiKeyRequired({
                          hint: webSearchApiKeyHint(form.webSearchProvider, config),
                        })}
                  </small>
                  <FieldError errors={fieldErrors} path="webSearch.apiKey" />
                </label>
              </div>
            </section>
            <WorkspaceGitSettingsPanel bridge={workspaceBridge} />
            <SaveStatus state={saveState} />
            <ReadinessIssues readiness={readiness} />
            <div className={styles.footerActions}>
              <Button
                disabled={
                  saveState.kind === "saving" ||
                  saveState.kind === "rechecking"
                }
                type="submit"
                variant="primary"
              >
                {saveState.kind === "saving"
                  ? uiText.settings.messages.saving
                  : uiText.settings.actions.saveAndCheck}
              </Button>
              <Button
                disabled={
                  saveState.kind === "saving" ||
                  saveState.kind === "rechecking"
                }
                onClick={() => void recheckReadiness()}
              >
                {saveState.kind === "rechecking"
                  ? uiText.settings.messages.checkingReadiness
                  : uiText.settings.actions.retryCheck}
              </Button>
              <Button
                disabled={!canContinue}
                onClick={() => navigateApp(routeContext.returnTo)}
                variant={canContinue ? "primary" : "secondary"}
              >
                {uiText.settings.actions.continueToMainPage}
              </Button>
            </div>
          </form>
          <DiagnosticsPanel
            diagnosticsAvailable={config.diagnostics.httpExportRouteAvailable}
            onExport={() => void exportDiagnostics()}
            sessionId={diagnosticSessionId}
            state={diagnosticExportState}
          />
        </>
      )}
    </SettingsShell>
  );
}

function SettingsShell({
  activeTab,
  children,
  heading,
  presentation,
  routeContext,
  status,
}: {
  activeTab: SettingsTab;
  children: ReactNode;
  heading: string;
  presentation: "modal" | "page";
  routeContext: SettingsRouteContext;
  status: string;
}) {
  const uiText = useUiText();
  const isModal = presentation === "modal";
  const headingId = "settings-route-heading";
  const content = (
    <section
      aria-label={isModal ? undefined : uiText.settings.labels.settings}
      aria-labelledby={isModal ? headingId : undefined}
      aria-modal={isModal ? true : undefined}
      className={`${styles.panel} ${isModal ? styles.modalPanel : ""}`}
      role={isModal ? "dialog" : undefined}
    >
      <div className={styles.headerRow}>
        <div>
          <span className={styles.eyebrow}>
            {routeContext.source === "first-run"
              ? uiText.settings.labels.firstRun
              : uiText.settings.labels.localSetup}
          </span>
          <h1 id={headingId}>{heading}</h1>
          <p>{uiText.settings.messages.settingsDescription}</p>
        </div>
        <div className={styles.headerActions}>
          <span className={styles.statusBadge}>{status}</span>
          {isModal ? (
            <Button
              aria-label={uiText.settings.actions.closeSettings}
              onClick={() => navigateApp(routeContext.returnTo)}
              size="icon"
              title={uiText.settings.actions.closeSettings}
              variant="ghost"
            >
              <X aria-hidden="true" size={18} />
            </Button>
          ) : null}
        </div>
      </div>
      <SettingsTabs activeTab={activeTab} routeContext={routeContext} />
      {children}
    </section>
  );

  if (isModal) {
    return <div className={styles.modalViewport}>{content}</div>;
  }

  return (
    <main className={styles.page}>
      {content}
    </main>
  );
}

function SettingsTabs({
  activeTab,
  routeContext,
}: {
  activeTab: SettingsTab;
  routeContext: SettingsRouteContext;
}) {
  const uiText = useUiText();
  if (routeContext.source === "first-run") {
    return null;
  }
  const tabs: Array<{ id: SettingsTab; label: string }> = [
    { id: "configuration", label: uiText.settings.tabs.configuration },
    { id: "data", label: uiText.settings.tabs.dataManagement },
    { id: "usage", label: uiText.settings.tabs.usageInformation },
  ];

  return (
    <nav className={styles.tabRow} aria-label={uiText.settings.labels.settings}>
      {tabs.map((tab) => {
        const href = buildSettingsRoute({ ...routeContext, tab: tab.id });
        return (
          <a
            aria-current={activeTab === tab.id ? "page" : undefined}
            className={
              activeTab === tab.id
                ? `${styles.tabLink} ${styles.tabLinkActive}`
                : styles.tabLink
            }
            href={href}
            key={tab.id}
            onClick={(event) => {
              event.preventDefault();
              if (activeTab !== tab.id) {
                navigateApp(href);
              }
            }}
          >
            {tab.label}
          </a>
        );
      })}
    </nav>
  );
}

function SettingsSummary({
  config,
  readiness,
}: {
  config: SettingsConfigSummary;
  readiness: SettingsReadinessReport | null;
}) {
  const uiText = useUiText();

  return (
    <dl className={styles.summaryGrid}>
      <div>
        <dt>{uiText.settings.fields.provider}</dt>
        <dd>{settingsProviderLabel(config.llm.provider)}</dd>
      </div>
      <div>
        <dt>{uiText.settings.fields.model}</dt>
        <dd>{config.llm.model}</dd>
      </div>
      <div>
        <dt>{uiText.settings.fields.apiKey}</dt>
        <dd>
          {config.llm.apiKeyConfigured
            ? uiText.settings.labels.configured
            : uiText.settings.labels.missing}
        </dd>
      </div>
      <div>
        <dt>{uiText.settings.fields.readiness}</dt>
        <dd>{readiness?.status ?? uiText.settings.labels.notChecked}</dd>
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
  const uiText = useUiText();

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
      ? uiText.settings.messages.saving
      : state.kind === "rechecking"
        ? uiText.settings.messages.checkingReadiness
        : uiText.settings.messages.saved;
  return <div className={styles.infoBanner}>{message}</div>;
}

function ReadinessIssues({
  readiness,
}: {
  readiness: SettingsReadinessReport | null;
}) {
  const uiText = useUiText();

  if (readiness === null) {
    return null;
  }
  const issues = readiness.firstRun.ready
    ? readiness.warnings
    : readiness.blockingIssues;
  if (issues.length === 0) {
    return (
      <section
        className={styles.issueSection}
        aria-label={uiText.settings.labels.readinessResult}
      >
        <h2>{uiText.settings.labels.readinessResult}</h2>
        <p className={styles.helperText}>
          {uiText.settings.labels.firstRunReady}
        </p>
      </section>
    );
  }
  return (
    <section
      className={styles.issueSection}
      aria-label={uiText.settings.labels.readinessIssues}
    >
      <h2>
        {readiness.firstRun.ready
          ? uiText.settings.labels.warnings
          : uiText.settings.labels.blockingIssues}
      </h2>
      <ul className={styles.issueList}>
        {issues.map((issue) => (
          <li key={issue.code}>
            <strong>{issue.code}</strong>
            <span>{issue.message}</span>
            {issue.recoveryActions.filter((action) => action !== "none").length > 0 && (
              <span>
                {issue.recoveryActions
                  .filter((action) => action !== "none")
                  .map((action) => formatRecoveryAction(action, uiText))
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
  const uiText = useUiText();
  const disabled = !diagnosticsAvailable || sessionId === null || state.kind === "exporting";
  return (
    <section
      className={styles.diagnosticsPanel}
      aria-label={uiText.settings.fields.diagnostics}
    >
      <div>
        <h2>{uiText.settings.fields.diagnostics}</h2>
        <p>
          {uiText.settings.messages.diagnosticExportHelp}
        </p>
      </div>
      <Button disabled={disabled} onClick={onExport}>
        {state.kind === "exporting"
          ? uiText.settings.actions.exportingDiagnostics
          : uiText.settings.actions.exportDiagnostics}
      </Button>
      {sessionId === null && (
        <p className={styles.helperText}>
          {uiText.settings.messages.noDiagnosticSession}
        </p>
      )}
      <DiagnosticExportStatus state={state} />
    </section>
  );
}

function DiagnosticExportStatus({ state }: { state: DiagnosticExportState }) {
  const uiText = useUiText();

  if (state.kind === "error") {
    return (
      <div className={styles.errorBanner} role="alert">
        {uiText.settings.messages.diagnosticExportFailed}
      </div>
    );
  }
  if (state.kind !== "success") {
    return null;
  }
  return (
    <dl className={styles.exportResult}>
      <div>
        <dt>{uiText.settings.fields.bundle}</dt>
        <dd>{state.result.bundleId}</dd>
      </div>
      <div>
        <dt>{uiText.settings.labels.zipPath}</dt>
        <dd>{state.result.zipPathLabel ?? uiText.settings.labels.notCreated}</dd>
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
  uiText: UiTextCatalog,
): string {
  if (saveState.kind === "saving") {
    return uiText.settings.messages.saving;
  }
  if (saveState.kind === "rechecking") {
    return uiText.settings.messages.checkingReadiness;
  }
  if (readiness !== null) {
    return readiness.status;
  }
  return uiText.settings.labels.editable;
}

function webSearchStatusLabel(
  status: SettingsWebSearchStatus,
  uiText: UiTextCatalog,
): string {
  if (status === "ready") {
    return uiText.settings.labels.webSearchReady;
  }
  if (status === "missing_key") {
    return uiText.settings.labels.missing;
  }
  return uiText.common.status.disabled;
}
