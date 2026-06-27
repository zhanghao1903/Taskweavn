import { describe, expect, it } from "vitest";

import type { SessionMessageView } from "../../../shared/api/types";
import {
  appendedMessages,
  createInitialFocusScrollRuntimeState,
  isNearBottomMetrics,
  mainPageFocusScrollRuntimeReducer,
  messageListSignature,
  requestRouteTargetFocus,
  requestRouteTargetScroll,
} from "./mainPageFocusScrollRuntime";

describe("mainPageFocusScrollRuntime", () => {
  it("requests bottom scroll when a runtime input starts and follows its appended message", () => {
    const submitState = mainPageFocusScrollRuntimeReducer(initialState(), {
      commandId: "command-1",
      type: "runtime_input.submit_started",
    });

    expect(submitState.pendingScrollRequest).toMatchObject({
      reason: "submit_started",
      target: { kind: "bottom" },
    });
    expect(submitState.shouldFollowNextAppend).toBe(true);

    const appended = [
      message({
        id: "message-1",
        relatedCommandId: "command-1",
        title: "User input",
      }),
    ];
    const changedState = mainPageFocusScrollRuntimeReducer(submitState, {
      appendedMessages: appended,
      messageListSignature: messageListSignature(appended),
      type: "messages.changed",
    });

    expect(changedState.pendingScrollRequest).toMatchObject({
      reason: "message_appended",
      target: { kind: "bottom" },
    });
    expect(changedState.shouldFollowNextAppend).toBe(false);
  });

  it("does not auto-scroll appended messages while the user has a manual scroll lock", () => {
    const lockedState = mainPageFocusScrollRuntimeReducer(initialState(), {
      isAtBottom: false,
      source: "user",
      type: "conversation.scrolled",
    });

    const changedState = mainPageFocusScrollRuntimeReducer(lockedState, {
      appendedMessages: [message({ id: "message-1" })],
      messageListSignature: "message-1",
      type: "messages.changed",
    });

    expect(changedState.manualScrollLock).toBe(true);
    expect(changedState.pendingScrollRequest).toBeNull();
  });

  it("unlocks auto-scroll after the user returns to the bottom", () => {
    const lockedState = mainPageFocusScrollRuntimeReducer(initialState(), {
      isAtBottom: false,
      source: "user",
      type: "conversation.scrolled",
    });
    const pinnedState = mainPageFocusScrollRuntimeReducer(lockedState, {
      isAtBottom: true,
      source: "user",
      type: "conversation.scrolled",
    });

    const changedState = mainPageFocusScrollRuntimeReducer(pinnedState, {
      appendedMessages: [message({ id: "message-1" })],
      messageListSignature: "message-1",
      type: "messages.changed",
    });

    expect(changedState.manualScrollLock).toBe(false);
    expect(changedState.pendingScrollRequest).toMatchObject({
      target: { kind: "bottom" },
    });
  });

  it("focuses the appended pending ASK card that belongs to the current submit", () => {
    const submitState = mainPageFocusScrollRuntimeReducer(initialState(), {
      commandId: "command-1",
      type: "runtime_input.submit_started",
    });
    const ask = questionMessage({
      id: "ask-message-1",
      relatedCommandId: "command-1",
    });
    const changedState = mainPageFocusScrollRuntimeReducer(submitState, {
      appendedMessages: [ask],
      messageListSignature: messageListSignature([ask]),
      type: "messages.changed",
    });

    expect(changedState.pendingScrollRequest).toMatchObject({
      reason: "ask_card_created",
      target: { kind: "message", messageId: "ask-message-1" },
    });
    expect(changedState.pendingFocusRequest).toMatchObject({
      reason: "ask_card_created",
      target: { kind: "ask_card", messageId: "ask-message-1" },
    });
  });

  it("restores composer focus when a runtime input submit fails", () => {
    const submitState = mainPageFocusScrollRuntimeReducer(initialState(), {
      commandId: "command-1",
      type: "runtime_input.submit_started",
    });
    const failedState = mainPageFocusScrollRuntimeReducer(submitState, {
      commandId: "command-1",
      type: "runtime_input.submit_failed",
    });

    expect(failedState.pendingFocusRequest).toMatchObject({
      reason: "submit_failed",
      target: { kind: "composer" },
    });
    expect(failedState.awaitingSubmitSettlement).toBe(false);
    expect(failedState.pendingSubmitCommandId).toBeNull();
  });

  it("restores composer focus when a runtime input submit settles", () => {
    const submitState = mainPageFocusScrollRuntimeReducer(initialState(), {
      commandId: "command-1",
      type: "runtime_input.submit_started",
    });
    const settledState = mainPageFocusScrollRuntimeReducer(submitState, {
      commandId: "command-1",
      type: "runtime_input.submit_settled",
    });

    expect(settledState.pendingFocusRequest).toMatchObject({
      reason: "submit_settled",
      target: { kind: "composer" },
    });
  });

  it("resets scope and requests a bottom scroll", () => {
    const lockedState = mainPageFocusScrollRuntimeReducer(initialState(), {
      isAtBottom: false,
      source: "user",
      type: "conversation.scrolled",
    });
    const resetState = mainPageFocusScrollRuntimeReducer(lockedState, {
      messageListSignature: "next-signature",
      sessionId: "session-2",
      type: "runtime.reset_scope",
      workspaceId: "workspace-1",
    });

    expect(resetState.sessionId).toBe("session-2");
    expect(resetState.manualScrollLock).toBe(false);
    expect(resetState.messageListSignature).toBe("next-signature");
    expect(resetState.pendingScrollRequest).toMatchObject({
      reason: "scope_changed",
      target: { kind: "bottom" },
    });
  });

  it("detects appended messages from prior and next message lists", () => {
    const previous = [message({ id: "message-1" })];
    const next = [...previous, message({ id: "message-2" })];

    expect(appendedMessages(previous, next)).toEqual([next[1]]);
  });

  it("detects whether scroll metrics are near the bottom", () => {
    expect(
      isNearBottomMetrics({
        clientHeight: 300,
        scrollHeight: 1000,
        scrollTop: 660,
      }),
    ).toBe(true);
    expect(
      isNearBottomMetrics({
        clientHeight: 300,
        scrollHeight: 1000,
        scrollTop: 500,
      }),
    ).toBe(false);
  });

  it("requests static route target focus without replacing submit reducer targets", () => {
    expect(
      requestRouteTargetFocus({
        reason: "route_restored",
        target: "selected_task",
      }),
    ).toEqual({
      reason: "route_restored",
      target: "selected_task",
      type: "target.focus",
    });

    expect(
      requestRouteTargetFocus({
        inputDisabled: true,
        reason: "route_restored",
        target: "input_composer",
      }),
    ).toBeNull();
  });

  it("requests static route target scrolling for inspectable panels", () => {
    expect(
      requestRouteTargetScroll({
        reason: "route_restored",
        target: "file_changes",
      }),
    ).toEqual({
      behavior: "smooth",
      reason: "route_restored",
      target: "file_changes",
      type: "target.scroll_into_view",
    });
  });
});

function initialState() {
  return createInitialFocusScrollRuntimeState({
    sessionId: "session-1",
    workspaceId: "workspace-1",
  });
}

function message(
  overrides: Partial<SessionMessageView> = {},
): SessionMessageView {
  return {
    id: "message-1",
    body: "Body",
    createdAt: "2026-06-26T00:00:00Z",
    kind: "informational",
    relatedCommandId: null,
    sessionId: "session-1",
    taskNodeId: null,
    title: "Message",
    ...overrides,
  };
}

function questionMessage(
  overrides: Partial<SessionMessageView> = {},
): SessionMessageView {
  return message({
    conversationRender: {
      protocolVersion: "plato.conversation.render.v1",
      renderKind: "question_card",
      questionCard: {
        answerMode: "runtime_input",
        body: "Need one more detail.",
        cardId: "ask-card-1",
        cardKind: "clarification",
        options: [],
        questions: [
          {
            id: "question-1",
            inputHint: "Answer here",
            label: "What is the audience?",
            required: true,
          },
        ],
        status: "pending",
        title: "Plato needs one more detail",
      },
    },
    kind: "actionable",
    title: "Router question",
    ...overrides,
  });
}
