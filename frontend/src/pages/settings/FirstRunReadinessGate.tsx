import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useMemo } from "react";

import { navigateApp } from "../../app/navigation";
import type { PlatoRuntimeEnv } from "../../app/platoRuntime";
import { Button } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import type {
  PlatoApi,
  SettingsReadinessReport,
} from "../../shared/api/platoApi";
import { createHttpPlatoApi } from "../../shared/api/platoApi";
import { formatRecoveryAction } from "./settingsCopy";
import { buildSettingsRoute } from "./settingsRouteModel";
import styles from "./FirstRunReadinessGate.module.css";

export type SettingsReadinessApi = Pick<PlatoApi, "getSettingsReadiness">;

export type FirstRunReadinessGateProps = {
  api?: SettingsReadinessApi;
  children: ReactNode;
  runtimeEnv?: PlatoRuntimeEnv;
};

export function FirstRunReadinessGate({
  api,
  children,
  runtimeEnv = import.meta.env,
}: FirstRunReadinessGateProps) {
  const uiText = useUiText();
  const readinessApi = useMemo(
    () => api ?? createSettingsReadinessApi(runtimeEnv),
    [api, runtimeEnv],
  );
  const readinessQuery = useQuery({
    enabled: readinessApi !== null,
    queryFn: () => readinessApi!.getSettingsReadiness(),
    queryKey: [
      "settings-readiness",
      runtimeEnv.VITE_PLATO_API_BASE_URL ?? globalThis.location.origin,
    ],
    retry: false,
  });

  if (readinessApi === null) {
    return <>{children}</>;
  }

  if (readinessQuery.status === "pending") {
    return (
      <ReadinessShell
        description={uiText.settings.messages.checkingSidecarReadiness}
        heading={uiText.settings.labels.checkingSetup}
        tone="neutral"
      />
    );
  }

  const response = readinessQuery.data;
  if (readinessQuery.status === "error" || response?.ok !== true || response.data === null) {
    return (
      <ReadinessShell
        action={
          <Button onClick={() => void readinessQuery.refetch()} variant="secondary">
            {uiText.settings.actions.retryCheck}
          </Button>
        }
        description={uiText.settings.messages.noReadinessReport}
        heading={uiText.settings.labels.setupCheckUnavailable}
        tone="warning"
      />
    );
  }

  if (response.data.firstRun.ready) {
    if (response.data.status === "degraded" || response.data.warnings.length > 0) {
      return (
        <>
          <ReadinessDegradedBanner readiness={response.data} />
          {children}
        </>
      );
    }
    return <>{children}</>;
  }

  return (
    <FirstRunReadinessPanel
      onRetry={() => void readinessQuery.refetch()}
      readiness={response.data}
    />
  );
}

function FirstRunReadinessPanel({
  onRetry,
  readiness,
}: {
  onRetry: () => void;
  readiness: SettingsReadinessReport;
}) {
  const uiText = useUiText();
  const missingEnvVars = new Set([
    ...readiness.llm.missingEnvVars,
    ...readiness.blockingIssues.flatMap((issue) => issue.envVars),
  ]);
  const recommendedActions = readiness.firstRun.recommendedActions.filter(
    (action) => action !== "none",
  );

  return (
    <main className={styles.page}>
      <section aria-label={uiText.settings.labels.firstRun} className={styles.panel}>
        <div className={styles.headerRow}>
          <div>
            <span className={styles.eyebrow}>{uiText.settings.labels.firstRun}</span>
            <h1>{uiText.settings.labels.setupRequired}</h1>
            <p>
              {uiText.settings.messages.setupRequiredBody}
            </p>
          </div>
          <span className={styles.statusBadge}>{readiness.status}</span>
        </div>

        <dl className={styles.summaryGrid}>
          <div>
            <dt>{uiText.settings.fields.provider}</dt>
            <dd>{readiness.llm.provider}</dd>
          </div>
          <div>
            <dt>{uiText.settings.fields.model}</dt>
            <dd>{readiness.llm.model}</dd>
          </div>
          <div>
            <dt>{uiText.settings.fields.logging}</dt>
            <dd>
              {readiness.logging.enabled
                ? readiness.logging.level
                : uiText.common.status.disabled}
            </dd>
          </div>
          <div>
            <dt>{uiText.settings.fields.diagnostics}</dt>
            <dd>
              {readiness.diagnostics.bundleExportAvailable
                ? uiText.settings.labels.diagnosticsAvailable
                : uiText.settings.labels.diagnosticsUnavailable}
            </dd>
          </div>
        </dl>

        <section
          className={styles.section}
          aria-label={uiText.settings.labels.blockingIssues}
        >
          <h2>{uiText.settings.labels.blockingIssues}</h2>
          <ul className={styles.issueList}>
            {readiness.blockingIssues.map((issue) => (
              <li key={issue.code}>
                <strong>{issue.code}</strong>
                <span>{issue.message}</span>
              </li>
            ))}
          </ul>
        </section>

        {missingEnvVars.size > 0 && (
          <section
            className={styles.section}
            aria-label={uiText.settings.labels.missingEnvironmentVariables}
          >
            <h2>{uiText.settings.labels.missingEnvironmentVariables}</h2>
            <div className={styles.codeList}>
              {[...missingEnvVars].map((name) => (
                <code key={name}>{name}</code>
              ))}
            </div>
          </section>
        )}

        {recommendedActions.length > 0 && (
          <section
            className={styles.section}
            aria-label={uiText.settings.labels.recommendedActions}
          >
            <h2>{uiText.settings.labels.recommendedActions}</h2>
            <ul className={styles.actionList}>
              {recommendedActions.map((action) => (
                <li key={action}>{formatRecoveryAction(action, uiText)}</li>
              ))}
            </ul>
          </section>
        )}

        <div className={styles.footerRow}>
          <Button
            onClick={() =>
              navigateApp(
                buildSettingsRoute({
                  returnTo: "/",
                  source: "first-run",
                }),
              )
            }
            variant="primary"
          >
            {uiText.settings.actions.configureSettings}
          </Button>
          <Button onClick={onRetry} variant="secondary">
            {uiText.settings.actions.retryCheck}
          </Button>
        </div>
      </section>
    </main>
  );
}

function ReadinessDegradedBanner({
  readiness,
}: {
  readiness: SettingsReadinessReport;
}) {
  const uiText = useUiText();
  const warning = readiness.warnings[0];
  return (
    <div className={styles.degradedBanner} role="status">
      <strong>{uiText.settings.labels.setupWarning}</strong>
      <span>{warning?.message ?? uiText.settings.messages.localSetupReadyWithWarnings}</span>
      <Button
        onClick={() =>
          navigateApp(
            buildSettingsRoute({
              returnTo: globalThis.location.pathname || "/",
              source: "settings",
            }),
          )
        }
        size="sm"
      >
        {uiText.settings.actions.openSettings}
      </Button>
    </div>
  );
}

function ReadinessShell({
  action,
  description,
  heading,
  tone,
}: {
  action?: ReactNode;
  description: string;
  heading: string;
  tone: "neutral" | "warning";
}) {
  const uiText = useUiText();
  return (
    <main className={styles.page}>
      <section
        aria-label={uiText.settings.labels.firstRun}
        className={styles.panel}
        data-tone={tone}
      >
        <div className={styles.headerRow}>
          <div>
            <span className={styles.eyebrow}>{uiText.settings.labels.firstRun}</span>
            <h1>{heading}</h1>
            <p>{description}</p>
          </div>
        </div>
        {action !== undefined && <div className={styles.footerRow}>{action}</div>}
      </section>
    </main>
  );
}

function createSettingsReadinessApi(
  runtimeEnv: PlatoRuntimeEnv,
): SettingsReadinessApi | null {
  if (runtimeEnv.VITE_PLATO_API_MODE !== "http") {
    return null;
  }

  return createHttpPlatoApi({
    baseUrl: runtimeEnv.VITE_PLATO_API_BASE_URL ?? globalThis.location.origin,
  });
}
