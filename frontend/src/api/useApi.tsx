import { createContext, useContext } from "react";
import type { ReactNode } from "react";

import type { TaskWeavnApi } from "./contracts";

const ApiContext = createContext<TaskWeavnApi | null>(null);

export function ApiProvider({
  api,
  children,
}: {
  api: TaskWeavnApi;
  children: ReactNode;
}) {
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}

export function useApi(): TaskWeavnApi {
  const api = useContext(ApiContext);
  if (!api) {
    throw new Error("TaskWeavnApi provider is missing");
  }
  return api;
}
