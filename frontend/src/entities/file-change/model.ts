import type { TaskNodeId } from "../task/model";

export type FileChangeSummary = {
  taskNodeId: TaskNodeId;
  changedFiles: string[];
};
