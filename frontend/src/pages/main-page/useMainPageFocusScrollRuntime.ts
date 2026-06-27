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
} from "./runtime/mainPageFocusScrollRuntime";

export type UseMainPageFocusScrollRuntimeOptions = {
  inputError: string | null;
  inputRef: RefObject<HTMLInputElement | null>;
  isInputSubmitting: boolean;
  messages: readonly SessionMessageView[];
  sessionId: string | null;
  workspaceId: WorkspaceId | null;
};

export type UseMainPageFocusScrollRuntimeResult = {
  bottomSentinelRef: RefObject<HTMLDivElement | null>;
  messageListRef: RefObject<HTMLDivElement | null>;
  notifyRuntimeInputSubmitStarted: (commandId?: string | null) => void;
  onMessageListScroll: UIEventHandler<HTMLDivElement>;
};

export function useMainPageFocusScrollRuntime({
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
    },
    [],
  );

  return {
    bottomSentinelRef,
    messageListRef,
    notifyRuntimeInputSubmitStarted,
    onMessageListScroll,
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
