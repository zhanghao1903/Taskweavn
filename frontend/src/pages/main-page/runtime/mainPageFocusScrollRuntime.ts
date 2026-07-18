import type {
  SessionMessageView,
  WorkspaceId,
} from "../../../shared/api/types";

const DEFAULT_BOTTOM_THRESHOLD_PX = 48;

export type MainPageFocusTarget =
  | { kind: "composer" }
  | { kind: "ask_card"; messageId: string };

export type MainPageRouteFocusTarget =
  | "ask_card"
  | "conversation"
  | "detail_panel"
  | "file_changes"
  | "input_composer"
  | "overlay_trigger"
  | "selected_activity"
  | "selected_task";

export type MainPageScrollTarget =
  | { kind: "bottom" }
  | { kind: "message"; messageId: string };

export type MainPageFocusScrollReason =
  | "scope_changed"
  | "submit_started"
  | "message_appended"
  | "ask_card_created"
  | "submit_settled"
  | "submit_failed";

export type MainPageRouteFocusReason =
  | "ask_presented"
  | "overlay_closed"
  | "overlay_opened"
  | "route_restored";

export type MainPageRouteScrollReason =
  | "ask_presented"
  | "overlay_closed"
  | "overlay_opened"
  | "route_restored";

export type MainPageFocusRequest = {
  id: number;
  reason: MainPageFocusScrollReason;
  target: MainPageFocusTarget;
};

export type MainPageScrollRequest = {
  id: number;
  reason: MainPageFocusScrollReason;
  target: MainPageScrollTarget;
};

export type MainPageFocusScrollRuntimeState = {
  awaitingSubmitSettlement: boolean;
  isPinnedToBottom: boolean;
  manualScrollLock: boolean;
  messageListSignature: string;
  pendingFocusRequest: MainPageFocusRequest | null;
  pendingScrollRequest: MainPageScrollRequest | null;
  pendingSubmitCommandId: string | null;
  requestSequence: number;
  sessionId: string | null;
  shouldFollowNextAppend: boolean;
  workspaceId: WorkspaceId | null;
};

export type MainPageFocusScrollRuntimeAction =
  | {
      messageListSignature?: string;
      sessionId: string | null;
      type: "runtime.reset_scope";
      workspaceId: WorkspaceId | null;
    }
  | {
      messageListSignature: string;
      type: "conversation.mounted";
    }
  | {
      isAtBottom: boolean;
      source: "user" | "program";
      type: "conversation.scrolled";
    }
  | {
      commandId: string | null;
      type: "runtime_input.submit_started";
    }
  | {
      commandId: string | null;
      type: "runtime_input.submit_failed";
    }
  | {
      commandId: string | null;
      type: "runtime_input.submit_settled";
    }
  | {
      appendedMessages: readonly SessionMessageView[];
      messageListSignature: string;
      type: "messages.changed";
    }
  | {
      requestId: number;
      type: "scroll.completed";
    }
  | {
      requestId: number;
      type: "focus.completed";
    };

export type MainPageScrollMetrics = {
  clientHeight: number;
  scrollHeight: number;
  scrollTop: number;
};

export type MainPageRouteFocusScrollEffectRequest =
  | {
      reason: MainPageRouteFocusReason;
      target: MainPageRouteFocusTarget;
      type: "target.focus";
    }
  | {
      behavior: ScrollBehavior;
      reason: MainPageRouteScrollReason;
      target: Exclude<
        MainPageRouteFocusTarget,
        "input_composer" | "overlay_trigger"
      >;
      type: "target.scroll_into_view";
    };

export function createInitialFocusScrollRuntimeState({
  messageListSignature = "",
  sessionId,
  workspaceId,
}: {
  messageListSignature?: string;
  sessionId: string | null;
  workspaceId: WorkspaceId | null;
}): MainPageFocusScrollRuntimeState {
  return {
    awaitingSubmitSettlement: false,
    isPinnedToBottom: true,
    manualScrollLock: false,
    messageListSignature,
    pendingFocusRequest: null,
    pendingScrollRequest: null,
    pendingSubmitCommandId: null,
    requestSequence: 0,
    sessionId,
    shouldFollowNextAppend: false,
    workspaceId,
  };
}

export function mainPageFocusScrollRuntimeReducer(
  state: MainPageFocusScrollRuntimeState,
  action: MainPageFocusScrollRuntimeAction,
): MainPageFocusScrollRuntimeState {
  switch (action.type) {
    case "runtime.reset_scope":
      return withScrollRequest(
        createInitialFocusScrollRuntimeState({
          messageListSignature: action.messageListSignature ?? "",
          sessionId: action.sessionId,
          workspaceId: action.workspaceId,
        }),
        { kind: "bottom" },
        "scope_changed",
      );

    case "conversation.mounted":
      return {
        ...state,
        isPinnedToBottom: true,
        manualScrollLock: false,
        messageListSignature: action.messageListSignature,
      };

    case "conversation.scrolled":
      return {
        ...state,
        isPinnedToBottom: action.isAtBottom,
        manualScrollLock:
          action.source === "user" ? !action.isAtBottom : state.manualScrollLock,
      };

    case "runtime_input.submit_started":
      return withOptionalBottomScrollRequest(
        {
          ...state,
          awaitingSubmitSettlement: true,
          pendingSubmitCommandId: action.commandId,
          shouldFollowNextAppend: shouldAutoFollowConversation(state),
        },
        "submit_started",
        shouldAutoFollowConversation(state),
      );

    case "runtime_input.submit_failed":
      return requestComposerFocus(
        {
          ...state,
          awaitingSubmitSettlement: false,
          pendingSubmitCommandId: clearMatchingCommandId(
            state.pendingSubmitCommandId,
            action.commandId,
          ),
          shouldFollowNextAppend: false,
        },
        "submit_failed",
      );

    case "runtime_input.submit_settled":
      if (!state.awaitingSubmitSettlement) {
        return state;
      }
      return requestComposerFocus(
        {
          ...state,
          awaitingSubmitSettlement: false,
          pendingSubmitCommandId: clearMatchingCommandId(
            state.pendingSubmitCommandId,
            action.commandId,
          ),
          shouldFollowNextAppend: false,
        },
        "submit_settled",
      );

    case "messages.changed":
      return reduceMessagesChanged(state, action);

    case "scroll.completed":
      if (state.pendingScrollRequest?.id !== action.requestId) {
        return state;
      }
      return {
        ...state,
        pendingScrollRequest: null,
      };

    case "focus.completed":
      if (state.pendingFocusRequest?.id !== action.requestId) {
        return state;
      }
      return {
        ...state,
        pendingFocusRequest: null,
      };
  }
}

export function isNearBottomMetrics(
  metrics: MainPageScrollMetrics,
  thresholdPx = DEFAULT_BOTTOM_THRESHOLD_PX,
): boolean {
  return (
    metrics.scrollHeight - metrics.scrollTop - metrics.clientHeight <=
    thresholdPx
  );
}

export function messageListSignature(
  messages: readonly SessionMessageView[],
): string {
  return messages
    .map((message) =>
      [
        message.id,
        message.createdAt,
        message.relatedCommandId ?? "",
        message.conversationRender?.renderKind ?? "",
      ].join(":"),
    )
    .join("|");
}

export function appendedMessages(
  previousMessages: readonly SessionMessageView[],
  nextMessages: readonly SessionMessageView[],
): SessionMessageView[] {
  const previousIds = new Set(previousMessages.map((message) => message.id));
  return nextMessages.filter((message) => !previousIds.has(message.id));
}

export function requestRouteTargetFocus({
  inputDisabled = false,
  reason,
  target,
}: {
  inputDisabled?: boolean;
  reason: MainPageRouteFocusReason;
  target: MainPageRouteFocusTarget;
}): MainPageRouteFocusScrollEffectRequest | null {
  if (target === "input_composer" && inputDisabled) {
    return null;
  }

  return {
    reason,
    target,
    type: "target.focus",
  };
}

export function requestRouteTargetScroll({
  behavior = "smooth",
  reason,
  target,
}: {
  behavior?: ScrollBehavior;
  reason: MainPageRouteScrollReason;
  target: Exclude<MainPageRouteFocusTarget, "input_composer" | "overlay_trigger">;
}): MainPageRouteFocusScrollEffectRequest {
  return {
    behavior,
    reason,
    target,
    type: "target.scroll_into_view",
  };
}

function reduceMessagesChanged(
  state: MainPageFocusScrollRuntimeState,
  action: Extract<
    MainPageFocusScrollRuntimeAction,
    { type: "messages.changed" }
  >,
): MainPageFocusScrollRuntimeState {
  if (action.messageListSignature === state.messageListSignature) {
    return state;
  }

  let nextState: MainPageFocusScrollRuntimeState = {
    ...state,
    messageListSignature: action.messageListSignature,
  };

  const askMessage = action.appendedMessages.find(isPendingQuestionCardMessage);
  if (askMessage !== undefined && shouldFollowCommandMessage(state, askMessage)) {
    nextState = withScrollRequest(
      nextState,
      { kind: "message", messageId: askMessage.id },
      "ask_card_created",
    );
    nextState = withFocusRequest(
      nextState,
      { kind: "ask_card", messageId: askMessage.id },
      "ask_card_created",
    );
    return {
      ...nextState,
      shouldFollowNextAppend: false,
    };
  }

  const shouldFollow =
    action.appendedMessages.length > 0 &&
    ((state.isPinnedToBottom && !state.manualScrollLock) ||
      state.shouldFollowNextAppend ||
      action.appendedMessages.some((message) =>
        shouldFollowCommandMessage(state, message),
      ));

  if (shouldFollow) {
    nextState = withScrollRequest(
      nextState,
      { kind: "bottom" },
      "message_appended",
    );
  }

  if (
    action.appendedMessages.some(
      (message) =>
        isRuntimeFailureMessage(message) &&
        shouldFollowCommandMessage(state, message),
    )
  ) {
    nextState = requestComposerFocus(nextState, "submit_failed");
  }

  return {
    ...nextState,
    shouldFollowNextAppend:
      action.appendedMessages.length > 0 ? false : state.shouldFollowNextAppend,
  };
}

function shouldFollowCommandMessage(
  state: MainPageFocusScrollRuntimeState,
  message: SessionMessageView,
): boolean {
  if (!shouldAutoFollowConversation(state)) {
    return false;
  }
  if (state.shouldFollowNextAppend) {
    return true;
  }
  if (state.pendingSubmitCommandId === null) {
    return false;
  }
  return message.relatedCommandId === state.pendingSubmitCommandId;
}

function clearMatchingCommandId(
  currentCommandId: string | null,
  actionCommandId: string | null,
): string | null {
  if (actionCommandId === null || currentCommandId === actionCommandId) {
    return null;
  }
  return currentCommandId;
}

function requestComposerFocus(
  state: MainPageFocusScrollRuntimeState,
  reason: MainPageFocusScrollReason,
): MainPageFocusScrollRuntimeState {
  return withFocusRequest(state, { kind: "composer" }, reason);
}

function withScrollRequest(
  state: MainPageFocusScrollRuntimeState,
  target: MainPageScrollTarget,
  reason: MainPageFocusScrollReason,
): MainPageFocusScrollRuntimeState {
  const requestSequence = state.requestSequence + 1;
  return {
    ...state,
    pendingScrollRequest: {
      id: requestSequence,
      reason,
      target,
    },
    requestSequence,
  };
}

function withOptionalBottomScrollRequest(
  state: MainPageFocusScrollRuntimeState,
  reason: MainPageFocusScrollReason,
  shouldScroll: boolean,
): MainPageFocusScrollRuntimeState {
  return shouldScroll ? withScrollRequest(state, { kind: "bottom" }, reason) : state;
}

function shouldAutoFollowConversation(
  state: MainPageFocusScrollRuntimeState,
): boolean {
  return state.isPinnedToBottom && !state.manualScrollLock;
}

function withFocusRequest(
  state: MainPageFocusScrollRuntimeState,
  target: MainPageFocusTarget,
  reason: MainPageFocusScrollReason,
): MainPageFocusScrollRuntimeState {
  const requestSequence = state.requestSequence + 1;
  return {
    ...state,
    pendingFocusRequest: {
      id: requestSequence,
      reason,
      target,
    },
    requestSequence,
  };
}

function isPendingQuestionCardMessage(message: SessionMessageView): boolean {
  return (
    message.conversationRender?.protocolVersion ===
      "plato.conversation.render.v1" &&
    message.conversationRender.renderKind === "question_card" &&
    message.conversationRender.questionCard?.status === "pending"
  );
}

function isRuntimeFailureMessage(message: SessionMessageView): boolean {
  if (message.kind === "error") {
    return true;
  }
  const title = message.title.trim().toLocaleLowerCase();
  return (
    title === "runtime input failed" ||
    title === "runtime input rejected" ||
    title === "input rejected"
  );
}
