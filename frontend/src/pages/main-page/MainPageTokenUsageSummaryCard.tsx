import { useQuery } from "@tanstack/react-query";

import type {
  TokenUsageSummary,
  TokenUsageSummaryRequest,
} from "../../shared/api/tokenUsageTypes";
import type { WorkspaceId } from "../../shared/api/types";
import { Badge, Panel, Text } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import type { LoadTokenUsageSummary } from "./runtime/adapter";
import styles from "./MainPage.module.css";

export type MainPageTokenUsageSummaryCardProps = {
  loadTokenUsageSummary?: LoadTokenUsageSummary;
  request: TokenUsageSummaryRequest;
  workspaceId?: WorkspaceId | null;
};

export function MainPageTokenUsageSummaryCard({
  loadTokenUsageSummary,
  request,
  workspaceId,
}: MainPageTokenUsageSummaryCardProps) {
  if (!loadTokenUsageSummary) {
    return null;
  }

  return (
    <MainPageTokenUsageSummaryQueryCard
      loadTokenUsageSummary={loadTokenUsageSummary}
      request={request}
      workspaceId={workspaceId}
    />
  );
}

function MainPageTokenUsageSummaryQueryCard({
  loadTokenUsageSummary,
  request,
  workspaceId,
}: {
  loadTokenUsageSummary: LoadTokenUsageSummary;
  request: TokenUsageSummaryRequest;
  workspaceId?: WorkspaceId | null;
}) {
  const query = useQuery({
    queryFn: () => loadTokenUsageSummary(request, workspaceId ?? null),
    queryKey: [
      "main-detail-usage",
      workspaceId ?? "current",
      request.dimension,
      request.sessionId ?? null,
      request.planId ?? null,
      request.taskNodeId ?? null,
    ],
  });

  if (query.isPending) {
    return <TokenUsagePanel state="loading" />;
  }

  if (query.isError) {
    return <TokenUsagePanel state="error" />;
  }

  return <TokenUsagePanel summary={query.data.totals} />;
}

function TokenUsagePanel({
  state,
  summary,
}: {
  state?: "loading" | "error";
  summary?: TokenUsageSummary;
}) {
  const uiText = useUiText();
  const totalTokens =
    state === "loading"
      ? uiText.common.status.loading
      : state === "error"
        ? uiText.usage.states.summaryUnavailable
        : formatUsageTokens(summary?.totalTokens ?? null, uiText);
  const cacheRate =
    summary === undefined
      ? uiText.usage.states.cacheUnavailable
      : formatUsageCacheRate(summary.cacheHitRatio, uiText);

  return (
    <Panel
      aria-label={uiText.usage.labels.tokenUsage}
      className={styles.detailBox}
      tone="muted"
    >
      <div className={styles.detailTitleRow}>
        <Text as="strong" variant="label">
          {uiText.usage.labels.tokenUsage}
        </Text>
        <Badge size="sm" tone={summary?.unknownUsageCallCount ? "warning" : "blue"}>
          {summary
            ? `${summary.callCount} ${uiText.usage.labels.calls.toLowerCase()}`
            : uiText.usage.states.notReported}
        </Badge>
      </div>
      <Text variant="muted">{uiText.usage.messages.compactHelp}</Text>
      <div className={styles.usageMetricGrid}>
        <UsageMetric
          label={uiText.usage.labels.totalTokens}
          value={totalTokens}
        />
        <UsageMetric
          label={uiText.usage.labels.inputOutput}
          value={
            summary
              ? `${formatUsageTokens(
                  summary.inputTokens,
                  uiText,
                )} / ${formatUsageTokens(summary.outputTokens, uiText)}`
              : uiText.usage.states.notReported
          }
        />
        <UsageMetric label={uiText.usage.labels.cacheHitRate} value={cacheRate} />
        <UsageMetric
          label={uiText.usage.labels.unknownUsage}
          value={summary ? String(summary.unknownUsageCallCount) : "0"}
        />
      </div>
    </Panel>
  );
}

function UsageMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.usageMetric}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function formatUsageTokens(
  value: number | null,
  uiText: ReturnType<typeof useUiText>,
): string {
  return value === null ? uiText.usage.states.notReported : value.toLocaleString();
}

function formatUsageCacheRate(
  value: number | null,
  uiText: ReturnType<typeof useUiText>,
): string {
  if (value === null) {
    return uiText.usage.states.cacheUnavailable;
  }
  return `${(value * 100).toFixed(1)}%`;
}
