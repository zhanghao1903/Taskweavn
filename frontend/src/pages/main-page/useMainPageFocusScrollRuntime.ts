import {
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  type RefObject,
} from "react";

import {
  isNearScrollBottom,
  requestConversationAppendScroll,
  requestInputFocus,
  requestTargetFocus,
  requestTargetScroll,
  type MainPageFocusRequestReason,
  type MainPageFocusScrollEffectRequest,
  type MainPageFocusTarget,
  type MainPageScrollRequestReason,
} from "./runtime/mainPageFocusScrollRuntime";

export type MainPageFocusScrollRuntime = {
  askCardRef: RefObject<HTMLElement | null>;
  captureOverlayTrigger: () => void;
  captureOverlayTriggerElement: (trigger: HTMLElement | null) => void;
  conversationBottomAnchorRef: RefObject<HTMLDivElement | null>;
  conversationMessageListRef: RefObject<HTMLDivElement | null>;
  conversationRootRef: RefObject<HTMLElement | null>;
  contextInputRef: RefObject<HTMLInputElement | null>;
  detailPanelRef: RefObject<HTMLElement | null>;
  fileChangesRef: RefObject<HTMLElement | null>;
  focusContextInput: (reason: MainPageFocusRequestReason) => void;
  focusTarget: (
    target: MainPageFocusTarget,
    reason: MainPageFocusRequestReason,
  ) => void;
  onConversationScroll: () => void;
  scrollTargetIntoView: (
    target: Exclude<MainPageFocusTarget, "input_composer" | "overlay_trigger">,
    reason: MainPageScrollRequestReason,
  ) => void;
  selectedActivityItemRef: RefObject<HTMLLIElement | null>;
  selectedTaskCardRef: RefObject<HTMLButtonElement | null>;
};

export function useMainPageFocusScrollRuntime({
  conversationMessageCount,
  inputDisabled,
}: {
  conversationMessageCount: number;
  inputDisabled: boolean;
}): MainPageFocusScrollRuntime {
  const conversationMessageListRef = useRef<HTMLDivElement | null>(null);
  const conversationRootRef = useRef<HTMLElement | null>(null);
  const conversationBottomAnchorRef = useRef<HTMLDivElement | null>(null);
  const contextInputRef = useRef<HTMLInputElement | null>(null);
  const detailPanelRef = useRef<HTMLElement | null>(null);
  const fileChangesRef = useRef<HTMLElement | null>(null);
  const selectedTaskCardRef = useRef<HTMLButtonElement | null>(null);
  const selectedActivityItemRef = useRef<HTMLLIElement | null>(null);
  const askCardRef = useRef<HTMLElement | null>(null);
  const overlayTriggerRef = useRef<HTMLElement | null>(null);
  const isConversationNearBottomRef = useRef(true);
  const conversationScrollTopRef = useRef(0);
  const previousConversationMessageCountRef = useRef(conversationMessageCount);

  const updateConversationNearBottom = useCallback(() => {
    const node = conversationMessageListRef.current;
    if (node === null) {
      isConversationNearBottomRef.current = true;
      conversationScrollTopRef.current = 0;
      return;
    }

    conversationScrollTopRef.current = node.scrollTop;
    isConversationNearBottomRef.current = isNearScrollBottom({
      clientHeight: node.clientHeight,
      scrollHeight: node.scrollHeight,
      scrollTop: node.scrollTop,
    });
  }, []);

  const resolveTargetElement = useCallback(
    (target: MainPageFocusTarget): HTMLElement | null => {
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
          return contextInputRef.current;
        case "overlay_trigger":
          return overlayTriggerRef.current;
        case "selected_activity":
          return selectedActivityItemRef.current;
        case "selected_task":
          return selectedTaskCardRef.current;
      }
    },
    [],
  );

  const applyEffectRequest = useCallback(
    (request: MainPageFocusScrollEffectRequest) => {
      switch (request.type) {
        case "conversation.scroll_to_bottom":
          conversationBottomAnchorRef.current?.scrollIntoView({
            block: "end",
            behavior: request.behavior,
          });
          updateConversationNearBottom();
          return;

        case "target.focus": {
          const target = resolveTargetElement(request.target);
          const focusable = shouldFocusTargetElement(request.target)
            ? target
            : findFocusableTarget(target);
          focusable?.focus({ preventScroll: true });
          return;
        }

        case "target.scroll_into_view": {
          const target = resolveTargetElement(request.target);
          if (typeof target?.scrollIntoView !== "function") {
            return;
          }
          target.scrollIntoView({
            block: "center",
            behavior: request.behavior,
          });
          return;
        }
      }
    },
    [resolveTargetElement, updateConversationNearBottom],
  );

  useLayoutEffect(() => {
    const node = conversationMessageListRef.current;
    if (node === null) {
      return;
    }

    const updateMetrics = () => {
      updateConversationNearBottom();
    };
    updateMetrics();
    node.addEventListener("scroll", updateMetrics, { passive: true });

    return () => {
      node.removeEventListener("scroll", updateMetrics);
    };
  }, [updateConversationNearBottom]);

  useLayoutEffect(() => {
    const previousMessageCount = previousConversationMessageCountRef.current;
    const wasNearBottom = isConversationNearBottomRef.current;
    const previousScrollTop = conversationScrollTopRef.current;
    const scrollRequest = requestConversationAppendScroll({
      nextMessageCount: conversationMessageCount,
      previousMessageCount,
      wasNearBottom,
    });

    previousConversationMessageCountRef.current = conversationMessageCount;

    if (scrollRequest !== null) {
      applyEffectRequest(scrollRequest);
      return;
    }

    if (
      conversationMessageCount > previousMessageCount &&
      previousMessageCount > 0 &&
      !wasNearBottom
    ) {
      const node = conversationMessageListRef.current;
      if (node !== null) {
        node.scrollTop = previousScrollTop;
        updateConversationNearBottom();
      }
    }
  }, [applyEffectRequest, conversationMessageCount, updateConversationNearBottom]);

  const focusContextInput = useCallback(
    (reason: MainPageFocusRequestReason) => {
      const focusRequest = requestInputFocus({
        inputDisabled,
        reason,
      });

      if (focusRequest !== null) {
        applyEffectRequest(focusRequest);
      }
    },
    [applyEffectRequest, inputDisabled],
  );

  const focusTarget = useCallback(
    (target: MainPageFocusTarget, reason: MainPageFocusRequestReason) => {
      const focusRequest = requestTargetFocus({
        inputDisabled,
        reason,
        target,
      });

      if (focusRequest !== null) {
        applyEffectRequest(focusRequest);
      }
    },
    [applyEffectRequest, inputDisabled],
  );

  const scrollTargetIntoView = useCallback(
    (
      target: Exclude<
        MainPageFocusTarget,
        "input_composer" | "overlay_trigger"
      >,
      reason: MainPageScrollRequestReason,
    ) => {
      applyEffectRequest(requestTargetScroll({ reason, target }));
    },
    [applyEffectRequest],
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

  return useMemo(
    () => ({
      askCardRef,
      captureOverlayTrigger,
      captureOverlayTriggerElement,
      conversationBottomAnchorRef,
      conversationMessageListRef,
      conversationRootRef,
      contextInputRef,
      detailPanelRef,
      fileChangesRef,
      focusContextInput,
      focusTarget,
      onConversationScroll: updateConversationNearBottom,
      scrollTargetIntoView,
      selectedActivityItemRef,
      selectedTaskCardRef,
    }),
    [
      captureOverlayTrigger,
      captureOverlayTriggerElement,
      focusContextInput,
      focusTarget,
      scrollTargetIntoView,
      updateConversationNearBottom,
    ],
  );
}

function findFocusableTarget(target: HTMLElement | null): HTMLElement | null {
  if (target === null) {
    return null;
  }

  const activeChild = target.querySelector<HTMLElement>(
    [
      "button:not([disabled])",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "a[href]",
      "[tabindex]:not([tabindex='-1'])",
    ].join(","),
  );

  return activeChild ?? target;
}

function shouldFocusTargetElement(target: MainPageFocusTarget): boolean {
  return (
    target === "conversation" ||
    target === "detail_panel" ||
    target === "file_changes" ||
    target === "selected_activity"
  );
}
