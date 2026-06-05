import { describe, expect, it } from "vitest";

import {
  getMainPageMockScenarioSnapshot,
  listMainPageMockScenarios,
} from "./mockScenarios";

describe("Main Page mock scenarios", () => {
  it("declares the P6.2 Main Page happy and recovery scenarios", () => {
    expect(listMainPageMockScenarios().map((scenario) => scenario.id)).toEqual([
      "s1-empty",
      "s2-understanding",
      "s3-draft-ready",
      "s4-task-selected",
      "s5-task-editing",
      "s6-running",
      "s7-confirmation",
      "s8-completed",
      "s9-file-changes",
      "s10-permission-denied",
      "s11-stale-snapshot",
      "s12-backend-busy",
      "s13-command-failed",
      "s14-execution-ask",
    ]);
  });

  it("loads a valid MainPageSnapshot for every manifest", () => {
    for (const scenario of listMainPageMockScenarios()) {
      const { snapshot } = getMainPageMockScenarioSnapshot(scenario.id);

      expect(snapshot.session.id).toBe("session-website-plan");
      expect(snapshot.planning?.state).toBe(scenario.canonicalStates.planning);
      expect(snapshot.cursor).toBe(`cursor-${scenario.fixtureId}`);
      expect(scenario.expectedVisibleComponents.length).toBeGreaterThan(0);
    }
  });

  it("keeps scenario manifest labels free of internal implementation language", () => {
    const scenarioCopy = listMainPageMockScenarios().flatMap((scenario) => [
      scenario.title,
      ...scenario.expectedVisibleComponents,
      ...scenario.expectedPrimaryActions,
      ...scenario.expectedDisabledActions,
      scenario.expectedRecoveryBehavior ?? undefined,
    ]);

    const manifestCopy = scenarioCopy.filter(Boolean).join("\n");

    expect(manifestCopy).not.toMatch(
      /TaskTree|task tree|TaskNode|AuthoringAskWorkArea|ExecutionAskDetailPanel|ConfirmationDetailPanel|ResultCard|ContextInputBar|LatestActivity|FileChangeSummary|AuditEntry|ErrorState|Context inspector|TopBar|SideNav|EmptyState|DetailPanel|backend|command|projection|snapshot/i,
    );
    expect(manifestCopy).not.toMatch(/\bASK\b/);
  });

  it("declares interaction scenarios for questions, confirmations, and stale states", () => {
    const scenarios = listMainPageMockScenarios();

    expect(scenarios.find((item) => item.id === "s2-understanding")).toMatchObject({
      expectedDisabledActions: expect.arrayContaining(["Context input"]),
      expectedPrimaryActions: ["Submit all answers"],
      expectedVisibleComponents: expect.arrayContaining(["Planning questions"]),
    });
    expect(scenarios.find((item) => item.id === "s7-confirmation")).toMatchObject({
      expectedDisabledActions: expect.arrayContaining(["Duplicate submit"]),
      expectedVisibleComponents: expect.arrayContaining([
        "Confirmation details",
      ]),
    });
    expect(scenarios.find((item) => item.id === "s11-stale-snapshot")).toMatchObject({
      expectedDisabledActions: expect.arrayContaining(["Confirm", "Retry"]),
      expectedVisibleComponents: expect.arrayContaining(["Sync banner"]),
    });
    expect(scenarios.find((item) => item.id === "s14-execution-ask")).toMatchObject({
      canonicalStates: expect.objectContaining({
        execution: "waiting_for_user",
      }),
      expectedPrimaryActions: ["Answer question"],
      expectedVisibleComponents: expect.arrayContaining([
        "Task question",
      ]),
    });
  });

  it("projects question fixtures through the same MainPageSnapshot contract", () => {
    const { snapshot: authoringSnapshot } =
      getMainPageMockScenarioSnapshot("s2-understanding");
    const { snapshot: executionSnapshot } =
      getMainPageMockScenarioSnapshot("s14-execution-ask");

    expect(authoringSnapshot.planning?.asks).toHaveLength(2);
    expect(authoringSnapshot.activeAsk).toBeNull();
    expect(executionSnapshot.pendingAsks).toHaveLength(1);
    expect(executionSnapshot.activeAsk).toMatchObject({
      id: "ask-deployment-target",
      status: "pending",
    });
  });

  it("keeps explicit Audit entry routes for result and file-change scenarios", () => {
    const scenarios = listMainPageMockScenarios();

    expect(scenarios.find((item) => item.id === "s8-completed")).toMatchObject({
      auditEntryRoute: expect.stringContaining("/audit?entry=from_result"),
    });
    expect(scenarios.find((item) => item.id === "s9-file-changes")).toMatchObject({
      auditEntryRoute: expect.stringContaining("filter=files"),
    });
  });
});
