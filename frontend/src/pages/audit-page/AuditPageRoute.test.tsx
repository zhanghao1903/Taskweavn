import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAuditMockApi } from "./mockAuditApi";
import type { AuditMockScenarioId } from "./mockAuditScenarios";
import {
  AuditPageRoute,
  type AuditApi,
} from "./AuditPageRoute";
import { parseAuditLocation } from "./auditRouteModel";
import type {
  AuditRecordDetail,
  EvidenceDetail,
  QueryResponse,
} from "../../shared/api/types";

describe("AuditPageRoute", () => {
  afterEach(() => {
    globalThis.history.pushState(null, "", "/");
  });

  it("parses session audit routes", () => {
    const route = parseAuditLocation(
      "/sessions/session-website-plan/audit",
      "?filter=confirmations",
    );

    expect(route).toEqual({
      request: {
        entry: undefined,
        filter: "confirmations",
        includeDetail: false,
        limit: 50,
        recordId: undefined,
        sessionId: "session-website-plan",
        taskNodeId: undefined,
      },
      routeKind: "session",
    });
  });

  it("parses task audit routes with selected record detail", () => {
    const route = parseAuditLocation(
      "/sessions/session-website-plan/tasks/task-implementation/audit",
      "?entry=from_task&filter=actions&recordId=record-action-1",
    );

    expect(route).toEqual({
      request: {
        entry: "from_task",
        filter: "actions",
        includeDetail: true,
        limit: 50,
        recordId: "record-action-1",
        sessionId: "session-website-plan",
        taskNodeId: "task-implementation",
      },
      routeKind: "task",
    });
  });

  it("renders a mock Audit Page snapshot for task routes", async () => {
    const api = createAuditMockApi("a3-records-ready");

    renderWithQueryClient(
      <AuditPageRoute
        api={api}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "",
        }}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Audit" })).toBeInTheDocument();
    expect(screen.getAllByText("Personal website plan").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Audit records ready").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Audit records")).toBeInTheDocument();
    expect(screen.getByText("Action completed")).toBeInTheDocument();
  });

  it("passes route request fields to the audit API", async () => {
    const api: AuditApi = {
      ...createAuditMockApi("a4-record-selected"),
      getAuditSnapshot: vi.fn(createAuditMockApi("a4-record-selected").getAuditSnapshot),
    };

    renderWithQueryClient(
      <AuditPageRoute
        api={api}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "?filter=files&recordId=record-file-1",
        }}
      />,
    );

    expect((await screen.findAllByText("Audit record selected")).length).toBeGreaterThan(0);
    expect(api.getAuditSnapshot).toHaveBeenCalledWith({
      entry: undefined,
      filter: "files",
      includeDetail: true,
      limit: 50,
      recordId: "record-file-1",
      sessionId: "session-website-plan",
      taskNodeId: "task-implementation",
    });
  });

  it("renders the AP-005B shell with scope, return action, and detail panel", async () => {
    renderWithQueryClient(
      <AuditPageRoute
        api={createAuditMockApi("a4-record-selected")}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "?recordId=record-file-1",
        }}
      />,
    );

    expect(await screen.findByText("Scope: Task")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Return" })).toBeInTheDocument();
    expect(screen.getByText("No mutations")).toBeInTheDocument();
    expect(screen.getByLabelText("Audit record detail")).toBeInTheDocument();
    expect(screen.getByText("What happened")).toBeInTheDocument();
    expect(screen.getByText("Disclosure")).toBeInTheDocument();
    expect(screen.getByText("Effective configuration")).toBeInTheDocument();
    expect(screen.getByText("Related logs")).toBeInTheDocument();
  });

  it("surfaces non-ready snapshot state without hiding the audit shell", async () => {
    renderWithQueryClient(
      <AuditPageRoute
        api={createAuditMockApi("a5-partial-evidence")}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "",
        }}
      />,
    );

    expect((await screen.findAllByText("Partial evidence")).length).toBeGreaterThan(0);
    expect(screen.getByText("Some evidence is still loading.")).toBeInTheDocument();
    expect(screen.getByText("Audit Overview")).toBeInTheDocument();
    expect(screen.getByLabelText("Audit records")).toBeInTheDocument();
  });

  it("does not expose Task or Session mutation actions in the audit shell", async () => {
    renderWithQueryClient(
      <AuditPageRoute
        api={createAuditMockApi("a3-records-ready")}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "",
        }}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Audit" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Publish task" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm execution" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resolve confirmation" })).not.toBeInTheDocument();
  });

  it("renders filter counts and keeps zero-count filters selectable", async () => {
    renderWithQueryClient(
      <AuditPageRoute
        api={createAuditMockApi("a3-records-ready")}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "",
        }}
      />,
    );

    const filters = await screen.findByLabelText("Audit record filters");

    expect(within(filters).getByRole("button", { name: "All records 2" })).toBeEnabled();
    expect(within(filters).getByRole("button", { name: "Actions 1" })).toBeEnabled();
    expect(within(filters).getByRole("button", { name: "Confirmations 1" })).toBeEnabled();
    expect(within(filters).getByRole("button", { name: "Risks 0" })).toBeEnabled();
  });

  it("renders records in API order", async () => {
    renderWithQueryClient(
      <AuditPageRoute
        api={createAuditMockApi("a3-records-ready")}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "",
        }}
      />,
    );

    const records = await screen.findByLabelText("Audit records");
    const recordCards = within(records).getAllByRole("button");

    expect(recordCards).toHaveLength(2);
    expect(recordCards[0]).toHaveTextContent("Action completed");
    expect(recordCards[1]).toHaveTextContent("User approved limited edits");
  });

  it("uses the route filter as selected filter and projects visible records", async () => {
    renderWithQueryClient(
      <AuditPageRoute
        api={createAuditMockApi("a3-records-ready")}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "?filter=confirmations",
        }}
      />,
    );

    const filters = await screen.findByLabelText("Audit record filters");
    const confirmations = within(filters).getByRole("button", {
      name: "Confirmations 1",
    });
    const records = screen.getByLabelText("Audit records");

    expect(confirmations).toHaveAttribute("aria-current", "true");
    expect(confirmations).toHaveAttribute("aria-pressed", "true");
    expect(within(records).getByText("User approved limited edits")).toBeInTheDocument();
    expect(within(records).queryByText("Action completed")).not.toBeInTheDocument();
  });

  it("clicking a filter updates local state and route query", async () => {
    const user = userEvent.setup();

    globalThis.history.pushState(
      null,
      "",
      "/sessions/session-website-plan/tasks/task-implementation/audit",
    );
    renderWithQueryClient(<AuditPageRoute api={createAuditMockApi("a3-records-ready")} />);

    const filters = await screen.findByLabelText("Audit record filters");
    await user.click(within(filters).getByRole("button", { name: "Confirmations 1" }));

    await waitFor(() => {
      expect(globalThis.location.search).toBe("?filter=confirmations");
    });

    await waitFor(() => {
      expect(
        within(screen.getByLabelText("Audit record filters")).getByRole("button", {
          name: "Confirmations 1",
        }),
      ).toHaveAttribute("aria-current", "true");
    });
    expect(screen.getByText("User approved limited edits")).toBeInTheDocument();
    expect(screen.queryByText("Action completed")).not.toBeInTheDocument();
  });

  it("clicking a record opens detail state, loads fallback detail, and updates the route query", async () => {
    const user = userEvent.setup();
    const baseApi = createAuditMockApi("a3-records-ready");
    const api: AuditApi = {
      ...baseApi,
      getAuditRecordDetail: vi.fn(baseApi.getAuditRecordDetail),
    };

    globalThis.history.pushState(
      null,
      "",
      "/sessions/session-website-plan/tasks/task-implementation/audit",
    );
    renderWithQueryClient(<AuditPageRoute api={api} />);

    await user.click(
      await screen.findByRole("button", { name: "Audit record Action completed" }),
    );

    await waitFor(() => {
      expect(globalThis.location.search).toBe("?filter=all&recordId=record-action-1");
    });

    const detailPanel = screen.getByLabelText("Audit record detail");
    expect(detailPanel).toBeInTheDocument();
    expect(detailPanel).toHaveAttribute("tabindex", "-1");
    await waitFor(() => {
      expect(detailPanel).toHaveFocus();
    });
    expect(await screen.findByText("Action completed detail body.")).toBeInTheDocument();
    expect(api.getAuditRecordDetail).toHaveBeenCalledWith({
      includeEvidence: true,
      includeSanitizedPayload: true,
      recordId: "record-action-1",
      sessionId: "session-website-plan",
    });
  });

  it("requests and renders sanitized record and evidence payload disclosure", async () => {
    const user = userEvent.setup();
    const baseApi = createAuditMockApi("a3-records-ready");
    const api: AuditApi = {
      ...baseApi,
      getAuditRecordDetail: vi.fn(async (request) => {
        const response = await baseApi.getAuditRecordDetail(request);
        if (response.ok !== true || response.data === null) {
          return response;
        }
        return {
          ...response,
          data: {
            ...response.data,
            disclosure: {
              rawPayloadAvailable: true,
              rawPayloadShown: true,
              redactionReason: "Secrets were redacted.",
            },
            rawPayload: {
              content: "{\"action\":\"run\",\"token\":\"[redacted:secret]\"}",
              format: "json",
              redactions: ["secret:token"],
            },
          },
        } satisfies QueryResponse<AuditRecordDetail>;
      }),
      getEvidenceDetail: vi.fn(async (request) => ({
        cursor: null,
        data: {
          available: true,
          body: "Sanitized evidence detail.",
          disclosure: {
            partialReason: "Payload was truncated for safe display.",
            rawPayloadAvailable: true,
            rawPayloadShown: true,
            redactionReason: "Paths were normalized.",
          },
          hidden: false,
          id: request.evidenceId,
          kind: "observation",
          label: "Execution observation",
          occurredAt: "2026-05-24T10:01:00Z",
          redacted: true,
          sanitizedPayload: {
            content: "stdout=[redacted:secret]\nworkspace://src/App.tsx",
            format: "text",
            redactions: ["secret:stdout", "path:workspace"],
          },
          source: "event_stream",
          summary: "Observation payload.",
        },
        error: null,
        generatedAt: "2026-05-24T10:02:00Z",
        ok: true,
        requestId: "request-evidence-sanitized",
      }) satisfies QueryResponse<EvidenceDetail>),
    };

    globalThis.history.pushState(
      null,
      "",
      "/sessions/session-website-plan/tasks/task-implementation/audit",
    );
    renderWithQueryClient(<AuditPageRoute api={api} />);

    await user.click(
      await screen.findByRole("button", { name: "Audit record Action completed" }),
    );

    expect(await screen.findByText("Sanitized record payload")).toBeInTheDocument();
    expect(screen.getByText("Sanitized evidence payload")).toBeInTheDocument();
    expect(screen.getAllByText("Secrets were redacted.").length).toBeGreaterThan(0);
    expect(screen.getByText("Payload was truncated for safe display.")).toBeInTheDocument();
    expect(screen.getAllByText("secret:token").length).toBeGreaterThan(0);
    expect(screen.getByText("path:workspace")).toBeInTheDocument();
    expect(api.getAuditRecordDetail).toHaveBeenCalledWith({
      includeEvidence: true,
      includeSanitizedPayload: true,
      recordId: "record-action-1",
      sessionId: "session-website-plan",
    });
    expect(api.getEvidenceDetail).toHaveBeenCalledWith({
      evidenceId: "evidence-record-action-1",
      includeSanitizedPayload: true,
      sessionId: "session-website-plan",
    });
  });

  it("uses snapshot selected detail without calling the fallback detail query", async () => {
    const baseApi = createAuditMockApi("a4-record-selected");
    const api: AuditApi = {
      ...baseApi,
      getAuditRecordDetail: vi.fn(baseApi.getAuditRecordDetail),
    };

    renderWithQueryClient(
      <AuditPageRoute
        api={api}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "?recordId=record-file-1",
        }}
      />,
    );

    expect(await screen.findByText("File change linked detail body.")).toBeInTheDocument();
    expect(api.getAuditRecordDetail).not.toHaveBeenCalled();
  });

  it("closing detail clears selected record query state and returns to the list", async () => {
    const user = userEvent.setup();

    globalThis.history.pushState(
      null,
      "",
      "/sessions/session-website-plan/tasks/task-implementation/audit?recordId=record-action-1",
    );
    renderWithQueryClient(<AuditPageRoute api={createAuditMockApi("a3-records-ready")} />);

    expect(await screen.findByText("Action completed detail body.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Back to list" }));

    await waitFor(() => {
      expect(globalThis.location.search).toBe("?filter=all");
    });
    expect(screen.queryByLabelText("Audit record detail")).not.toBeInTheDocument();
  });

  it("renders partial disclosure reasons in record detail", async () => {
    renderWithQueryClient(
      <AuditPageRoute
        api={createAuditMockApi("a5-partial-evidence")}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "?recordId=record-partial-1",
        }}
      />,
    );

    expect(await screen.findByLabelText("Audit record detail")).toBeInTheDocument();
    expect(screen.getByText("Partial reason")).toBeInTheDocument();
    expect(screen.getByText("Evidence is incomplete.")).toBeInTheDocument();
    expect(screen.getAllByText("Partial").length).toBeGreaterThan(0);
  });

  it("renders hidden disclosure reasons in record detail", async () => {
    renderWithQueryClient(
      <AuditPageRoute
        api={createAuditMockApi("a6-hidden-evidence")}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "?recordId=record-hidden-1",
        }}
      />,
    );

    expect(await screen.findByLabelText("Audit record detail")).toBeInTheDocument();
    expect(screen.getAllByText("Hidden reason").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Evidence is permission-limited.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Hidden").length).toBeGreaterThan(0);
  });

  it.each([
    [
      "a1-audit-empty",
      ["Empty", "No audit records exist for this scope.", "No audit records yet"],
    ],
    [
      "a2-audit-loading",
      ["Loading", "Loading audit records.", "Running", "No audit records yet"],
    ],
    [
      "a5-partial-evidence",
      ["Partial evidence", "Some evidence is still loading.", "Verdict: Inconclusive"],
    ],
    [
      "a6-hidden-evidence",
      [
        "Hidden evidence",
        "Some evidence exists but is permission-limited.",
        "Verdict: Warning",
      ],
    ],
    [
      "a10-not-available",
      ["Empty", "Audit is not available for this draft task.", "Verdict: Not available"],
    ],
    [
      "a11-permission-denied",
      ["Permission denied", "Permission limited", "Audit permission denied."],
    ],
    [
      "a12-stale-snapshot",
      [
        "Stale snapshot",
        "Audit records changed after this snapshot.",
        "Refresh audit",
      ],
    ],
    [
      "a13-query-error",
      ["Recoverable error", "Audit query failed.", "Code: internal_error", "Retry"],
    ],
  ] satisfies Array<[AuditMockScenarioId, string[]]>)(
    "renders AP-005E boundary scenario %s",
    async (scenarioId, expectedTexts) => {
      renderWithQueryClient(
        <AuditPageRoute
          api={createAuditMockApi(scenarioId)}
          location={{
            pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
            search: "",
          }}
        />,
      );

      for (const text of expectedTexts) {
        expect((await screen.findAllByText(text)).length).toBeGreaterThan(0);
      }
      expect(screen.getByRole("button", { name: "Return" })).toBeInTheDocument();
    },
  );

  it("announces non-ready boundary changes as live status regions", async () => {
    renderWithQueryClient(
      <AuditPageRoute
        api={createAuditMockApi("a12-stale-snapshot")}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "",
        }}
      />,
    );

    const boundaryMessage = await screen.findByText(
      "Audit records changed after this snapshot.",
    );

    expect(boundaryMessage.closest('[role="status"]')).not.toBeNull();
  });

  it.each([
    [
      "a7-warning-verdict",
      "Audit found a non-blocking concern.",
      "Verdict: Warning",
    ],
    [
      "a8-failed-verdict",
      "Audit found a blocking issue.",
      "Verdict: Failed",
    ],
    [
      "a9-inconclusive-verdict",
      "Audit cannot establish confidence yet.",
      "Verdict: Inconclusive",
    ],
  ] satisfies Array<[AuditMockScenarioId, string, string]>)(
    "renders AP-005E verdict notice for %s",
    async (scenarioId, notice, verdict) => {
      renderWithQueryClient(
        <AuditPageRoute
          api={createAuditMockApi(scenarioId)}
          location={{
            pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
            search: "",
          }}
        />,
      );

      expect(await screen.findByText(notice)).toBeInTheDocument();
      expect(screen.getAllByText(verdict).length).toBeGreaterThan(0);
    },
  );

  it("isolates A14 evidence detail errors from the Audit Page snapshot", async () => {
    const baseApi = createAuditMockApi("a14-evidence-load-error");
    const api: AuditApi = {
      ...baseApi,
      getEvidenceDetail: vi.fn(baseApi.getEvidenceDetail),
    };

    renderWithQueryClient(
      <AuditPageRoute
        api={api}
        location={{
          pathname: "/sessions/session-website-plan/tasks/task-implementation/audit",
          search: "?filter=files&recordId=record-evidence-error-1",
        }}
      />,
    );

    expect(await screen.findByLabelText("Audit record detail")).toBeInTheDocument();
    expect(screen.getByLabelText("Audit records")).toBeInTheDocument();
    expect(
      await screen.findByText("Evidence detail could not be loaded: Evidence detail failed."),
    ).toBeInTheDocument();
    expect(api.getEvidenceDetail).toHaveBeenCalledWith({
      evidenceId: "evidence-record-evidence-error-1",
      includeSanitizedPayload: true,
      sessionId: "session-website-plan",
    });
  });

  it("renders an invalid route boundary", () => {
    renderWithQueryClient(
      <AuditPageRoute
        location={{
          pathname: "/not-audit",
          search: "",
        }}
      />,
    );

    expect(screen.getByText("Invalid Audit Page route.")).toBeInTheDocument();
  });
});

function renderWithQueryClient(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>,
  );
}
