import type { ApiClientOptions } from "./client";
import { ApiClient } from "./client";
import type { ApiError, WorkspaceId } from "./types";

export type WorkspacePathRef = {
  relativePath: string;
  pathLabel: string;
};

export type WorkspaceContentHash = {
  algorithm: "sha256";
  value: string;
};

export type WorkspaceInspectionEvidenceRef = {
  evidenceId: string;
  kind: "git_status_snapshot" | "diff_snapshot" | "file_snapshot";
  workspaceId: WorkspaceId;
  pathLabel?: string;
  createdAt: string;
};

export type WorkspaceInspectionWarning = {
  code:
    | "workspace.not_git"
    | "workspace.inspection_truncated"
    | "workspace.file_too_large"
    | "workspace.binary_unsupported"
    | "workspace.evidence_stale"
    | "workspace.provider_partial";
  message: string;
  pathLabel?: string;
};

export type WorkspaceChangedFile = WorkspacePathRef & {
  changeKind:
    | "added"
    | "modified"
    | "deleted"
    | "renamed"
    | "copied"
    | "type_changed"
    | "untracked"
    | "unknown";
  staged: boolean;
  unstaged: boolean;
  oldPathLabel?: string;
  oldRelativePath?: string;
  displayCategory?: "project" | "local_tooling";
  binary: boolean | null;
  relatedTaskRefs: {
    sessionId: string;
    taskNodeId?: string;
    taskId?: string;
  }[];
};

export type WorkspaceGitStatusResponse = {
  schemaVersion: "plato.workspace_inspection.git_status.v1";
  workspaceId: WorkspaceId;
  generatedAt: string;
  repository: {
    status: "clean" | "dirty" | "untracked_only" | "not_git" | "unavailable";
    branch?: string | null;
    headSha?: string | null;
    isDetachedHead: boolean;
    rootLabel: string;
  };
  summary: {
    changedFileCount: number;
    stagedFileCount: number;
    unstagedFileCount: number;
    untrackedFileCount: number;
    localToolingFileCount?: number;
    suppressedLocalNoiseFileCount?: number;
    hasMore: boolean;
  };
  files: WorkspaceChangedFile[];
  warnings: WorkspaceInspectionWarning[];
};

export type WorkspaceDiffLine = {
  kind: "context" | "add" | "delete";
  oldLine: number | null;
  newLine: number | null;
  text: string;
};

export type WorkspaceDiffHunk = {
  hunkId: string;
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  header: string;
  lines: WorkspaceDiffLine[];
};

export type WorkspaceDiffResponse = {
  schemaVersion: "plato.workspace_inspection.diff.v1";
  workspaceId: WorkspaceId;
  generatedAt: string;
  file: WorkspacePathRef & {
    changeKind: WorkspaceChangedFile["changeKind"];
    oldRelativePath?: string;
    oldPathLabel?: string;
    binary: boolean;
  };
  base: "head" | "index";
  isAvailable: boolean;
  unavailableReason?:
    | "not_git"
    | "file_not_changed"
    | "file_missing"
    | "binary"
    | "too_large"
    | "provider_error";
  hunks: WorkspaceDiffHunk[];
  stats: {
    additions: number;
    deletions: number;
    hunkCount: number;
    truncated: boolean;
  };
  contentHash?: WorkspaceContentHash;
  evidenceRef?: WorkspaceInspectionEvidenceRef;
  warnings: WorkspaceInspectionWarning[];
};

export type WorkspaceFileContentResponse = {
  schemaVersion: "plato.workspace_inspection.file_content.v1";
  workspaceId: WorkspaceId;
  generatedAt: string;
  file: WorkspacePathRef & {
    exists: boolean;
    fileKind: "text" | "binary" | "directory" | "missing" | "unsupported";
    sizeBytes?: number;
    encoding?: string;
  };
  range: {
    startLine: number;
    endLine: number;
    totalLines: number | null;
    truncated: boolean;
  };
  content: {
    lines: {
      lineNumber: number;
      text: string;
    }[];
  };
  contentHash?: WorkspaceContentHash;
  source: "live" | "captured_evidence";
  evidenceRef?: WorkspaceInspectionEvidenceRef;
  unavailableReason?:
    | "file_missing"
    | "binary"
    | "directory"
    | "too_large"
    | "unsupported_encoding"
    | "path_forbidden"
    | "provider_error";
  warnings: WorkspaceInspectionWarning[];
};

export type WorkspaceInspectionEnvelope<T> = {
  ok: boolean;
  data: T | null;
  error: ApiError | null;
};

export type WorkspaceInspectionApi = {
  getStatus(request: {
    workspaceId: WorkspaceId;
    maxFiles?: number;
  }): Promise<WorkspaceInspectionEnvelope<WorkspaceGitStatusResponse>>;
  getDiff(request: {
    workspaceId: WorkspaceId;
    path: string;
    base?: "head" | "index";
    contextLines?: number;
    maxBytes?: number;
  }): Promise<WorkspaceInspectionEnvelope<WorkspaceDiffResponse>>;
  getFileContent(request: {
    workspaceId: WorkspaceId;
    path?: string;
    startLine?: number;
    lineCount?: number;
    evidenceId?: string;
  }): Promise<WorkspaceInspectionEnvelope<WorkspaceFileContentResponse>>;
};

export function createHttpWorkspaceInspectionApi(
  options: ApiClientOptions,
): WorkspaceInspectionApi {
  const client = new ApiClient(options);

  return {
    getStatus(request) {
      return client.getJson<WorkspaceInspectionEnvelope<WorkspaceGitStatusResponse>>(
        withQuery(`/api/v1/workspaces/${segment(request.workspaceId)}/inspection/status`, {
          maxFiles: numberQuery(request.maxFiles),
        }),
      );
    },
    getDiff(request) {
      return client.getJson<WorkspaceInspectionEnvelope<WorkspaceDiffResponse>>(
        withQuery(`/api/v1/workspaces/${segment(request.workspaceId)}/inspection/diff`, {
          base: request.base,
          contextLines: numberQuery(request.contextLines),
          maxBytes: numberQuery(request.maxBytes),
          path: request.path,
        }),
      );
    },
    getFileContent(request) {
      return client.getJson<WorkspaceInspectionEnvelope<WorkspaceFileContentResponse>>(
        withQuery(`/api/v1/workspaces/${segment(request.workspaceId)}/files/content`, {
          evidenceId: request.evidenceId,
          lineCount: numberQuery(request.lineCount),
          path: request.path,
          startLine: numberQuery(request.startLine),
        }),
      );
    },
  };
}

function segment(value: string): string {
  return encodeURIComponent(value);
}

function withQuery(
  path: string,
  query: Record<string, string | undefined>,
): string {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") {
      params.set(key, value);
    }
  }

  const queryString = params.toString();
  return queryString.length > 0 ? `${path}?${queryString}` : path;
}

function numberQuery(value: number | undefined): string | undefined {
  return value === undefined ? undefined : String(value);
}
