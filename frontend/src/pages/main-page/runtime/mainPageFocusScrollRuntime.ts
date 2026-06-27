export const DEFAULT_CONVERSATION_BOTTOM_THRESHOLD_PX = 96;

export type MainPageFocusRequestReason =
  | "ask_presented"
  | "input_submitted"
  | "overlay_opened"
  | "overlay_closed"
  | "route_restored";

export type MainPageScrollRequestReason =
  | "ask_presented"
  | "initial_hydration"
  | "message_appended"
  | "overlay_closed"
  | "overlay_opened"
  | "route_restored";

export type MainPageFocusTarget =
  | "ask_card"
  | "conversation"
  | "detail_panel"
  | "file_changes"
  | "input_composer"
  | "overlay_trigger"
  | "selected_activity"
  | "selected_task";

export type MainPageFocusScrollEffectRequest =
  | {
      behavior: ScrollBehavior;
      reason: MainPageScrollRequestReason;
      type: "conversation.scroll_to_bottom";
    }
  | {
      reason: MainPageFocusRequestReason;
      target: MainPageFocusTarget;
      type: "target.focus";
    }
  | {
      behavior: ScrollBehavior;
      reason: MainPageScrollRequestReason;
      target: Exclude<MainPageFocusTarget, "input_composer" | "overlay_trigger">;
      type: "target.scroll_into_view";
    };

export type ScrollMetrics = {
  clientHeight: number;
  scrollHeight: number;
  scrollTop: number;
};

export function isNearScrollBottom(
  metrics: ScrollMetrics,
  thresholdPx = DEFAULT_CONVERSATION_BOTTOM_THRESHOLD_PX,
): boolean {
  const maxScrollTop = Math.max(0, metrics.scrollHeight - metrics.clientHeight);
  const distanceFromBottom = Math.max(0, maxScrollTop - metrics.scrollTop);

  return distanceFromBottom <= thresholdPx;
}

export function requestConversationAppendScroll({
  nextMessageCount,
  previousMessageCount,
  wasNearBottom,
}: {
  nextMessageCount: number;
  previousMessageCount: number;
  wasNearBottom: boolean;
}): MainPageFocusScrollEffectRequest | null {
  if (nextMessageCount <= previousMessageCount) {
    return null;
  }

  if (!wasNearBottom && previousMessageCount > 0) {
    return null;
  }

  return {
    behavior: previousMessageCount === 0 ? "auto" : "smooth",
    reason:
      previousMessageCount === 0 ? "initial_hydration" : "message_appended",
    type: "conversation.scroll_to_bottom",
  };
}

export function requestInputFocus({
  inputDisabled,
  reason,
}: {
  inputDisabled: boolean;
  reason: MainPageFocusRequestReason;
}): MainPageFocusScrollEffectRequest | null {
  if (inputDisabled) {
    return null;
  }

  return requestTargetFocus({
    reason,
    target: "input_composer",
  });
}

export function requestTargetFocus({
  inputDisabled = false,
  reason,
  target,
}: {
  inputDisabled?: boolean;
  reason: MainPageFocusRequestReason;
  target: MainPageFocusTarget;
}): MainPageFocusScrollEffectRequest | null {
  if (target === "input_composer" && inputDisabled) {
    return null;
  }

  return {
    reason,
    target,
    type: "target.focus",
  };
}

export function requestTargetScroll({
  behavior = "smooth",
  reason,
  target,
}: {
  behavior?: ScrollBehavior;
  reason: MainPageScrollRequestReason;
  target: Exclude<MainPageFocusTarget, "input_composer" | "overlay_trigger">;
}): MainPageFocusScrollEffectRequest {
  return {
    behavior,
    reason,
    target,
    type: "target.scroll_into_view",
  };
}
