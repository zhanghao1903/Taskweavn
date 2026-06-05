import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MainPageWorkspaceHeader } from "./MainPageWorkspaceHeader";
import type { MainPageAuditEntryViewModel } from "./mainPageViewModel";

describe("MainPageWorkspaceHeader", () => {
  it("uses the workspace title as the only visible header label", () => {
    render(
      <MainPageWorkspaceHeader
        auditEntry={auditEntry({ isEnabled: true })}
        eventError={null}
        isPublishingTaskTree={false}
        onPublishTaskTree={vi.fn()}
        showPublishTaskTree={false}
        taskTreeCommandError={null}
        title="Personal website project plan"
        uiNotice={null}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Personal website project plan" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Session")).not.toBeInTheDocument();
  });

  it("keeps disabled audit reasons out of the visible workspace header copy", () => {
    render(
      <MainPageWorkspaceHeader
        auditEntry={auditEntry({
          disabledReason:
            "Audit entry is reserved until the Audit Page UI is implemented.",
          isEnabled: false,
        })}
        eventError={null}
        isPublishingTaskTree={false}
        onPublishTaskTree={vi.fn()}
        showPublishTaskTree={false}
        taskTreeCommandError={null}
        title="Personal website project plan"
        uiNotice={null}
      />,
    );

    const auditButton = screen.getByRole("button", { name: "View audit" });

    expect(auditButton).toBeDisabled();
    expect(auditButton).toHaveAttribute(
      "title",
      "Audit entry is reserved until the Audit Page UI is implemented.",
    );
    expect(
      screen.queryByText(
        "Audit entry is reserved until the Audit Page UI is implemented.",
      ),
    ).not.toBeInTheDocument();
  });

  it("keeps enabled audit entries as route links", () => {
    render(
      <MainPageWorkspaceHeader
        auditEntry={auditEntry({ isEnabled: true })}
        eventError={null}
        isPublishingTaskTree={false}
        onPublishTaskTree={vi.fn()}
        showPublishTaskTree={false}
        taskTreeCommandError={null}
        title="Personal website project plan"
        uiNotice={null}
      />,
    );

    expect(screen.getByRole("link", { name: "View audit" })).toHaveAttribute(
      "href",
      "/sessions/session-website-plan/audit",
    );
  });
});

function auditEntry(
  overrides: Partial<MainPageAuditEntryViewModel> = {},
): MainPageAuditEntryViewModel {
  return {
    disabledReason: null,
    href: "/sessions/session-website-plan/audit",
    isEnabled: true,
    label: "View audit",
    returnFocus: "session",
    scope: "session",
    ...overrides,
  };
}
