import { describe, expect, it } from "vitest";

import {
  isNearScrollBottom,
  requestConversationAppendScroll,
  requestInputFocus,
  requestTargetFocus,
  requestTargetScroll,
} from "./mainPageFocusScrollRuntime";

describe("mainPageFocusScrollRuntime", () => {
  it("treats a conversation as near the bottom within the configured threshold", () => {
    expect(
      isNearScrollBottom({
        clientHeight: 400,
        scrollHeight: 1000,
        scrollTop: 520,
      }),
    ).toBe(true);
  });

  it("does not treat a conversation as near the bottom outside the threshold", () => {
    expect(
      isNearScrollBottom({
        clientHeight: 400,
        scrollHeight: 1000,
        scrollTop: 400,
      }),
    ).toBe(false);
  });

  it("requests an initial auto scroll when conversation messages first hydrate", () => {
    expect(
      requestConversationAppendScroll({
        nextMessageCount: 3,
        previousMessageCount: 0,
        wasNearBottom: false,
      }),
    ).toEqual({
      behavior: "auto",
      reason: "initial_hydration",
      type: "conversation.scroll_to_bottom",
    });
  });

  it("requests smooth append scrolling only when the reader is already near bottom", () => {
    expect(
      requestConversationAppendScroll({
        nextMessageCount: 4,
        previousMessageCount: 3,
        wasNearBottom: true,
      }),
    ).toEqual({
      behavior: "smooth",
      reason: "message_appended",
      type: "conversation.scroll_to_bottom",
    });

    expect(
      requestConversationAppendScroll({
        nextMessageCount: 4,
        previousMessageCount: 3,
        wasNearBottom: false,
      }),
    ).toBeNull();
  });

  it("does not request focus when the input composer is disabled", () => {
    expect(
      requestInputFocus({
        inputDisabled: true,
        reason: "input_submitted",
      }),
    ).toBeNull();
  });

  it("requests focus for enabled composer recovery", () => {
    expect(
      requestInputFocus({
        inputDisabled: false,
        reason: "input_submitted",
      }),
    ).toEqual({
      reason: "input_submitted",
      target: "input_composer",
      type: "target.focus",
    });
  });

  it("requests focus for route-return and ASK-card targets", () => {
    expect(
      requestTargetFocus({
        reason: "route_restored",
        target: "selected_task",
      }),
    ).toEqual({
      reason: "route_restored",
      target: "selected_task",
      type: "target.focus",
    });

    expect(
      requestTargetFocus({
        reason: "ask_presented",
        target: "ask_card",
      }),
    ).toEqual({
      reason: "ask_presented",
      target: "ask_card",
      type: "target.focus",
    });

    expect(
      requestTargetFocus({
        reason: "route_restored",
        target: "file_changes",
      }),
    ).toEqual({
      reason: "route_restored",
      target: "file_changes",
      type: "target.focus",
    });
  });

  it("requests target scrolling for route-return and ASK-card targets", () => {
    expect(
      requestTargetScroll({
        reason: "route_restored",
        target: "selected_task",
      }),
    ).toEqual({
      behavior: "smooth",
      reason: "route_restored",
      target: "selected_task",
      type: "target.scroll_into_view",
    });

    expect(
      requestTargetScroll({
        behavior: "auto",
        reason: "ask_presented",
        target: "ask_card",
      }),
    ).toEqual({
      behavior: "auto",
      reason: "ask_presented",
      target: "ask_card",
      type: "target.scroll_into_view",
    });

    expect(
      requestTargetScroll({
        reason: "route_restored",
        target: "detail_panel",
      }),
    ).toEqual({
      behavior: "smooth",
      reason: "route_restored",
      target: "detail_panel",
      type: "target.scroll_into_view",
    });
  });
});
