import { AppErrorBoundary } from "./AppErrorBoundary";
import { MainPageRoute } from "./MainPageRoute";

export function App() {
  return (
    <AppErrorBoundary>
      <MainPageRoute />
    </AppErrorBoundary>
  );
}
