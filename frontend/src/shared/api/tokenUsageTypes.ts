import type { SessionId, TaskNodeId, WorkspaceId } from "./types";

export type UsageAggregationDimension = "task" | "plan" | "session" | "workspace";

export type UsageSource =
  | "provider_reported"
  | "provider_partial"
  | "estimated"
  | "unavailable";

export type CacheRateSource =
  | "hit_miss_tokens"
  | "input_tokens"
  | "unavailable";

export type TokenUsageSummary = {
  dimension: UsageAggregationDimension;
  id: string;
  label: string;
  workspaceId: WorkspaceId;
  sessionId?: SessionId | null;
  planId?: string | null;
  taskNodeId?: TaskNodeId | null;
  callCount: number;
  unknownUsageCallCount: number;
  inputTokens: number | null;
  outputTokens: number | null;
  totalTokens: number | null;
  reasoningTokens: number | null;
  cachedTokens: number | null;
  cacheHitTokens: number | null;
  cacheMissTokens: number | null;
  cacheHitRatio: number | null;
  cacheRateSource: CacheRateSource;
  firstOccurredAt: string | null;
  lastOccurredAt: string | null;
};

export type TokenUsageSummaryResponse = {
  dimension: UsageAggregationDimension;
  totals: TokenUsageSummary;
  rows: TokenUsageSummary[];
};

export type TokenUsageSummaryRequest = {
  dimension: UsageAggregationDimension;
  sessionId?: SessionId;
  planId?: string;
  taskNodeId?: TaskNodeId;
  from?: string;
  to?: string;
  provider?: string;
  model?: string;
};
