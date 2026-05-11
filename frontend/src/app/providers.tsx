import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";

import { mockTaskWeavnApi } from "../api/mock/mockApi";
import { ApiProvider } from "../api/useApi";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: false,
    },
  },
});

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <ApiProvider api={mockTaskWeavnApi}>{children}</ApiProvider>
    </QueryClientProvider>
  );
}
