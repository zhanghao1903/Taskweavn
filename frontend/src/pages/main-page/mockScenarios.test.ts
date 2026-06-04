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
