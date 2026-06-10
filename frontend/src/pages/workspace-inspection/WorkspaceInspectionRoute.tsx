import { useEffect, useMemo, useState, type ReactNode } from "react";

import { navigateApp } from "../../app/navigation";
import type { PlatoRuntimeEnv } from "../../app/platoRuntime";
import {
  buildMainSessionFallbackRoute,
  buildWorkspaceInspectionRoute,
} from "../../app/routes";
import { Badge, Button, Panel, Text } from "../../shared/components";
import { useUiText, type UiTextCatalog } from "../../shared/ui-text";
import type {
  WorkspaceChangedFile,
  WorkspaceDiffResponse,
  WorkspaceFileContentResponse,
  WorkspaceGitStatusResponse,
  WorkspaceInspectionApi,
  WorkspaceInspectionWarning,
} from "../../shared/api/workspaceInspectionApi";
import { createHttpWorkspaceInspectionApi } from "../../shared/api/workspaceInspectionApi";
import type { WorkspaceInspectionRouteLocation } from "./workspaceInspectionRouteModel";
import {
  parseWorkspaceInspectionLocation,
  type WorkspaceInspectionRouteContext,
} from "./workspaceInspectionRouteModel";
import styles from "./WorkspaceInspectionRoute.module.css";

export type WorkspaceInspectionRouteProps = {
  api?: WorkspaceInspectionApi | null;
  location?: WorkspaceInspectionRouteLocation;
  runtimeEnv?: PlatoRuntimeEnv;
};

type InspectionState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "status"; status: WorkspaceGitStatusResponse }
  | { kind: "file"; file: WorkspaceFileContentResponse }
  | { kind: "diff"; diff: WorkspaceDiffResponse };

export function WorkspaceInspectionRoute({
  api,
  location,
  runtimeEnv = import.meta.env,
}: WorkspaceInspectionRouteProps = {}) {
  const uiText = useUiText();
  const resolvedLocation = location ?? globalThis.location;
  const context = useMemo(
    () =>
      parseWorkspaceInspectionLocation(
        resolvedLocation.pathname,
        resolvedLocation.search,
      ),
    [resolvedLocation.pathname, resolvedLocation.search],
  );
  const inspectionApi = useMemo(
    () => api ?? createInspectionApi(runtimeEnv),
    [api, runtimeEnv],
  );
  const [state, setState] = useState<InspectionState>({ kind: "loading" });
  const [reloadNonce, setReloadNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (context === null) {
        setState({
          kind: "error",
          message: uiText.workspaceInspection.states.inspectionRouteUnavailable,
        });
        return;
      }
      if (inspectionApi === null) {
        setState({
          kind: "error",
          message: uiText.workspaceInspection.states.requiresSidecar,
        });
        return;
      }

      setState({ kind: "loading" });
      try {
        if (context.mode === "status") {
          const response = await inspectionApi.getStatus({
            workspaceId: context.workspaceId,
          });
          if (!response.ok || response.data === null) {
            throw new Error(
              response.error?.message ??
                uiText.workspaceInspection.states.statusUnavailable,
            );
          }
          if (!cancelled) {
            setState({ kind: "status", status: response.data });
          }
          return;
        }

        if (context.mode === "diff") {
          if (context.path === null) {
            throw new Error(uiText.workspaceInspection.states.diffUnavailable({
              reason: "missing path",
            }));
          }
          const response = await inspectionApi.getDiff({
            path: context.path,
            workspaceId: context.workspaceId,
          });
          if (!response.ok || response.data === null) {
            throw new Error(
              response.error?.message ??
                uiText.workspaceInspection.states.diffUnavailable({
                  reason: "unknown",
                }),
            );
          }
          if (!cancelled) {
            setState({ kind: "diff", diff: response.data });
          }
          return;
        }

        const response = await inspectionApi.getFileContent({
          evidenceId: context.evidenceId ?? undefined,
          path: context.path ?? undefined,
          workspaceId: context.workspaceId,
        });
        if (!response.ok || response.data === null) {
          throw new Error(
            response.error?.message ??
              uiText.workspaceInspection.states.fileUnavailable({
                reason: "unknown",
              }),
          );
        }
        if (!cancelled) {
          setState({ kind: "file", file: response.data });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            kind: "error",
            message:
              error instanceof Error
                ? error.message
                : uiText.workspaceInspection.states.inspectionFailed,
          });
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [context, inspectionApi, reloadNonce, uiText]);

  if (context === null) {
    return (
      <InspectionShell
        context={null}
        title={uiText.workspaceInspection.labels.workspaceInspection}
      >
        <EmptyState
          actionLabel={uiText.workspaceInspection.actions.return}
          message={uiText.workspaceInspection.states.inspectionRouteUnavailableBody}
          onAction={() => navigateApp("/")}
          title={uiText.workspaceInspection.states.inspectionRouteUnavailable}
        />
      </InspectionShell>
    );
  }

  return (
    <InspectionShell
      context={context}
      title={titleForContext(context, uiText)}
    >
      <InspectionTabs context={context} />
      {state.kind === "loading" ? (
        <EmptyState
          message={uiText.workspaceInspection.states.loading}
          title={uiText.common.status.loading}
        />
      ) : state.kind === "error" ? (
        <EmptyState
          actionLabel={uiText.common.actions.retry}
          message={state.message}
          onAction={() => setReloadNonce((value) => value + 1)}
          title={uiText.workspaceInspection.states.inspectionUnavailable}
        />
      ) : state.kind === "status" ? (
        <StatusView context={context} status={state.status} />
      ) : state.kind === "file" ? (
        <FileView file={state.file} />
      ) : (
        <DiffView diff={state.diff} />
      )}
    </InspectionShell>
  );
}

function InspectionShell({
  children,
  context,
  title,
}: {
  children: ReactNode;
  context: WorkspaceInspectionRouteContext | null;
  title: string;
}) {
  const uiText = useUiText();
  const returnPath =
    context?.returnSessionId || context?.sessionId
      ? buildMainSessionFallbackRoute({
          sessionId: context.returnSessionId ?? context.sessionId ?? "",
          taskNodeId: context.returnTaskNodeId ?? context.taskNodeId ?? undefined,
        })
      : "/";

  return (
    <main className={styles.page}>
      <section
        className={styles.shell}
        aria-label={uiText.workspaceInspection.labels.workspaceInspection}
      >
        <header className={styles.header}>
          <div>
            <Text variant="eyebrow">
              {uiText.workspaceInspection.labels.workspaceInspection}
            </Text>
            <h1>{title}</h1>
            <p>
              {context === null
                ? uiText.workspaceInspection.states.readOnly
                : context.path ?? context.evidenceId ?? context.workspaceId}
            </p>
          </div>
          <div className={styles.headerActions}>
            {context !== null ? (
              <Badge tone="blue">workspace {context.workspaceId}</Badge>
            ) : null}
            <Button onClick={() => navigateApp(returnPath)}>
              {uiText.workspaceInspection.actions.return}
            </Button>
          </div>
        </header>
        {children}
      </section>
    </main>
  );
}

function InspectionTabs({ context }: { context: WorkspaceInspectionRouteContext }) {
  const uiText = useUiText();
  const filePath = context.path ?? undefined;

  return (
    <nav
      className={styles.tabs}
      aria-label={uiText.workspaceInspection.labels.inspectionViews}
    >
      <a
        aria-current={context.mode === "status" ? "page" : undefined}
        href={buildWorkspaceInspectionRoute({
          returnSessionId: context.returnSessionId ?? undefined,
          returnTaskNodeId: context.returnTaskNodeId ?? undefined,
          sessionId: context.sessionId ?? undefined,
          taskNodeId: context.taskNodeId ?? undefined,
          view: "status",
          workspaceId: context.workspaceId,
        })}
      >
        {uiText.workspaceInspection.labels.changedFiles}
      </a>
      {filePath ? (
        <>
          <a
            aria-current={context.mode === "file" ? "page" : undefined}
            href={buildWorkspaceInspectionRoute({
              path: filePath,
              returnSessionId: context.returnSessionId ?? undefined,
              returnTaskNodeId: context.returnTaskNodeId ?? undefined,
              sessionId: context.sessionId ?? undefined,
              taskNodeId: context.taskNodeId ?? undefined,
              view: "file",
              workspaceId: context.workspaceId,
            })}
          >
            {uiText.workspaceInspection.labels.file}
          </a>
          <a
            aria-current={context.mode === "diff" ? "page" : undefined}
            href={buildWorkspaceInspectionRoute({
              path: filePath,
              returnSessionId: context.returnSessionId ?? undefined,
              returnTaskNodeId: context.returnTaskNodeId ?? undefined,
              sessionId: context.sessionId ?? undefined,
              taskNodeId: context.taskNodeId ?? undefined,
              view: "diff",
              workspaceId: context.workspaceId,
            })}
          >
            {uiText.workspaceInspection.labels.diff}
          </a>
        </>
      ) : null}
    </nav>
  );
}

function StatusView({
  context,
  status,
}: {
  context: WorkspaceInspectionRouteContext;
  status: WorkspaceGitStatusResponse;
}) {
  const uiText = useUiText();
  const files = status.files;

  return (
    <Panel className={styles.panel}>
      <div className={styles.summaryRow}>
        <div>
          <Text variant="eyebrow">
            {uiText.workspaceInspection.labels.repository}
          </Text>
          <h2>{status.repository.status.replaceAll("_", " ")}</h2>
        </div>
        <div className={styles.metricGroup}>
          <Metric
            label={uiText.workspaceInspection.labels.changed}
            value={status.summary.changedFileCount}
          />
          <Metric
            label={uiText.workspaceInspection.labels.staged}
            value={status.summary.stagedFileCount}
          />
          <Metric
            label={uiText.workspaceInspection.labels.unstaged}
            value={status.summary.unstagedFileCount}
          />
          <Metric
            label={uiText.workspaceInspection.labels.untracked}
            value={status.summary.untrackedFileCount}
          />
        </div>
      </div>
      <WarningList warnings={status.warnings} />
      {files.length === 0 ? (
        <EmptyState
          message={uiText.workspaceInspection.states.cleanBody}
          title={uiText.workspaceInspection.labels.clean}
        />
      ) : (
        <div className={styles.fileList} role="list">
          {files.map((file) => (
            <ChangedFileRow context={context} file={file} key={file.pathLabel} />
          ))}
        </div>
      )}
    </Panel>
  );
}

function ChangedFileRow({
  context,
  file,
}: {
  context: WorkspaceInspectionRouteContext;
  file: WorkspaceChangedFile;
}) {
  const uiText = useUiText();
  const baseRoute = {
    path: file.relativePath,
    returnSessionId: context.returnSessionId ?? context.sessionId ?? undefined,
    returnTaskNodeId: context.returnTaskNodeId ?? context.taskNodeId ?? undefined,
    sessionId: context.sessionId ?? undefined,
    taskNodeId: context.taskNodeId ?? undefined,
    workspaceId: context.workspaceId,
  };

  return (
    <article className={styles.fileRow} role="listitem">
      <div>
        <strong>{file.relativePath}</strong>
        <div className={styles.fileMeta}>
          <span>{file.changeKind.replaceAll("_", " ")}</span>
          <span>{stageLabel(file, uiText)}</span>
        </div>
      </div>
      <div className={styles.rowActions}>
        <a href={buildWorkspaceInspectionRoute({ ...baseRoute, view: "file" })}>
          {uiText.workspaceInspection.actions.openFile}
        </a>
        <a href={buildWorkspaceInspectionRoute({ ...baseRoute, view: "diff" })}>
          {uiText.workspaceInspection.actions.viewDiff}
        </a>
      </div>
    </article>
  );
}

function FileView({ file }: { file: WorkspaceFileContentResponse }) {
  const uiText = useUiText();

  if (file.unavailableReason !== undefined || file.file.fileKind !== "text") {
    return (
      <Panel className={styles.panel}>
        <EmptyState
          message={uiText.workspaceInspection.states.fileUnavailable({
            reason: file.unavailableReason ?? file.file.fileKind,
          })}
          title={uiText.workspaceInspection.states.fileUnavailableTitle}
        />
        <WarningList warnings={file.warnings} />
      </Panel>
    );
  }

  return (
    <Panel className={styles.panel}>
      <div className={styles.summaryRow}>
        <div>
          <Text variant="eyebrow">{uiText.workspaceInspection.labels.file}</Text>
          <h2>{file.file.relativePath}</h2>
        </div>
        <Badge tone={file.range.truncated ? "warning" : "success"}>
          {file.source === "captured_evidence"
            ? uiText.workspaceInspection.labels.captured
            : uiText.workspaceInspection.labels.live}
        </Badge>
      </div>
      <WarningList warnings={file.warnings} />
      <pre
        className={styles.codeBlock}
        aria-label={uiText.workspaceInspection.labels.fileContent}
      >
        {file.content.lines.map((line) => (
          <span className={styles.codeLine} key={line.lineNumber}>
            <span className={styles.lineNumber}>{line.lineNumber}</span>
            <code>{line.text}</code>
          </span>
        ))}
      </pre>
    </Panel>
  );
}

function DiffView({ diff }: { diff: WorkspaceDiffResponse }) {
  const uiText = useUiText();

  if (!diff.isAvailable) {
    return (
      <Panel className={styles.panel}>
        <EmptyState
          message={uiText.workspaceInspection.states.diffUnavailable({
            reason: diff.unavailableReason ?? "unknown",
          })}
          title={uiText.workspaceInspection.states.diffUnavailableTitle}
        />
        <WarningList warnings={diff.warnings} />
      </Panel>
    );
  }

  return (
    <Panel className={styles.panel}>
      <div className={styles.summaryRow}>
        <div>
          <Text variant="eyebrow">{uiText.workspaceInspection.labels.diff}</Text>
          <h2>{diff.file.relativePath}</h2>
        </div>
        <div className={styles.badgeGroup}>
          <Badge tone="success">+{diff.stats.additions}</Badge>
          <Badge tone="warning">-{diff.stats.deletions}</Badge>
          {diff.stats.truncated ? (
            <Badge tone="warning">
              {uiText.workspaceInspection.labels.truncated}
            </Badge>
          ) : null}
        </div>
      </div>
      <WarningList warnings={diff.warnings} />
      <div className={styles.diffHunks}>
        {diff.hunks.map((hunk) => (
          <section className={styles.hunk} key={hunk.hunkId}>
            <div className={styles.hunkHeader}>
              @@ -{hunk.oldStart},{hunk.oldLines} +{hunk.newStart},{hunk.newLines} @@
              {hunk.header ? ` ${hunk.header}` : ""}
            </div>
            <pre className={styles.codeBlock}>
              {hunk.lines.map((line, index) => (
                <span
                  className={`${styles.codeLine} ${styles[line.kind]}`}
                  key={`${hunk.hunkId}-${index}`}
                >
                  <span className={styles.lineNumber}>
                    {line.newLine ?? line.oldLine ?? ""}
                  </span>
                  <code>{linePrefix(line.kind)}{line.text}</code>
                </span>
              ))}
            </pre>
          </section>
        ))}
      </div>
    </Panel>
  );
}

function WarningList({ warnings }: { warnings: WorkspaceInspectionWarning[] }) {
  if (warnings.length === 0) {
    return null;
  }

  return (
    <div className={styles.warningList} role="status">
      {warnings.map((warning) => (
        <span key={`${warning.code}-${warning.pathLabel ?? ""}`}>
          {warning.message}
        </span>
      ))}
    </div>
  );
}

function EmptyState({
  actionLabel,
  message,
  onAction,
  title,
}: {
  actionLabel?: string;
  message: string;
  onAction?: () => void;
  title: string;
}) {
  return (
    <div className={styles.emptyState}>
      <h2>{title}</h2>
      <p>{message}</p>
      {onAction && actionLabel ? (
        <Button onClick={onAction}>{actionLabel}</Button>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className={styles.metric}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function titleForContext(
  context: WorkspaceInspectionRouteContext,
  uiText: UiTextCatalog,
): string {
  if (context.mode === "status") {
    return uiText.workspaceInspection.labels.changedFiles;
  }
  if (context.mode === "diff") {
    return uiText.workspaceInspection.labels.fileDiff;
  }
  return uiText.workspaceInspection.labels.fileViewer;
}

function stageLabel(file: WorkspaceChangedFile, uiText: UiTextCatalog): string {
  if (file.changeKind === "untracked") {
    return uiText.workspaceInspection.labels.untracked;
  }
  if (file.staged && file.unstaged) {
    return uiText.workspaceInspection.labels.mixed;
  }
  if (file.staged) {
    return uiText.workspaceInspection.labels.staged;
  }
  return uiText.workspaceInspection.labels.unstaged;
}

function linePrefix(kind: "context" | "add" | "delete"): string {
  if (kind === "add") {
    return "+";
  }
  if (kind === "delete") {
    return "-";
  }
  return " ";
}

function createInspectionApi(
  runtimeEnv: PlatoRuntimeEnv,
): WorkspaceInspectionApi | null {
  if (runtimeEnv.VITE_PLATO_API_MODE !== "http") {
    return null;
  }

  return createHttpWorkspaceInspectionApi({
    baseUrl: runtimeEnv.VITE_PLATO_API_BASE_URL ?? globalThis.location.origin,
  });
}
