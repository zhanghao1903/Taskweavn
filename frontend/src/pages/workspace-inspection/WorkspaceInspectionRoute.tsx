import { useEffect, useMemo, useState, type ReactNode } from "react";

import { navigateApp } from "../../app/navigation";
import type { PlatoRuntimeEnv } from "../../app/platoRuntime";
import {
  buildMainSessionFallbackRoute,
  buildWorkspaceInspectionRoute,
} from "../../app/routes";
import { Badge, Button, Panel, Text } from "../../shared/components";
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
        setState({ kind: "error", message: "Inspection route is unavailable." });
        return;
      }
      if (inspectionApi === null) {
        setState({
          kind: "error",
          message: "Workspace inspection requires the local sidecar.",
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
            throw new Error(response.error?.message ?? "Status unavailable.");
          }
          if (!cancelled) {
            setState({ kind: "status", status: response.data });
          }
          return;
        }

        if (context.mode === "diff") {
          if (context.path === null) {
            throw new Error("A file path is required for diff inspection.");
          }
          const response = await inspectionApi.getDiff({
            path: context.path,
            workspaceId: context.workspaceId,
          });
          if (!response.ok || response.data === null) {
            throw new Error(response.error?.message ?? "Diff unavailable.");
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
          throw new Error(response.error?.message ?? "File unavailable.");
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
                : "Workspace inspection failed.",
          });
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [context, inspectionApi, reloadNonce]);

  if (context === null) {
    return (
      <InspectionShell
        context={null}
        title="Workspace inspection"
      >
        <EmptyState
          actionLabel="Return"
          message="Inspection context is unavailable for this route."
          onAction={() => navigateApp("/")}
          title="Inspection route unavailable"
        />
      </InspectionShell>
    );
  }

  return (
    <InspectionShell
      context={context}
      title={titleForContext(context)}
    >
      <InspectionTabs context={context} />
      {state.kind === "loading" ? (
        <EmptyState message="Loading workspace inspection data." title="Loading" />
      ) : state.kind === "error" ? (
        <EmptyState
          actionLabel="Retry"
          message={state.message}
          onAction={() => setReloadNonce((value) => value + 1)}
          title="Inspection unavailable"
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
  const returnPath =
    context?.returnSessionId || context?.sessionId
      ? buildMainSessionFallbackRoute({
          sessionId: context.returnSessionId ?? context.sessionId ?? "",
          taskNodeId: context.returnTaskNodeId ?? context.taskNodeId ?? undefined,
        })
      : "/";

  return (
    <main className={styles.page}>
      <section className={styles.shell} aria-label="Workspace inspection">
        <header className={styles.header}>
          <div>
            <Text variant="eyebrow">Workspace inspection</Text>
            <h1>{title}</h1>
            <p>
              {context === null
                ? "Read-only workspace inspection."
                : context.path ?? context.evidenceId ?? context.workspaceId}
            </p>
          </div>
          <div className={styles.headerActions}>
            {context !== null ? (
              <Badge tone="blue">workspace {context.workspaceId}</Badge>
            ) : null}
            <Button onClick={() => navigateApp(returnPath)}>Return</Button>
          </div>
        </header>
        {children}
      </section>
    </main>
  );
}

function InspectionTabs({ context }: { context: WorkspaceInspectionRouteContext }) {
  const filePath = context.path ?? undefined;

  return (
    <nav className={styles.tabs} aria-label="Inspection views">
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
        Changed files
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
            File
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
            Diff
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
  const files = status.files;

  return (
    <Panel className={styles.panel}>
      <div className={styles.summaryRow}>
        <div>
          <Text variant="eyebrow">Repository</Text>
          <h2>{status.repository.status.replaceAll("_", " ")}</h2>
        </div>
        <div className={styles.metricGroup}>
          <Metric label="Changed" value={status.summary.changedFileCount} />
          <Metric label="Staged" value={status.summary.stagedFileCount} />
          <Metric label="Unstaged" value={status.summary.unstagedFileCount} />
          <Metric label="Untracked" value={status.summary.untrackedFileCount} />
        </div>
      </div>
      <WarningList warnings={status.warnings} />
      {files.length === 0 ? (
        <EmptyState message="No changed files in this workspace." title="Clean" />
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
          <span>{stageLabel(file)}</span>
        </div>
      </div>
      <div className={styles.rowActions}>
        <a href={buildWorkspaceInspectionRoute({ ...baseRoute, view: "file" })}>
          Open file
        </a>
        <a href={buildWorkspaceInspectionRoute({ ...baseRoute, view: "diff" })}>
          View diff
        </a>
      </div>
    </article>
  );
}

function FileView({ file }: { file: WorkspaceFileContentResponse }) {
  if (file.unavailableReason !== undefined || file.file.fileKind !== "text") {
    return (
      <Panel className={styles.panel}>
        <EmptyState
          message={`File cannot be rendered as text: ${
            file.unavailableReason ?? file.file.fileKind
          }.`}
          title="File unavailable"
        />
        <WarningList warnings={file.warnings} />
      </Panel>
    );
  }

  return (
    <Panel className={styles.panel}>
      <div className={styles.summaryRow}>
        <div>
          <Text variant="eyebrow">File</Text>
          <h2>{file.file.relativePath}</h2>
        </div>
        <Badge tone={file.range.truncated ? "warning" : "success"}>
          {file.source === "captured_evidence" ? "captured" : "live"}
        </Badge>
      </div>
      <WarningList warnings={file.warnings} />
      <pre className={styles.codeBlock} aria-label="File content">
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
  if (!diff.isAvailable) {
    return (
      <Panel className={styles.panel}>
        <EmptyState
          message={`Diff is unavailable: ${diff.unavailableReason ?? "unknown"}.`}
          title="Diff unavailable"
        />
        <WarningList warnings={diff.warnings} />
      </Panel>
    );
  }

  return (
    <Panel className={styles.panel}>
      <div className={styles.summaryRow}>
        <div>
          <Text variant="eyebrow">Diff</Text>
          <h2>{diff.file.relativePath}</h2>
        </div>
        <div className={styles.badgeGroup}>
          <Badge tone="success">+{diff.stats.additions}</Badge>
          <Badge tone="warning">-{diff.stats.deletions}</Badge>
          {diff.stats.truncated ? <Badge tone="warning">truncated</Badge> : null}
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

function titleForContext(context: WorkspaceInspectionRouteContext): string {
  if (context.mode === "status") {
    return "Changed files";
  }
  if (context.mode === "diff") {
    return "File diff";
  }
  return "File viewer";
}

function stageLabel(file: WorkspaceChangedFile): string {
  if (file.changeKind === "untracked") {
    return "Untracked";
  }
  if (file.staged && file.unstaged) {
    return "Mixed";
  }
  if (file.staged) {
    return "Staged";
  }
  return "Unstaged";
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
