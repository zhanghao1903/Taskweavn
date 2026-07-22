import { productRecoveryActionText } from "../../shared/api/productErrors";
import type {
  MainPageSnapshot,
  RuntimeInputPendingClarification,
  RuntimeInputRouteRequest,
  RuntimeInputRouteResult,
  SessionActivityItemView,
  TaskNodeId,
} from "../../shared/api/types";
import { zhCN } from "../../shared/ui-text";
import type { InputTarget } from "./mainPageUiTypes";
import type { MainPageInputCommandMode } from "./mainPageViewModel";

export function buildRuntimeInputRouteRequest({
  commandId,
  content,
  mode,
  pendingClarification,
  sessionId,
  snapshot,
  target,
  taskNodeId,
}: {
  commandId?: string;
  content: string;
  mode: RuntimeInputRouteRequest["mode"];
  pendingClarification?: RuntimeInputPendingClarification | null;
  sessionId: string;
  snapshot: MainPageSnapshot | null;
  target: InputTarget;
  taskNodeId: TaskNodeId | null;
}): RuntimeInputRouteRequest {
  const activePlan = snapshot?.activePlan ?? null;
  const scopeKind =
    target === "task" && taskNodeId !== null
      ? "task"
      : target === "plan" && activePlan !== null
        ? "plan"
        : "session";

  return {
    commandId: commandId ?? createRuntimeInputCommandId(),
    sessionId,
    content,
    mode,
    selection: {
      scopeKind,
      planId: scopeKind === "session" ? null : activePlan?.id ?? null,
      taskNodeId: scopeKind === "task" ? taskNodeId : null,
      refs: [],
    },
    clientState: {
      activeAskId: snapshot?.activeAsk?.id ?? null,
      activeConfirmationId: snapshot?.pendingConfirmations[0]?.id ?? null,
      pendingClarification: pendingClarification ?? null,
    },
  };
}

export function createRuntimeInputCommandId(): string {
  return `route-input-${Date.now()}`;
}

export function runtimeInputActivity(
  result: RuntimeInputRouteResult,
): SessionActivityItemView | null {
  return result.activity ?? result.inquiryResult?.activity ?? null;
}

export function runtimeInputModeFor(
  content: string,
  mode: MainPageInputCommandMode,
): NonNullable<RuntimeInputRouteRequest["mode"]> {
  if (shouldRouteReadOnlyQuestion(content)) {
    return "ask";
  }

  if (mode === "generate_task_tree") {
    return "change";
  }

  if (
    mode === "append_plan_input" ||
    mode === "append_session_input" ||
    mode === "append_task_input"
  ) {
    return "guide";
  }

  return "auto";
}

export function runtimeInputNotice(result: RuntimeInputRouteResult): string {
  const answer = result.inquiryResult?.answer;
  const message =
    answer === null || answer === undefined
      ? result.outcome.userMessage
      : answer.title
        ? `${answer.title}: ${answer.body}`
        : answer.body;

  return compactNotice(message);
}

export function runtimeInputUserActivity(
  request: RuntimeInputRouteRequest,
  result: RuntimeInputRouteResult,
): SessionActivityItemView {
  return {
    id: `activity:runtime-input:${request.commandId}:user_input`,
    sessionId: request.sessionId,
    kind: "user_input",
    title: "User input",
    body: request.content,
    occurredAt: result.generatedAt,
    scopeKind: result.decision.scope.kind,
    planId: result.decision.scope.planId ?? null,
    taskNodeId: result.decision.scope.taskNodeId ?? null,
    sideEffect: "context_effect",
    relatedRefs: result.decision.relatedRefs,
    sourceKind: "router",
    sourceId: request.commandId,
    disclosureLevel: "public",
  };
}

export function runtimeInputRouteActivities(
  request: RuntimeInputRouteRequest,
  result: RuntimeInputRouteResult,
): SessionActivityItemView[] {
  const runtimeActivity = runtimeInputActivity(result);
  const routerReplyActivity = runtimeInputRouterReplyActivity(request, result);

  return [
    runtimeInputUserActivity(request, result),
    ...(routerReplyActivity === null ? [] : [routerReplyActivity]),
    ...(runtimeActivity === null ? [] : [runtimeActivity]),
  ];
}

function runtimeInputRouterReplyActivity(
  request: RuntimeInputRouteRequest,
  result: RuntimeInputRouteResult,
): SessionActivityItemView | null {
  if (
    result.outcome.status !== "rejected" &&
    result.outcome.status !== "unsupported"
  ) {
    return null;
  }

  return {
    id: `activity:runtime-input:${request.commandId}:router_reply`,
    sessionId: request.sessionId,
    kind: "recovery_note",
    title: "Router reply",
    body: runtimeInputRouterReplyBody(result),
    occurredAt: result.generatedAt,
    scopeKind: result.decision.scope.kind,
    planId: result.decision.scope.planId ?? null,
    taskNodeId: result.decision.scope.taskNodeId ?? null,
    sideEffect: "state_effect",
    relatedRefs: result.decision.relatedRefs,
    sourceKind: "router",
    sourceId: result.decision.id,
    disclosureLevel: "public",
  };
}

function runtimeInputRouterReplyBody(result: RuntimeInputRouteResult): string {
  const suggestions = result.outcome.recoveryActions
    .map((action) => productRecoveryActionText(action, zhCN).description)
    .filter((description) => description.trim().length > 0);

  if (suggestions.length === 0) {
    return result.outcome.userMessage;
  }

  return [
    result.outcome.userMessage,
    "",
    "建议的恢复操作：",
    ...suggestions.map((suggestion) => `- ${suggestion}`),
  ].join("\n");
}

export function prependRuntimeActivityItems(
  items: SessionActivityItemView[],
  nextItems: SessionActivityItemView[],
): SessionActivityItemView[] {
  const nextIds = new Set(nextItems.map((item) => item.id));
  return [
    ...nextItems,
    ...items.filter((candidate) => !nextIds.has(candidate.id)),
  ].slice(0, 20);
}

function shouldRouteReadOnlyQuestion(content: string): boolean {
  const trimmed = content.trim();
  if (!trimmed) {
    return false;
  }

  if (trimmed.includes("?") || trimmed.includes("？")) {
    return true;
  }

  const lower = trimmed.toLowerCase();
  const englishQuestionPrefixes = [
    "what ",
    "why ",
    "how ",
    "where ",
    "when ",
    "who ",
    "which ",
    "can ",
    "could ",
    "should ",
    "is ",
    "are ",
    "do ",
    "does ",
    "did ",
  ];
  if (englishQuestionPrefixes.some((prefix) => lower.startsWith(prefix))) {
    return true;
  }

  return [
    "什么",
    "为什么",
    "为何",
    "如何",
    "怎么",
    "是否",
    "吗",
    "哪",
    "能不能",
  ].some((marker) => trimmed.includes(marker));
}

function compactNotice(message: string): string {
  const maxLength = 360;
  if (message.length <= maxLength) {
    return message;
  }

  return `${message.slice(0, maxLength - 3)}...`;
}
