import {
  buildAuditSessionRoute,
  buildAuditTaskRoute,
  buildMainSessionFallbackRoute,
} from "../../app/routes";
import type {
  AuditVerdict,
  ExecutionStatus,
  MockScenarioManifest,
  PlanningState,
  TaskNodeReadiness,
} from "../../shared/api/types";
import {
  getMainPageMockSnapshot,
  type MainPageMockSnapshot,
} from "./mockPlatoApi";
import type { MainPageStateId } from "./fixtures";

export type MainPageMockScenario = MockScenarioManifest<MainPageStateId> & {
  auditEntryRoute?: string;
};

export const mainPageMockScenarios: readonly MainPageMockScenario[] = [
  mainScenario({
    fixtureId: "s1-empty",
    title: "Empty new session",
    planning: "empty",
    readiness: "unknown",
    execution: "not_started",
    primary: ["Start"],
    disabled: ["Publish", "Audit"],
    visible: ["Header", "Workspace navigation", "Empty plan", "Context input"],
  }),
  mainScenario({
    fixtureId: "s2-understanding",
    title: "Planning questions / clarification",
    planning: "assessing",
    readiness: "unknown",
    execution: "not_started",
    primary: ["Submit all answers"],
    disabled: ["Publish", "Context input"],
    visible: ["Header", "Planning questions", "Details", "Context input"],
  }),
  mainScenario({
    fixtureId: "s3-draft-ready",
    title: "Draft task plan ready",
    planning: "draft_ready",
    readiness: "draft",
    execution: "not_started",
    primary: ["Publish task plan"],
    disabled: [],
    visible: ["Task plan", "Latest activity", "Details", "Context input"],
  }),
  mainScenario({
    fixtureId: "s4-task-selected",
    title: "Task selected",
    planning: "draft_ready",
    readiness: "draft",
    execution: "not_started",
    primary: ["Edit task"],
    disabled: [],
    visible: ["Task plan", "Selected task", "Details"],
  }),
  mainScenario({
    fixtureId: "s5-task-editing",
    title: "Task editing",
    planning: "draft_ready",
    readiness: "draft",
    execution: "not_started",
    primary: ["Save guidance"],
    disabled: [],
    visible: ["Task plan", "Task input", "Details"],
  }),
  mainScenario({
    fixtureId: "s6-running",
    title: "Published / running",
    planning: "published",
    readiness: "published",
    execution: "running",
    primary: ["Append guidance"],
    disabled: ["Publish task plan"],
    visible: ["Task plan", "Running task", "Latest activity"],
  }),
  mainScenario({
    fixtureId: "s7-confirmation",
    title: "Waiting for confirmation",
    planning: "published",
    readiness: "published",
    execution: "running",
    confirmation: "pending",
    primary: ["Confirm baseline"],
    disabled: ["Repeated action"],
    visible: ["Task plan", "Confirmation details", "Latest activity"],
  }),
  mainScenario({
    fixtureId: "s8-completed",
    title: "Completed with result",
    planning: "published",
    readiness: "published",
    execution: "done",
    primary: ["Review result"],
    disabled: ["Cancel"],
    visible: ["Result summary", "Task plan", "Context input"],
    auditEntryRoute: buildAuditSessionRoute("session-website-plan", {
      entry: "from_result",
      returnFocus: "result",
    }),
  }),
  mainScenario({
    fixtureId: "s9-file-changes",
    title: "File change summary / audit entry",
    planning: "published",
    readiness: "published",
    execution: "done",
    auditVerdict: "warning",
    primary: ["View audit"],
    disabled: [],
    visible: ["File changes", "Audit entry", "Task plan"],
    auditEntryRoute: buildAuditTaskRoute("session-website-plan", "task-implementation", {
      entry: "from_file_change",
      filter: "files",
      returnFocus: "file_change",
      returnTaskNodeId: "task-implementation",
    }),
  }),
  mainScenario({
    fixtureId: "s10-permission-denied",
    title: "Permission denied",
    planning: "draft_ready",
    readiness: "draft",
    execution: "not_started",
    permission: "disabled_permission",
    primary: ["Return"],
    disabled: ["Edit", "Publish"],
    visible: ["Error state", "Task plan", "Disabled input"],
    recovery: "Return to the previous valid state or wait for permissions to change.",
  }),
  mainScenario({
    fixtureId: "s11-stale-snapshot",
    title: "Sync required / refresh before continuing",
    planning: "published",
    readiness: "published",
    execution: "running",
    permission: "disabled_stale",
    primary: ["Resync"],
    disabled: ["Publish", "Confirm", "Retry"],
    visible: ["Sync banner", "Task plan", "Disabled input"],
    recovery: "Refresh the session state before allowing changes.",
  }),
  mainScenario({
    fixtureId: "s12-backend-busy",
    title: "Update pending / accepted but delayed",
    planning: "published",
    readiness: "published",
    execution: "running",
    permission: "pending_command",
    primary: ["Wait for event"],
    disabled: ["Repeated action"],
    visible: ["Pending update notice", "Task plan", "Latest activity"],
    recovery: "Keep the current task plan visible and wait for the next update.",
  }),
  mainScenario({
    fixtureId: "s13-command-failed",
    title: "Action needs retry / recoverable error",
    planning: "unknown",
    readiness: "published",
    execution: "failed",
    primary: ["Retry"],
    disabled: ["Repeated action"],
    visible: ["Error state", "Task plan", "Context input"],
    recovery: "Retry the last action or revise the task instruction.",
  }),
  mainScenario({
    fixtureId: "s14-execution-ask",
    title: "Task input waiting for answer",
    planning: "published",
    readiness: "published",
    execution: "waiting_for_user",
    primary: ["Answer question"],
    disabled: ["Repeated action"],
    visible: ["Task plan", "Task question", "Latest activity"],
    recovery: "Answer, defer, or cancel the question and wait for Plato to update the task.",
  }),
];

export function listMainPageMockScenarios(): readonly MainPageMockScenario[] {
  return mainPageMockScenarios;
}

export function getMainPageMockScenario(
  scenarioId: string,
): MainPageMockScenario {
  return (
    mainPageMockScenarios.find((scenario) => scenario.id === scenarioId) ??
    mainPageMockScenarios[0]
  );
}

export function getMainPageMockScenarioSnapshot(
  scenarioId: string,
): MainPageMockSnapshot {
  return getMainPageMockSnapshot(getMainPageMockScenario(scenarioId).fixtureId);
}

function mainScenario({
  auditEntryRoute,
  auditVerdict = "not_available",
  confirmation,
  disabled,
  execution,
  fixtureId,
  permission = "enabled",
  planning,
  primary,
  readiness,
  recovery = null,
  title,
  visible,
}: {
  auditEntryRoute?: string;
  auditVerdict?: AuditVerdict;
  confirmation?: "pending" | "resolved" | "expired";
  disabled: string[];
  execution: ExecutionStatus;
  fixtureId: MainPageStateId;
  permission?: "enabled" | "disabled_permission" | "disabled_stale" | "pending_command";
  planning: PlanningState;
  primary: string[];
  readiness: TaskNodeReadiness;
  recovery?: string | null;
  title: string;
  visible: string[];
}): MainPageMockScenario {
  const route = buildMainSessionFallbackRoute({
    sessionId: "session-website-plan",
  });

  return {
    auditEntryRoute,
    canonicalStates: {
      auditVerdict,
      confirmation,
      execution,
      permission,
      planning,
      readiness,
    },
    expectedDisabledActions: disabled,
    expectedPrimaryActions: primary,
    expectedRecoveryBehavior: recovery,
    expectedVisibleComponents: visible,
    fixtureId,
    id: fixtureId,
    page: "main",
    route,
    title,
  };
}
