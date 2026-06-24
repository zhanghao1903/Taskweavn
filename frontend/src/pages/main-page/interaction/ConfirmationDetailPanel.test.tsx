import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { UiTextProvider } from "../../../shared/ui-text";
import { ConfirmationDetailPanel } from "./ConfirmationDetailPanel";
import type { MainPageDetailView } from "../mainPageViewModel";

type ConfirmationDetail = Extract<
  MainPageDetailView,
  { kind: "confirmation" }
>;

describe("ConfirmationDetailPanel", () => {
  it("requires explicit selection before resolving the default recommendation", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn();

    render(
      <ConfirmationDetailPanel
        detail={confirmationDetail()}
        onResolve={onResolve}
      />,
    );

    expect(screen.getByRole("button", { name: "Confirm" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(
      screen.getByRole("button", { name: "Resolve decision" }),
    ).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Confirm" }));
    await user.click(screen.getByRole("button", { name: "Resolve decision" }));

    expect(onResolve).toHaveBeenCalledWith("confirmed");
  });

  it("foregrounds impact and options without repeating the confirmation body", () => {
    render(
      <ConfirmationDetailPanel
        detail={confirmationDetail()}
        onResolve={vi.fn()}
      />,
    );

    expect(screen.getByText("Impact")).toBeInTheDocument();
    expect(screen.getByText("Allows implementation to continue.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
    expect(screen.queryByText("No option selected")).not.toBeInTheDocument();
    expect(screen.queryByText("1 option selected")).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        "Approve the first visual baseline before implementation continues.",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Default options are recommendations/i),
    ).not.toBeInTheDocument();
  });

  it("preserves selection when a command error is shown", async () => {
    const user = userEvent.setup();

    render(
      <ConfirmationDetailPanel
        detail={confirmationDetail({
          commandError: "Confirmation was rejected.",
          commandRecoveryActions: ["refresh_snapshot", "open_audit"],
        })}
        onResolve={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Revise task" }));

    expect(screen.getByRole("button", { name: "Revise task" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Confirmation was rejected.",
    );
    expect(screen.getByText("Refresh session")).toBeInTheDocument();
    expect(screen.getByText("View audit")).toBeInTheDocument();
  });

  it("disables options and resolve while resolving", () => {
    render(
      <ConfirmationDetailPanel
        detail={confirmationDetail({ isResolvingConfirmation: true })}
        onResolve={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Resolving" })).toBeDisabled();
  });

  it("renders resolved confirmations as read-only", () => {
    render(
      <ConfirmationDetailPanel
        detail={confirmationDetail({
          confirmation: {
            ...confirmationDetail().confirmation!,
            status: "resolved",
          },
        })}
        onResolve={vi.fn()}
      />,
    );

    expect(screen.getByText("Confirmation resolved")).toBeInTheDocument();
    expect(screen.getByText("This decision is read-only.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resolve decision" })).toBeNull();
  });

  it("renders expired confirmations as read-only", () => {
    render(
      <ConfirmationDetailPanel
        detail={confirmationDetail({
          confirmation: {
            ...confirmationDetail().confirmation!,
            status: "expired",
          },
        })}
        onResolve={vi.fn()}
      />,
    );

    expect(screen.getByText("Confirmation expired")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resolve decision" })).toBeNull();
  });

  it("renders fallback confirmation controls in zh-CN", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn();

    render(
      <UiTextProvider locale="zh-CN">
        <ConfirmationDetailPanel
          detail={confirmationDetail({
            confirmation: {
              ...confirmationDetail().confirmation!,
              options: [],
              riskLabel: undefined,
            },
          })}
          onResolve={onResolve}
        />
      </UiTextProvider>,
    );

    expect(screen.getByText("需要决定")).toBeInTheDocument();
    expect(screen.getByText("待处理")).toBeInTheDocument();
    expect(screen.getByText("影响")).toBeInTheDocument();
    expect(screen.getByText("执行正在等待这个决定。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "确认" }));
    await user.click(screen.getByRole("button", { name: "提交决定" }));

    expect(onResolve).toHaveBeenCalledWith("confirmed");
  });
});

function confirmationDetail(
  overrides: Partial<ConfirmationDetail> = {},
): ConfirmationDetail {
  const detail: ConfirmationDetail = {
    commandError: null,
    commandRecoveryActions: [],
    confirmation: {
      id: "confirmation-visual-baseline",
      sessionId: "session-website-plan",
      taskNodeId: "task-visual-direction",
      taskRef: {
        kind: "published",
        id: "task-visual-direction",
      },
      title: "Confirm visual baseline",
      body: "Approve the first visual baseline before implementation continues.",
      options: [
        { value: "confirmed", label: "Confirm", tone: "primary" },
        { value: "revise", label: "Revise task", tone: "secondary" },
        { value: "skipped", label: "Skip", tone: "danger" },
      ],
      defaultOptionValue: "confirmed",
      status: "pending",
      localStatus: "idle",
      riskLabel: "Allows implementation to continue.",
      createdAt: "2026-05-17T10:03:00+08:00",
      resolvedAt: null,
    },
    fallbackBody: "Confirmation is required.",
    header: {
      body: "Confirmation is attached to this task.",
      eyebrow: "Confirmation required",
      title: "Confirm visual baseline",
    },
    isResolvingConfirmation: false,
    kind: "confirmation",
  };

  return {
    ...detail,
    ...overrides,
  };
}
