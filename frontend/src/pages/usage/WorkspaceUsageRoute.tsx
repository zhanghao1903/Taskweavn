import { useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { navigateApp } from "../../app/navigation";
import type { PlatoRuntimeEnv } from "../../app/platoRuntime";
import {
  buildMainSessionFallbackRoute,
} from "../../app/routes";
import { Badge, Button, Panel, Text } from "../../shared/components";
import type { PlatoApi } from "../../shared/api/platoApi";
import { createHttpPlatoApi } from "../../shared/api/platoApi";
import type {
  TokenUsageSummary,
  TokenUsageSummaryRequest,
  TokenUsageSummaryResponse,
  UsageAggregationDimension,
} from "../../shared/api/tokenUsageTypes";
import { useUiText, type UiTextCatalog } from "../../shared/ui-text";
import {
  parseWorkspaceUsageLocation,
  type WorkspaceUsageRouteLocation,
  type WorkspaceUsageRouteContext,
} from "./workspaceUsageRouteModel";
import styles from "./WorkspaceUsageRoute.module.css";

export type WorkspaceUsageRouteProps = {
  api?: WorkspaceUsageApi | null;
  location?: WorkspaceUsageRouteLocation;
  presentation?: "page" | "embedded";
  runtimeEnv?: PlatoRuntimeEnv;
};

export type WorkspaceUsageApi = Pick<PlatoApi, "getTokenUsageSummary">;

export function WorkspaceUsageRoute({
  api,
  location,
  presentation = "page",
  runtimeEnv = import.meta.env,
}: WorkspaceUsageRouteProps = {}) {
  const uiText = useUiText();
  const resolvedLocation = location ?? globalThis.location;
  const context = useMemo(
    () =>
      parseWorkspaceUsageLocation(
        resolvedLocation.pathname,
        resolvedLocation.search,
      ),
    [resolvedLocation.pathname, resolvedLocation.search],
  );
  const usageApi = useMemo(
    () => api ?? createUsageApi(runtimeEnv),
    [api, runtimeEnv],
  );

  if (context === null) {
    return (
      <UsageShell context={null} presentation={presentation}>
        <Panel className={styles.section}>
          <Text as="h2" variant="heading">
            {uiText.usage.states.routeUnavailable}
          </Text>
          <Text variant="muted">{uiText.usage.states.routeUnavailableBody}</Text>
          <Button onClick={() => navigateApp("/")}>
            {uiText.usage.actions.return}
          </Button>
        </Panel>
      </UsageShell>
    );
  }

  return (
    <UsageShell context={context} presentation={presentation}>
      <UsageDimensionSection
        api={usageApi}
        context={context}
        dimension="workspace"
      />
      <UsageDimensionSection
        api={usageApi}
        context={context}
        dimension="session"
      />
      <UsageDimensionSection
        api={usageApi}
        context={context}
        dimension="plan"
      />
      <UsageDimensionSection
        api={usageApi}
        context={context}
        dimension="task"
      />
    </UsageShell>
  );
}

function UsageShell({
  children,
  context,
  presentation,
}: {
  children: ReactNode;
  context: WorkspaceUsageRouteContext | null;
  presentation: "page" | "embedded";
}) {
  const uiText = useUiText();
  const returnPath =
    context?.sessionId !== null && context?.sessionId !== undefined
      ? buildMainSessionFallbackRoute({
          sessionId: context.sessionId,
          taskNodeId: context.taskNodeId ?? undefined,
          workspaceId: context.workspaceId,
        })
      : "/";

  const shell = (
    <section
      className={presentation === "embedded" ? styles.embeddedShell : styles.shell}
      aria-label={uiText.usage.labels.usage}
    >
        <header className={styles.header}>
          <div>
            <Text variant="eyebrow">{uiText.usage.labels.usage}</Text>
            <h1>{uiText.usage.labels.tokenUsage}</h1>
            <p>{uiText.usage.messages.workspaceUsageHelp}</p>
          </div>
          <div className={styles.headerActions}>
            {context !== null ? (
              <Badge tone="blue">
                {uiText.usage.labels.workspaceId({ id: context.workspaceId })}
              </Badge>
            ) : null}
            {presentation === "page" ? (
              <Button onClick={() => navigateApp(returnPath)}>
                {uiText.usage.actions.return}
              </Button>
            ) : null}
          </div>
        </header>
        {children}
    </section>
  );

  if (presentation === "embedded") {
    return shell;
  }

  return (
    <main className={styles.page}>
      {shell}
    </main>
  );
}

function UsageDimensionSection({
  api,
  context,
  dimension,
}: {
  api: WorkspaceUsageApi | null;
  context: WorkspaceUsageRouteContext;
  dimension: UsageAggregationDimension;
}) {
  const uiText = useUiText();
  const request = usageRequestForDimension(dimension, context);
  const query = useQuery({
    enabled: api !== null,
    queryFn: async () => {
      if (api === null) {
        throw new Error(uiText.usage.states.sidecarRequired);
      }
      const response = await api.getTokenUsageSummary(request, {
        workspaceId: context.workspaceId,
      });
      if (!response.ok || response.data === null) {
        throw new Error(
          response.error?.message ?? uiText.usage.states.summaryUnavailable,
        );
      }
      return response.data;
    },
    queryKey: [
      "usage-summary",
      context.workspaceId,
      dimension,
      request.sessionId ?? null,
      request.planId ?? null,
      request.taskNodeId ?? null,
    ],
  });

  const title = dimensionLabel(dimension, uiText);

  return (
    <Panel className={styles.section} aria-label={title}>
      <div>
        <Text as="h2" variant="heading">
          {title}
        </Text>
        <Text variant="muted">{dimensionHelp(dimension, uiText)}</Text>
      </div>
      {api === null ? (
        <Text variant="muted">{uiText.usage.states.sidecarRequired}</Text>
      ) : query.isPending ? (
        <Text variant="muted">{uiText.common.status.loading}</Text>
      ) : query.isError ? (
        <Text variant="muted">
          {query.error instanceof Error
            ? query.error.message
            : uiText.usage.states.summaryUnavailable}
        </Text>
      ) : (
        <UsageSummaryView summary={query.data} />
      )}
    </Panel>
  );
}

function UsageSummaryView({
  summary,
}: {
  summary: TokenUsageSummaryResponse;
}) {
  const uiText = useUiText();

  return (
    <>
      <div className={styles.summaryGrid}>
        <Metric
          label={uiText.usage.labels.totalTokens}
          value={formatTokens(summary.totals.totalTokens, uiText)}
        />
        <Metric
          label={uiText.usage.labels.calls}
          value={String(summary.totals.callCount)}
        />
        <Metric
          label={uiText.usage.labels.unknownUsage}
          value={String(summary.totals.unknownUsageCallCount)}
        />
        <Metric
          label={uiText.usage.labels.cacheHitRate}
          value={formatCacheRate(summary.totals.cacheHitRatio, uiText)}
        />
      </div>
      <div className={styles.rows} role="list">
        {summary.rows.length === 0 ? (
          <Text className={styles.empty} variant="muted">
            {summary.totals.callCount === 0
              ? uiText.usage.states.noUsageTracked
              : uiText.usage.states.noBreakdownRows}
          </Text>
        ) : (
          summary.rows.slice(0, 12).map((row) => (
            <UsageRow key={`${row.dimension}:${row.id}`} row={row} />
          ))
        )}
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.metric}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function UsageRow({ row }: { row: TokenUsageSummary }) {
  const uiText = useUiText();

  return (
    <article className={styles.row} role="listitem">
      <div>
        <strong>{row.label}</strong>
        <span className={styles.rowMeta}>
          {row.lastOccurredAt ?? uiText.usage.states.notReported}
        </span>
      </div>
      <RowMetric
        label={uiText.usage.labels.totalTokens}
        value={formatTokens(row.totalTokens, uiText)}
      />
      <RowMetric
        label={uiText.usage.labels.inputOutput}
        value={`${formatTokens(row.inputTokens, uiText)} / ${formatTokens(
          row.outputTokens,
          uiText,
        )}`}
      />
      <RowMetric
        label={uiText.usage.labels.cacheHitRate}
        value={formatCacheRate(row.cacheHitRatio, uiText)}
      />
      <RowMetric label={uiText.usage.labels.calls} value={String(row.callCount)} />
    </article>
  );
}

function RowMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.rowMetric}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function usageRequestForDimension(
  dimension: UsageAggregationDimension,
  context: WorkspaceUsageRouteContext,
): TokenUsageSummaryRequest {
  if (dimension === "workspace") {
    return { dimension };
  }
  if (dimension === "session") {
    return { dimension };
  }
  if (dimension === "plan") {
    return {
      dimension,
      planId: context.planId ?? undefined,
      sessionId: context.sessionId ?? undefined,
    };
  }
  return {
    dimension,
    sessionId: context.sessionId ?? undefined,
    taskNodeId: context.taskNodeId ?? undefined,
  };
}

function dimensionLabel(
  dimension: UsageAggregationDimension,
  uiText: UiTextCatalog,
): string {
  return uiText.usage.dimensions[dimension];
}

function dimensionHelp(
  dimension: UsageAggregationDimension,
  uiText: UiTextCatalog,
): string {
  return uiText.usage.dimensionHelp[dimension];
}

function formatTokens(value: number | null, uiText: UiTextCatalog): string {
  return value === null ? uiText.usage.states.notReported : value.toLocaleString();
}

function formatCacheRate(value: number | null, uiText: UiTextCatalog): string {
  if (value === null) {
    return uiText.usage.states.cacheUnavailable;
  }
  return `${(value * 100).toFixed(1)}%`;
}

function createUsageApi(runtimeEnv: PlatoRuntimeEnv): WorkspaceUsageApi | null {
  if (runtimeEnv.VITE_PLATO_API_MODE !== "http") {
    return null;
  }

  return createHttpPlatoApi({
    baseUrl: runtimeEnv.VITE_PLATO_API_BASE_URL ?? "",
  });
}
