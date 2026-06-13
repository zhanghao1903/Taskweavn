import { useQuery } from "@tanstack/react-query";

import type {
  TokenUsageSummary,
  TokenUsageSummaryRequest,
} from "../../shared/api/tokenUsageTypes";
import type { WorkspaceId } from "../../shared/api/types";
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
        : formatUsageTokens(reportedTokenTotal(summary), uiText);
  return (
    <div
      aria-label={uiText.usage.labels.tokenUsage}
      className={styles.tokenUsageLine}
      role={state === "loading" ? "status" : undefined}
    >
      <span className={styles.tokenUsageLabel}>{uiText.usage.labels.tokenUsage}</span>
      <strong className={styles.tokenUsageValue}>{totalTokens}</strong>
    </div>
  );
}

function reportedTokenTotal(summary?: TokenUsageSummary): number | null {
  if (!summary) {
    return null;
  }
  if (summary.totalTokens !== null) {
    return summary.totalTokens;
  }
  if (summary.inputTokens !== null && summary.outputTokens !== null) {
    return summary.inputTokens + summary.outputTokens;
  }
  return summary.inputTokens ?? summary.outputTokens;
}

function formatUsageTokens(
  value: number | null,
  uiText: ReturnType<typeof useUiText>,
): string {
  return value === null ? uiText.usage.states.notReported : value.toLocaleString();
}
