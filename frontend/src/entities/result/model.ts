import type { TaskNodeId } from "../task/model";

export type ResultCard = {
  id: string;
  taskNodeId: TaskNodeId;
  title: string;
  summary: string;
};
