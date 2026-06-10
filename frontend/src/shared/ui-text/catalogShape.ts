import type { ProductRecoveryAction } from "../api/platoApi";
import type {
  AuditCompleteness,
  AuditFilterKind,
  AuditVerdict,
} from "../api/types";

export type UiLocale = "en-US" | "zh-CN";

export type UiTextTemplate<
  TParams extends Record<string, string | number>,
> = (params: TParams) => string;

export type UiTextCatalog = {
  audit: {
    actions: {
      refreshAudit: string;
      return: string;
      viewAudit: string;
    };
    empty: {
      noEvidence: string;
    };
    labels: {
      audit: string;
      auditEvidenceWorkspace: string;
      auditWorkflow: string;
      evidence: string;
      filter: string;
      noMutations: string;
      project: string;
      readOnly: string;
      scope: UiTextTemplate<{ kind: string }>;
      sessionName: UiTextTemplate<{ name: string }>;
      trustPlane: string;
    };
    boundary: Record<string, string>;
    completeness: Record<AuditCompleteness, string>;
    filters: Record<AuditFilterKind, string>;
    liveStatus: {
      disconnectedMessage: string;
      disconnectedTitle: string;
      refreshingMessage: string;
      refreshingTitle: string;
      staleMessage: string;
      staleTitle: string;
    };
    messages: {
      loadingAudit: string;
      permissionLimited: string;
      readOnlyTrustPlane: string;
      snapshotUnavailable: string;
      unavailable: string;
    };
    scopeStatus: UiTextTemplate<{ kind: string; status: string }>;
    verdict: Record<AuditVerdict, string>;
    verdictNotice: Partial<Record<AuditVerdict, string>>;
  };
  common: {
    actions: {
      cancel: string;
      close: string;
      retry: string;
    };
    status: {
      creating: string;
      disabled: string;
      failed: string;
      loading: string;
      ready: string;
    };
  };
  diagnostics: {
    actions: {
      exportBundle: string;
      returnToAudit: string;
      returnToSession: string;
    };
    labels: {
      auditRecord: string;
      bundle: string;
      bundleReady: string;
      diagnosticExportResult: string;
      diagnostics: string;
      exportBundle: string;
      manifest: string;
      readOnly: string;
      redaction: string;
      session: string;
      task: string;
      zipPath: string;
    };
    messages: {
      contextUnavailable: string;
      exportBody: string;
      exportFailed: string;
      fileCount: UiTextTemplate<{ count: number }>;
      handoffReady: string;
      includedSections: UiTextTemplate<{ sections: string }>;
      noSections: string;
      sidecarRequired: string;
      warningCount: UiTextTemplate<{ count: number }>;
    };
  };
  main: {
    actions: {
      createSession: string;
      copySessionId: string;
      deleteSession: string;
      newSession: string;
      openSession: string;
      publishPlan: string;
      renameSession: string;
      repairAuthoringState: string;
    };
    empty: {
      createFirstSessionBody: string;
      createFirstSessionTitle: string;
      noPlanBody: string;
      noPlanTitle: string;
    };
    input: {
      contextMessageAriaLabel: string;
      sendMessageAriaLabel: string;
      writingToPrefix: string;
      writingTo: UiTextTemplate<{ target: string }>;
    };
    labels: {
      noSessions: string;
      noSessionSelected: string;
      sessionActions: string;
      sessionName: UiTextTemplate<{ name: string }>;
      taskWorkspace: string;
      workspaceSessions: string;
    };
    plan: {
      defaultTitle: string;
      generatingBody: string;
      generatingTitle: string;
      overviewLabel: string;
      overviewPrepared: string;
      overviewSummary: UiTextTemplate<{
        count: number;
        remainingCount: number;
        titles: string;
      }>;
      taskCount: UiTextTemplate<{ count: number }>;
    };
    repair: {
      authoringStateNeedsRepair: string;
      repairing: string;
    };
    sessionDialog: {
      createFormAriaLabel: string;
      createTitle: string;
      deleteConfirmationAriaLabel: string;
      deleteConfirmationBody: UiTextTemplate<{ name: string }>;
      deleteTitle: string;
      deleting: string;
      renameFormAriaLabel: string;
      renameTitle: string;
      renaming: string;
      sessionName: string;
    };
    states: {
      creatingSession: string;
      creatingSessionFull: string;
      loadError: string;
      openingSessionBody: string;
      openingSessionTitle: string;
      publishingPlan: string;
      unableToOpenSessionBody: string;
      unableToOpenSessionTitle: string;
      workspaceSwitchFailed: string;
      workspaceSwitchUnavailable: string;
      workspaceSwitching: string;
    };
  };
  productError: {
    recoveryAriaLabel: string;
    recovery: Record<
      ProductRecoveryAction,
      {
        description: string;
        label: string;
      }
    >;
  };
  settings: {
    actions: {
      configureSettings: string;
      continueToMainPage: string;
      closeSettings: string;
      exportDiagnostics: string;
      exportingDiagnostics: string;
      openSettings: string;
      retryCheck: string;
      retryLoad: string;
      return: string;
      saveAndCheck: string;
    };
    fields: {
      apiKey: string;
      bundle: string;
      defaultProfile: string;
      diagnostics: string;
      logging: string;
      loggingProfile: string;
      model: string;
      provider: string;
      readiness: string;
    };
    labels: {
      blockingIssues: string;
      checkingSetup: string;
      completeFirstRunSetup: string;
      configured: string;
      degradedReady: string;
      diagnosticsAvailable: string;
      diagnosticsUnavailable: string;
      editable: string;
      firstRun: string;
      firstRunReady: string;
      localSetup: string;
      missing: string;
      missingEnvironmentVariables: string;
      noDiagnosticSession: string;
      notChecked: string;
      notCreated: string;
      readinessIssues: string;
      readinessResult: string;
      recommendedActions: string;
      setupCheckUnavailable: string;
      setupRequired: string;
      setupWarning: string;
      settings: string;
      settingsSetupForm: string;
      settingsUnavailable: string;
      sidecarRequired: string;
      warnings: string;
      zipPath: string;
    };
    messages: {
      apiKeyConfigured: UiTextTemplate<{ source: string }>;
      apiKeyRequired: UiTextTemplate<{ hint: string }>;
      checkingReadiness: string;
      checkingSidecarReadiness: string;
      diagnosticExportFailed: string;
      diagnosticExportHelp: string;
      loadingSettings: string;
      loadingSettingsHelp: string;
      localSetupReadyWithWarnings: string;
      noReadinessReport: string;
      noDiagnosticSession: string;
      readinessRecheckFailed: string;
      saveFailed: string;
      saved: string;
      saving: string;
      settingsContractUnavailable: string;
      settingsDescription: string;
      settingsUnavailableHelp: string;
      setupRequiredBody: string;
    };
    recovery: Record<ProductRecoveryAction, string>;
  };
  workspace: {
    actions: {
      openOrAddWorkspace: string;
    };
    labels: {
      workspace: string;
      workspaces: string;
    };
  };
  workspaceInspection: {
    actions: {
      openFile: string;
      refresh: string;
      return: string;
      viewDiff: string;
    };
    labels: {
      captured: string;
      changed: string;
      changedFiles: string;
      clean: string;
      diff: string;
      fileContent: string;
      file: string;
      fileDiff: string;
      fileViewer: string;
      gitStatus: string;
      inspectionViews: string;
      live: string;
      mixed: string;
      repository: string;
      staged: string;
      truncated: string;
      unstaged: string;
      untracked: string;
      workspaceInspection: string;
    };
    states: {
      cleanBody: string;
      diffUnavailable: UiTextTemplate<{ reason: string }>;
      diffUnavailableTitle: string;
      fileUnavailable: UiTextTemplate<{ reason: string }>;
      fileUnavailableTitle: string;
      inspectionFailed: string;
      inspectionUnavailable: string;
      inspectionRouteUnavailable: string;
      inspectionRouteUnavailableBody: string;
      loading: string;
      readOnly: string;
      requiresSidecar: string;
      statusUnavailable: string;
    };
  };
};
