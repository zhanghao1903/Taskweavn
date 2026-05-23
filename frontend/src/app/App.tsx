import { MainPage } from "../pages/main-page/MainPage";
import { AppErrorBoundary } from "./AppErrorBoundary";
import { createMainPageAdapterFromRuntimeEnv } from "./platoRuntime";

const mainPageAdapter = createMainPageAdapterFromRuntimeEnv();

export function App() {
  return (
    <AppErrorBoundary>
      <MainPage adapter={mainPageAdapter} />
    </AppErrorBoundary>
  );
}
