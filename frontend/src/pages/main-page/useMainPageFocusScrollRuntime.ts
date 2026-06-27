import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  type RefObject,
  type UIEventHandler,
} from "react";

import type {
  SessionMessageView,
  WorkspaceId,
} from "../../shared/api/types";
import {
  appendedMessages,
  createInitialFocusScrollRuntimeState,
  isNearBottomMetrics,
  mainPageFocusScrollRuntimeReducer,
  messageListSignature,
  requestRouteTargetFocus,
  requestRouteTargetScroll,
  type MainPageRouteFocusReason,
  type MainPageRouteFocusTarget,
  type MainPageRouteScrollReason,
  type MainPageRouteFocusScrollEffectRequest,
} from "./runtime/mainPageFocusScrollRuntime";

export type UseMainPageFocusScrollRuntimeOptions = {
  inputDisabled: boolean;
  inputError: string | null;
  inputRef: RefObject<HTMLInputElement | null>;
  isInputSubmitting: boolean;
  messages: readonly SessionMessageView[];
  sessionId: string | null;
  workspaceId: WorkspaceId | null;
};

export type UseMainPageFocusScrollRuntimeResult = {
  askCardRef: RefObject<HTMLElement | null>;
  bottomSentinelRef: RefObject<HTMLDivElement | null>;
  captureOverlayTrigger: () => void;
  captureOverlayTriggerElement: (trigger: HTMLElement | null) => void;
  conversationRootRef: RefObject<HTMLElement | null>;
  detailPanelRef: RefObject<HTMLElement | null>;
  fileChangesRef: RefObject<HTMLElement | null>;
  focusContextInput: (reason: MainPageRouteFocusReason) => void;
  focusTarget: (
    target: MainPageRouteFocusTarget,
    reason: MainPageRouteFocusReason,
  ) => void;
  messageListRef: RefObject<HTMLDivElement | null>;
  notifyRuntimeInputSubmitStarted: (commandId?: string | null) => void;
  onMessageListScroll: UIEventHandler<HTMLDivElement>;
  scrollTargetIntoView: (
    target: Exclude<
      MainPageRouteFocusTarget,
      "input_composer" | "overlay_trigger"
    >,
    reason: MainPageRouteScrollReason,
  ) => void;
  selectedActivityItemRef: RefObject<HTMLLIElement | null>;
  selectedTaskCardRef: RefObject<HTMLButtonElement | null>;
};

export function useMainPageFocusScrollRuntime({
  inputDisabled,
  inputError,
  inputRef,
  isInputSubmitting,
  messages,
  sessionId,
  workspaceId,
}: UseMainPageFocusScrollRuntimeOptions): UseMainPageFocusScrollRuntimeResult {
  const initialMessageListSignature = useMemo(
    () => messageListSignature(messages),
    [messages],
  );
  const [state, dispatch] = useReducer(
    mainPageFocusScrollRuntimeReducer,
    {
      messageListSignature: initialMessageListSignature,
      sessionId,
      workspaceId,
    },
    createInitialFocusScrollRuntimeState,
  );
  const bottomSentinelRef = useRef<HTMLDivElement>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const askCardRef = useRef<HTMLElement | null>(null);
  const conversationRootRef = useRef<HTMLElement | null>(null);
  const detailPanelRef = useRef<HTMLElement | null>(null);
  const fileChangesRef = useRef<HTMLElement | null>(null);
  const overlayTriggerRef = useRef<HTMLElement | null>(null);
  const selectedActivityItemRef = useRef<HTMLLIElement | null>(null);
  const selectedTaskCardRef = useRef<HTMLButtonElement | null>(null);
  const currentMessageListSignature = useMemo(
    () => messageListSignature(messages),
    [messages],
  );
  const latestMessagesRef = useRef<readonly SessionMessageView[]>(messages);
  const latestMessageListSignatureRef = useRef(currentMessageListSignature);
  const previousMessagesRef = useRef<readonly SessionMessageView[]>(messages);
  const previousMessageListSignatureRef = useRef(initialMessageListSignature);
  const wasInputSubmittingRef = useRef(isInputSubmitting);
  const previousInputErrorRef = useRef(inputError);

  const resolveRouteTargetElement = useCallback(
    (target: MainPageRouteFocusTarget): HTMLElement | null => {
      switch (target) {
        case "ask_card":
          return askCardRef.current;
        case "conversation":
          return conversationRootRef.current;
        case "detail_panel":
          return detailPanelRef.current;
        case "file_changes":
          return fileChangesRef.current ?? detailPanelRef.current;
        case "input_composer":
          return inputRef.current;
        case "overlay_trigger":
          return overlayTriggerRef.current;
        case "selected_activity":
          return selectedActivityItemRef.current;
        case "selected_task":
          return selectedTaskCardRef.current;
      }
    },
    [inputRef],
  );

  const applyRouteEffectRequest = useCallback(
    (request: MainPageRouteFocusScrollEffectRequest | null) => {
      if (request === null) {
        return;
      }

      switch (request.type) {
        case "target.focus": {
          const target = resolveRouteTargetElement(request.target);
          const focusable = shouldFocusRouteTargetElement(request.target)
            ? target
            : findFocusableTarget(target);
          focusElement(focusable);
          return;
        }

        case "target.scroll_into_view": {
          const target = resolveRouteTargetElement(request.target);
          target?.scrollIntoView?.({
            block: "center",
            behavior: request.behavior,
          });
          return;
        }
      }
    },
    [resolveRouteTargetElement],
  );

  useEffect(() => {
    latestMessagesRef.current = messages;
    latestMessageListSignatureRef.current = currentMessageListSignature;
  }, [currentMessageListSignature, messages]);

  useEffect(() => {
    previousMessagesRef.current = latestMessagesRef.current;
    previousMessageListSignatureRef.current =
      latestMessageListSignatureRef.current;
    dispatch({
      messageListSignature: latestMessageListSignatureRef.current,
      sessionId,
      type: "runtime.reset_scope",
      workspaceId,
    });
  }, [sessionId, workspaceId]);

  useEffect(() => {
    if (currentMessageListSignature === previousMessageListSignatureRef.current) {
      return;
    }

    const previousMessages = previousMessagesRef.current;
    const nextAppendedMessages = appendedMessages(previousMessages, messages);
    previousMessagesRef.current = messages;
    previousMessageListSignatureRef.current = currentMessageListSignature;
    dispatch({
      appendedMessages: nextAppendedMessages,
      messageListSignature: currentMessageListSignature,
      type: "messages.changed",
    });
  }, [currentMessageListSignature, messages]);

  useEffect(() => {
    const wasInputSubmitting = wasInputSubmittingRef.current;
    wasInputSubmittingRef.current = isInputSubmitting;

    if (wasInputSubmitting && !isInputSubmitting) {
      dispatch({
        commandId: null,
        type: "runtime_input.submit_settled",
      });
    }
  }, [isInputSubmitting]);

  useEffect(() => {
    if (
      inputError !== null &&
      inputError !== previousInputErrorRef.current
    ) {
      dispatch({
        commandId: null,
        type: "runtime_input.submit_failed",
      });
    }
    previousInputErrorRef.current = inputError;
  }, [inputError]);

  useLayoutEffect(() => {
    const request = state.pendingScrollRequest;
    const messageList = messageListRef.current;
    if (request === null || messageList === null) {
      return;
    }

    if (request.target.kind === "bottom") {
      messageList.scrollTop = messageList.scrollHeight;
      bottomSentinelRef.current?.scrollIntoView?.({
        block: "end",
        behavior: preferredScrollBehavior(),
      });
      dispatch({
        isAtBottom: true,
        source: "program",
        type: "conversation.scrolled",
      });
    } else {
      const target = findMessageElement(messageList, request.target.messageId);
      target?.scrollIntoView?.({
        block: "nearest",
        behavior: preferredScrollBehavior(),
      });
    }

    dispatch({
      requestId: request.id,
      type: "scroll.completed",
    });
  }, [state.pendingScrollRequest]);

  useLayoutEffect(() => {
    const request = state.pendingFocusRequest;
    if (request === null) {
      return;
    }

    if (request.target.kind === "composer") {
      focusElement(inputRef.current);
    } else {
      const messageList = messageListRef.current;
      const messageElement =
        messageList === null
          ? null
          : findMessageElement(messageList, request.target.messageId);
      const answerControl = messageElement?.querySelector<HTMLElement>(
        [
          "[data-router-ask-answer-control]:not(:disabled)",
          "textarea:not(:disabled)",
          "input:not(:disabled)",
          "button:not(:disabled)",
          "select:not(:disabled)",
          "[tabindex]",
        ].join(","),
      );
      focusElement(answerControl ?? messageElement ?? null);
    }

    dispatch({
      requestId: request.id,
      type: "focus.completed",
    });
  }, [inputRef, state.pendingFocusRequest]);

  const onMessageListScroll: UIEventHandler<HTMLDivElement> = useCallback(
    (event) => {
      const element = event.currentTarget;
      dispatch({
        isAtBottom: isNearBottomMetrics({
          clientHeight: element.clientHeight,
          scrollHeight: element.scrollHeight,
          scrollTop: element.scrollTop,
        }),
        source: "user",
        type: "conversation.scrolled",
      });
    },
    [],
  );

  const notifyRuntimeInputSubmitStarted = useCallback(
    (commandId: string | null = null) => {
      dispatch({
        commandId,
        type: "runtime_input.submit_started",
      });
      if (!inputDisabled) {
        focusElement(inputRef.current);
      }
    },
    [inputDisabled, inputRef],
  );

  const focusTarget = useCallback(
    (target: MainPageRouteFocusTarget, reason: MainPageRouteFocusReason) => {
      applyRouteEffectRequest(
        requestRouteTargetFocus({
          inputDisabled,
          reason,
          target,
        }),
      );
    },
    [applyRouteEffectRequest, inputDisabled],
  );

  const focusContextInput = useCallback(
    (reason: MainPageRouteFocusReason) => {
      focusTarget("input_composer", reason);
    },
    [focusTarget],
  );

  const scrollTargetIntoView = useCallback(
    (
      target: Exclude<
        MainPageRouteFocusTarget,
        "input_composer" | "overlay_trigger"
      >,
      reason: MainPageRouteScrollReason,
    ) => {
      applyRouteEffectRequest(requestRouteTargetScroll({ reason, target }));
    },
    [applyRouteEffectRequest],
  );

  const captureOverlayTriggerElement = useCallback(
    (trigger: HTMLElement | null) => {
      overlayTriggerRef.current = trigger;
    },
    [],
  );

  const captureOverlayTrigger = useCallback(() => {
    const activeElement = document.activeElement;
    captureOverlayTriggerElement(
      activeElement instanceof HTMLElement ? activeElement : null,
    );
  }, [captureOverlayTriggerElement]);

  return {
    askCardRef,
    bottomSentinelRef,
    captureOverlayTrigger,
    captureOverlayTriggerElement,
    conversationRootRef,
    detailPanelRef,
    fileChangesRef,
    focusContextInput,
    focusTarget,
    messageListRef,
    notifyRuntimeInputSubmitStarted,
    onMessageListScroll,
    scrollTargetIntoView,
    selectedActivityItemRef,
    selectedTaskCardRef,
  };
}

function findMessageElement(
  messageList: HTMLElement,
  messageId: string,
): HTMLElement | null {
  return messageList.querySelector<HTMLElement>(
    `[data-session-message-id="${cssEscape(messageId)}"]`,
  );
}

function focusElement(element: HTMLElement | null): void {
  element?.focus({ preventScroll: true });
}

function findFocusableTarget(target: HTMLElement | null): HTMLElement | null {
  if (target === null) {
    return null;
  }

  const activeChild = target.querySelector<HTMLElement>(
    [
      "[data-router-ask-answer-control]:not(:disabled)",
      "textarea:not(:disabled)",
      "input:not(:disabled)",
      "button:not(:disabled)",
      "select:not(:disabled)",
      "a[href]",
      "[tabindex]:not([tabindex='-1'])",
    ].join(","),
  );

  return activeChild ?? target;
}

function shouldFocusRouteTargetElement(target: MainPageRouteFocusTarget): boolean {
  return (
    target === "conversation" ||
    target === "detail_panel" ||
    target === "file_changes" ||
    target === "selected_activity"
  );
}

function preferredScrollBehavior(): ScrollBehavior {
  if (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    return "auto";
  }
  return "smooth";
}

function cssEscape(value: string): string {
  if (
    typeof CSS !== "undefined" &&
    typeof CSS.escape === "function"
  ) {
    return CSS.escape(value);
  }
  return value.replace(/["\\]/gu, "\\$&");
}
