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
    visible: ["TopBar", "SideNav", "EmptyState", "ContextInputBar"],
  }),
  mainScenario({
    fixtureId: "s2-understanding",
    title: "Authoring ASK / planning clarification",
    planning: "assessing",
    readiness: "unknown",
    execution: "not_started",
    primary: ["Submit all answers"],
    disabled: ["Publish", "Context input"],
    visible: ["TopBar", "AuthoringAskWorkArea", "DetailPanel", "ContextInputBar"],
  }),
  mainScenario({
    fixtureId: "s3-draft-ready",
    title: "Draft TaskTree ready",
    planning: "draft_ready",
    readiness: "draft",
    execution: "not_started",
    primary: ["Publish TaskTree"],
    disabled: [],
    visible: ["TaskTree", "MessageStream", "DetailPanel", "ContextInputBar"],
  }),
  mainScenario({
    fixtureId: "s4-task-selected",
    title: "TaskNode selected",
    planning: "draft_ready",
    readiness: "draft",
    execution: "not_started",
    primary: ["Edit task"],
    disabled: [],
    visible: ["TaskTree", "Selected TaskNode", "DetailPanel"],
  }),
  mainScenario({
    fixtureId: "s5-task-editing",
    title: "TaskNode editing",
    planning: "draft_ready",
    readiness: "draft",
    execution: "not_started",
    primary: ["Save guidance"],
    disabled: [],
    visible: ["TaskTree", "Task input", "DetailPanel"],
  }),
  mainScenario({
    fixtureId: "s6-running",
    title: "Published / running",
    planning: "published",
    readiness: "published",
    execution: "running",
    primary: ["Append guidance"],
    disabled: ["Publish TaskTree"],
    visible: ["TaskTree", "Running TaskNode", "MessageStream"],
  }),
  mainScenario({
    fixtureId: "s7-confirmation",
    title: "Waiting for confirmation",
    planning: "published",
    readiness: "published",
    execution: "running",
    confirmation: "pending",
    primary: ["Confirm baseline"],
    disabled: ["Duplicate submit"],
    visible: ["TaskTree", "ConfirmationPanel", "MessageStream"],
  }),
  mainScenario({
    fixtureId: "s8-completed",
    title: "Completed with result",
    planning: "published",
    readiness: "published",
    execution: "done",
    primary: ["Review result"],
    disabled: ["Cancel"],
    visible: ["ResultCard", "TaskTree", "ContextInputBar"],
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
    visible: ["FileChangeSummary", "AuditEntry", "TaskTree"],
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
    visible: ["ErrorState", "TaskTree", "Disabled input"],
    recovery: "Return to the previous valid state or wait for permission context.",
  }),
  mainScenario({
    fixtureId: "s11-stale-snapshot",
    title: "Stale snapshot / resync required",
    planning: "published",
    readiness: "published",
    execution: "running",
    permission: "disabled_stale",
    primary: ["Resync"],
    disabled: ["Publish", "Confirm", "Retry"],
    visible: ["Stale banner", "TaskTree", "Disabled input"],
    recovery: "Reload the MainPageSnapshot before allowing mutations.",
  }),
  mainScenario({
    fixtureId: "s12-backend-busy",
    title: "Backend busy / command accepted but delayed",
    planning: "published",
    readiness: "published",
    execution: "running",
    permission: "pending_command",
    primary: ["Wait for event"],
    disabled: ["Duplicate submit"],
    visible: ["Pending command notice", "TaskTree", "MessageStream"],
    recovery: "Keep current snapshot and wait for event or retry timeout.",
  }),
  mainScenario({
    fixtureId: "s13-command-failed",
    title: "Command failed / recoverable error",
    planning: "unknown",
    readiness: "published",
    execution: "failed",
    primary: ["Retry"],
    disabled: ["Duplicate submit"],
    visible: ["ErrorState", "TaskTree", "ContextInputBar"],
    recovery: "Retry the command or revise the task instruction.",
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
