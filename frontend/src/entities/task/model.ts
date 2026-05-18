export type TaskNodeId = string;

export type TaskNodeStatus =
  | "done"
  | "running"
  | "waiting_user"
  | "queued"
  | "draft";

export type TaskNode = {
  id: TaskNodeId;
  parentId: TaskNodeId | null;
  title: string;
  summary: string;
  status: TaskNodeStatus;
};

export type TaskTree = {
  id: string;
  title: string;
  nodes: TaskNode[];
};
