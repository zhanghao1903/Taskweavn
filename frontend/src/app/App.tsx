import { MainPage } from "../pages/main-page/MainPage";
import { createMainPageAdapterFromRuntimeEnv } from "./platoRuntime";

const mainPageAdapter = createMainPageAdapterFromRuntimeEnv();

export function App() {
  return <MainPage adapter={mainPageAdapter} />;
}
