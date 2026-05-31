import { AppErrorBoundary } from "./AppErrorBoundary";
import { MainPageRoute } from "./MainPageRoute";
import { AuditPageRoute } from "../pages/audit-page/AuditPageRoute";
import { isAuditPath } from "../pages/audit-page/auditRouteModel";

export function App() {
  return (
    <AppErrorBoundary>
      {isAuditPath(globalThis.location.pathname) ? (
        <AuditPageRoute />
      ) : (
        <MainPageRoute />
      )}
    </AppErrorBoundary>
  );
}
