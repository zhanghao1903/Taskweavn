import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionMessageView } from "../../shared/api/types";
import { useMainPageFocusScrollRuntime } from "./useMainPageFocusScrollRuntime";

describe("useMainPageFocusScrollRuntime", () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    window.matchMedia = vi.fn().mockReturnValue({
      matches: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("scrolls to the bottom for a local submit and the next appended message", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<Harness messages={[]} />);
    const messageList = screen.getByTestId("message-list");
    installScrollMetrics(messageList, {
      clientHeight: 300,
      scrollHeight: 1000,
      scrollTop: 0,
    });

    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(messageList.scrollTop).toBe(1000);

    installScrollMetrics(messageList, {
      clientHeight: 300,
      scrollHeight: 1200,
      scrollTop: 1000,
    });
    rerender(<Harness messages={[message({ id: "message-1" })]} />);

    await waitFor(() => {
      expect(messageList.scrollTop).toBe(1200);
    });
  });

  it("does not auto-scroll while the user has manually scrolled away from the bottom", async () => {
    const { rerender } = render(
      <Harness messages={[message({ id: "message-1" })]} />,
    );
    const messageList = screen.getByTestId("message-list");
    installScrollMetrics(messageList, {
      clientHeight: 300,
      scrollHeight: 1000,
      scrollTop: 100,
    });

    fireEvent.scroll(messageList);
    rerender(
      <Harness
        messages={[message({ id: "message-1" }), message({ id: "message-2" })]}
      />,
    );

    await waitFor(() => {
      expect(messageList.scrollTop).toBe(100);
    });
  });

  it("focuses the composer again after a submitted input is rejected", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<Harness messages={[]} />);
    const input = screen.getByLabelText("Context message");
    const submit = screen.getByRole("button", { name: "Submit" });

    await user.click(submit);
    rerender(<Harness isInputSubmitting messages={[]} />);
    rerender(
      <Harness
        inputError="Question routing failed."
        isInputSubmitting={false}
        messages={[]}
      />,
    );

    await waitFor(() => {
      expect(input).toHaveFocus();
    });
  });

  it("focuses a newly appended pending Router question card", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<Harness messages={[]} />);
    const messageList = screen.getByTestId("message-list");
    installScrollMetrics(messageList, {
      clientHeight: 300,
      scrollHeight: 900,
      scrollTop: 0,
    });

    await user.click(screen.getByRole("button", { name: "Submit" }));

    const ask = questionMessage({
      id: "ask-message-1",
      relatedCommandId: "command-1",
    });
    rerender(<Harness messages={[ask]} />);

    await waitFor(() => {
      expect(screen.getByTestId("message-ask-message-1")).toHaveFocus();
    });
  });
});

function Harness({
  inputError = null,
  isInputSubmitting = false,
  messages,
}: {
  inputError?: string | null;
  isInputSubmitting?: boolean;
  messages: readonly SessionMessageView[];
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const focusScrollRuntime = useMainPageFocusScrollRuntime({
    inputDisabled: false,
    inputError,
    inputRef,
    isInputSubmitting,
    messages,
    sessionId: "session-1",
    workspaceId: "workspace-1",
  });

  return (
    <div>
      <div
        data-testid="message-list"
        onScroll={focusScrollRuntime.onMessageListScroll}
        ref={focusScrollRuntime.messageListRef}
      >
        {messages.map((item) => (
          <article
            data-session-message-id={item.id}
            data-testid={`message-${item.id}`}
            key={item.id}
            tabIndex={-1}
          >
            {item.body}
            {item.conversationRender?.renderKind === "question_card" ? (
              <div data-router-ask-card>Question</div>
            ) : null}
          </article>
        ))}
        <div
          data-testid="bottom"
          ref={focusScrollRuntime.bottomSentinelRef}
        />
      </div>
      <input aria-label="Context message" ref={inputRef} />
      <button
        onClick={() =>
          focusScrollRuntime.notifyRuntimeInputSubmitStarted("command-1")
        }
        type="button"
      >
        Submit
      </button>
    </div>
  );
}

function installScrollMetrics(
  element: HTMLElement,
  metrics: {
    clientHeight: number;
    scrollHeight: number;
    scrollTop: number;
  },
) {
  Object.defineProperty(element, "clientHeight", {
    configurable: true,
    value: metrics.clientHeight,
  });
  Object.defineProperty(element, "scrollHeight", {
    configurable: true,
    value: metrics.scrollHeight,
  });
  element.scrollTop = metrics.scrollTop;
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
    body: "Plato needs one more detail.",
    conversationRender: {
      protocolVersion: "plato.conversation.render.v1",
      renderKind: "question_card",
      questionCard: {
        answerMode: "runtime_input",
        body: "Need one more detail.",
        cardId: "ask-card-1",
        cardKind: "clarification",
        options: [],
        questions: [],
        status: "pending",
        title: "Plato needs one more detail",
      },
    },
    kind: "actionable",
    title: "Router question",
    ...overrides,
  });
}
