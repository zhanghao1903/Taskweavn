import { useQuery } from "@tanstack/react-query";

import type {
  PlatoApi,
  RuntimeConfigEffective,
  RuntimeConfigEffectiveValue,
} from "../../shared/api/platoApi";
import { Button } from "../../shared/components";
import styles from "./SettingsRoute.module.css";

export type SettingsRuntimeBehaviorApi = Pick<
  PlatoApi,
  "getRuntimeConfigEffective"
>;

export type SettingsRuntimeBehaviorTabProps = {
  api: SettingsRuntimeBehaviorApi;
  apiBaseUrl: string;
};

type RuntimeConfigDisplayGroup = {
  title: string;
  keys: string[];
};

const runtimeConfigGroups: RuntimeConfigDisplayGroup[] = [
  {
    keys: [
      "agent_loop.default_max_steps",
      "context_manager.checkpoint_interval_steps",
      "context_manager.max_prior_messages",
      "context_manager.budget.max_events",
      "context_manager.budget.max_rendered_chars",
    ],
    title: "Agent and context limits",
  },
  {
    keys: [
      "execution_dispatcher.enabled",
      "execution_dispatcher.max_ticks_per_trigger",
      "task_api.enabled",
      "task_api.require_valid_session",
    ],
    title: "Execution and Task API",
  },
  {
    keys: [
      "computer_use.enabled",
      "computer_use.backend",
      "computer_use.allowed_apps",
      "safety.high_risk_confirmation",
    ],
    title: "Computer use and safety",
  },
  {
    keys: [
      "llm.default_provider",
      "llm.default_model",
      "llm.request_timeout_seconds",
      "read_only_inquiry.llm_enabled",
    ],
    title: "LLM and inquiry",
  },
  {
    keys: ["logging.level", "logging.profile", "web.search_enabled"],
    title: "Logging and web tools",
  },
];

export function SettingsRuntimeBehaviorTab({
  api,
  apiBaseUrl,
}: SettingsRuntimeBehaviorTabProps) {
  const runtimeConfigQuery = useQuery({
    queryFn: () => api.getRuntimeConfigEffective(),
    queryKey: ["runtime-config-effective", apiBaseUrl],
    retry: false,
  });

  if (runtimeConfigQuery.status === "pending") {
    return (
      <section className={styles.runtimeBehavior}>
        <p className={styles.helperText}>Loading runtime behavior.</p>
      </section>
    );
  }

  if (
    runtimeConfigQuery.status === "error" ||
    !runtimeConfigQuery.data?.ok ||
    runtimeConfigQuery.data.data === null
  ) {
    return (
      <section className={styles.runtimeBehavior}>
        <div className={styles.errorBanner}>
          Runtime behavior is unavailable from the local sidecar.
        </div>
        <div className={styles.footerActions}>
          <Button onClick={() => void runtimeConfigQuery.refetch()} variant="primary">
            Retry
          </Button>
        </div>
      </section>
    );
  }

  return <RuntimeConfigContent config={runtimeConfigQuery.data.data} />;
}

function RuntimeConfigContent({ config }: { config: RuntimeConfigEffective }) {
  return (
    <section className={styles.runtimeBehavior}>
      <div className={styles.infoBanner}>
        Runtime behavior is read-only here. Persisted changes may be visible in
        diagnostics, but non-live values do not affect already-running agents.
      </div>

      <dl className={styles.summaryGrid}>
        <div>
          <dt>Scope</dt>
          <dd>{formatScope(config.scope.level)}</dd>
        </div>
        <div>
          <dt>Config hash</dt>
          <dd>{config.configHash}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatTimestamp(config.createdAt)}</dd>
        </div>
        <div>
          <dt>Source layers</dt>
          <dd>{config.sourceLayers.length}</dd>
        </div>
      </dl>

      <div className={styles.runtimeConfigGroups}>
        {runtimeConfigGroups.map((group) => (
          <section className={styles.settingsSubsection} key={group.title}>
            <h2>{group.title}</h2>
            <div className={styles.runtimeConfigTable} role="table">
              <div className={styles.runtimeConfigHeader} role="row">
                <span role="columnheader">Key</span>
                <span role="columnheader">Value</span>
                <span role="columnheader">Source</span>
                <span role="columnheader">Applies</span>
              </div>
              {group.keys.map((key) => (
                <RuntimeConfigRow key={key} value={config.values[key]} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}

function RuntimeConfigRow({
  value,
}: {
  value: RuntimeConfigEffectiveValue | undefined;
}) {
  if (value === undefined) {
    return null;
  }
  return (
    <div className={styles.runtimeConfigRow} role="row">
      <span role="cell">{value.key}</span>
      <strong role="cell">{formatConfigValue(value)}</strong>
      <span role="cell">{formatSource(value.source.kind)}</span>
      <span role="cell">{formatEffectiveStatus(value.effectiveStatus)}</span>
    </div>
  );
}

function formatConfigValue(value: RuntimeConfigEffectiveValue): string {
  if (value.redacted) {
    return "redacted";
  }
  if (value.value === null || value.value === undefined) {
    return "not set";
  }
  if (Array.isArray(value.value)) {
    return value.value.length === 0 ? "none" : value.value.join(", ");
  }
  if (typeof value.value === "object") {
    return JSON.stringify(value.value);
  }
  return String(value.value);
}

function formatEffectiveStatus(value: string): string {
  return value.replace(/^pending_/, "pending ").replaceAll("_", " ");
}

function formatScope(value: string): string {
  return value.replaceAll("_", " ");
}

function formatSource(value: string): string {
  return value.replaceAll("_", " ");
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}
