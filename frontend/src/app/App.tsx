import { useEffect, useState } from "react";

import { AppErrorBoundary } from "./AppErrorBoundary";
import { MainPageRoute } from "./MainPageRoute";
import { PLATO_NAVIGATION_EVENT } from "./navigation";
import { AuditPageRoute } from "../pages/audit-page/AuditPageRoute";
import { isAuditPath } from "../pages/audit-page/auditRouteModel";

export function App() {
  const [pathname, setPathname] = useState(() => globalThis.location.pathname);

  useEffect(() => {
    const handleRouteChange = () => {
      setPathname(globalThis.location.pathname);
    };

    globalThis.addEventListener("popstate", handleRouteChange);
    globalThis.addEventListener(PLATO_NAVIGATION_EVENT, handleRouteChange);
    return () => {
      globalThis.removeEventListener("popstate", handleRouteChange);
      globalThis.removeEventListener(PLATO_NAVIGATION_EVENT, handleRouteChange);
    };
  }, []);

  return (
    <AppErrorBoundary>
      {isAuditPath(pathname) ? (
        <AuditPageRoute />
      ) : (
        <MainPageRoute />
      )}
    </AppErrorBoundary>
  );
}
