import { useMemo, useState } from "react";

import type {
  SessionActivityItemKind,
  SessionActivityItemView,
  SessionActivityRefView,
  SessionActivitySideEffect,
  TaskNodeCardView,
} from "../../shared/api/types";
import type { BadgeTone } from "../../shared/components";
import { Badge, Button, MarkdownContent, Text } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import { cx } from "../../shared/utils/cx";
import styles from "./ActivityOverlay.module.css";

type ActivityFilter = "currentTask" | "all" | "results" | "errors";

export type ActivityOverlayStatusMessage = {
  body: string;
  tone: "danger" | "info";
};

export type ActivityOverlayProps = {
  errorMessage?: string | null;
  isLoading?: boolean;
  items: readonly SessionActivityItemView[];
  onClose: () => void;
  onOpenAudit?: (ref: SessionActivityRefView) => void;
  onOpenDiagnostic?: (ref: SessionActivityRefView) => void;
  onOpenFiles?: (taskNodeId: string | null) => void;
  onOpenPlan?: () => void;
  onOpenResult?: (taskNodeId: string | null) => void;
  onOpenTask?: (taskNodeId: string) => void;
  onRetry?: () => void;
  selectedTask: TaskNodeCardView | undefined;
  statusMessage?: ActivityOverlayStatusMessage | null;
};

export function ActivityOverlay({
  errorMessage = null,
  isLoading = false,
  items,
  onClose,
  onOpenAudit,
  onOpenDiagnostic,
  onOpenFiles,
  onOpenPlan,
  onOpenResult,
  onOpenTask,
  onRetry,
  selectedTask,
  statusMessage = null,
}: ActivityOverlayProps) {
  const uiText = useUiText();
  const [activeFilter, setActiveFilter] = useState<ActivityFilter>(
    selectedTask ? "currentTask" : "all",
  );
  const [readerItem, setReaderItem] = useState<SessionActivityItemView | null>(
    null,
  );
  const visibleItems = useMemo(
    () =>
      selectOverlayItems({
        activeFilter,
        items,
        selectedTaskNodeId: selectedTask?.id ?? null,
      }),
    [activeFilter, items, selectedTask?.id],
  );
  const overlayTitle = selectedTask
    ? uiText.main.activity.labels.taskUpdates
    : uiText.main.activity.labels.sessionActivity;

  return (
    <aside
      aria-label={overlayTitle}
      className={styles.overlay}
      role="dialog"
    >
      <div className={styles.header}>
        <div>
          <Text as="span" variant="eyebrow">
            {uiText.main.activity.labels.activity}
          </Text>
          <h2>{overlayTitle}</h2>
          <p className={styles.headerDescription}>
            {selectedTask
              ? uiText.main.activity.descriptions.focusedOnTask({
                  title: selectedTask.title,
                })
              : uiText.main.activity.descriptions.sessionUpdates}
          </p>
        </div>
        <Button onClick={onClose} size="sm" variant="secondary">
          {uiText.main.activity.actions.close}
        </Button>
      </div>

      <div
        aria-label={uiText.main.activity.labels.filterControls}
        className={styles.filters}
      >
        {(["currentTask", "all", "results", "errors"] as const).map(
          (filter) => (
            <button
              aria-pressed={activeFilter === filter}
              className={
                activeFilter === filter ? styles.activeFilter : styles.filter
              }
              disabled={filter === "currentTask" && !selectedTask}
              key={filter}
              onClick={() => setActiveFilter(filter)}
              type="button"
            >
              {uiText.main.activity.filters[filter]}
            </button>
          ),
        )}
      </div>

      <div className={styles.statusRegion}>
        {statusMessage ? (
          <div
            className={cx(
              styles.statusBanner,
              statusMessage.tone === "danger"
                ? styles.statusBannerDanger
                : styles.statusBannerInfo,
            )}
            role={statusMessage.tone === "danger" ? "alert" : "status"}
          >
            {statusMessage.body}
          </div>
        ) : null}
      </div>

      {readerItem ? (
        <ResultReader
          item={readerItem}
          onBack={() => setReaderItem(null)}
        />
      ) : errorMessage ? (
        <ActivityBoundary
          body={errorMessage}
          onRetry={onRetry}
          title={uiText.main.activity.descriptions.loadError}
        />
      ) : isLoading ? (
        <ActivityBoundary
          body={uiText.main.activity.descriptions.loading}
          title={uiText.main.activity.labels.loadingActivity}
        />
      ) : visibleItems.length === 0 ? (
        <div className={styles.emptyState}>
          <strong>{uiText.main.activity.labels.noMatchingActivity}</strong>
          <p>
            {selectedTask
              ? uiText.main.activity.descriptions.noMatchingWithTask
              : uiText.main.activity.descriptions.noMatchingWithoutTask}
          </p>
        </div>
      ) : (
        <ol className={styles.timeline}>
          {visibleItems.map((item) => (
            <ActivityItem
              item={item}
              key={item.id}
              onOpenAudit={onOpenAudit}
              onOpenDiagnostic={onOpenDiagnostic}
              onOpenFiles={onOpenFiles}
              onOpenPlan={onOpenPlan}
              onOpenReader={() => setReaderItem(item)}
              onOpenResult={onOpenResult}
              onOpenTask={onOpenTask}
            />
          ))}
        </ol>
      )}
    </aside>
  );
}

function ActivityItem({
  item,
  onOpenAudit,
  onOpenDiagnostic,
  onOpenFiles,
  onOpenPlan,
  onOpenReader,
  onOpenResult,
  onOpenTask,
}: {
  item: SessionActivityItemView;
  onOpenAudit?: (ref: SessionActivityRefView) => void;
  onOpenDiagnostic?: (ref: SessionActivityRefView) => void;
  onOpenFiles?: (taskNodeId: string | null) => void;
  onOpenPlan?: () => void;
  onOpenReader: () => void;
  onOpenResult?: (taskNodeId: string | null) => void;
  onOpenTask?: (taskNodeId: string) => void;
}) {
  const uiText = useUiText();
  const kind = activityKindPresentation(item.kind, uiText);
  const scopeLabel = activityScopeLabel(item, uiText);
  const isResult = item.kind === "result_ready";
  const isReadableArchivedPlan =
    item.kind === "plan_updated" && item.title === "Plan archived";

  return (
    <li className={cx(styles.activityItem, activityItemKindClass(item.kind))}>
      <div className={styles.itemHeader}>
        <Badge size="sm" tone={kind.tone}>
          {kind.label}
        </Badge>
        <time dateTime={item.occurredAt}>
          {formatActivityTime(item.occurredAt)}
        </time>
      </div>
      <strong className={styles.itemTitle} title={item.title}>
        {item.title}
      </strong>
      <MarkdownContent
        className={styles.itemBody}
        maxLines={3}
        source={item.body}
        variant="activity"
      />
      <div className={styles.itemFooter}>
        <div className={styles.itemMeta}>
          <Badge size="sm" tone={item.scopeKind === "task" ? "blue" : "neutral"}>
            {scopeLabel}
          </Badge>
          <Badge size="sm" tone="neutral">
            {activitySideEffectLabel(item.sideEffect, uiText)}
          </Badge>
          {isResult || isReadableArchivedPlan ? (
            <Button onClick={onOpenReader} size="sm" variant="ghost">
              {isResult
                ? uiText.main.activity.actions.viewFullResult
                : uiText.main.activity.actions.openPlan}
            </Button>
          ) : null}
        </div>
        <RelatedRefs
          item={item}
          onOpenAudit={onOpenAudit}
          onOpenDiagnostic={onOpenDiagnostic}
          onOpenFiles={onOpenFiles}
          onOpenPlan={onOpenPlan}
          onOpenResult={onOpenResult}
          onOpenTask={onOpenTask}
        />
      </div>
    </li>
  );
}

function RelatedRefs({
  item,
  onOpenAudit,
  onOpenDiagnostic,
  onOpenFiles,
  onOpenPlan,
  onOpenResult,
  onOpenTask,
}: {
  item: SessionActivityItemView;
  onOpenAudit?: (ref: SessionActivityRefView) => void;
  onOpenDiagnostic?: (ref: SessionActivityRefView) => void;
  onOpenFiles?: (taskNodeId: string | null) => void;
  onOpenPlan?: () => void;
  onOpenResult?: (taskNodeId: string | null) => void;
  onOpenTask?: (taskNodeId: string) => void;
}) {
  const uiText = useUiText();
  const controls = relatedControls({
    item,
    onOpenAudit,
    onOpenDiagnostic,
    onOpenFiles,
    onOpenPlan,
    onOpenResult,
    onOpenTask,
    uiText,
  });

  if (controls.length === 0) {
    return null;
  }

  return (
    <div
      aria-label={uiText.main.activity.labels.evidence}
      className={styles.relatedRefs}
    >
      {controls.map((control) => (
        control.href ? (
          <Button asChild key={control.key} size="sm" variant="ghost">
            <a href={control.href}>{control.label}</a>
          </Button>
        ) : (
          <Button
            key={control.key}
            onClick={control.onClick}
            size="sm"
            variant="ghost"
          >
            {control.label}
          </Button>
        )
      ))}
    </div>
  );
}

function relatedControls({
  item,
  onOpenAudit,
  onOpenDiagnostic,
  onOpenFiles,
  onOpenPlan,
  onOpenResult,
  onOpenTask,
  uiText,
}: {
  item: SessionActivityItemView;
  onOpenAudit?: (ref: SessionActivityRefView) => void;
  onOpenDiagnostic?: (ref: SessionActivityRefView) => void;
  onOpenFiles?: (taskNodeId: string | null) => void;
  onOpenPlan?: () => void;
  onOpenResult?: (taskNodeId: string | null) => void;
  onOpenTask?: (taskNodeId: string) => void;
  uiText: ReturnType<typeof useUiText>;
}) {
  const controls: Array<{
    key: string;
    label: string;
    href?: string | null;
    onClick?: () => void;
  }> = [];
  const hasRef = (kind: SessionActivityItemView["relatedRefs"][number]["kind"]) =>
    item.relatedRefs.some((ref) => ref.kind === kind);
  const firstRef = (
    kind: SessionActivityItemView["relatedRefs"][number]["kind"],
  ) => item.relatedRefs.find((ref) => ref.kind === kind);

  if (hasRef("plan") && onOpenPlan) {
    controls.push({
      key: "plan",
      label: uiText.main.activity.actions.openPlan,
      onClick: onOpenPlan,
    });
  }
  if (hasRef("task") && item.taskNodeId && onOpenTask) {
    controls.push({
      key: "task",
      label: uiText.main.activity.actions.openTask,
      onClick: () => onOpenTask(item.taskNodeId as string),
    });
  }
  if (hasRef("result") && onOpenResult) {
    controls.push({
      key: "result",
      label: uiText.main.activity.actions.openResult,
      onClick: () => onOpenResult(item.taskNodeId ?? null),
    });
  }
  const fileRef = firstRef("file");
  if (fileRef?.href) {
    controls.push({
      href: fileRef.href,
      key: "files",
      label: uiText.main.activity.actions.openFiles,
    });
  } else if (hasRef("file") && onOpenFiles) {
    controls.push({
      key: "files",
      label: uiText.main.activity.actions.openFiles,
      onClick: () => onOpenFiles(item.taskNodeId ?? null),
    });
  }
  const auditRef =
    item.relatedRefs.find(
      (ref) => ref.kind === "audit" && ref.href?.includes("evidenceId="),
    ) ?? firstRef("audit");
  if (auditRef?.href) {
    controls.push({
      href: auditRef.href,
      key: "audit",
      label: uiText.main.activity.actions.openAudit,
    });
  } else if (auditRef && onOpenAudit) {
    controls.push({
      key: "audit",
      label: uiText.main.activity.actions.openAudit,
      onClick: () => onOpenAudit(auditRef),
    });
  }
  const diagnosticRef = firstRef("diagnostic");
  if (diagnosticRef?.href) {
    controls.push({
      href: diagnosticRef.href,
      key: "diagnostic",
      label: uiText.main.activity.actions.openDiagnostic,
    });
  } else if (diagnosticRef && onOpenDiagnostic) {
    controls.push({
      key: "diagnostic",
      label: uiText.settings.actions.exportDiagnostics,
      onClick: () => onOpenDiagnostic(diagnosticRef),
    });
  }

  return controls;
}

function ResultReader({
  item,
  onBack,
}: {
  item: SessionActivityItemView;
  onBack: () => void;
}) {
  const uiText = useUiText();
  const isArchivedPlan =
    item.kind === "plan_updated" && item.title === "Plan archived";
  const readerLabel = isArchivedPlan
    ? "Plan details"
    : uiText.main.activity.labels.fullResult;

  return (
    <section
      aria-label={readerLabel}
      className={styles.reader}
    >
      <div className={styles.readerHeader}>
        <div>
          <Text as="span" variant="eyebrow">
            {readerLabel}
          </Text>
          <h3>{item.title}</h3>
        </div>
        <Button onClick={onBack} size="sm" variant="secondary">
          {uiText.main.activity.actions.backToActivity}
        </Button>
      </div>
      <article className={styles.readerBody}>
        <Badge size="sm" tone="blue">
          {isArchivedPlan ? "Plan" : uiText.main.activity.kinds.resultReady}
        </Badge>
        <MarkdownContent source={item.body} variant="detail" />
      </article>
    </section>
  );
}

function ActivityBoundary({
  body,
  onRetry,
  title,
}: {
  body: string;
  onRetry?: () => void;
  title: string;
}) {
  const uiText = useUiText();

  return (
    <div className={styles.emptyState}>
      <strong>{title}</strong>
      <p>{body}</p>
      {onRetry ? (
        <Button onClick={onRetry} size="sm" variant="secondary">
          {uiText.main.activity.actions.retry}
        </Button>
      ) : null}
    </div>
  );
}

function selectOverlayItems({
  activeFilter,
  items,
  selectedTaskNodeId,
}: {
  activeFilter: ActivityFilter;
  items: readonly SessionActivityItemView[];
  selectedTaskNodeId: string | null;
}) {
  const source =
    activeFilter === "currentTask" && selectedTaskNodeId !== null
      ? items.filter((item) => item.taskNodeId === selectedTaskNodeId)
      : items;
  const filtered =
    activeFilter === "errors"
      ? items.filter((item) => item.kind === "recovery_note")
      : activeFilter === "results"
        ? items.filter(
            (item) =>
              item.kind === "result_ready" || item.kind === "file_summary",
          )
        : source;

  return filtered
    .slice()
    .sort(
      (left, right) =>
        Date.parse(right.occurredAt) - Date.parse(left.occurredAt),
    );
}

function activityItemKindClass(kind: SessionActivityItemKind) {
  switch (kind) {
    case "ask_asked":
    case "confirmation_requested":
      return styles.activityItemActionable;
    case "recovery_note":
      return styles.activityItemError;
    case "answer":
    case "result_ready":
      return styles.activityItemResponse;
    default:
      return styles.activityItemInformational;
  }
}

function activityKindPresentation(
  kind: SessionActivityItemKind,
  uiText: ReturnType<typeof useUiText>,
): { label: string; tone: BadgeTone } {
  const labels = uiText.main.activity.kinds;
  switch (kind) {
    case "answer":
      return { label: labels.answer, tone: "success" };
    case "ask_answered":
      return { label: labels.askAnswered, tone: "success" };
    case "ask_asked":
      return { label: labels.askAsked, tone: "warning" };
    case "confirmation_requested":
      return { label: labels.confirmationRequested, tone: "warning" };
    case "confirmation_resolved":
      return { label: labels.confirmationResolved, tone: "success" };
    case "file_summary":
      return { label: labels.fileSummary, tone: "blue" };
    case "guidance_recorded":
      return { label: labels.guidanceRecorded, tone: "blue" };
    case "plan_updated":
      return { label: labels.planUpdated, tone: "blue" };
    case "recovery_note":
      return { label: labels.recoveryNote, tone: "danger" };
    case "result_ready":
      return { label: labels.resultReady, tone: "success" };
    case "router_interpretation":
      return { label: labels.routerInterpretation, tone: "blue" };
    case "task_changed":
      return { label: labels.taskChanged, tone: "blue" };
    case "task_created":
      return { label: labels.taskCreated, tone: "blue" };
    case "task_removed":
      return { label: labels.taskRemoved, tone: "warning" };
    case "user_input":
      return { label: labels.userInput, tone: "neutral" };
    case "execution_update":
    default:
      return { label: labels.executionUpdate, tone: "neutral" };
  }
}

function activityScopeLabel(
  item: SessionActivityItemView,
  uiText: ReturnType<typeof useUiText>,
) {
  if (item.scopeKind === "task") {
    return uiText.main.activity.labels.scopeTask;
  }
  if (item.scopeKind === "plan") {
    return uiText.main.activity.labels.scopePlan;
  }
  return uiText.main.activity.labels.scopeSession;
}

function activitySideEffectLabel(
  sideEffect: SessionActivitySideEffect,
  uiText: ReturnType<typeof useUiText>,
) {
  const labels = uiText.main.activity.sideEffects;
  switch (sideEffect) {
    case "authorization_effect":
      return labels.authorizationEffect;
    case "context_effect":
      return labels.contextEffect;
    case "evidence_effect":
      return labels.evidenceEffect;
    case "execution_request":
      return labels.executionRequest;
    case "resume_effect":
      return labels.resumeEffect;
    case "state_effect":
      return labels.stateEffect;
    case "no_effect":
    default:
      return labels.noEffect;
  }
}

function formatActivityTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    day: "2-digit",
  }).format(date);
}
