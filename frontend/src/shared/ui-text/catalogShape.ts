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
    detail: {
      actions: {
        backToList: string;
        openFile: string;
        viewDiff: string;
      };
      labels: {
        auditRecordDetail: string;
        disclosure: string;
        effectiveConfiguration: string;
        evidenceVisibility: string;
        hiddenReason: string;
        partialReason: string;
        permissionReason: string;
        rawPayload: string;
        recordPayload: string;
        redactionReason: string;
        relatedLogs: string;
        reservedLinks: string;
        sanitizedEvidence: string;
        sanitizedEvidencePayload: string;
        sanitizedRecordPayload: string;
        whatHappened: string;
        whyItMatters: string;
        workspaceEvidence: string;
      };
      messages: {
        availableByPolicy: string;
        configurationSummaryUnavailable: string;
        evidenceDetailLoadError: UiTextTemplate<{ message: string }>;
        evidenceDetailLoading: string;
        evidencePayloadTitle: UiTextTemplate<{ label: string }>;
        hiddenByDefault: string;
        hiddenByPermission: string;
        hiddenByPolicy: string;
        limited: string;
        loadingCompleteRecordDetail: string;
        noEvidenceForRecord: string;
        noPayloadAvailable: string;
        noRelatedLogLink: string;
        noSanitizedPayloadForRecord: string;
        payloadAvailableNotShown: string;
        recordDetailLoadError: UiTextTemplate<{ message: string }>;
        recordEventSummary: UiTextTemplate<{
          kind: string;
          source: string;
          time: string;
        }>;
        sanitizedPayloadShown: string;
        visible: string;
      };
    };
    empty: {
      noEvidence: string;
    };
    labels: {
      audit: string;
      auditEvidenceWorkspace: string;
      auditOverview: string;
      auditRecordFilters: string;
      auditRecords: string;
      auditVerdictNotice: string;
      auditWorkflow: string;
      code: string;
      cursor: string;
      confidence: UiTextTemplate<{ value: string }>;
      evidenceRefCount: UiTextTemplate<{ count: number }>;
      evidenceTimeline: string;
      filterCountsHelp: string;
      evidence: string;
      filter: string;
      keyIssue: string;
      noMutations: string;
      project: string;
      productSubtitle: string;
      readOnly: string;
      recordCount: UiTextTemplate<{ count: number }>;
      recordFilters: string;
      resyncSuggested: string;
      retryable: string;
      scope: UiTextTemplate<{ kind: string }>;
      sessionName: UiTextTemplate<{ name: string }>;
      session: string;
      task: string;
      taskAuthoring: string;
      taskPlanningExecution: string;
      trustPlane: string;
      visibleRecords: string;
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
      auditRecordEmptyBody: string;
      auditRecordEmptyTitle: string;
      evidenceTimelineHelp: string;
      loadingAudit: string;
      permissionLimited: string;
      readOnlyTrustPlane: string;
      snapshotUnavailable: string;
      unavailable: string;
    };
    scopeStatus: UiTextTemplate<{ kind: string; status: string }>;
    actors: Record<string, string>;
    confidenceLevels: Record<string, string>;
    flags: Record<string, string>;
    recordKinds: Record<string, string>;
    sourceLabels: Record<string, string>;
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
    activity: {
      actions: {
        backToActivity: string;
        close: string;
        openAudit: string;
        openDiagnostic: string;
        openFiles: string;
        openPlan: string;
        openResult: string;
        openTask: string;
        retry: string;
        viewFullResult: string;
      };
      descriptions: {
        focusedOnTask: UiTextTemplate<{ title: string }>;
        loadError: string;
        loading: string;
        noMatchingWithTask: string;
        noMatchingWithoutTask: string;
        sessionUpdates: string;
      };
      filters: {
        all: string;
        currentTask: string;
        errors: string;
        results: string;
      };
      labels: {
        activity: string;
        activityCount: UiTextTemplate<{ count: number }>;
        allActivity: string;
        currentTask: string;
        disclosure: string;
        effect: string;
        evidence: string;
        filterControls: string;
        fullResult: string;
        loadingActivity: string;
        noMatchingActivity: string;
        scopePlan: string;
        scopeSession: string;
        scopeTask: string;
        sessionActivity: string;
        source: string;
        taskUpdates: string;
      };
      kinds: {
        answer: string;
        askAnswered: string;
        askAsked: string;
        confirmationRequested: string;
        confirmationResolved: string;
        executionUpdate: string;
        fileSummary: string;
        guidanceRecorded: string;
        planUpdated: string;
        recoveryNote: string;
        resultReady: string;
        routerInterpretation: string;
        taskChanged: string;
        taskCreated: string;
        taskRemoved: string;
        userInput: string;
      };
      sideEffects: {
        authorizationEffect: string;
        contextEffect: string;
        evidenceEffect: string;
        executionRequest: string;
        noEffect: string;
        resumeEffect: string;
        stateEffect: string;
      };
    };
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
    interaction: {
      ask: {
        actions: {
          answer: string;
          answering: string;
          cancelQuestion: string;
          cancelling: string;
          defer: string;
          deferring: string;
        };
        labels: {
          answerText: string;
          optional: string;
          task: UiTextTemplate<{ title: string }>;
          taskInputRequired: string;
        };
        messages: {
          addMissingInformation: string;
          addYourAnswer: string;
          batchAnswerHeader: string;
          batchAnswerItem: UiTextTemplate<{
            answer: string;
            index: number;
            question: string;
          }>;
          chooseOption: string;
          chooseOptionOrEnterAnswer: string;
          enterAnswer: string;
          requiredQuestions: string;
          staleAsk: string;
        };
        statuses: Record<
          "answered" | "cancelled" | "deferred" | "expired" | "pending",
          string
        >;
      };
      confirmation: {
        actions: {
          confirm: string;
          resolveDecision: string;
          resolving: string;
          reviseTask: string;
          skip: string;
        };
        labels: {
          confirmationStatus: UiTextTemplate<{ status: string }>;
          decisionNeeded: string;
          decisionUnavailable: string;
          impact: string;
          resolvingDecision: string;
        };
        messages: {
          decisionReadOnly: string;
          executionWaits: string;
          selectOneOption: string;
        };
        statuses: Record<"expired" | "pending" | "resolved", string>;
      };
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
  usage: {
    actions: {
      openUsage: string;
      return: string;
    };
    dimensions: Record<"task" | "plan" | "session" | "workspace", string>;
    dimensionHelp: Record<"task" | "plan" | "session" | "workspace", string>;
    labels: {
      cacheHitRate: string;
      calls: string;
      inputOutput: string;
      reasoningTokens: string;
      tokenUsage: string;
      tokenUsageBudget: string;
      totalTokens: string;
      unknownUsage: string;
      usage: string;
      workspaceId: UiTextTemplate<{ id: string }>;
    };
    messages: {
      compactHelp: string;
      highUsageWarning: string;
      highUsageWarningTitle: UiTextTemplate<{ threshold: string }>;
      workspaceUsageHelp: string;
    };
    states: {
      cacheUnavailable: string;
      noBreakdownRows: string;
      noUsageTracked: string;
      notReported: string;
      routeUnavailable: string;
      routeUnavailableBody: string;
      sidecarRequired: string;
      summaryUnavailable: string;
    };
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
    tabs: {
      configuration: string;
      dataManagement: string;
      runtimeBehavior: string;
      usageInformation: string;
    };
    fields: {
      apiKey: string;
      bundle: string;
      defaultProfile: string;
      diagnostics: string;
      gitAvailability: string;
      initializeGitForOpenedWorkspaces: string;
      interfaceLanguage: string;
      logging: string;
      loggingProfile: string;
      model: string;
      provider: string;
      readiness: string;
      webFetch: string;
      webFetchMaxCharsPerUrl: string;
      webFetchMaxTotalChars: string;
      webFetchMaxUrls: string;
      webSearch: string;
      webSearchApiKey: string;
      webSearchMaxResults: string;
      webSearchMode: string;
      webSearchProvider: string;
      webSearchStatus: string;
    };
    labels: {
      blockingIssues: string;
      checkingSetup: string;
      completeFirstRunSetup: string;
      computerUseAccessibility: string;
      computerUseBackend: string;
      computerUseExecutable: string;
      computerUseFailureKind: string;
      computerUseHelperApp: string;
      computerUseReadiness: string;
      computerUseRecoveryActions: string;
      computerUseSignature: string;
      computerUseStatus: string;
      configured: string;
      degradedReady: string;
      diagnosticsAvailable: string;
      diagnosticsUnavailable: string;
      editable: string;
      firstRun: string;
      firstRunReady: string;
      gitAvailable: string;
      gitFailed: string;
      gitMissing: string;
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
      webSearchReady: string;
      warnings: string;
      workspaceGit: string;
      zipPath: string;
    };
    messages: {
      apiKeyConfigured: UiTextTemplate<{ source: string }>;
      apiKeyRequired: UiTextTemplate<{ hint: string }>;
      checkingReadiness: string;
      checkingSidecarReadiness: string;
      checkingGitAvailability: string;
      diagnosticExportFailed: string;
      diagnosticExportHelp: string;
      gitAvailable: UiTextTemplate<{ version: string }>;
      gitFailedHelp: string;
      gitMissingHelp: string;
      initializeGitForOpenedWorkspacesHelp: string;
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
      webSearchApiKeyConfigured: UiTextTemplate<{ source: string }>;
      webSearchApiKeyRequired: UiTextTemplate<{ hint: string }>;
      webFetchDescription: string;
      webSearchDescription: string;
      workspaceGitDesktopUnavailable: string;
    };
    localeOptions: Record<UiLocale, string>;
    recovery: Record<ProductRecoveryAction, string>;
  };
  workspace: {
    actions: {
      archiveWorkspace: string;
      cancelDelete: string;
      confirmDeletePlatoData: string;
      deletePlatoData: string;
      openWorkspaceMenu: string;
      openOrAddWorkspace: string;
      restoreWorkspace: string;
      workspaceManagement: string;
    };
    labels: {
      activeWorkspaces: string;
      archived: string;
      archivedWorkspaces: string;
      dataManagement: string;
      deletePlatoData: string;
      workspace: string;
      workspaceManagement: string;
      workspaces: string;
    };
    messages: {
      archiveHelp: string;
      bridgeUnavailable: string;
      deletePlatoDataConfirmation: UiTextTemplate<{ name: string }>;
      deletePlatoDataHelp: string;
      lifecycleActionFailed: string;
      loadingWorkspaces: string;
      noArchivedWorkspaces: string;
      noWorkspaceData: string;
      restoreHelp: string;
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
      localToolFiles: string;
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
      localNoiseSuppressed: UiTextTemplate<{ count: number }>;
      readOnly: string;
      requiresSidecar: string;
      statusUnavailable: string;
    };
  };
};
